/*
 * acoustic_roundtrip_test.c
 *
 * STEP 1b of the audio pipeline (speaker version): play a known test
 * tone out through your speakers, and simultaneously capture through
 * your microphone, so you can confirm the FULL ACOUSTIC PATH works
 * (speaker -> air -> mic) before any FFT or spike code touches it.
 *
 * This is an ACOUSTIC round-trip, not a digital loopback: the sound
 * actually has to travel through air and be picked up by the mic.
 * That means real-world factors apply -- speaker volume, mic
 * sensitivity, distance, and room noise all affect what you see.
 * If nothing shows up, that's useful information (turn up volume,
 * move mic closer), not necessarily a bug.
 *
 * What this does:
 *   - Generates a 440 Hz sine tone (concert A) in software
 *   - Plays it out the default playback device (speakers)
 *   - Simultaneously captures from the default microphone
 *   - Prints a live peak/RMS readout of what the MIC actually picks up
 *
 * What this deliberately does NOT do yet:
 *   - No FFT (next step)
 *   - No spike encoding (after that)
 *   - No synchronization/alignment between played and captured signal
 *     beyond "they're running on the same duplex callback" -- that's
 *     enough to prove the path works, not enough for precise latency
 *     measurement, which is a separate, harder problem if you need it
 *     later.
 *
 * BUILD (download the real miniaudio.h from
 *   https://github.com/mackron/miniaudio and place it next to this file):
 *
 *   Linux:   gcc acoustic_roundtrip_test.c -o acoustic_roundtrip_test -lpthread -lm -ldl
 *   macOS:   gcc acoustic_roundtrip_test.c -o acoustic_roundtrip_test -lpthread -lm
 *   Windows: gcc acoustic_roundtrip_test.c -o acoustic_roundtrip_test.exe -lwinmm
 *
 * RUN:
 *   ./acoustic_roundtrip_test
 *   You should HEAR a steady tone from your speakers, and the mic
 *   readout should show peak/rms rising above the room-noise floor
 *   while the tone plays. Press Enter to stop.
 *
 * IF NOTHING SHOWS UP ON THE MIC SIDE:
 *   - Turn speaker volume up
 *   - Move the mic closer to the speaker, or use a laptop with both
 *     built in
 *   - Check OS mic permissions (same as the plain capture test)
 *   - Some OSes route playback and capture through separate default
 *     devices that aren't acoustically coupled (e.g. headphones as
 *     default playback + a far-away desktop mic) -- check what your
 *     actual default devices are if this happens
 */

#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#define SAMPLE_RATE    48000
#define CHANNELS       1
#define FORMAT         ma_format_f32
#define TONE_FREQ_HZ   440.0
#define TONE_AMPLITUDE 0.4   /* keep well below 1.0 to avoid clipping/distortion */

static double g_phase = 0.0;
static const double g_phase_inc = 2.0 * 3.14159265358979323846 * TONE_FREQ_HZ / (double)SAMPLE_RATE;

/* Duplex callback: pOutput is what we write to play OUT to speakers,
 * pInput is what the mic just captured. Both happen in the same call
 * when the device is opened in full-duplex mode. We must not block
 * here, same caution as the plain capture test.
 */
void duplex_callback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount) {
    (void)pDevice;
    float* out = (float*)pOutput;
    const float* in = (const float*)pInput;

    /* --- generate and write the outgoing test tone --- */
    for (ma_uint32 i = 0; i < frameCount; i++) {
        out[i] = (float)(TONE_AMPLITUDE * sin(g_phase));
        g_phase += g_phase_inc;
        if (g_phase > 2.0 * 3.14159265358979323846) {
            g_phase -= 2.0 * 3.14159265358979323846;
        }
    }

    /* --- read back what the mic captured --- */
    float peak = 0.0f;
    double sum_sq = 0.0;
    for (ma_uint32 i = 0; i < frameCount; i++) {
        float s = in[i];
        float a = fabsf(s);
        if (a > peak) peak = a;
        sum_sq += (double)s * (double)s;
    }
    float rms = (float)sqrt(sum_sq / (frameCount > 0 ? frameCount : 1));

    int bar_len = (int)(peak * 60.0f);
    if (bar_len > 60) bar_len = 60;
    char bar[61];
    memset(bar, '#', bar_len);
    bar[bar_len] = '\0';

    printf("\r[mic hears] peak=%.4f rms=%.4f  [%-60s]", peak, rms, bar);
    fflush(stdout);
}

int main(void) {
    ma_device_config config = ma_device_config_init(ma_device_type_duplex);
    config.capture.format    = FORMAT;
    config.capture.channels  = CHANNELS;
    config.playback.format   = FORMAT;
    config.playback.channels = CHANNELS;
    config.sampleRate        = SAMPLE_RATE;
    config.dataCallback      = duplex_callback;

    ma_device device;
    if (ma_device_init(NULL, &config, &device) != MA_SUCCESS) {
        fprintf(stderr, "\nFailed to initialize duplex device.\n");
        fprintf(stderr, "Common causes: no default playback or capture device,\n");
        fprintf(stderr, "or OS mic permission not yet granted (Windows: Settings >\n");
        fprintf(stderr, "Privacy > Microphone; macOS: System Settings > Privacy &\n");
        fprintf(stderr, "Security > Microphone).\n");
        fprintf(stderr, "\nIf duplex mode specifically fails but the plain capture\n");
        fprintf(stderr, "test worked, your system may not support simultaneous\n");
        fprintf(stderr, "playback+capture on the default devices -- tell me the\n");
        fprintf(stderr, "exact error and we'll find another way.\n");
        return 1;
    }

    printf("Duplex device initialized (playback + capture).\n");
    printf("Sample rate: %u Hz, tone: %.0f Hz, amplitude: %.2f\n\n",
           SAMPLE_RATE, TONE_FREQ_HZ, TONE_AMPLITUDE);

    if (ma_device_start(&device) != MA_SUCCESS) {
        fprintf(stderr, "Failed to start duplex device.\n");
        ma_device_uninit(&device);
        return 1;
    }

    printf("Playing a steady %.0f Hz tone through your speakers...\n", TONE_FREQ_HZ);
    printf("Watching what the mic picks up below. Press Enter to stop.\n\n");
    getchar();

    ma_device_uninit(&device);
    printf("\n\nStopped cleanly.\n");
    return 0;
}
