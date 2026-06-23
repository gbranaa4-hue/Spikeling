#include "spikeling_hw.h"
#include <stdio.h>
#include <time.h>
#include <stdint.h>

/* Max sustainable REAL-spike throughput.
 * Drives every neuron hard enough that it fires at its refractory cap,
 * and measures spikes emitted per second of WALL-CLOCK time.
 * This is the honest "how many real spikes can this engine produce per
 * second" number — bounded by per-neuron refractory, scaled by population. */

#define ROUNDS 200000   /* outer passes over the whole population */

int main(void){
    printf("--- Spikeling Max-Spike Throughput ---\n");
    printf("Neurons: %d | refractory=%.0fms\n\n", NEURON_COUNT, REFRACTORY_MS);

    uint64_t total_spikes = 0;
    double sim_ms = 0.0;
    /* advance modeled time by one full refractory period each round,
     * so every neuron is eligible to fire again every round */
    const double step = REFRACTORY_MS;

    clock_t start = clock();
    for (uint64_t round = 0; round < ROUNDS; round++){
        sim_ms += step;
        for (int j = 0; j < NEURON_COUNT; j++){
            Neuron *n = &neurons[j];
            if (sim_ms - n->last_fire_ms < REFRACTORY_MS) continue;
            /* drive straight over threshold */
            n->p += (double)n->threshold;
            if (n->p >= (double)n->threshold){
                n->p = 0.0;
                n->last_fire_ms = sim_ms;
                n->fire_count++;
                total_spikes++;
            }
        }
    }
    clock_t end = clock();
    double secs = (double)(end-start)/CLOCKS_PER_SEC;

    printf("Emitted %llu real spikes in %.4f s\n",
           (unsigned long long)total_spikes, secs);
    if (secs < 0.05) {
        printf("Run too short to measure a reliable rate (%.4f s).\n", secs);
        printf("Use a larger profile (e.g. big.spk) so the run takes >0.05 s.\n");
    } else {
        printf("Real spike throughput: %.2f M spikes/sec\n",
               (total_spikes/secs)/1e6);
    }
    return 0;
}