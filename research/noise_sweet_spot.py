"""
Stochastic Resonance at Inference Time
=======================================
Experiments 1-3: Does adding noise at inference time improve
accuracy on uncertain/borderline examples?
"""

import numpy as np
import json
from pathlib import Path

# ── Try to import torch/torchvision, fall back to numpy-only demo ──
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torchvision import datasets, transforms
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ─────────────────────────────────────────────────
# NUMPY-ONLY DEMO (always runs, no GPU needed)
# Shows the SR effect on a toy classification problem
# ─────────────────────────────────────────────────

def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

def make_weak_signal_dataset(n=2000, signal_strength=0.4, seed=42):
    """
    Two overlapping Gaussians — weak separation so many examples
    sit near the decision boundary (the 'uncertain' zone).
    """
    rng = np.random.default_rng(seed)
    half = n // 2
    X0 = rng.normal(loc=-signal_strength, scale=1.0, size=(half, 8))
    X1 = rng.normal(loc=+signal_strength, scale=1.0, size=(half, 8))
    X  = np.vstack([X0, X1]).astype(np.float32)
    y  = np.array([0]*half + [1]*half)
    return X, y

class ToyClassifier:
    """Simple logistic regression trained with SGD."""
    def __init__(self, n_features=8):
        self.W = np.zeros(n_features)
        self.b = 0.0

    def predict_proba(self, X):
        logits = X @ self.W + self.b
        return sigmoid(logits)

    def train(self, X, y, lr=0.05, epochs=200):
        n = len(y)
        for _ in range(epochs):
            probs = self.predict_proba(X)
            err   = probs - y
            self.W -= lr * (X.T @ err) / n
            self.b -= lr * err.mean()

def find_uncertain_examples(model, X, y, low=0.40, high=0.60):
    """Return indices where model confidence is in [low, high]."""
    probs   = model.predict_proba(X)
    mask    = (probs >= low) & (probs <= high)
    return np.where(mask)[0]

# ─────────────────────────────────────────────────
# EXPERIMENT 1 — Baseline on uncertain examples
# ─────────────────────────────────────────────────

def experiment_1(model, X, y, uncertain_idx):
    probs   = model.predict_proba(X[uncertain_idx])
    preds   = (probs >= 0.5).astype(int)
    acc     = (preds == y[uncertain_idx]).mean()
    avg_conf = np.abs(probs - 0.5).mean() + 0.5
    return {
        "n_uncertain": len(uncertain_idx),
        "baseline_accuracy": float(acc),
        "avg_confidence": float(avg_conf),
        "description": "Accuracy on uncertain examples with NO noise"
    }

# ─────────────────────────────────────────────────
# EXPERIMENT 2 — Noise sweep (stochastic resonance)
# ─────────────────────────────────────────────────

def noisy_majority_vote(model, X_sub, y_sub, sigma, n_samples=200, rng=None):
    """
    For each example, add Gaussian noise n_samples times,
    collect predictions, majority-vote → final prediction.
    """
    if rng is None:
        rng = np.random.default_rng(0)

    n = len(X_sub)
    votes = np.zeros(n)  # accumulate P(class=1)

    for _ in range(n_samples):
        noise = rng.normal(0, sigma, X_sub.shape).astype(np.float32)
        probs = model.predict_proba(X_sub + noise)
        votes += probs

    avg_probs = votes / n_samples
    preds     = (avg_probs >= 0.5).astype(int)
    acc       = (preds == y_sub).mean()
    return float(acc), avg_probs

def experiment_2(model, X, y, uncertain_idx, sigmas=None, n_samples=200):
    if sigmas is None:
        sigmas = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00,
                  1.25, 1.50, 2.00, 3.00]

    X_u = X[uncertain_idx]
    y_u = y[uncertain_idx]
    rng = np.random.default_rng(1)

    results = []
    for sigma in sigmas:
        if sigma == 0.0:
            probs = model.predict_proba(X_u)
            preds = (probs >= 0.5).astype(int)
            acc   = (preds == y_u).mean()
        else:
            acc, _ = noisy_majority_vote(model, X_u, y_u, sigma,
                                         n_samples=n_samples, rng=rng)
        results.append({"sigma": sigma, "accuracy": acc})

    best = max(results, key=lambda r: r["accuracy"])
    return {
        "sweep": results,
        "best_sigma": best["sigma"],
        "best_accuracy": best["accuracy"],
        "baseline_accuracy": results[0]["accuracy"],
        "improvement": best["accuracy"] - results[0]["accuracy"],
        "description": "Noise sweep over uncertain examples"
    }

