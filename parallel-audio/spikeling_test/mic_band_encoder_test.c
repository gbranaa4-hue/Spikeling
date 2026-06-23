/*
 * mic_band_encoder_test.c
 *
 * STEP 3 of the audio pipeline: take the working FFT from step 2
 * (mic_fft_test.c) and bucket its spectrum into a small number of
 * frequency bands suitable for driving a spiking-neuron array (one
 * band per neuron group), instead of just reporting a single
 * dominant frequency.
 *
 * Builds on the same duplex audio harness and the same vendored
 * kiss_fft library already in this folder (kiss_fft.c/.h,
 * _kiss_fft_guts.h, kiss_fft_log.h, miniaudio.h).
 *
 * BAND LAYOUT:
 *   NUM_BANDS bands, log-spaced edges between BAND_FREQ_MIN and
 *   BAND_FREQ_MAX (frequency perception and music/speech content are
 *   both roughly logarithmic, so equal-width-in-log bands cover
 *   "equally important" ranges, unlike equal-width-in-Hz bands which
 *   would waste most of their bands above 5 kHz).
 *
 *   PROBLEM with naive log spacing: at FFT_SIZE=1024 / 48 kHz, each
 *   bin is 46.875 Hz wide. Pure log spacing puts very few bins (1-2)
 *   in the lowest bands, which is narrower than the leakage skirt of
 *   a Hann-windowed peak -- a tone sitting dead center in a narrow
 *   band still leaks real energy into the band's immediate
 *   neighbors. FIX: clamp every band to a minimum width of
 *   MIN_BAND_BINS bins, expanding narrow low-frequency bands as
 *   needed (this is why bands 7+ in a 12-band/80-12000Hz layout end
 *   up naturally wide from log spacing alone, while bands 1-6 are
 *   exactly at the clamped minimum).
 *
 * ACTIVATION THRESHOLD (the actual fix this file exists to test):
 *   A fixed absolute floor (e.g. -40 dB) is wrong because it doesn't
 *   account for how loud the input currently is -- at the clamped
 *   4-bin minimum band width, a Hann window's leakage skirt is often
 *   only 1-2 bins from the true peak, well within ANY fixed absolute
 *   floor, so narrow bands next to a loud tone falsely "activate"
 *   even though no real energy belongs there.
 *
 *   FIX: threshold each band RELATIVE to the loudest band in the
 *   current frame (ACTIVATION_DB_BELOW_PEAK), not relative to an
 *   absolute zero. A band only activates if its energy is within
 *   that many dB of the loudest band right now. This self-scales
 *   with input level and rejects leakage-only bands much more
 *   reliably than a fixed floor did.
 *
 * SELF-CHECK: same dual-tone idea as step 1/2 -- plays a tone (default
 * 220 Hz, switch with --freq) out the speakers and shows which
 * band(s) the mic picks it up in, so correctness is something you can
 * actually verify by ear + eye, not just "did it compile."
 *
 * What this deliberately does NOT do yet:
 *   - No spike encoding from band energy (next step)
 *   - No continuous/overlapping windows (same simple non-overlapping
 *     blocks as step 2)
 *
 * BUILD: same folder/deps as mic_fft_test.c:
 *   Linux/MSYS2: gcc mic_band_encoder_test.c kiss_fft.c -o mic_band_encoder_test -lwinmm -lm
 *   (on Linux instead of -lwinmm use: -lpthread -lm -ldl)
 *
 * RUN:
 *   ./mic_band_encoder_test
 *   Watch the band activation row update live. With the default
 *   220 Hz test tone playing, you should see band 0 (and very often
 *   its immediate neighbor band 1, since 220 Hz sits near that
 *   boundary -- see the layout note above) light up, and nothing
 *   else.
 */

#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"
#include "kiss_fft.h"

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#define SAMPLE_RATE    48000
#define CHANNELS       1
#define FORMAT         ma_format_f32
#define TONE_FREQ_HZ   220.0
#define TONE_AMPLITUDE 0.4

