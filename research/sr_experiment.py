import re
import heapq
import math
import os
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
#  TOKENS & LEXER
# ─────────────────────────────────────────────

TOKEN_TYPES = [
    ("NEURON",      r'\bneuron\b'),
    ("SYNAPSE",     r'\bsynapse\b'),
    ("SIMULATE",    r'\bsimulate\b'),
    ("ARROW",       r'→|->'),
    ("EXCITATORY",  r'\bexcitatory\b'),
    ("INHIBITORY",  r'\binhibitory\b'),
    ("PLASTIC",     r'\bplastic\b'),        # New keyword for learning
    ("FLOAT_MS",    r'\d+\.\d+ms\b'),
    ("INT_MS",      r'\d+ms\b'),
    ("FLOAT",       r'\d+\.\d+'),
    ("INT",         r'\d+'),
    ("MS",          r'\bms\b'),
    ("KEY",         r'\b(threshold|leak|refractory|weight|delay|at)\b'),
    ("EQ",          r'='),
    ("IDENT",       r'\b[A-Za-z_][A-Za-z0-9_]*\b'),
    ("SKIP",        r'[ \t]+'),
    ("NEWLINE",     r'\n'),
    ("COMMENT",     r'#[^\n]*'),
    ("MISMATCH",    r'[^\s]'),
]

@dataclass
class Token:
    type: str
    value: str
    line: int

def lex(source: str) -> list[Token]:
    pattern = "|".join(f"(?P<{name}>{regex})" for name, regex in TOKEN_TYPES)
    tokens = []
    line = 1
    for m in re.finditer(pattern, source):
        kind = m.lastgroup
        value = m.group()
        if kind in ("SKIP", "COMMENT"):
            continue
        elif kind == "NEWLINE":
            line += 1
            continue
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character {value!r} on line {line}")
        elif kind == "FLOAT_MS":
            tokens.append(Token("FLOAT", value[:-2], line))
            tokens.append(Token("MS", "ms", line))
        elif kind == "INT_MS":
            tokens.append(Token("INT", value[:-2], line))
            tokens.append(Token("MS", "ms", line))
        else:
            tokens.append(Token(kind, value, line))
    return tokens

# ─────────────────────────────────────────────
#  AST NODES
# ─────────────────────────────────────────────

@dataclass
class NeuronDef:
    name: str
    threshold: float = 0.5
    leak: float = 0.1
    refractory: float = 2.0   # ms

@dataclass
class SynapseDef:
    src: str
    dst: str
    weight: float = 1.0
    delay: float = 0.0        # ms
    polarity: str = "excitatory"
    plastic: bool = False     # Learns via STDP
    at: Optional[float] = None  

@dataclass
class SimulateDef:
    duration: float           # ms

# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, type_=None):
        tok = self.tokens[self.pos]
        if type_ and tok.type != type_:
            raise SyntaxError(f"Line {tok.line}: expected {type_}, got {tok.type} ({tok.value!r})")
        self.pos += 1
        return tok

    def parse_float(self):
        tok = self.peek()
        if tok and tok.type in ("FLOAT", "INT"):
            self.pos += 1
            return float(tok.value)
        raise SyntaxError(f"Expected number, got {tok}")

    def parse_ms_value(self):
        val = self.parse_float()
        if self.peek() and self.peek().type == "MS":
            self.pos += 1
        return val

    def parse_kv(self, keys):
        result = {}
        while self.peek() and self.peek().type == "KEY" and self.peek().value in keys:
            key = self.consume("KEY").value
            self.consume("EQ")
            if key in ("threshold", "leak", "weight"):
                result[key] = self.parse_float()
            else:
                result[key] = self.parse_ms_value()
        return result

    def parse_neuron(self):
        self.consume("NEURON")
        name = self.consume("IDENT").value
        kv = self.parse_kv({"threshold", "leak", "refractory"})
        return NeuronDef(name=name, **kv)

    def parse_synapse(self):
        self.consume("SYNAPSE")
        src = self.consume("IDENT").value
        self.consume("ARROW")
        dst = self.consume("IDENT").value
        kv = self.parse_kv({"weight", "delay", "at"})
        
        polarity = "excitatory"
        if self.peek() and self.peek().type in ("EXCITATORY", "INHIBITORY"):
            polarity = self.consume().value
            
        plastic = False
        if self.peek() and self.peek().type == "PLASTIC":
            self.consume("PLASTIC")
            plastic = True
            
        return SynapseDef(src=src, dst=dst, polarity=polarity, plastic=plastic, **kv)

    def parse_simulate(self):
        self.consume("SIMULATE")
        duration = self.parse_ms_value()
        return SimulateDef(duration=duration)

    def parse(self):
        ast = []
        while self.peek():
            tok = self.peek()
            if tok.type == "NEURON":
                ast.append(self.parse_neuron())
            elif tok.type == "SYNAPSE":
                ast.append(self.parse_synapse())
            elif tok.type == "SIMULATE":
                ast.append(self.parse_simulate())
            else:
                raise SyntaxError(f"Line {tok.line}: unexpected token {tok.value!r}")
        return ast

# ─────────────────────────────────────────────
#  SIMULATOR (WITH STDP LEARNING)
# ─────────────────────────────────────────────

@dataclass
class Neuron:
    name: str
    threshold: float
    leak: float
    refractory: float
    potential: float = 0.0
    last_fired: float = -999.0