# ─────────────────────────────────────────────────
# EXPERIMENT 3 — Does optimal σ transfer?
# ─────────────────────────────────────────────────

def experiment_3(model, X, y, uncertain_idx, best_sigma, n_samples=200):
    """
    Split uncertain examples into two halves.
    Find optimal σ on half-A, apply to half-B — does it transfer?
    """
    rng = np.random.default_rng(2)
    n   = len(uncertain_idx)
    idx_A = uncertain_idx[:n//2]
    idx_B = uncertain_idx[n//2:]

    sigmas = np.linspace(0.0, 2.0, 20)

    # Find sweet spot on A
    best_acc_A, best_sig_A = 0, 0
    for sigma in sigmas:
        if sigma == 0:
            probs = model.predict_proba(X[idx_A])
            acc   = ((probs >= 0.5).astype(int) == y[idx_A]).mean()
        else:
            acc, _ = noisy_majority_vote(model, X[idx_A], y[idx_A],
                                          sigma, n_samples=n_samples, rng=rng)
        if acc > best_acc_A:
            best_acc_A = acc
            best_sig_A = sigma

    # Apply A's sweet-spot to B
    baseline_B, _  = noisy_majority_vote(model, X[idx_B], y[idx_B],
                                          0.0, n_samples=1, rng=rng)
    baseline_B = ((model.predict_proba(X[idx_B]) >= 0.5).astype(int) == y[idx_B]).mean()

    transfer_acc, _ = noisy_majority_vote(model, X[idx_B], y[idx_B],
                                           best_sig_A, n_samples=n_samples, rng=rng)

    return {
        "optimal_sigma_from_A": float(best_sig_A),
        "accuracy_on_A_with_opt_sigma": float(best_acc_A),
        "baseline_accuracy_B": float(baseline_B),
        "transfer_accuracy_B": float(transfer_acc),
        "transfer_improvement": float(transfer_acc - baseline_B),
        "transfers": transfer_acc > baseline_B,
        "description": "Does the optimal sigma found on half-A transfer to half-B?"
    }

# ─────────────────────────────────────────────────
# ASCII BAR CHART (terminal output)
# ─────────────────────────────────────────────────

def bar(val, max_val=1.0, width=40, char="█"):
    filled = int(round(val / max_val * width))
    return char * filled

def print_results(r1, r2, r3):
    W = 68
    print("\n" + "=" * W)
    print("  STOCHASTIC RESONANCE AT INFERENCE TIME — RESULTS")
    print("=" * W)

    # ── Exp 1 ──
    print(f"\nEXPERIMENT 1 — Baseline (no noise)")
    print("-" * W)
    print(f"  Uncertain examples: {r1['n_uncertain']}")
    print(f"  Baseline accuracy:  {r1['baseline_accuracy']:.3f}")
    print(f"  Avg confidence:     {r1['avg_confidence']:.3f}")

    # ── Exp 2 ──
    print(f"\nEXPERIMENT 2 — Noise sweep on uncertain examples")
    print("-" * W)
    baseline = r2["baseline_accuracy"]
    best     = r2["best_accuracy"]
    for row in r2["sweep"]:
        sig  = row["sigma"]
        acc  = row["accuracy"]
        mark = " <── sweet spot" if sig == r2["best_sigma"] else ""
        b    = bar(acc, max_val=1.0, width=36)
        print(f"  σ={sig:5.2f} | acc={acc:+.3f} | {b}{mark}")

    print(f"\n  Baseline (σ=0):   {baseline:.3f}")
    print(f"  Best (σ={r2['best_sigma']:.2f}): {best:.3f}")
    delta = r2["improvement"]
    sign  = "+" if delta >= 0 else ""
    print(f"  Improvement:      {sign}{delta:.3f}  {'✓ NOISE HELPED' if delta > 0 else '✗ no improvement'}")

    # ── Exp 3 ──
    print(f"\nEXPERIMENT 3 — Does the sweet spot transfer?")
    print("-" * W)
    print(f"  Optimal σ found on split-A:  {r3['optimal_sigma_from_A']:.3f}")
    print(f"  Accuracy on A:               {r3['accuracy_on_A_with_opt_sigma']:.3f}")
    print(f"  Baseline on split-B:         {r3['baseline_accuracy_B']:.3f}")
    print(f"  Transfer accuracy on B:      {r3['transfer_accuracy_B']:.3f}")
    d = r3["transfer_improvement"]
    s = "+" if d >= 0 else ""
    print(f"  Transfer improvement:        {s}{d:.3f}  {'✓ TRANSFERS' if r3['transfers'] else '✗ does not transfer'}")

    print("\n" + "=" * W)
    print("  WHAT THIS SHOWS")
    print("=" * W)
    if r2["improvement"] > 0.01:
        print("""
  ✓ Stochastic resonance improves uncertain predictions.
    A classifier that would normally guess wrong on borderline
    examples can be rescued at inference time by sampling
    noisy versions and majority-voting the result.

  Next step: learn the optimal σ per-input with a small
  meta-network ("noise predictor") — see sr_learnable.py
""")
    else:
        print("""
  The toy model did not show strong SR improvement here.
  This can happen when the model is already well-calibrated
  or the signal is too weak for any noise level to help.
  Try a deeper model or stronger signal overlap.
""")

# ─────────────────────────────────────────────────
# PYTORCH VERSION (MNIST, if torch available)
# ─────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class SmallCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
                nn.MaxPool2d(2),
                nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
                nn.MaxPool2d(2),
                nn.Flatten(),
                nn.Linear(32*7*7, 128), nn.ReLU(),
                nn.Linear(128, 10)
            )
        def forward(self, x): return self.net(x)

    def run_mnist_experiment(n_train=5000, n_test=1000, epochs=5):
        print("\n[PyTorch] Running MNIST stochastic-resonance experiment...")
        device = torch.device("cpu")
        tf = transforms.Compose([transforms.ToTensor(),
                                  transforms.Normalize((0.1307,), (0.3081,))])
        train_ds = datasets.MNIST(".", train=True,  download=True, transform=tf)
        test_ds  = datasets.MNIST(".", train=False, download=True, transform=tf)

        # Subset for speed
        train_ds = torch.utils.data.Subset(train_ds, range(n_train))
        test_ds  = torch.utils.data.Subset(test_ds,  range(n_test))

        train_dl = torch.utils.data.DataLoader(train_ds, batch_size=128, shuffle=True)
        test_dl  = torch.utils.data.DataLoader(test_ds,  batch_size=256)

        model = SmallCNN().to(device)
        opt   = torch.optim.Adam(model.parameters(), lr=1e-3)

        # Train
        for ep in range(epochs):
            model.train()
            for xb, yb in train_dl:
                xb, yb = xb.to(device), yb.to(device)
                opt.zero_grad()
                F.cross_entropy(model(xb), yb).backward()
                opt.step()
            print(f"  Epoch {ep+1}/{epochs} done")

        # Collect uncertain examples
        model.eval()
        all_x, all_y, all_conf, all_pred = [], [], [], []
        with torch.no_grad():
            for xb, yb in test_dl:
                xb = xb.to(device)
                probs = F.softmax(model(xb), dim=1)
                conf, pred = probs.max(dim=1)
                all_x.append(xb.cpu()); all_y.append(yb)
                all_conf.append(conf.cpu()); all_pred.append(pred.cpu())

        all_x    = torch.cat(all_x)
        all_y    = torch.cat(all_y)
        all_conf = torch.cat(all_conf)
        all_pred = torch.cat(all_pred)

        uncertain_mask = (all_conf < 0.70)
        ux = all_x[uncertain_mask]
        uy = all_y[uncertain_mask]
        up = all_pred[uncertain_mask]

        baseline_acc = (up == uy).float().mean().item()
        print(f"\n  Uncertain examples (conf < 0.70): {uncertain_mask.sum().item()}")
        print(f"  Baseline accuracy on uncertain:   {baseline_acc:.3f}")

        # Noise sweep
        sigmas = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.00]
        print("\n  Noise sweep:")
        best_sigma, best_acc = 0.0, baseline_acc
        for sigma in sigmas:
            if sigma == 0:
                acc = baseline_acc
            else:
                votes = torch.zeros(len(ux), 10)
                for _ in range(50):
                    noisy = ux + torch.randn_like(ux) * sigma
                    with torch.no_grad():
                        votes += F.softmax(model(noisy), dim=1).cpu()
                preds = votes.argmax(dim=1)
                acc   = (preds == uy).float().mean().item()
            mark = ""
            if acc > best_acc:
                best_acc = acc; best_sigma = sigma; mark = " <── sweet spot"
            b = bar(acc, width=30)
            print(f"    σ={sigma:.2f} | acc={acc:.3f} | {b}{mark}")

        print(f"\n  Best σ={best_sigma:.2f}  acc={best_acc:.3f}  improvement={best_acc-baseline_acc:+.3f}")
        return best_sigma, best_acc

# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────

def main():
    print("\n" + "="*68)
    print("  STOCHASTIC RESONANCE AT INFERENCE TIME")
    print("  Toy (numpy) experiments — no GPU needed")
    print("="*68)

    # Build dataset & model
    print("\nBuilding weak-signal dataset (8 features, overlapping classes)...")
    X, y = make_weak_signal_dataset(n=3000, signal_strength=0.5)

    # Train/test split
    split = 2000
    X_train, y_train = X[:split], y[:split]
    X_test,  y_test  = X[split:], y[split:]

    print("Training toy logistic-regression classifier...")
    model = ToyClassifier(n_features=8)
    model.train(X_train, y_train, lr=0.1, epochs=500)

    overall_acc = ((model.predict_proba(X_test) >= 0.5).astype(int) == y_test).mean()
    print(f"Overall test accuracy: {overall_acc:.3f}")

    # Find uncertain examples
    uncertain_idx = find_uncertain_examples(model, X_test, y_test, low=0.40, high=0.60)
    print(f"Uncertain examples (conf 40-60%): {len(uncertain_idx)}")

    if len(uncertain_idx) < 20:
        print("Too few uncertain examples — relaxing threshold to 35-65%...")
        uncertain_idx = find_uncertain_examples(model, X_test, y_test, low=0.35, high=0.65)

    # Run experiments
    print("\nRunning Experiment 1 (baseline)...")
    r1 = experiment_1(model, X_test, y_test, uncertain_idx)

    print("Running Experiment 2 (noise sweep, ~30s)...")
    r2 = experiment_2(model, X_test, y_test, uncertain_idx, n_samples=300)

    print("Running Experiment 3 (transfer test)...")
    r3 = experiment_3(model, X_test, y_test, uncertain_idx,
                       best_sigma=r2["best_sigma"], n_samples=300)

    # Print results
    print_results(r1, r2, r3)

    # Save JSON (convert numpy types to native python)
    def to_native(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.bool_,)): return bool(obj)
        if isinstance(obj, dict): return {k: to_native(v) for k, v in obj.items()}
        if isinstance(obj, list): return [to_native(v) for v in obj]
        return obj

    out = to_native({"experiment_1": r1, "experiment_2": r2, "experiment_3": r3})
    with open("sr_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Results saved to sr_results.json\n")

    # Optional PyTorch run
    if TORCH_AVAILABLE:
        ans = input("Run MNIST experiment? (requires ~200MB download) [y/N]: ")
        if ans.strip().lower() == "y":
            run_mnist_experiment()

if __name__ == "__main__":
    main()