#define FFT_SIZE       1024

#define NUM_BANDS         12
#define BAND_FREQ_MIN     80.0
#define BAND_FREQ_MAX     12000.0
#define MIN_BAND_BINS     4        /* clamp: no band narrower than this many FFT bins */

/* A band only counts as "active" if its energy is within this many
 * dB of the loudest band in the current frame -- see header comment
 * for why this replaces a fixed absolute floor. */
#define ACTIVATION_DB_BELOW_PEAK   15.0

static double g_phase = 0.0;
static double g_phase_inc;

static float  g_ring[FFT_SIZE];
static size_t g_ring_count = 0;
static volatile int g_block_ready = 0;
static float  g_ready_block[FFT_SIZE];

void duplex_callback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount) {
    (void)pDevice;
    float* out = (float*)pOutput;
    const float* in = (const float*)pInput;

    for (ma_uint32 i = 0; i < frameCount; i++) {
        out[i] = (float)(TONE_AMPLITUDE * sin(g_phase));
        g_phase += g_phase_inc;
        if (g_phase > 2.0 * 3.14159265358979323846) {
            g_phase -= 2.0 * 3.14159265358979323846;
        }

        if (!g_block_ready) {
            g_ring[g_ring_count++] = in[i];
            if (g_ring_count >= FFT_SIZE) {
                memcpy(g_ready_block, g_ring, sizeof(g_ring));
                g_ring_count = 0;
                g_block_ready = 1;
            }
        }
    }
}

/* band_lo_bin[k] / band_hi_bin[k] : inclusive bin range for band k */
static int g_band_lo_bin[NUM_BANDS];
static int g_band_hi_bin[NUM_BANDS];
static double g_bin_hz;

/* Build NUM_BANDS log-spaced bands between BAND_FREQ_MIN and
 * BAND_FREQ_MAX, then walk left-to-right enforcing MIN_BAND_BINS by
 * pushing each band's hi edge out until it satisfies the minimum,
 * shifting all following edges along with it. This keeps bands
 * monotonic and non-overlapping while guaranteeing none are narrower
 * than the leakage skirt. */
static void build_bands(void) {
    double edges_hz[NUM_BANDS + 1];
    double ratio = pow(BAND_FREQ_MAX / BAND_FREQ_MIN, 1.0 / NUM_BANDS);
    edges_hz[0] = BAND_FREQ_MIN;
    for (int k = 1; k <= NUM_BANDS; k++) {
        edges_hz[k] = edges_hz[k - 1] * ratio;
    }

    int edge_bin[NUM_BANDS + 1];
    for (int k = 0; k <= NUM_BANDS; k++) {
        edge_bin[k] = (int)lround(edges_hz[k] / g_bin_hz);
    }
    edge_bin[0] = (edge_bin[0] < 1) ? 1 : edge_bin[0];   /* never include DC */

    for (int k = 1; k <= NUM_BANDS; k++) {
        if (edge_bin[k] < edge_bin[k - 1] + MIN_BAND_BINS) {
            edge_bin[k] = edge_bin[k - 1] + MIN_BAND_BINS;
        }
    }

    int max_bin = FFT_SIZE / 2 - 1;
    if (edge_bin[NUM_BANDS] > max_bin) {
        /* shouldn't normally happen at these defaults, but keep it
         * safe if NUM_BANDS/MIN_BAND_BINS are tuned up later */
        edge_bin[NUM_BANDS] = max_bin;
    }

    for (int k = 0; k < NUM_BANDS; k++) {
        g_band_lo_bin[k] = edge_bin[k];
        g_band_hi_bin[k] = edge_bin[k + 1] - 1;
        if (g_band_hi_bin[k] < g_band_lo_bin[k]) g_band_hi_bin[k] = g_band_lo_bin[k];
    }
}

