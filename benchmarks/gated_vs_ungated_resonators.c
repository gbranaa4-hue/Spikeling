/*
 * C version of gated_vs_ungated_resonators.py -- tests whether
 * amplitude-gating the resonator energy update (skip x*x when |x| is
 * below the noise floor) is actually faster in compiled code, or
 * whether (like benchmark #1/#2's lesson) the gate's branch costs more
 * than the multiply it avoids -- especially relevant here since modern
 * CPUs pipeline multiplies cheaply but pay real misprediction penalties
 * on data-dependent (unpredictable) branches, which "which channel is
 * loud" inherently is.
 *
 * Build: gcc -O2 -o gated_vs_ungated_resonators.exe gated_vs_ungated_resonators.c -lm
 * Run:   ./gated_vs_ungated_resonators.exe
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>

typedef struct {
    double freq_hz, damping, coupling, threshold, gate_threshold;
    double x, v, energy_ema;
} Resonator;

static void init_resonator(Resonator *r, double freq_hz) {
    double omega = 2.0 * M_PI * freq_hz;
    r->freq_hz = freq_hz;
    r->damping = 0.02;
    r->coupling = 4.0e-4 * omega * omega;
    r->threshold = 0.0008;
    r->gate_threshold = 0.00024;
    r->x = 0.0; r->v = 0.0; r->energy_ema = 0.0;
}

static void step_ungated(Resonator *r, double drive, double dt) {
    double omega = 2.0 * M_PI * r->freq_hz;
    double accel = -(omega * omega) * r->x - 2.0 * r->damping * omega * r->v;
    accel += r->coupling * drive;
    r->v += accel * dt;
    r->x += r->v * dt;
    r->energy_ema += 0.01 * (r->x * r->x - r->energy_ema);  // always pays the multiply
}

static void step_gated(Resonator *r, double drive, double dt) {
    double omega = 2.0 * M_PI * r->freq_hz;
    double accel = -(omega * omega) * r->x - 2.0 * r->damping * omega * r->v;
    accel += r->coupling * drive;
    r->v += accel * dt;
    r->x += r->v * dt;
    if (fabs(r->x) >= r->gate_threshold) {
        r->energy_ema += 0.01 * (r->x * r->x - r->energy_ema);
    } else {
        r->energy_ema *= 0.99;
    }
}

static double frand(void) { return (double)rand() / RAND_MAX; }

static double run_trial(int n_channels, double loud_fraction, int ticks, int gated) {
    Resonator *bank = malloc(sizeof(Resonator) * n_channels);
    for (int i = 0; i < n_channels; i++) init_resonator(&bank[i], 110.0 + i * 30.0);

    int n_loud = (int)(n_channels * loud_fraction);
    if (n_loud < 1) n_loud = 1;
    int *is_loud = calloc(n_channels, sizeof(int));
    for (int k = 0; k < n_loud; k++) is_loud[k] = 1; /* first n_loud channels are loud -- order doesn't matter, distribution is what's tested */

    double dt = 1.0 / 40000.0;
    clock_t start = clock();
    for (int t = 0; t < ticks; t++) {
        double time_s = t * dt;
        for (int i = 0; i < n_channels; i++) {
            double drive;
            if (is_loud[i]) {
                drive = sin(2.0 * M_PI * bank[i].freq_hz * time_s) + (frand() - 0.5) * 0.1;
            } else {
                drive = (frand() - 0.5) * 0.1;
            }
            if (gated) step_gated(&bank[i], drive, dt);
            else step_ungated(&bank[i], drive, dt);
        }
    }
    double elapsed = (double)(clock() - start) / CLOCKS_PER_SEC;
    free(bank); free(is_loud);
    return elapsed;
}

int main(void) {
    srand(11);
    int ticks = 20000;
    int channel_counts[] = {16, 64, 256};
    double loud_fractions[] = {0.02, 0.10, 0.30, 1.00};

    printf("%9s %7s %13s %11s %9s\n", "Channels", "%loud", "Ungated (s)", "Gated (s)", "Speedup");
    for (size_t ci = 0; ci < sizeof(channel_counts)/sizeof(int); ci++) {
        for (size_t fi = 0; fi < sizeof(loud_fractions)/sizeof(double); fi++) {
            int n = channel_counts[ci];
            double f = loud_fractions[fi];
            srand(11);
            double t_ungated = run_trial(n, f, ticks, 0);
            srand(11);
            double t_gated = run_trial(n, f, ticks, 1);
            double speedup = t_gated > 0 ? t_ungated / t_gated : 0.0;
            printf("%9d %6.0f%% %13.4f %11.4f %8.2fx\n", n, f * 100, t_ungated, t_gated, speedup);
        }
        printf("\n");
    }
    return 0;
}
