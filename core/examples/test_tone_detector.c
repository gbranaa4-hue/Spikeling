/*
 * C-backend equivalent of test_tone_detector.py -- proves the Resonator
 * neuron type works through the generated C codegen (spikeling_hw.h/.c
 * from compiling tone_detector.spk), not just the Python runtime.
 *
 * Same scenario: a mixed signal containing 440Hz (strong) and 1760Hz
 * (weaker) tones plus noise, fed through the 5-channel resonator bank.
 * Only TONE_440HZ and TONE_1760HZ should fire.
 *
 * Build (from this directory, after compiling tone_detector.spk to
 * regenerate spikeling_hw.h/.c):
 *   gcc -O2 -o test_tone_detector.exe test_tone_detector.c spikeling_hw.c -lm
 * Run:
 *   ./test_tone_detector.exe
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include "spikeling_hw.h"

int main(void) {
    printf("[test] RESONATOR_COUNT = %d\n", RESONATOR_COUNT);
    if (RESONATOR_COUNT != 5) {
        printf("[test] FAIL -- expected 5 resonators from tone_detector.spk\n");
        return 1;
    }

    int fired[5] = {0, 0, 0, 0, 0};

    double dt = 1.0 / 40000.0;
    int steps = 2000;
    double target_freqs[2] = {440.0, 1760.0};
    double target_amps[2] = {1.0, 0.6};

    srand(42);
    for (int i = 0; i < steps; i++) {
        double t = i * dt;
        double drive = target_amps[0] * sin(2.0 * M_PI * target_freqs[0] * t)
                      + target_amps[1] * sin(2.0 * M_PI * target_freqs[1] * t);
        drive += ((double)rand() / RAND_MAX - 0.5) * 0.2; /* noise in [-0.1, 0.1] */

        for (uint32_t r = 0; r < RESONATOR_COUNT; r++) {
            if (spikeling_resonator_step(r, (float)drive, (float)dt, (float)(t * 1000.0))) {
                fired[r] = 1;
            }
        }
    }

    printf("\n[test] final state:\n");
    for (uint32_t r = 0; r < RESONATOR_COUNT; r++) {
        printf("  %-12s freq=%7.1fHz  energy=%.6f  fired=%s\n",
               resonators[r].name, resonators[r].freq_hz, resonators[r].energy_ema,
               fired[r] ? "YES" : "no");
    }

    /* indices: 0=110, 1=220, 2=440, 3=880, 4=1760 (matches tone_detector.spk order) */
    int ok = 1;
    if (!fired[2]) { printf("[test] FAIL -- missing expected detection: 440Hz\n"); ok = 0; }
    if (!fired[4]) { printf("[test] FAIL -- missing expected detection: 1760Hz\n"); ok = 0; }
    if (fired[0])  { printf("[test] FAIL -- unexpected false positive: 110Hz\n"); ok = 0; }
    if (fired[1])  { printf("[test] FAIL -- unexpected false positive: 220Hz\n"); ok = 0; }
    if (fired[3])  { printf("[test] FAIL -- unexpected false positive: 880Hz\n"); ok = 0; }

    if (ok) {
        printf("\n[test] PASS -- Resonator C backend correctly detected 440Hz and 1760Hz, "
               "no false positives on 110/220/880Hz channels.\n");
        return 0;
    }
    return 1;
}