int main(int argc, char** argv) {
    double tone_freq = TONE_FREQ_HZ;
    for (int i = 1; i < argc - 1; i++) {
        if (strcmp(argv[i], "--freq") == 0) {
            tone_freq = atof(argv[i + 1]);
        }
    }
    g_phase_inc = 2.0 * 3.14159265358979323846 * tone_freq / (double)SAMPLE_RATE;

    ma_device_config config = ma_device_config_init(ma_device_type_duplex);
    config.capture.format    = FORMAT;
    config.capture.channels  = CHANNELS;
    config.playback.format   = FORMAT;
    config.playback.channels = CHANNELS;
    config.sampleRate        = SAMPLE_RATE;
    config.dataCallback      = duplex_callback;

    ma_device device;
    if (ma_device_init(NULL, &config, &device) != MA_SUCCESS) {
        fprintf(stderr, "Failed to initialize duplex device.\n");
        return 1;
    }

    kiss_fft_cfg fft_cfg = kiss_fft_alloc(FFT_SIZE, 0, NULL, NULL);
    if (fft_cfg == NULL) {
        fprintf(stderr, "Failed to allocate kiss_fft config.\n");
        ma_device_uninit(&device);
        return 1;
    }

    g_bin_hz = (double)SAMPLE_RATE / (double)FFT_SIZE;
    build_bands();

    printf("Band layout (%d bands, %.0f-%.0f Hz, min width %d bins = %.1f Hz):\n",
           NUM_BANDS, BAND_FREQ_MIN, BAND_FREQ_MAX, MIN_BAND_BINS, MIN_BAND_BINS * g_bin_hz);
    for (int k = 0; k < NUM_BANDS; k++) {
        printf("  band %2d: bins [%4d, %4d]  ~ %7.1f - %7.1f Hz\n",
               k, g_band_lo_bin[k], g_band_hi_bin[k],
               g_band_lo_bin[k] * g_bin_hz, (g_band_hi_bin[k] + 1) * g_bin_hz);
    }
    printf("\n");

    static float hann[FFT_SIZE];
    for (int i = 0; i < FFT_SIZE; i++) {
        hann[i] = 0.5f - 0.5f * cosf((float)(2.0 * 3.14159265358979323846 * i) / (FFT_SIZE - 1));
    }

    kiss_fft_cpx fin[FFT_SIZE];
    kiss_fft_cpx fout[FFT_SIZE];
    float band_db[NUM_BANDS];
    int   band_active[NUM_BANDS];

    if (ma_device_start(&device) != MA_SUCCESS) {
        fprintf(stderr, "Failed to start duplex device.\n");
        kiss_fft_free(fft_cfg);
        ma_device_uninit(&device);
        return 1;
    }

    printf("Playing %.0f Hz test tone (--freq <hz> to change). Press Ctrl+C to stop.\n\n", tone_freq);

    while (1) {
        if (g_block_ready) {
            for (int i = 0; i < FFT_SIZE; i++) {
                fin[i].r = g_ready_block[i] * hann[i];
                fin[i].i = 0.0f;
            }
            kiss_fft(fft_cfg, fin, fout);

            float peak_db = -1000.0f;
            for (int k = 0; k < NUM_BANDS; k++) {
                double sum_mag2 = 0.0;
                for (int b = g_band_lo_bin[k]; b <= g_band_hi_bin[k]; b++) {
                    sum_mag2 += (double)fout[b].r * fout[b].r + (double)fout[b].i * fout[b].i;
                }
                float db = 10.0f * log10f((float)sum_mag2 + 1e-12f);
                band_db[k] = db;
                if (db > peak_db) peak_db = db;
            }
            for (int k = 0; k < NUM_BANDS; k++) {
                band_active[k] = (band_db[k] >= peak_db - ACTIVATION_DB_BELOW_PEAK);
            }

            printf("\r");
            for (int k = 0; k < NUM_BANDS; k++) {
                printf("%c", band_active[k] ? ('0' + (k % 10)) : '.');
            }
            printf("  peak=%.1f dB   ", peak_db);
            fflush(stdout);

            g_block_ready = 0;
        }
    }

    kiss_fft_free(fft_cfg);
    ma_device_uninit(&device);
    return 0;
}
