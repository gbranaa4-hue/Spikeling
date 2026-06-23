"""
spikeling/trainer/trainer.py
============================
Trains a Spikeling network using real spike-timing dependent plasticity.

Three training modes:
  1. Interactive  — type words at a prompt, teach associations live
  2. File         — point at a text file, learns co-occurrence patterns
  3. Signal       — feed a real-time float stream (mic, sensor)

How training actually works
---------------------------
For each word:
  1. Encode it as a spike train (list of neuron_idx, time_ms pairs)
  2. Inject those spikes into the network's input neurons in time order
  3. Let spikes propagate through synapses to hidden/output neurons
  4. STDP fires: synapses between co-active neurons strengthen
  5. Repeat. Repeated co-occurrence = stronger weights = memory.

For supervised pairs (teach "quantum" → "energy"):
  1. Fire "quantum" spike train
  2. Fire "energy" spike train 10ms later
  3. STDP sees pre (quantum neurons) firing before post (energy neurons)
  4. LTP: those synapses strengthen
  5. At query time: fire "quantum", energy neurons activate most strongly
"""

import time
import sys
import os
import math
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from encoder.encoder import WordEncoder, FileEncoder, SignalEncoder
from memory.memory   import MemoryManager


# ─────────────────────────────────────────────
#  Spike Network Adapter
#  (thin wrapper so trainer doesn't depend on
#   runtime internals)
# ─────────────────────────────────────────────

class NetworkAdapter:
    """
    Bridges the trainer to the runtime's neuron/synapse model.
    Maps encoder neuron indices → actual named neurons in the network.
    """

    def __init__(self, runtime, num_input_neurons: int = 64):
        self.runtime           = runtime
        self.num_input_neurons = num_input_neurons
        self.neuron_names      = list(runtime.neurons.keys())
        self.word_activations: dict[str, list[str]] = {}
        self.last_fired_neurons: list[str] = []

    def inject_spikes(self, spike_train: list[tuple[int, float]],
                      base_time_ms: float, drive: float = 60.0) -> int:
        """
        Inject a spike train into the network.
        Maps encoder indices → actual neuron names via modulo.
        Returns number of neurons that fired. Also records which
        neurons fired (including downstream cascades) in
        `last_fired_neurons`, so callers can capture an activation
        pattern that reflects the *current* synapse weights.
        """
        fired = 0
        self.last_fired_neurons = []
        for neuron_idx, delay_ms in spike_train:
            # Map encoder index to actual neuron name
            name = self.neuron_names[neuron_idx % len(self.neuron_names)]
            t    = base_time_ms + delay_ms
            # stimulate() returns the dispatched *action command*, which
            # is None for any neuron without an action — not a reliable
            # "did it spike" signal. Compare fire_count instead.
            count_before = self.runtime.neurons[name].fire_count
            self.runtime.stimulate(name, t, drive=drive)
            if self.runtime.neurons[name].fire_count > count_before:
                fired += 1
                self.last_fired_neurons.append(name)
        # Downstream neurons pushed over threshold purely by propagation
        # (no direct stimulate() call) still count as "activated" —
        # capture them too so the activation pattern reflects synapse weight.
        for n_name in self.active_neurons(threshold_fraction=0.9):
            if n_name not in self.last_fired_neurons:
                self.last_fired_neurons.append(n_name)
        return fired

    def capture_activation(self, word: str):
        """
        Snapshot the neurons activated by the most recent inject_spikes()
        call under `word`. This is what _query() compares against, so
        the comparison reflects live synapse weights (STDP), not just
        the raw character-hash of the word.
        """
        if self.last_fired_neurons:
            self.word_activations[word] = list(self.last_fired_neurons)

    def active_neurons(self, threshold_fraction: float = 0.5) -> list[str]:
        """Return neurons with membrane potential above threshold fraction."""
        active = []
        for name, n in self.runtime.neurons.items():
            if n.membrane_potential >= n.threshold * threshold_fraction:
                active.append(name)
        return active

    def strongest_output(self) -> Optional[str]:
        """Return the neuron with the highest current membrane potential."""
        if not self.runtime.neurons:
            return None
        return max(self.runtime.neurons.items(),
                   key=lambda x: x[1].membrane_potential)[0]

    def decay_all(self):
        """Apply leak decay to all neurons between training steps."""
        self.runtime.tick(time.time() * 1000.0)


