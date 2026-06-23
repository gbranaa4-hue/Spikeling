# Spikeling Benchmarks

Real, measured results — not marketing claims. This file gets updated as
more benchmarks are added. Each entry states what was tested, the actual
numbers, and what they do/don't prove.

---

## 1. Dormant event-driven LIF brains vs naive polling FSM (pure Python)

**Script:** `dormant_vs_polling.py`
**Claim being tested:** "Spikeling's event-driven dormant-brain model is
cheaper than naively running full AI logic on every NPC every tick" —
the core architectural pitch for using Spikeling as cheap game AI.

**Method:** N NPCs placed around a player, a configurable fraction within
"activation range." Both models pay the same cheap distance check for
every NPC every tick. Beyond that:
- **Polling FSM** runs a small fixed decision tree (health/distance
  comparisons) for every NPC regardless of distance — representative of
  typical unoptimized game AI.
- **Spikeling LIF** only integrates a 5-neuron LIF network (same shape as
  `fps-game/enemy_brain.spk`) for NPCs inside activation range; NPCs
  outside range are skipped entirely (the actual "dormant" optimization).

200 ticks per trial.

**Results (wall-clock seconds, lower is better; speedup = polling time / Spikeling time, >1.0 means Spikeling wins):**

| NPCs | % active | Polling FSM | Spikeling LIF | Speedup |
|---|---|---|---|---|
| 50 | 5% | 0.0021s | 0.0024s | 0.89x |
| 50 | 100% | 0.0029s | 0.0108s | 0.27x |
| 200 | 5% | 0.0090s | 0.0103s | 0.88x |
| 200 | 100% | 0.0112s | 0.0420s | 0.27x |
| 1000 | 5% | 0.0462s | 0.0487s | 0.95x |
| 1000 | 100% | 0.0543s | 0.1999s | 0.27x |

**Verdict: claim NOT supported in pure Python.** Spikeling's dormant LIF
model is slower than naive polling at every scale and every active
fraction tested, including its best case (1000 NPCs, 5% active: still
0.95x, i.e. slightly slower).

