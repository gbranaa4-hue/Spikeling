# parallel-audio

Experimental branch of the `sdk-verilog` C engine that adds real microphone
input: audio samples get FFT'd and converted into spike trains feeding a
Spikeling network, instead of using synthetic/scripted input.

This is the newest-touched part of the whole Spikeling project (6/17) —
treat it as active/in-progress work, not a finished distribution.

## Key files
- `README.txt`, `README_VERILOG.txt` — original authored docs
- `src/spikeling_native.c` — much larger than the sdk-verilog version; adds parallel audio processing
- `src/kiss_fft.*` — FFT library vendored in for frequency-domain analysis
- `include/miniaudio.h` — vendored audio I/O library (mic capture)
- `Audio_Assets/` — test audio clips + C audio driver
- `spikeling_engine.exe` (1.06 MB) / `build/` build output — compiled with audio support (larger than the sdk-verilog `.exe` because of the audio stack)
- `spikeling_compiler.py` — same snapshot as `sdk-verilog/` (not canonical, see `../core/`)
- `profile.spk`, `big.spk`, `stress.spk`, `stress/` — test configs / stress harness, same role as in sdk-verilog

## Status
Active/experimental. If you continue this work, this is the folder to build on.
