#!/usr/bin/env python3
"""Causal self-analysis for the voice command system's REAL interaction log
(voice_interaction_log.csv). Reuses the EXACT backdoor-adjustment +
Cinelli-Hazlett robustness-value formula from methodlm.py's adjust()
function (read directly from llama_demo/methodlm.py, not reconstructed) --
same tool, same gbranaa-hue discipline, applied to this system's own real
usage data instead of a benchmark dataset.

Target: whether a spoken command was successfully matched (1) or not (0).
Candidate drivers: word_count, listen_latency_s, session_elapsed_s.

PRE-REGISTERED: no prediction on which (if any) driver survives adjustment
-- there isn't enough real usage yet to have a prior. Report honestly,
including "not enough data" if that's the honest answer.

--validate runs the SAME adjust() logic on a small synthetic dataset with
KNOWN ground truth first, to confirm the mechanism itself works correctly
-- clearly separate from any claim about the real log.
"""
import sys, csv, os
import numpy as np

LOG_PATH = "voice_interaction_log.csv"
MIN_ROWS = 20   # below this, a 3-predictor regression is unreliable -- say so, don't force it

def zsc(a):
    a = np.asarray(a, float)
    return (a - a.mean()) / (a.std() + 1e-9)

def adjust(data, x, target, zs):
    """EXACT reuse of methodlm.py's adjust() formula -- backdoor adjustment
    (standardized multiple regression) + Cinelli-Hazlett robustness value."""
    zs = [z for z in zs if z in data and z not in (x, target)]
    n = len(data[target])
    y = zsc(data[target])

    def fit(cond):
        X = np.column_stack([zsc(data[c]) for c in [x] + cond] + [np.ones(n)])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        dof = n - X.shape[1]
        se = np.sqrt(((resid ** 2).sum() / max(dof, 1)) * np.diag(np.linalg.pinv(X.T @ X)))
        t = float(beta[0] / (se[0] + 1e-12))
        partial = t / np.sqrt(t * t + dof) if dof > 0 else float("nan")
        f = abs(t) / np.sqrt(max(dof, 1))
        rv = 0.5 * (np.sqrt(f ** 4 + 4 * f ** 2) - f ** 2)
        return partial, t, rv

    partial, t, rv = fit(zs)
    raw = float(np.corrcoef(data[x], data[target])[0, 1])
    return raw, partial, t, rv

def run_adjust_report(data, target, candidates):
    results = {}
    print(f"n={len(data[target])} rows\n")
    for x in candidates:
        others = [c for c in candidates if c != x]
        raw, partial, t, rv = adjust(data, x, target, others)
        results[x] = (raw, partial, rv)
        fragile = " (fragile -- likely bystander)" if rv < 0.10 else " (robust)"
        print(f"  ADJUST: {x} | {', '.join(others)}  raw={raw:+.3f}  adjusted={partial:+.3f}  RV={rv:.3f}{fragile}")
    return results

def validate_mechanism():
    print("=== --validate: confirming the ADJUST mechanism itself on SYNTHETIC data with known ===")
    print("=== ground truth (NOT a claim about your real log) ===\n")
    rng = np.random.default_rng(0)
    n = 200
    real_driver = rng.standard_normal(n)
    confound = rng.standard_normal(n)
    decoy = 0.8 * confound + 0.2 * rng.standard_normal(n)   # correlated with target only via confound
    target = 0.6 * real_driver + 0.7 * confound + 0.15 * rng.standard_normal(n)
    data = {"real_driver": real_driver, "decoy": decoy, "confound": confound, "target": target}
    run_adjust_report(data, "target", ["real_driver", "decoy", "confound"])
    print("\nExpected: real_driver and confound stay robust (high RV) after adjustment; decoy's")
    print("raw correlation should collapse once confound is controlled for. If that's what")
    print("printed above, the mechanism is working correctly.\n")

if __name__ == "__main__":
    if "--validate" in sys.argv:
        validate_mechanism()
        sys.exit(0)

    if not os.path.exists(LOG_PATH):
        print("No real interaction log yet -- use voice_commands.py a few times first.")
        print("SPOKEN_SUMMARY: I don't have any real usage data logged yet. Try using some voice commands first, then ask for a report.")
        sys.exit(0)

    rows = list(csv.DictReader(open(LOG_PATH)))
    if len(rows) < MIN_ROWS:
        print(f"Only {len(rows)} real interactions logged so far -- need at least {MIN_ROWS} for a")
        print("reliable 3-predictor causal test. Reporting the raw tally honestly instead.")
        matched = sum(1 for r in rows if r["matched_command"] != "NONE")
        print(f"  {matched}/{len(rows)} interactions matched a command.")
        print(f"SPOKEN_SUMMARY: I only have {len(rows)} real interactions logged, not enough yet "
              f"for a real causal test. So far {matched} out of {len(rows)} matched a command.")
        sys.exit(0)

    data = {
        "word_count": [float(r["word_count"]) for r in rows],
        "listen_latency_s": [float(r["listen_latency_s"]) for r in rows],
        "session_elapsed_s": [float(r["session_elapsed_s"]) for r in rows],
        "matched": [1.0 if r["matched_command"] != "NONE" else 0.0 for r in rows],
    }
    print("=== Real causal analysis of your actual voice-command usage ===\n")
    results = run_adjust_report(data, "matched", ["word_count", "listen_latency_s", "session_elapsed_s"])

    best = max(results, key=lambda k: results[k][2])
    raw, partial, rv = results[best]
    if rv >= 0.10:
        summary = f"The strongest real driver of whether a command matched is {best.replace('_',' ')}, robustness value {rv:.2f}."
    else:
        summary = "None of the candidates I tested had a robust effect on whether a command matched -- all fragile."
    print(f"\nSPOKEN_SUMMARY: {summary}")
