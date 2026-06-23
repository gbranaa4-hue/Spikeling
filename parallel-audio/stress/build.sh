#!/usr/bin/env bash
# Usage: ./build.sh            (uses profile.spk)
#        ./build.sh stress.spk (uses a different profile)
set -e
PROFILE="$1"
echo "[1/3] Compiling profile to C header..."
python3 spikeling_compiler.py $PROFILE
echo
echo "[2/3] Building native engine..."
gcc -O2 -o spikeling_engine spikeling_native.c
echo
echo "[3/3] Running benchmark..."
echo
./spikeling_engine
