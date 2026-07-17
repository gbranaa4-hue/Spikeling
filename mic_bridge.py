import sys, time
sys.path.insert(0, "core")
import sounddevice as sd
from compiler.compiler import SpikelingParser
from runtime.runtime import SpikelingRuntime

# tone_detector.spk is used UNMODIFIED -- already validated at 99.2% detection
# accuracy in resonator-prototype/accuracy_benchmark.py. This script only
# changes where the drive signal comes from (live mic instead of a
# precomputed stimulus file), not the network itself.
with open("core/examples/tone_detector.spk") as f:
    ast = SpikelingParser().parse(f.read())
rt = SpikelingRuntime(ast)

LABELS = {
    "TONE_110HZ":  "110 Hz",
    "TONE_220HZ":  "220 Hz",
    "TONE_440HZ":  "440 Hz (concert A)",
    "TONE_880HZ":  "880 Hz",
    "TONE_1760HZ": "1760 Hz",
}
for command, label in LABELS.items():
    def make_handler(label=label):
        def handler():
            print(f"*** DETECTED: {label} ***", flush=True)
        return handler
    rt.register_handler(command, make_handler())

SAMPLE_RATE = 44100   # standard mic rate, close to the ~40kHz dt this whole
                       # project's Resonator model was already validated around
                       # (see ResonatorState.step()'s docstring) -- not an
                       # arbitrary choice
DT = 1.0 / SAMPLE_RATE
t0 = time.time()

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, flush=True)
    now_ms = (time.time() - t0) * 1000
    samples = indata[:, 0]   # mono channel 0
    for s in samples:
        rt.step_resonators(float(s), DT, current_time_ms=now_ms)

print("Opening microphone stream...", flush=True)
with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                     blocksize=512, callback=audio_callback):
    print("Listening live. Try whistling or humming near 440Hz (concert A),", flush=True)
    print("220Hz, or 880Hz -- those are the easiest to hit reliably by voice.", flush=True)
    print("Press Ctrl+C to stop (or this will just run until the task is stopped).", flush=True)
    while True:
        time.sleep(1)
