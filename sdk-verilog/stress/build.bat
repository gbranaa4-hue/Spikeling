@echo off
REM Usage: build.bat [profile.spk]   default: big.spk (max-spike throughput)
set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=big.spk
echo [1/3] Compiling %PROFILE% to C header...
python spikeling_compiler.py %PROFILE%
if errorlevel 1 goto :err
echo.
echo [2/3] Building native engine...
where gcc >nul 2>nul
if errorlevel 1 ( echo gcc not found. Install MinGW-w64. & goto :err )
gcc -O2 -o spikeling_engine.exe spikeling_native.c
if errorlevel 1 goto :err
echo.
echo [3/3] Running benchmark...
echo.
spikeling_engine.exe
goto :eof
:err
echo Build failed.
exit /b 1