"""
spikeling/encoder/encoder.py
============================
Converts real-world input into spike trains.

Three encoders:
  WordEncoder   — text/words → spike timing patterns
  FileEncoder   — reads a text file, yields spike trains word by word
  SignalEncoder — float signal (audio, sensor) → rate-coded spikes

How spike encoding works
------------------------
A "spike train" is a list of (neuron_index, time_ms) pairs.
Each word gets a deterministic but unique pattern across N input neurons,
based on its characters. Same word always → same pattern (no randomness).
The *timing* between spikes encodes meaning — this is what STDP learns from.
"""

import math
import re
from typing import Generator


# ─────────────────────────────────────────────
#  Word Encoder
# ─────────────────────────────────────────────

class WordEncoder:
    """
    Encodes a word as a spike train across `num_neurons` input neurons.

    Encoding strategy: Temporal coding
      - Each neuron fires at most once per word
      - The firing TIME of neuron i encodes how strongly that neuron
        responds to this word (earlier = stronger response)
      - Based on a hash of the word's characters, so it's deterministic

    Returns: list of (neuron_idx, delay_ms) sorted by delay
    """

    def __init__(self, num_neurons: int = 64, window_ms: float = 50.0):
        self.num_neurons = num_neurons
        self.window_ms   = window_ms   # total time window for one word

    def encode(self, word: str) -> list[tuple[int, float]]:
        """
        Encode a single word into a spike train.
        Returns [(neuron_idx, time_ms), ...] sorted by time.
        """
        word = word.lower().strip()
        if not word:
            return []

        spikes = []
        # Each character contributes to activating certain neurons
        for i, ch in enumerate(word):
            base = ord(ch) * 31 + i * 7
            # Each character activates ~4 neurons
            for k in range(4):
                neuron_idx = (base + k * 17) % self.num_neurons
                # Delay: earlier chars fire earlier, modulated by char value
                delay_ms = (i * self.window_ms / max(len(word), 1)) + \
                           (ord(ch) % 10) * 0.5 + k * 0.3
                delay_ms = min(delay_ms, self.window_ms - 0.1)
                spikes.append((neuron_idx, round(delay_ms, 2)))

        # Deduplicate: if same neuron appears twice, keep earliest firing
        seen: dict[int, float] = {}
        for nidx, t in spikes:
            if nidx not in seen or t < seen[nidx]:
                seen[nidx] = t

        result = sorted(seen.items(), key=lambda x: x[1])
        return [(nidx, t) for nidx, t in result]

    def encode_pair(self, word_a: str, word_b: str
                    ) -> tuple[list, list]:
        """
        Encode a (stimulus, response) word pair.
        Used for supervised association training:
          teach("quantum", "energy") fires 'quantum' then 'energy'
          STDP strengthens the path between them.
        """
        return self.encode(word_a), self.encode(word_b)

    def similarity(self, word_a: str, word_b: str) -> float:
        """
        Cosine similarity between two spike patterns.
        Useful for checking how 'close' two words are in spike-space.
        Returns 0.0 (totally different) to 1.0 (identical).
        """
        a = dict(self.encode(word_a))
        b = dict(self.encode(word_b))
        shared = set(a) & set(b)
        if not shared:
            return 0.0
        dot    = sum(1.0 / (1.0 + abs(a[n] - b[n])) for n in shared)
        norm_a = math.sqrt(len(a))
        norm_b = math.sqrt(len(b))
        return dot / (norm_a * norm_b)


# ─────────────────────────────────────────────
#  File Encoder
# ─────────────────────────────────────────────

class FileEncoder:
    """
    Reads a text file and yields (word, spike_train) pairs.

    Skips stopwords by default (configurable).
    Words that appear close together in the file are treated as
    co-occurring — the trainer will use this to build associations.
    """

    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at",
        "to", "for", "of", "with", "by", "from", "is", "are",
        "was", "were", "be", "been", "have", "has", "had", "do",
        "does", "did", "will", "would", "could", "should", "may",
        "might", "this", "that", "these", "those", "it", "its",
        "as", "if", "then", "than", "so", "not", "no", "nor",
    }

    def __init__(self, num_neurons: int = 64, skip_stopwords: bool = True,
                 min_word_len: int = 3):
        self.encoder        = WordEncoder(num_neurons=num_neurons)
        self.skip_stopwords = skip_stopwords
        self.min_word_len   = min_word_len

    def words_from_file(self, filepath: str) -> Generator[str, None, None]:
        """Yield cleaned words from a text file."""
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            for line in f:
                for raw in re.split(r"[^\w']+", line):
                    word = raw.strip("'").lower()
                    if len(word) < self.min_word_len:
                        continue
                    if self.skip_stopwords and word in self.STOPWORDS:
                        continue
                    yield word

    def encode_file(self, filepath: str,
                    window: int = 3) -> Generator[tuple, None, None]:
        """
        Yield (focus_word, context_words, spike_trains) tuples.

        For each word, yields it paired with the `window` words around it.
        This is how co-occurrence learning works: 'quantum' near 'physics'
        repeatedly → strong association between them.
        """
        words = list(self.words_from_file(filepath))
        for i, word in enumerate(words):
            context = words[max(0, i - window): i] + \
                      words[i + 1: i + window + 1]
            focus_train   = self.encoder.encode(word)
            context_trains = [(w, self.encoder.encode(w)) for w in context]
            yield word, context, focus_train, context_trains

    def word_count(self, filepath: str) -> dict[str, int]:
        """Return word frequency counts from a file."""
        counts: dict[str, int] = {}
        for word in self.words_from_file(filepath):
            counts[word] = counts.get(word, 0) + 1
        return counts


# ─────────────────────────────────────────────
#  Signal Encoder (audio / sensor)
# ─────────────────────────────────────────────

class SignalEncoder:
    """
    Encodes a continuous float signal into spikes using rate coding.

    Higher signal value → neuron fires more frequently.
    Used for: microphone amplitude, sensor readings, any float stream.

    Returns list of (neuron_idx, time_ms) across `num_neurons` channels.
    """

    def __init__(self, num_neurons: int = 16, window_ms: float = 100.0,
                 threshold: float = 0.1):
        self.num_neurons = num_neurons
        self.window_ms   = window_ms
        self.threshold   = threshold   # minimum signal to produce a spike

    def encode(self, signal: list[float]) -> list[tuple[int, float]]:
        """
        Encode a signal buffer into spikes.

        signal: list of float values in [-1.0, 1.0]
        Returns [(neuron_idx, time_ms), ...]
        """
        if not signal:
            return []

        spikes = []
        chunk_size = max(1, len(signal) // self.num_neurons)

        for n in range(self.num_neurons):
            chunk = signal[n * chunk_size: (n + 1) * chunk_size]
            if not chunk:
                continue
            amplitude = sum(abs(x) for x in chunk) / len(chunk)
            if amplitude < self.threshold:
                continue
            # Higher amplitude = earlier spike time (temporal coding)
            delay_ms = self.window_ms * (1.0 - min(amplitude, 1.0))
            spikes.append((n, round(delay_ms, 2)))

        return sorted(spikes, key=lambda x: x[1])

    def encode_stream(self, stream: Generator,
                      chunk_ms: float = 100.0) -> Generator:
        """
        Wrap a real-time signal generator and yield spike trains.
        stream: yields lists of float samples
        """
        for chunk in stream:
            yield self.encode(chunk)