**Why:** the polling FSM's per-NPC cost (a few comparisons) is cheaper
than even one active NPC's LIF brain update (5 neuron objects, method
calls, list comprehension). Python's interpreter overhead per
object/function call dominates the actual arithmetic — initially assumed
to be the whole explanation (see benchmark #2).

---

## 2. Same comparison, compiled C (isolating interpreter overhead)

**Script:** `dormant_vs_polling.c` (build: `gcc -O2 -o dormant_vs_polling.exe dormant_vs_polling.c -lm`)
**Claim being tested:** that benchmark #1's result was caused by Python
interpreter overhead, and a compiled LIF implementation would show
dormancy winning.

**Method:** identical NPC counts, active fractions, and logic to
benchmark #1, ported 1:1 to C, compiled with `-O2`. 20,000 ticks per
trial (raised from 200 because Windows' `clock()` resolution is too
coarse to measure short runs accurately).

**Results:**

| NPCs | % active | Polling FSM | Spikeling LIF | Speedup |
|---|---|---|---|---|
| 50 | 5% | 0.0020s | 0.0020s | 1.00x |
| 50 | 100% | 0.0020s | 0.0060s | 0.33x |
| 1000 | 5% | 0.0360s | 0.0400s | 0.90x |
| 1000 | 100% | 0.0370s | 0.1230s | 0.30x |
| 10000 | 5% | 0.3700s | 0.4110s | 0.90x |
| 10000 | 100% | 0.3710s | 1.5420s | 0.24x |

**Verdict: claim still NOT supported, even in optimized native C.** The
interpreter-overhead theory from benchmark #1 was wrong. Dormant LIF
brains lose to naive polling at every scale and fraction tested here too.

**Why:** the polling FSM baseline is already cheap — a handful of
comparisons. A 5-neuron LIF update, even in compiled C, costs noticeably
more per *active* NPC than the entire polling FSM costs per NPC (roughly
6-7x). The "skip dormant NPCs" optimization is real, but the savings only
outweigh the per-active-NPC cost premium at very low active fractions —
and even at 5% active it's still a net loss here, because the thing being
skipped (3 comparisons) is too cheap to be worth skipping.

**What this means for the project:** "event-driven brains are cheaper
than polling" is not true as a blanket claim — it depends on how much
*more* the active-NPC logic does than the polling baseline. Real game AI
(pathfinding, raycasts, combat calc) is usually much heavier than 3
comparisons. **The benchmark needs a heavier, more realistic polling
baseline** before the claim can be fairly evaluated. See benchmark #3.

---

## 3. Heavy realistic polling baseline (raycast + pathfinding stand-in)

**Script:** `dormant_vs_polling_heavy.c` (build: `gcc -O2 -o dormant_vs_polling_heavy.exe dormant_vs_polling_heavy.c -lm`)
**Claim being tested:** benchmark #2 concluded dormancy only wins if the
skipped per-NPC logic is expensive enough. This replaces the 3-comparison
polling baseline with a `heavy_logic()` function doing a simulated
16-step line-of-sight raycast plus an 8x8 local-grid pathfinding
relaxation pass — comparable FLOP/branch volume to real game AI, not a
toy FSM. Both models pay this cost identically whenever they actually
evaluate an NPC; Spikeling skips it entirely for dormant NPCs.

**Build note (now fixed):** an earlier version of this benchmark, when
built with `-O2`, produced nonsensical results (the "always pays the
cost" polling baseline scaled its runtime with active fraction, which
shouldn't be possible). Root cause, found by inspection: `heavy_logic()`'s
result (`cost`) was only consumed inside the `dist < activation_range`
branch of `polling_tick`, so GCC legally **sank the call into that
branch** (provably dead in the other branch, no observable side effect)
— meaning the compiler was silently giving the "naive" baseline the same
dormancy skip Spikeling does on purpose, invalidating the comparison.
Fixed by routing `cost` through a `volatile` global sink so the compiler
can no longer treat the call as skippable. The numbers below are from
the corrected `-O2` build.

**Results (2000 ticks):**

| NPCs | % active | Polling FSM | Spikeling LIF | Speedup |
|---|---|---|---|---|
| 50 | 5% | 0.0160s | 0.0010s | 16.00x |
| 50 | 100% | 0.0120s | 0.0140s | 0.86x |
| 200 | 5% | 0.0750s | 0.0030s | 25.00x |
| 200 | 100% | 0.0520s | 0.0600s | 0.87x |
| 1000 | 5% | 0.4330s | 0.0150s | 28.87x |
| 1000 | 20% | 0.4020s | 0.0620s | 6.48x |
| 1000 | 50% | 0.3500s | 0.1500s | 2.33x |
| 1000 | 100% | 0.2720s | 0.2950s | 0.92x |

(A pre-fix `-O0` run, unaffected by the sinking bug, showed the same
shape with more conservative speedups: 17-18x at 5% active dropping to
~0.86-0.95x at 100% — corroborating the corrected `-O2` numbers above.)

**Verdict: claim SUPPORTED, with a clear boundary.** When the skipped
logic is realistically expensive, Spikeling's dormant model wins
decisively at low-to-moderate active fractions (16-29x faster at 5%
active, still 2.3x faster at 50% active), crossing over to a slight loss
only once nearly all NPCs are simultaneously active — a scenario most
games rarely hit.

**What this means for the project:** this is the first benchmark that
gives Spikeling's "cheap when idle" pitch real evidence, with a specific,
defensible claim: *"Spikeling-style dormant AI is up to ~29x faster than
naive always-on polling at typical (≤20%) NPC engagement rates, when
per-NPC AI logic is non-trivial (raycasts/pathfinding-class cost),
crossing to roughly break-even only once nearly all NPCs are
simultaneously active."*

---

## 4. Resonator-based detection vs naive amplitude-threshold detection

**Script:** `../resonator-prototype/accuracy_benchmark.py`
**Claim being tested:** that a resonator tuned to a target frequency can
correctly detect whether that specific frequency is present in a mixed
signal — even when other (distractor) tones and noise are also present —
whereas a naive "is the signal loud" amplitude threshold can't
distinguish the target tone from distractor tones, since it only
measures total energy, not which frequency it's at.

**Method:** 120 trials per noise level. Each trial: a coin flip decides
whether the target frequency (440Hz) is present (at random amplitude
0.5-1.0 if so); 1-2 random distractor tones (110/220/880/1760Hz, random
amplitude 0.3-1.0) are always added, plus broadband noise. Both detectors
see the identical mixed signal. Detection thresholds for both are
calibrated once from target-absent-only trials (the realistic way you'd
set a threshold in practice), then held fixed across all test trials and
noise levels for a fair comparison.

**Results:**

| Noise | Detector | Accuracy | False Positive % | Recall |
|---|---|---|---|---|
| 0.05 | Resonator | 99.2% | 1.7% | 100.0% |
| 0.05 | Raw-amplitude | 66.7% | 13.6% | 47.5% |
| 0.20 | Resonator | 99.2% | 1.7% | 100.0% |
| 0.20 | Raw-amplitude | 65.0% | 13.6% | 44.3% |
| 0.50 | Resonator | 99.2% | 1.7% | 100.0% |
| 0.50 | Raw-amplitude | 62.5% | 11.9% | 37.7% |

**Verdict: claim SUPPORTED, decisively.** The resonator detector holds
~99% accuracy and 100% recall across all tested noise levels, while the
naive amplitude detector tops out around 67% accuracy and misses more
than half the true positives (47.5% recall at best) — because distractor
tones inflate raw signal energy regardless of whether the target
frequency is actually present, fooling a threshold that can't tell
frequencies apart. Performance gap is stable across noise levels, meaning
it's specifically a frequency-discrimination win, not a noise-robustness
artifact.

**What this means for the project:** this is real, reusable evidence for
the "hearing" use case discussed earlier (an NPC/sensor distinguishing a
specific sound signature from background noise and other sounds) — a
naive volume-threshold approach genuinely cannot do this reliably, and
resonance-based detection can. This is the strongest, cleanest result of
all four benchmarks so far.

**Cross-backend confirmation:** the Resonator model behind this benchmark
is now implemented and independently verified in all three Spikeling
backends — Python (`core/runtime/runtime.py`), compiled C
(`core/compiler/compiler.py`'s codegen), and synthesizable fixed-point
Verilog hardware (`../sdk-verilog/spikeling_resonator_verilog.py`). All
three correctly detect the same 440Hz/1760Hz test tones with no false
positives, and the Python and C backends produce matching energy values
to 5+ significant figures. This isn't just a software trick — it holds
up as real digital hardware logic.

---

## 6. Amplitude-gated energy update (operand isolation) for Resonators

**Scripts:** `gated_vs_ungated_resonators.py`, `gated_vs_ungated_resonators.c`
**Claim being tested:** that skipping the Resonator's expensive `x*x`
energy multiply when a channel's amplitude is below the noise floor
(same "skip the dormant/quiet work" idea proven for NPC brains in
benchmark #3) would similarly speed up a bank of resonator channels
where most are quiet most of the time.

**Method:** a bank of N resonator channels (16/64/256), only a small
fraction ever actually driven near resonance ("loud") at once, the rest
seeing only noise. Both versions integrate the same oscillator mechanics
(x, v) every tick unconditionally — only the energy multiply is gated.
Tested in both Python (`runtime.ResonatorState`, gating built directly
into the class) and compiled C.

**Results — Python:**

| Channels | % loud | Ungated | Gated | Speedup |
|---|---|---|---|---|
| 256 | 2% | 0.3893s | 0.4779s | 0.81x |
| 256 | 100% | 0.4616s | 0.5922s | 0.78x |

**Results — C (`-O2`):**

| Channels | % loud | Ungated | Gated | Speedup |
|---|---|---|---|---|
| 256 | 2% | 0.0610s | 0.0600s | 1.02x |
| 256 | 100% | 0.0800s | 0.0820s | 0.98x |

**Verdict: claim NOT supported as a CPU speed optimization, in either
language.** In Python, gating is consistently *slower* (~0.8x) — the
`if` check costs more in interpreter overhead than the multiply it
avoids. In C, it's a wash (~1.0x, noise-level) — modern CPUs have
pipelined multiplier units that are already nearly free, so skipping one
multiply buys nothing measurable, and the branch can cost just as much
(data-dependent branches risk misprediction penalties that erase any
saving). **Unlike benchmark #3, this is not a software-architecture
win** — the original "skip dormant NPC logic entirely" benchmark worked
because it skipped *expensive multi-step logic* (raycasts, pathfinding);
this benchmark only ever skips *one multiply*, which was never expensive
enough on a CPU to be worth gating around.

**Where it DOES hold up: real hardware.** The same gating was implemented
in the synthesizable Verilog backend
(`sdk-verilog/spikeling_resonator_verilog.py`) as **operand isolation** —
a standard, real chip-design technique: instead of just ignoring the
multiplier's result when gated, the multiplier's *inputs* are forced to
zero (`gated_x`), so the multiplier sees unchanging zero operands and
has near-zero internal switching activity. This is where dynamic power
actually comes from in digital logic — NOT instruction/cycle count,
which is what the Python/C benchmarks measure and is exactly why they
showed no win. Verified correct with Icarus Verilog (identical detection
behavior, same fire steps, as the ungated version). **No power
measurement was possible in this environment** (Icarus Verilog simulates
logic, not power — that requires a real synthesis/place-and-route flow,
e.g. with a PDK and a tool like Yosys+OpenSTA or a vendor FPGA toolchain)
so the power savings claim rests on the well-established operand
isolation literature, not a number measured here. That's the honest
state of this claim: real and standard technique, correctly implemented,
*unverified magnitude* in this environment.

**What this means for the project:** the user's instinct to look for
more efficiency was reasonable, but the right place to apply it depends
entirely on what's actually expensive in the *target* environment —
"skip work when idle" only pays off when the skipped work is genuinely
costly relative to the check, which was true for NPC AI logic on a CPU
(benchmark #3) but not true for a single multiply on a CPU (this
benchmark). It only becomes true again once the cost model changes to
real silicon power, where multiplier toggling is genuinely expensive.
Applying an optimization technique to the wrong layer doesn't help even
when the technique itself is legitimate — this benchmark is the
demonstration of that, not a failure to find a win.

---

## 7. Resonator vs established techniques (Goertzel, FFT) — not a naive strawman this time

**Script:** `../resonator-prototype/vs_established_techniques.py`
**Claim being tested:** benchmark #4 showed the resonator beating a naive
amplitude threshold (99.2% vs 65% accuracy) — but a naive threshold isn't
a real competitor for "detect one specific frequency in noise." The
actual industry-standard technique for exactly this task is the
**Goertzel algorithm** (used in telephone systems for DTMF tone
detection since the 1970s) — a recursive, single-bin frequency detector
with comparable computational character to the resonator (a couple of
multiplies and adds per sample). FFT (full spectrum) is included too,
for context, even though it's solving a more general problem than
needed here.

**Method:** identical trial design to benchmark #4 (target tone
present/absent, 1-2 random distractor tones, broadband noise,
calibrated thresholds from negative-only trials), so the comparison is
apples-to-apples with the previously reported 99.2%/65% numbers. Both
accuracy AND per-trial wall-clock time measured for all three methods.

**Results:**

| Noise | Method | Accuracy | False Positive % | Recall | Time/trial |
|---|---|---|---|---|---|
| 0.05 | Resonator | 97.5% | 5.0% | 100.0% | 626.8us |
| 0.05 | Goertzel | 92.5% | 15.0% | 100.0% | 289.1us |
| 0.05 | FFT | 92.5% | 15.0% | 100.0% | 21.0us |
| 0.20 | Resonator | 97.5% | 5.0% | 100.0% | 628.1us |
| 0.20 | Goertzel | 98.8% | 2.5% | 100.0% | 288.0us |
| 0.20 | FFT | 100.0% | 0.0% | 100.0% | 20.6us |
| 0.50 | Resonator | 98.8% | 2.5% | 100.0% | 638.0us |
| 0.50 | Goertzel | 97.5% | 5.0% | 100.0% | 291.8us |
| 0.50 | FFT | 98.8% | 2.5% | 100.0% | 21.8us |

**Verdict: claim NOT supported against a real competitor.** Accuracy is
now a wash — all three methods land in the same 92-100% band with no
consistent winner across noise levels (Goertzel and FFT actually edge
out the resonator at moderate noise). On speed, the resonator is
**roughly 30x slower than FFT** and **~2x slower than Goertzel**, despite
Goertzel being structurally similar (a simple recursive filter, not a
full transform) — the resonator's extra cost comes from doing more
floating-point operations per sample and Python object/method-call
overhead in this implementation, not from doing fundamentally more
useful work.

**This directly overturns the framing of benchmark #4.** That benchmark
was correct on its own terms (resonator beats a naive amplitude
threshold), but a naive amplitude threshold was never a meaningful
baseline for "is this a good frequency detector" — Goertzel has been the
real answer to that question since 1958. Measured against the actual
state of the art for this exact task, the resonator does not win on
accuracy and clearly loses on speed.

**What this means for the project:** this is the test that should have
been run before claiming any kind of advantage for the resonator
approach, and it's a meaningfully different conclusion than benchmark #4
implied. It does not mean the resonator is useless — it still does the
job correctly and fits naturally inside the existing neuron-based DSL
(letting it compose with LIF networks and actions without a separate
signal-processing pipeline). But "resonance beats the obvious
alternative" is a different and much weaker claim than "resonance beats
the established technique," and the latter is what actually matters for
any claim of real-field usefulness. See the broader discussion in this
conversation on whether Spikeling represents genuine research
contribution vs. applied engineering — this result is direct evidence
for "applied engineering, not novel contribution."

**Follow-up: how much of the speed gap is real algorithm cost vs. fixable
implementation overhead?** Rewrote the resonator's energy computation as
a tight loop with local variables (no object attribute lookups, no
recomputing `omega^2` every sample, no growing history list) —
`fast_resonator_energy()` in the same script. Initial attempt actually
got *slower* (717us -> 1017us): iterating a numpy array directly yields
`np.float64` scalars, whose arithmetic goes through numpy's ufunc
dispatch machinery, which is slower than native Python floats for tight
scalar loops -- a real, easy-to-miss performance trap, not a one-off
mistake (the Goertzel implementation had the exact same latent issue;
fixed both with `.tolist()` for a fair comparison).

**Corrected results (noise=0.20, representative):**

| Method | Time/trial | vs Goertzel |
|---|---|---|
| Resonator (original, object-based) | 733.6us | 6.0x slower |
| Resonator (fast, tight loop) | 299.8us | 2.5x slower |
| Goertzel | 122.1us | — |
| FFT | 25.9us | 4.7x faster than Goertzel |

**Verdict: the rewrite recovered real ground (2.4x speedup) but did not
close the gap.** Accuracy was unaffected by the rewrite (same physics,
same numbers). The remaining ~2.5x gap to Goertzel is now a *structural*
one, not an implementation artifact: the resonator's update does
roughly 3x the floating-point operations per sample that Goertzel's
two-term recurrence does (`accel` needs two products plus a sum, then
two more additions for `v` and `x`, plus the energy accumulation term;
Goertzel needs one product and two additions, full stop) — and that
ratio (~3x more arithmetic) lines up closely with the measured ~2.5x
slowdown. The gap to FFT is mostly a language/implementation gap (pure
Python loop vs. compiled BLAS/FFTW), not an algorithmic one — both
Goertzel and the resonator are doing O(N) work for one frequency, while
FFT does O(N log N) for *every* frequency simultaneously and still wins
on raw wall-clock because it isn't running in the Python interpreter.

**Honest bottom line:** the resonator's per-sample math is inherently
more expensive than the established single-frequency techniques, by a
measurable and now well-understood margin. A C or Verilog
implementation (already built and verified in this project, see
benchmark entries on the C/Verilog backends) would shrink the *absolute*
time difference a great deal, but the *relative* 3x-more-arithmetic
disadvantage versus Goertzel would persist in any language, because it's
intrinsic to the resonator's physics, not the implementation.

---

## How to add a new benchmark entry

1. State the specific claim being tested up front.
2. Describe the method well enough that someone else could rerun it.
3. Report real numbers, not estimates.
4. State the verdict plainly, including if the claim fails — a benchmark
   that only ever confirms what you hoped is not evidence.
