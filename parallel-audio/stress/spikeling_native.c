#include "spikeling_hw.h"
#include <stdio.h>
#include <time.h>
#include <stdint.h>

/*
 * Spikeling honest neuromorphic benchmark.
 *
 * Reads neuron config (threshold, leak, refractory) from spikeling_hw.h,
 * which spikeling_compiler.py generates from your .spk profile.
 *
 * It does the real dynamics the DSL describes:
 *   - leaky integration (membrane decays by leak * idle_ms)
 *   - varied input intensity (not a constant +1)
 *   - per-neuron refractory gating
 *   - counts only spikes that ACTUALLY fire
 *
 * Two reported numbers:
 *   input throughput  = stimuli processed / sec
 *   spike throughput  = real spikes emitted / sec  (the meaningful one)
 *
 * Tune the workload with the two #defines below.
 */

#define N_INPUTS   50000000     /* total input stimuli to push */
#define DT_MS      0.002        /* simulated time between stimuli (ms) */

int main(void) {
    printf("--- Spikeling Neuromorphic Benchmark ---\n");
    printf("Neurons: %d | Inputs: %d | refractory=%.0fms\n",
           NEURON_COUNT, N_INPUTS, REFRACTORY_MS);
    for (int i = 0; i < NEURON_COUNT; i++) {
        printf("  %-10s threshold=%u leak=%u\n",
               NEURON_NAMES[i], neurons[i].threshold, neurons[i].leak);
    }
    printf("\n");

    /* deterministic xorshift PRNG -> reproducible runs */
    uint64_t rng = 0x9E3779B97F4A7C15ULL;
    #define NEXT() (rng ^= rng << 13, rng ^= rng >> 7, rng ^= rng << 17, rng)

    uint64_t total_spikes = 0;
    double sim_ms = 0.0;

    clock_t start = clock();

    for (int i = 0; i < N_INPUTS; i++) {
        sim_ms += DT_MS;

        uint64_t r = NEXT();
        int target = (int)(r % NEURON_COUNT);
        double intensity = (double)(1 + (r >> 20) % 60);

        Neuron *n = &neurons[target];

        /* leaky integration: decay by idle time */
        double idle = sim_ms - n->last_ms;
        if (idle > 0) {
            n->p -= (double)n->leak * idle;
            if (n->p < 0) n->p = 0.0;
        }
        n->last_ms = sim_ms;

        /* refractory gate */
        if (sim_ms - n->last_fire_ms < REFRACTORY_MS) continue;

        /* integrate and fire */
        n->p += intensity;
        if (n->p >= (double)n->threshold) {
            n->p = 0.0;
            n->last_fire_ms = sim_ms;
            n->fire_count++;
            total_spikes++;
        }
    }

    clock_t end = clock();
    double secs = (double)(end - start) / CLOCKS_PER_SEC;
    if (secs <= 0) secs = 1e-9;

    double in_rate  = (N_INPUTS / secs) / 1e6;
    double out_rate = (total_spikes / secs) / 1e6;
    double fire_pct = 100.0 * (double)total_spikes / (double)N_INPUTS;

    printf("Processed %d input stimuli in %.4f s\n", N_INPUTS, secs);
    printf("Emitted   %llu actual spikes (%.2f%% of inputs fired)\n",
           (unsigned long long)total_spikes, fire_pct);
    printf("Modeled time: %.1f ms\n\n", sim_ms);
    printf("Input throughput : %.2f M stimuli/sec\n", in_rate);
    printf("Spike throughput : %.2f M spikes/sec  <-- neuromorphic work rate\n\n", out_rate);

    printf("Per-neuron fire counts:\n");
    for (int i = 0; i < NEURON_COUNT; i++) {
        printf("  %-10s %llu fires\n",
               NEURON_NAMES[i], (unsigned long long)neurons[i].fire_count);
    }
    return 0;
}
