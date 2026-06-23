@echo off
REM ── Spikeling -> Verilog -> simulate ──
REM Usage: build_verilog.bat [profile.spk] [neuron_count]
REM   e.g. build_verilog.bat stress.spk 8
set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=stress.spk
set NC=%2
if "%NC%"=="" set NC=8

echo [1/3] Compiling %PROFILE% to Verilog...
python spikeling_verilog.py %PROFILE%
if errorlevel 1 goto :err

echo.
echo [2/3] Building simulation (iverilog)...
where iverilog >nul 2>nul
if errorlevel 1 (
    echo iverilog not found. Install Icarus Verilog for Windows:
    echo   https://bleyer.org/icarus/
    goto :err
)
iverilog -g2012 -D NCOUNT=%NC% -o spikeling_sim spikeling_neurons.v spikeling_tb.v
if errorlevel 1 goto :err

echo.
echo [3/3] Running simulation...
echo.
vvp spikeling_sim
echo.
echo Waveform: spikeling.vcd  (open in GTKWave to see registers toggle)
goto :eof

:err
echo Build failed.
exit /b 1