# ─────────────────────────────────────────────
#  Core Trainer
# ─────────────────────────────────────────────

class SpikelingTrainer:
    """
    Trains a Spikeling network on real input.

    Parameters
    ----------
    runtime      : SpikelingRuntime instance (already loaded from .spk)
    memory_path  : where to persist learned weights
    num_neurons  : encoder neuron count (should match network size)
    """

    def __init__(self, runtime, memory_path: str = "spikeling_memory.json",
                 num_neurons: int = 64):
        self.runtime  = runtime
        self.adapter  = NetworkAdapter(runtime, num_input_neurons=num_neurons)
        self.encoder  = WordEncoder(num_neurons=num_neurons)
        self.memory   = MemoryManager(memory_path)
        self.associations: dict[str, list[str]] = {}  # word → [associated words]

        # Load any previously learned weights
        self.memory.load(runtime)

    # ── 1. Interactive training ──────────────────

    def run_interactive(self):
        """
        Live training prompt.

        Commands:
          teach <word> <association>   — supervised pair training
          learn <word>                 — unsupervised single word
          query <word>                 — see what network associates
          file <path>                  — train on a text file
          save                         — save weights to disk
          weights                      — show current synapse weights
          history                      — show training history
          quit                         — save and exit
        """
        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║   🧠  SPIKELING TRAINER                                 ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print("║  teach <word> <word>   — teach an association           ║")
        print("║  learn <word>          — unsupervised learning          ║")
        print("║  query <word>          — recall what network knows      ║")
        print("║  file  <path>          — train on a text file           ║")
        print("║  save                  — save weights to disk           ║")
        print("║  weights               — show synapse weights           ║")
        print("║  quit                  — save and exit                  ║")
        print("╚══════════════════════════════════════════════════════════╝\n")

        while True:
            try:
                raw = input("spikeling> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[trainer] saving and exiting...")
                self._save()
                break

            if not raw:
                continue

            parts = raw.split()
            cmd   = parts[0].lower()

            if cmd == "quit" or cmd == "exit":
                self._save()
                break

            elif cmd == "teach" and len(parts) >= 3:
                word  = parts[1]
                assoc = parts[2]
                self._teach_pair(word, assoc, verbose=True)

            elif cmd == "learn" and len(parts) >= 2:
                word = parts[1]
                self._learn_word(word, verbose=True)

            elif cmd == "query" and len(parts) >= 2:
                word = parts[1]
                self._query(word)

            elif cmd == "file" and len(parts) >= 2:
                path = parts[1]
                self.train_on_file(path)

            elif cmd == "save":
                self._save()

            elif cmd == "weights":
                print(self.memory.report())

            elif cmd == "history":
                self._show_history()

            else:
                print(f"  [?] unknown command: '{raw}'")
                print("  try: teach quantum energy | query gravity | file physics.txt")

    # ── 2. File training ────────────────────────

    def train_on_file(self, filepath: str, epochs: int = 1,
                      max_words: Optional[int] = None):
        """
        Train on all words in a text file.
        Uses sliding window co-occurrence: nearby words learn to associate.
        """
        if not os.path.exists(filepath):
            print(f"  [error] file not found: {filepath}")
            return

        file_encoder = FileEncoder(num_neurons=self.encoder.num_neurons)
        word_counts  = file_encoder.word_count(filepath)
        total        = min(sum(word_counts.values()), max_words or 999999)

        print(f"\n[trainer] training on '{filepath}'")
        print(f"  {len(word_counts)} unique words, ~{total} total")
        print(f"  {epochs} epoch(s)\n")

        for epoch in range(epochs):
            count   = 0
            trained = 0

            for focus, context, focus_train, context_trains in \
                    file_encoder.encode_file(filepath):

                if max_words and count >= max_words:
                    break

                now_ms = time.time() * 1000.0

                # Fire focus word
                fired = self.adapter.inject_spikes(focus_train, now_ms)
                self.adapter.capture_activation(focus)

                # Fire each context word shortly after (STDP window)
                for ctx_word, ctx_train in context_trains:
                    ctx_fired = self.adapter.inject_spikes(
                        ctx_train, now_ms + 10.0
                    )
                    self.adapter.capture_activation(ctx_word)
                    if ctx_fired > 0:
                        if focus not in self.associations:
                            self.associations[focus] = []
                        if ctx_word not in self.associations[focus]:
                            self.associations[focus].append(ctx_word)

                self.adapter.decay_all()
                self.memory.log_training(focus, "", fired)

                count   += 1
                trained += 1

                if trained % 100 == 0:
                    pct = (trained / total) * 100
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    print(f"  [{bar}] {pct:.0f}%  {trained}/{total} words", end="\r")

            print(f"\n  epoch {epoch + 1}/{epochs} complete — {trained} words trained")

        self._save()
        print(f"\n[trainer] file training complete!")
        print(f"  learned associations for {len(self.associations)} words")

    # ── 3. Signal training ───────────────────────

    def train_on_signal(self, signal_generator, label: str = "",
                        duration_s: float = 5.0):
        """
        Train on a real-time signal stream.
        signal_generator: yields lists of float samples
        label: optional word to associate with this signal pattern
        """
        print(f"\n[trainer] recording signal for {duration_s}s"
              + (f" (label: '{label}')" if label else ""))

        sig_encoder = SignalEncoder(num_neurons=self.encoder.num_neurons)
        start       = time.time()
        total_fired = 0

        for chunk in signal_generator:
            if time.time() - start > duration_s:
                break

            spike_train = sig_encoder.encode(chunk)
            now_ms      = time.time() * 1000.0
            fired       = self.adapter.inject_spikes(spike_train, now_ms)
            total_fired += fired
            self.adapter.decay_all()

        # If a label was given, associate it with what just fired
        if label:
            label_train = self.encoder.encode(label)
            now_ms      = time.time() * 1000.0
            self.adapter.inject_spikes(label_train, now_ms + 5.0)
            self.memory.log_training("signal", label, total_fired)

        print(f"  {total_fired} spikes fired during recording")
        self._save()

    # ── Internal methods ─────────────────────────

    def _teach_pair(self, word: str, assoc: str, verbose: bool = False,
                    repetitions: int = 5):
        """
        Supervised association: fire word then assoc, STDP strengthens path.
        More repetitions = stronger association.
        """
        w_train = self.encoder.encode(word)
        a_train = self.encoder.encode(assoc)

        total_fired = 0
        for rep in range(repetitions):
            now_ms = time.time() * 1000.0

            # Fire stimulus word
            self.adapter.inject_spikes(w_train, now_ms, drive=80.0)
            self.adapter.capture_activation(word)
            # Fire association word 10ms later (STDP LTP window)
            fired = self.adapter.inject_spikes(a_train, now_ms + 10.0, drive=80.0)
            self.adapter.capture_activation(assoc)
            total_fired += fired
            self.adapter.decay_all()
            time.sleep(0.002)  # small gap between reps

        # Record association
        if word not in self.associations:
            self.associations[word] = []
        if assoc not in self.associations[word]:
            self.associations[word].append(assoc)

        self.memory.log_training(word, assoc, total_fired)

        if verbose:
            print(f"  ✓ taught '{word}' → '{assoc}'  "
                  f"({repetitions} reps, {total_fired} spikes)")
            # Show weight change
            self._show_weights_for(word, assoc)

    def _learn_word(self, word: str, verbose: bool = False):
        """Unsupervised: just fire the word's spike train."""
        train  = self.encoder.encode(word)
        now_ms = time.time() * 1000.0
        fired  = self.adapter.inject_spikes(train, now_ms)
        self.adapter.capture_activation(word)
        self.adapter.decay_all()
        self.memory.log_training(word, "", fired)

        if verbose:
            print(f"  ✓ learned '{word}'  ({fired} neurons activated)")

    def _query(self, word: str, top_n: int = 5):
        """
        Query the network: fire the word and see which neurons the
        *current* synapse weights actually push it to — STDP-trained
        recall, not just a lookup of taught pairs.
        """
        print(f"\n  querying: '{word}'")

        # Fire the query word and capture which neurons it reaches
        # (input firings + anything pushed over threshold downstream,
        # via inject_spikes' active_neurons() pass — this is what
        # changes as synapse weights shift under STDP).
        train  = self.encoder.encode(word)
        now_ms = time.time() * 1000.0
        self.adapter.inject_spikes(train, now_ms, drive=100.0)
        query_fired = set(self.adapter.last_fired_neurons)
        self.adapter.capture_activation(word)

        # Check direct taught associations first
        if word in self.associations:
            print(f"  taught associations:")
            for a in self.associations[word][:top_n]:
                print(f"    → {a}")

        # Network-weighted recall: compare the neurons THIS query
        # activated against the neurons every previously seen word
        # activated. Overlap here is driven by live synapse weights,
        # so it shifts as training progresses — unlike raw spike-space
        # similarity, which never changes.
        scored = []
        for known_word, fired_set in self.adapter.word_activations.items():
            if known_word == word:
                continue
            fired_set = set(fired_set)
            if not query_fired or not fired_set:
                continue
            overlap = len(query_fired & fired_set) / len(query_fired | fired_set)
            if overlap > 0:
                scored.append((known_word, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)

        if scored:
            print(f"  network-weighted recall (live synapse weights):")
            for w, s in scored[:top_n]:
                bar = "█" * max(1, int(s * 20))
                print(f"    {w:15s}  {bar}  {s:.3f}")

        # Raw spike-space similarity (encoder-only, ignores learning —
        # kept as a baseline to compare against the line above).
        known = self.memory.words_seen()
        if known:
            sims = []
            for known_word in known:
                sim = self.encoder.similarity(word, known_word)
                if sim > 0.1 and known_word != word:
                    sims.append((known_word, sim))
            sims.sort(key=lambda x: x[1], reverse=True)

            if sims:
                print(f"  raw spike-space similarity (untrained baseline):")
                for w, s in sims[:top_n]:
                    bar = "█" * int(s * 20)
                    print(f"    {w:15s}  {bar}  {s:.3f}")

        if query_fired:
            print(f"  neurons activated: {', '.join(list(query_fired)[:8])}")

        self.adapter.decay_all()
        print()

    def _save(self):
        self.memory.save(self.runtime, self.adapter.word_activations)

    def _show_weights_for(self, word_a: str, word_b: str):
        """Print synapse weights relevant to two words."""
        for syn in self.runtime.synapses:
            print(f"    synapse {syn.src} → {syn.dst}  w={syn.weight:.4f}")

    def _show_history(self, last_n: int = 20):
        history = self.memory.snapshot.training_history[-last_n:]
        if not history:
            print("  no training history yet")
            return
        print(f"\n  Last {len(history)} training events:")
        for evt in history:
            t   = time.strftime("%H:%M:%S", time.localtime(evt["timestamp"]))
            inp = evt["input_word"]
            asc = evt.get("assoc_word", "")
            spk = evt.get("spikes", 0)
            arrow = f" → {asc}" if asc else ""
            print(f"    [{t}]  {inp}{arrow}  ({spk} spikes)")
        print()
