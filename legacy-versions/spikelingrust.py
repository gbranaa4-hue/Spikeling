import asyncio
import time
import numpy as np
from spikeling_sdk import SpikelingSDK

# Simulation Parameters: 100,000 samples, 95% is "Silence" (0)
SAMPLES = 100_000
data_stream = np.random.choice([0, 0, 0, 0, 1], size=SAMPLES) # 80% zero, 20% spike

async def run_comparison():
    # 1. TRADITIONAL POLLER
    start_poll = time.perf_counter()
    count_poll = 0
    for sample in data_stream:
        # Traditional system checks every single sample
        if sample > 0.5: 
            count_poll += 1
    end_poll = time.perf_counter()

    # 2. SPIKELING SDK
    sdk = SpikelingSDK("profile.spk", license_key="SPK-DEMO")
    start_spk = time.perf_counter()
    
    # The SDK only 'works' when it receives an event
    for sample in data_stream:
        if sample > 0:
            await sdk.push("LeftMic", sample)
    end_spk = time.perf_counter()

    print(f"--- PERFORMANCE RESULTS ---")
    print(f"Traditional Poller: {(end_poll-start_poll)*1000:.4f} ms")
    print(f"Spikeling SDK:      {(end_spk-start_spk)*1000:.4f} ms")
    print(f"EFFICIENCY GAIN:    {((end_poll-start_poll)/(end_spk-start_spk)):.2f}x faster")

asyncio.run(run_comparison())