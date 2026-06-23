import os
import re

def find_config_file():
    # Looks for any file in the current directory that contains the Spikeling header
    for filename in os.listdir('.'):
        if filename.endswith(".txt") or filename.endswith(".spk"):
            with open(filename, 'r') as f:
                if "# Spikeling Neural Configuration" in f.read():
                    return filename
    return None

def compile_to_c():
    config_path = find_config_file()
    if not config_path:
        print("Error: Could not find a valid Spikeling configuration file (.txt or .spk).")
        return

    with open(config_path, 'r') as f:
        config_text = f.read()

    # Optimized C-struct for hardware memory mapping
    header = ["#include <stdint.h>\n", "typedef struct {", "    uint32_t threshold;", "    uint32_t p;", "} Neuron;"]
    
    # Regex updated to match your .txt file content format
    neurons = re.findall(r"neuron (\w+) threshold=(\d+) leak=(\d+)", config_text)
    
    header.append(f"\n#define NEURON_COUNT {len(neurons)}")
    header.append("Neuron neurons[NEURON_COUNT] = {")
    
    for name, thresh, leak in neurons:
        header.append(f"    {{.threshold = {thresh}, .p = 0}}, // {name}")
    header.append("};")

    with open("spikeling_hw.h", "w") as f:
        f.write("\n".join(header))
    print(f"Successfully compiled '{config_path}' to 'spikeling_hw.h'")

if __name__ == "__main__":
    compile_to_c()