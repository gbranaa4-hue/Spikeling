import time
import random
import os

def visualize_engine():
    # Simulation settings
    samples = 1000
    threshold = 95
    
    print("--- LIVE NEUROMORPHIC FILTER MONITOR ---")
    print("Legend: [.] = Noise (Ignored) | [⚡] = Spike (Event Triggered)\n")
    
    pulse_output = ""
    for _ in range(samples):
        val = random.randint(1, 100)
        
        # NEUROMORPHIC FILTERING LOGIC
        if val >= threshold:
            pulse_output += "⚡"
            # In a real app, this is where you'd trigger a function
        else:
            pulse_output += "."
            
        # UI Update
        if len(pulse_output) % 50 == 0:
            print(pulse_output)
            pulse_output = ""
            time.sleep(0.05) # Slowed down so you can see it happening

if __name__ == "__main__":
    visualize_engine()