SPIKELING NATIVE BENCHMARK — distribution
==========================================

WHAT THIS IS
  A toolchain that compiles your Spikeling DSL profile into C and runs an
  HONEST neuromorphic benchmark. Unlike the old demo (which counted every
  loop iteration as a "spike" and reported ~1 billion/sec from an empty
  loop), this version performs the real dynamics your .spk file describes:
  leaky integration, varied input intensity, and refractory gating — and
  reports only spikes that ACTUALLY fire.

FILES
  profile.spk            your real config (2-mic reflex detector)
  stress.spk             a large-population profile for throughput testing
  spikeling_compiler.py  .spk  ->  spikeling_hw.h  (now carries leak+refractory)
  spikeling_native.c     reads the header, runs the benchmark
  spikeling_hw.h         GENERATED — do not edit by hand
  build.bat / build.sh   one-command: compile -> build -> run

REQUIREMENTS
  - Python 3 (any 3.x)
  - gcc  (Windows: install MinGW-w64 / WinLibs, then make sure gcc is on PATH)

RUN IT (Windows)
  build.bat                 # uses profile.spk
  build.bat stress.spk      # uses the stress profile

RUN IT (Linux / Mac)
  ./build.sh
  ./build.sh stress.spk

READING THE OUTPUT
  Input throughput  = how fast stimuli are pushed through the model.
  Spike throughput  = how fast the model emits REAL spikes (the meaningful
                      neuromorphic number).
  Fire %            = fraction of inputs that crossed threshold. With leak
                      and refractory active, most inputs decay away — a low
                      fire % is correct, biological behavior, not a bug.

WHY YOUR REAL PROFILE FIRES SO LITTLE
  profile.spk has refractory=400ms and only 2 neurons. Each neuron can fire
  at most ~once per 400ms, so over 100s of modeled time you get a few hundred
  fires total. That's correct: profile.spk is a REFLEX DETECTOR, not a
  throughput fabric. Use stress.spk (8 neurons, 4ms refractory) to see the
  engine under load.

TUNING
  In spikeling_native.c, two knobs at the top:
    N_INPUTS   total stimuli to push (default 50,000,000)
    DT_MS      simulated time between stimuli (default 0.002 ms)
  Add neurons or change threshold/leak/refractory in the .spk file and rebuild.

HONEST CLAIM LANGUAGE (for patent / pitch use)
  OK:  "The software reference engine processes ~N M stimuli/sec and emits
        ~M M spikes/sec single-threaded on commodity x86."
  NOT OK: implying this is the hardware spike rate. The acoustic hardware is
        bound by the speed of sound and is many orders of magnitude slower
        PER OPERATION. Keep the software-model number and the hardware number
        separate.
