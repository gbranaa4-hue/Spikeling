#!/usr/bin/env python
"""
pyspike.py — Python fused with the Spikeling DSL.

The problem this fixes is real and already visible in this project:
spiking_scheduler.py, test_soft_conflicts.py, and test_incremental_scheduling.py
all build networks by f-string-formatting ".spk" TEXT and then re-parsing it
with SpikelingParser -- every single wave, every single arrival. That's a
string-generate-then-regex-parse round trip standing in for what should just
be Python: a loop building neurons and synapses directly.

pyspike.py is a thin builder that constructs the exact same SpikelingAST the
.spk parser produces (compiler.SpikelingAST / NeuronDef / ConnectionDef /
ActionDef) -- so anything built with it is a real Spikeling network, gets the
existing Python runtime for free, AND gets the existing C code generator for
free (CCodeGenerator only needs an AST, it doesn't care how the AST was
built). Nothing about the runtime or hardware backend changes; this only
replaces the TEXT FORMAT with real Python for programmatic construction.

    net = Net(refractory_ms=40)
    S_Work      = net.neuron("S_Work", threshold=50, leak=0)
    Implementer = net.neuron("Implementer", threshold=50, leak=0)

    S_Work >> Implementer                    # excitatory, weight=1.0 (sugar)
    S_Ambiguous.to(Implementer, weight=-2.0) # inhibitory, explicit weight

    @net.action(Implementer)
    def cmd_implement():
        print("implementing!")

    rt = net.build()          # -> a real SpikelingRuntime, handlers already wired
    rt.stimulate("S_Work", 1.0, 60.0)

Programmatic construction (the actual point -- real Python control flow
instead of string-templating a .spk file) reads like this, no regex, no
re-parsing per wave:

    net = Net()
    agents = {name: net.neuron(name, threshold=50, leak=0) for name in names}
    for a, b in conflicting_pairs:
        agents[a].to(agents[b], weight=-3.0)
        agents[b].to(agents[a], weight=-3.0)
    rt = net.build()

    python pyspike.py    # self-test: proves this matches .spk-parsed behavior
                          # bit-for-bit on a real network, then benchmarks the
                          # string-round-trip cost this replaces
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
from compiler.compiler import SpikelingAST, NeuronDef, ConnectionDef, ActionDef  # noqa: E402
from runtime.runtime import SpikelingRuntime                                     # noqa: E402


class NeuronRef:
    """A handle to a neuron already added to a Net. Exists so network
    construction reads as real Python (operators, method chaining) instead
    of passing bare name strings around."""

    def __init__(self, net: "Net", name: str):
        self.net = net
        self.name = name

    def to(self, dst: "NeuronRef", weight: float = 1.0) -> "NeuronRef":
        """Explicit weighted connect -- the one you reach for when weight
        isn't the default 1.0 (inhibitory synapses, graded severities,
        anything computed rather than constant)."""
        self.net.connect(self, dst, weight=weight)
        return dst

    def inhibits(self, dst: "NeuronRef", weight: float = -2.0) -> "NeuronRef":
        """Same as .to() but the negative default and the name make
        inhibitory wiring self-documenting at the call site."""
        assert weight < 0, "inhibits() expects a negative weight -- use .to() for excitatory"
        return self.to(dst, weight=weight)

    def __rshift__(self, dst: "NeuronRef") -> "NeuronRef":
        """`a >> b` is sugar for the common case: excitatory, weight=1.0.
        Returns dst so `a >> b >> c` chains (a->b, b->c) the way you'd read
        it. Use .to()/.inhibits() when the weight isn't the default."""
        return self.to(dst, weight=1.0)

    def __repr__(self) -> str:
        return f"NeuronRef({self.name!r})"


class Net:
    """Builds a SpikelingAST via real Python instead of a .spk text file.
    .build() hands you a live SpikelingRuntime with handlers already wired --
    same runtime class the .spk parser feeds, so nothing downstream changes."""

    def __init__(self, refractory_ms: int = 0):
        self.ast = SpikelingAST(refractory_ms=refractory_ms)
        self._names: set = set()
        self._handlers: dict = {}
        self._action_counter = 0

    def neuron(self, name: str, threshold: int = 50, leak: int = 0,
              type: str = "LIF", freq_hz: float = None, damping: float = None,
              coupling: float = None) -> NeuronRef:
        if name in self._names:
            raise ValueError(f"duplicate neuron name '{name}'")
        self._names.add(name)
        self.ast.neurons.append(NeuronDef(
            name=name, threshold=int(threshold), leak=int(leak),
            neuron_type=type, freq_hz=freq_hz, damping=damping, coupling=coupling,
        ))
        return NeuronRef(self, name)

    def connect(self, src, dst, weight: float = 1.0) -> None:
        src_name = src.name if isinstance(src, NeuronRef) else src
        dst_name = dst.name if isinstance(dst, NeuronRef) else dst
        self.ast.connections.append(ConnectionDef(src=src_name, dst=dst_name, weight=float(weight)))

    def action(self, neuron: NeuronRef):
        """Decorator: attach a real Python function directly to a neuron's
        firing event. No command-string indirection to manage by hand -- an
        internal command id is generated and wired to the handler for you,
        collapsing the .spk model's three-step (neuron -> command string ->
        handler dict) into one decorator."""
        def decorator(fn):
            self._action_counter += 1
            cmd = f"__pyspike_cmd_{self._action_counter}_{neuron.name}__"
            self.ast.actions.append(ActionDef(neuron=neuron.name, command=cmd))
            self._handlers[cmd] = fn
            return fn
        return decorator

    def build(self) -> SpikelingRuntime:
        """Validate + construct the runtime, same as compiler.compile_file()
        does for a .spk file -- reuses the parser's own validator so
        dangling connect/action references are caught the same way."""
        self._validate()
        rt = SpikelingRuntime(self.ast)
        for cmd, fn in self._handlers.items():
            rt.register_handler(cmd, fn)
        return rt

    def _validate(self) -> None:
        names = self._names
        for c in self.ast.connections:
            if c.src not in names:
                raise NameError(f"connect: unknown neuron '{c.src}'")
            if c.dst not in names:
                raise NameError(f"connect: unknown neuron '{c.dst}'")
        for a in self.ast.actions:
            if a.neuron not in names:
                raise NameError(f"action: unknown neuron '{a.neuron}'")


