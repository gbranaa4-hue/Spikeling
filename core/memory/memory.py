"""
spikeling/memory/memory.py
==========================
Persistent memory for Spikeling networks.

Saves and loads:
  - Synapse weights (the learned associations)
  - Neuron fire counts (which neurons are most active)
  - Word→neuron mappings (so we can query by word)
  - Training history (what was taught and when)

Format: JSON (human-readable, inspectable)
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────

@dataclass
class TrainingEvent:
    timestamp:  float
    input_word: str
    assoc_word: str  # empty string if unsupervised
    spikes:     int


@dataclass
class MemorySnapshot:
    version:          str                       = "1.0"
    created_at:       float                     = field(default_factory=time.time)
    updated_at:       float                     = field(default_factory=time.time)
    synapse_weights:  dict[str, float]          = field(default_factory=dict)
    neuron_fire_counts: dict[str, int]          = field(default_factory=dict)
    word_activations: dict[str, list[str]]      = field(default_factory=dict)
    training_history: list[dict]                = field(default_factory=list)
    total_spikes:     int                       = 0
    total_words_seen: int                       = 0


# ─────────────────────────────────────────────
#  Memory Manager
# ─────────────────────────────────────────────

class MemoryManager:
    """
    Handles saving and loading network state to disk.

    Synapse keys are stored as "src_name->dst_name" strings
    so the JSON is human-readable and inspectable.
    """

    def __init__(self, filepath: str = "spikeling_memory.json"):
        self.filepath = filepath
        self.snapshot = MemorySnapshot()

    # ── Save ────────────────────────────────────

    def save(self, runtime, word_activations: Optional[dict] = None):
        """
        Snapshot the current runtime state to disk.
        Call this after every training session.
        """
        self.snapshot.updated_at = time.time()
        self.snapshot.total_spikes = sum(
            n.fire_count for n in runtime.neurons.values()
        )

        # Synapse weights
        for syn in runtime.synapses:
            key = f"{syn.src}->{syn.dst}"
            self.snapshot.synapse_weights[key] = round(syn.weight, 6)

        # Neuron fire counts
        for name, n in runtime.neurons.items():
            self.snapshot.neuron_fire_counts[name] = n.fire_count

        # Word→neuron activation map
        if word_activations:
            self.snapshot.word_activations.update(word_activations)

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self.snapshot), f, indent=2)

        print(f"[memory] saved → {self.filepath}  "
              f"({len(self.snapshot.synapse_weights)} synapses, "
              f"{self.snapshot.total_spikes} total spikes)")

    # ── Load ────────────────────────────────────

    def load(self, runtime) -> bool:
        """
        Restore weights from disk into a live runtime.
        Returns True if memory file existed and was loaded.
        """
        if not os.path.exists(self.filepath):
            print(f"[memory] no memory file found at {self.filepath} — starting fresh")
            return False

        with open(self.filepath, encoding="utf-8") as f:
            data = json.load(f)

        self.snapshot = MemorySnapshot(**{
            k: v for k, v in data.items()
            if k in MemorySnapshot.__dataclass_fields__
        })

        # Restore synapse weights
        restored = 0
        for syn in runtime.synapses:
            key = f"{syn.src}->{syn.dst}"
            if key in self.snapshot.synapse_weights:
                syn.weight = self.snapshot.synapse_weights[key]
                restored += 1

        # Restore fire counts
        for name, count in self.snapshot.neuron_fire_counts.items():
            if name in runtime.neurons:
                runtime.neurons[name].fire_count = count

        print(f"[memory] loaded ← {self.filepath}  "
              f"({restored} synapses restored, "
              f"{self.snapshot.total_spikes} historical spikes)")
        return True

    # ── Training log ────────────────────────────

    def log_training(self, input_word: str, assoc_word: str = "", spikes: int = 0):
        event = TrainingEvent(
            timestamp  = time.time(),
            input_word = input_word,
            assoc_word = assoc_word,
            spikes     = spikes,
        )
        self.snapshot.training_history.append(asdict(event))
        self.snapshot.total_words_seen += 1

    # ── Inspect ─────────────────────────────────

    def strongest_associations(self, top_n: int = 10) -> list[tuple[str, float]]:
        """Return the top N strongest synapse weights."""
        weights = sorted(
            self.snapshot.synapse_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return weights[:top_n]

    def words_seen(self) -> list[str]:
        """Return all words the network has been trained on."""
        return list(self.snapshot.word_activations.keys())

    def report(self) -> str:
        lines = [
            "─── Memory Report ───",
            f"  File:          {self.filepath}",
            f"  Total spikes:  {self.snapshot.total_spikes}",
            f"  Words seen:    {self.snapshot.total_words_seen}",
            f"  Synapses:      {len(self.snapshot.synapse_weights)}",
            f"  Training events: {len(self.snapshot.training_history)}",
            "",
            "  Top associations:",
        ]
        for key, weight in self.strongest_associations(10):
            lines.append(f"    {key:30s}  w={weight:.4f}")
        return "\n".join(lines)
