#!/usr/bin/env bash
set -e
PROFILE="${1:-stress.spk}"
NC="${2:-8}"
echo "[1/3] Compiling $PROFILE to Verilog..."
python3 spikeling_verilog.py "$PROFILE"
echo
echo "[2/3] Building simulation (iverilog)..."
iverilog -g2012 -D NCOUNT=$NC -o spikeling_sim spikeling_neurons.v spikeling_tb.v
echo
echo "[3/3] Running simulation..."
echo
vvp spikeling_sim
echo
echo "Waveform: spikeling.vcd  (open in GTKWave to see registers toggle)"