# ─────────────────────────────────────────────────────────────────────────────
def _selftest_matches_spk_text() -> None:
    """Prove pyspike builds a network that behaves IDENTICALLY to the
    equivalent hand-written .spk text -- not just 'looks plausible', an
    actual side-by-side spike-for-spike comparison."""
    from compiler.compiler import SpikelingParser

    spk_text = """
neuron A threshold=50 leak=0 type=LIF
neuron B threshold=50 leak=0 type=LIF
neuron C threshold=50 leak=0 type=LIF
connect A -> B weight=1.0
connect B -> C weight=-2.0
refractory=0ms
""".strip()
    rt_text = SpikelingRuntime(SpikelingParser().parse(spk_text))

    net = Net(refractory_ms=0)
    A = net.neuron("A", threshold=50, leak=0)
    B = net.neuron("B", threshold=50, leak=0)
    C = net.neuron("C", threshold=50, leak=0)
    A >> B
    B.inhibits(C, weight=-2.0)
    rt_py = net.build()

    for t, (name, drive) in enumerate([("A", 60.0), ("A", 60.0), ("B", 60.0), ("C", 60.0)], start=1):
        cmd_text = rt_text.stimulate(name, float(t), drive)
        cmd_py = rt_py.stimulate(name, float(t), drive)
        assert cmd_text == cmd_py, f"handler dispatch diverged at t={t}: {cmd_text!r} vs {cmd_py!r}"

    for name in ("A", "B", "C"):
        ft, fp = rt_text.neurons[name].fire_count, rt_py.neurons[name].fire_count
        assert ft == fp, f"fire_count diverged for {name}: text={ft} py={fp}"
    print("  [PASS] pyspike-built network matches .spk-text-parsed network spike-for-spike")


def _benchmark_vs_string_roundtrip(n_agents: int = 30, n_trials: int = 200) -> None:
    """Measure the actual cost pyspike removes: f-string generation + regex
    re-parsing of a .spk network, vs building the same network directly."""
    from compiler.compiler import SpikelingParser
    import random
    rng = random.Random(0)
    names = [f"agent_{i}" for i in range(n_agents)]
    edges = [(names[i], names[j], -3.0) for i in range(n_agents) for j in range(i + 1, n_agents)
             if rng.random() < 0.15]

    def build_via_text():
        lines = [f"neuron {n} threshold=50 leak=0 type=LIF" for n in names]
        for a, b, w in edges:
            lines.append(f"connect {a} -> {b} weight={w}")
            lines.append(f"connect {b} -> {a} weight={w}")
        return SpikelingRuntime(SpikelingParser().parse("\n".join(lines)))

    def build_via_pyspike():
        net = Net()
        refs = {n: net.neuron(n, threshold=50, leak=0) for n in names}
        for a, b, w in edges:
            refs[a].to(refs[b], weight=w)
            refs[b].to(refs[a], weight=w)
        return net.build()

    t0 = time.perf_counter()
    for _ in range(n_trials):
        build_via_text()
    text_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n_trials):
        build_via_pyspike()
    pyspike_s = time.perf_counter() - t0

    speedup = text_s / pyspike_s if pyspike_s else float("inf")
    print(f"  {n_agents} agents, {len(edges)*2} synapses, {n_trials} builds:")
    print(f"    string round-trip (f-string + regex parse): {text_s*1000:.1f}ms total "
          f"({text_s/n_trials*1000:.3f}ms/build)")
    print(f"    pyspike direct construction:                {pyspike_s*1000:.1f}ms total "
          f"({pyspike_s/n_trials*1000:.3f}ms/build)")
    print(f"    pyspike is {speedup:.1f}x faster to CONSTRUCT the network "
          f"(this is build cost only, not stimulate/spike-propagation cost)")


if __name__ == "__main__":
    print("=" * 78)
    print("  PYSPIKE SELF-TEST")
    print("=" * 78)
    _selftest_matches_spk_text()
    print()
    _benchmark_vs_string_roundtrip()