@dataclass(order=True)
class SpikeEvent:
    time: float
    src: str = field(compare=False)
    dst: str = field(compare=False)
    weight: float = field(compare=False)

class Simulator:
    def __init__(self, ast):
        self.neurons: dict[str, Neuron] = {}
        self.synapses: list[SynapseDef] = []
        self.duration = 0.0
        self.spike_log: list[tuple[float, str]] = []
        self._build(ast)

    def _build(self, ast):
        self.neurons["world"]  = Neuron("world",  threshold=0.0, leak=0.0, refractory=0.0)
        self.neurons["output"] = Neuron("output", threshold=0.0, leak=0.0, refractory=0.0)

        for node in ast:
            if isinstance(node, NeuronDef):
                self.neurons[node.name] = Neuron(
                    name=node.name, threshold=node.threshold, leak=node.leak, refractory=node.refractory
                )
            elif isinstance(node, SynapseDef):
                self.synapses.append(node)
            elif isinstance(node, SimulateDef):
                self.duration = node.duration

    def run(self):
        queue: list[SpikeEvent] = []
        
        # STDP Rules Config
        A_plus, A_minus = 0.15, 0.12
        tau_plus, tau_minus = 15.0, 15.0

        for syn in self.synapses:
            if syn.src == "world" and syn.at is not None:
                heapq.heappush(queue, SpikeEvent(syn.at + syn.delay, "world", syn.dst, syn.weight))

        while queue:
            event = heapq.heappop(queue)
            t, src, dst, weight = event.time, event.src, event.dst, event.weight

            if t > self.duration: break
            if dst not in self.neurons: continue

            neuron = self.neurons[dst]

            if dst == "output":
                self.spike_log.append((t, "output"))
                continue

            dt = t - max(neuron.last_fired, 0)
            neuron.potential *= (1.0 - neuron.leak) ** dt

            if t - neuron.last_fired < neuron.refractory:
                continue

            neuron.potential += weight

            # Check if this input pushes the neuron to fire
            if neuron.potential >= neuron.threshold:
                
                # STDP: Pre-before-Post (Potentiation)
                for syn in self.synapses:
                    if syn.dst == dst and syn.plastic and syn.src != "world":
                        src_neuron = self.neurons[syn.src]
                        delta_t = t - src_neuron.last_fired
                        if delta_t > 0:
                            syn.weight = min(2.5, syn.weight + (A_plus * math.exp(-delta_t / tau_plus)))

                # Commit Fire
                neuron.potential = 0.0
                neuron.last_fired = t
                self.spike_log.append((t, dst))

                # Propagate Spikes
                for syn in self.synapses:
                    if syn.src == dst:
                        w = syn.weight if syn.polarity == "excitatory" else -syn.weight
                        heapq.heappush(queue, SpikeEvent(t + syn.delay, dst, syn.dst, w))
                        
                        # STDP: Post-before-Pre (Depression)
                        if syn.plastic and syn.dst in self.neurons:
                            dst_neuron = self.neurons[syn.dst]
                            delta_t = dst_neuron.last_fired - t
                            if delta_t > 0:
                                syn.weight = max(0.0, syn.weight - (A_minus * math.exp(-delta_t / tau_minus)))

        return self.spike_log

# ─────────────────────────────────────────────
#  COGNITIVE BRIDGE (LLM API INTERFACE)
# ─────────────────────────────────────────────

def run_cognitive_cycle(spikeling_code: str, user_text: str):
    """Executes the SNN script and pipes state findings directly to an LLM."""
    # 1. Run network simulation
    tokens = lex(spikeling_code)
    ast = Parser(tokens).parse()
    sim = Simulator(ast)
    spike_log = sim.run()
    
    # 2. Extract biometric frequencies
    counts = {}
    for _, node in spike_log:
        counts[node] = counts.get(node, 0) + 1
        
    snn_report = "\n".join([f"- Neuron '{k}' fired {v} times." for k, v in counts.items()])
    if not snn_report: snn_report = "The lower neural substrate remains completely silent."

    # 3. Construct prompt
    prompt = f"""
    You are the conscious mind of a hybrid neuro-symbolic AI agent. 
    Your biological, lower-level Spiking Neural Network just ran. 

    --- INTERNAL BRAIN STATE BIOMETRICS ---
    {snn_report}
    --- END BIOMETRICS ---

    The outside environment presents you with this input: "{user_text}"

    Acknowledge your sub-conscious firing patterns subtly through your tone, 
    and provide your response to the user.
    """
    
    # Check if API library is present, fallback gracefully if not
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"[Simulated Output - API key missing or error: {e}]\nPrompt payload would have read:\n{prompt}"

# ─────────────────────────────────────────────
#  RUNTIME TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Test script featuring our brand new 'plastic' keyword
    brain_script = """
    neuron Sensory threshold=0.3 leak=0.05 refractory=1ms
    neuron Thought threshold=0.5 leak=0.08 refractory=2ms
    
    synapse world -> Sensory weight=1.0 at=2ms
    synapse world -> Sensory weight=1.0 at=4ms
    
    # This synapse will learn dynamically via our STDP code engine!
    synapse Sensory -> Thought weight=0.2 delay=1ms excitatory plastic
    
    simulate 30ms
    """
    
    print("Awakening network core and passing data down the wire...")
    reply = run_cognitive_cycle(brain_script, "Are you functional?")
    print(f"\nFinal Brain Response:\n{reply}")