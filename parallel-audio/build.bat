@echo off
if not exist build mkdir build
echo Cleaning...
if exist build\spikeling_engine.exe del build\spikeling_engine.exe
echo Compiling with Optimization...
gcc -O3 -march=native -flto -fopenmp -Iinclude -Isrc -o build\spikeling_engine.exe src\spikeling_native.c src\miniaudio_impl.c src\kiss_fft.c -lole32 -lwinmm -lm
if %errorlevel% equ 0 (
    echo Build Successful!
    echo Launching with High Priority...
    start /high build\spikeling_engine.exe
) else (
    echo Build Failed!
)
pause