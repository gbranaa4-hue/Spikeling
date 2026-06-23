#include "spikeling_hw.h"
#include <stdio.h>
#include <time.h>

#define MAX_SPIKES 10000000 // 10 Million events

void run_benchmarked_load() {
    clock_t start = clock();
    
    // Simulating 10 million spikes distributed across neurons
    for (int i = 0; i < MAX_SPIKES; i++) {
        int target = i % NEURON_COUNT;
        neurons[target].p += 1;
        
        if (neurons[target].p >= neurons[target].threshold) {
            neurons[target].p = 0; // Hardware reset
        }
    }
    
    clock_t end = clock();
    double time_spent = (double)(end - start) / CLOCKS_PER_SEC;
    
    printf("Processed %d spikes in %.4f seconds\n", MAX_SPIKES, time_spent);
    printf("Throughput: %.2f million spikes/sec\n", (MAX_SPIKES / time_spent) / 1e6);
}

int main() {
    printf("--- Spikeling Large Scale Demo ---\n");
    run_benchmarked_load();
    return 0;
}