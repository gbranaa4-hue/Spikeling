import os
import re
import sys

def find_config_file():
    """Find a Spikeling config (.spk or .txt) by its header comment."""
    for filename in os.listdir('.'):
        if filename.endswith(".txt") or filename.endswith(".spk"):
            try:
                with open(filename, 'r') as f:
                    if "# Spikeling Neural Configuration" in f.read():
                        return filename
            except (IOError, UnicodeDecodeError):
                continue
    return None

def compile_to_c():
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        if not os.path.exists(config_path):
            print("Error: file not found: " + config_path)
            return
    else:
        config_path = find_config_file()
    if not config_path:
        print("Error: No valid Spikeling config (.spk or .txt) found in this folder.")
        return

    with open(config_path, 'r') as f:
        config_text = f.read()

    # neuron NAME threshold=N leak=N
    neurons = re.findall(r"neuron (\w+) threshold=(\d+) leak=(\d+)", config_text)
    if not neurons:
        print("Error: '" + config_path + "' has no parseable neuron definitions.")
        return

    # refractory=Nms   (optional; default 4ms)
    m = re.search(r"refractory=(\d+)ms", config_text)
    refractory_ms = int(m.group(1)) if m else 4

    L = []
    L.append("#include <stdint.h>")
    L.append("")
    L.append("/* Auto-generated from " + config_path + " by spikeling_compiler.py */")
    L.append("")
    L.append("typedef struct {")
    L.append("    uint32_t threshold;")
    L.append("    uint32_t leak;         /* membrane units lost per ms idle */")
    L.append("    double   p;            /* membrane potential */")
    L.append("    double   last_ms;      /* last update time (ms) */")
    L.append("    double   last_fire_ms; /* last fire time (ms) */")
    L.append("    uint64_t fire_count;")
    L.append("} Neuron;")
    L.append("")
    L.append("#define NEURON_COUNT " + str(len(neurons)))
    L.append("#define REFRACTORY_MS " + str(refractory_ms) + ".0")
    L.append("")
    L.append("static const char* NEURON_NAMES[NEURON_COUNT] = {")
    for name, _, _ in neurons:
        L.append('    "' + name + '",')
    L.append("};")
    L.append("")
    L.append("static Neuron neurons[NEURON_COUNT] = {")
    for name, thresh, leak in neurons:
        L.append("    {.threshold = " + thresh + ", .leak = " + leak +
                 ", .p = 0, .last_ms = 0, .last_fire_ms = -1e9, .fire_count = 0}, // " + name)
    L.append("};")
    L.append("")

    with open("spikeling_hw.h", "w") as f:
        f.write("\n".join(L))

    print("Compiled '" + config_path + "' -> 'spikeling_hw.h'")
    print("  " + str(len(neurons)) + " neurons, refractory = " + str(refractory_ms) + " ms")
    if len(neurons) <= 16:
        for name, thresh, leak in neurons:
            print("    " + name.ljust(10) + " threshold=" + thresh + " leak=" + leak)
    else:
        for name, thresh, leak in neurons[:4]:
            print("    " + name.ljust(10) + " threshold=" + thresh + " leak=" + leak)
        print("    ... (" + str(len(neurons) - 4) + " more)")

if __name__ == "__main__":
    compile_to_c()