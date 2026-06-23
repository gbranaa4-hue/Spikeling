# ai-apps

These are full conversational/tutoring AI applications branded "Spikeling"
and built on top of Ollama (local LLM) + retrieval-augmented generation
(RAG). They are NOT the core spiking-neural-network DSL — they're separate
products that reuse the name and some neuromorphic framing.

## Apps
- `spikeling_gui.py` — PyQt5 desktop chat app. Ollama backend + RAG knowledge retrieval from `spikeling_knowledge.db`.
- `SPIKEMESH.py` (+ `SPIKEMESH.txt`, likely a design/notes doc) — "College in a Box": educational AI that loads textbooks, adapts to a student, and syncs across a mesh network.
- `Spikeling_ai.py` — the larger (1500+ line) "Spikeling Ultimate" knowledge engine: 6 subjects, 100+ concepts, STDP-flavored learning, own UI.
- `ultimateAI.py` — an earlier/smaller (4KB) version of the same "Spikeling Ultimate" concept; `Spikeling_ai.py` supersedes it (confirmed via diff — not identical, `Spikeling_ai.py` is the expanded rewrite).
- `rag_test.py` — test harness for the RAG question-answering pipeline.
- `knowledge.py` — Ollama embedding interface + document chunking/ingestion CLI, used to populate `spikeling_knowledge.db`.
- `comprehensive_knowledge_pack.py` — hardcoded reference knowledge (math/physics/chemistry/biology/history) used as seed content.

## Data
- `spikeling_knowledge.db` (2.7 MB SQLite) — RAG embeddings/chunked documents for semantic search.
- `spikeling_memory.db` (248 KB SQLite) — training/spike history.

These two `.db` files are generated data, not source — exclude from git or
use Git LFS if you want them versioned.

## Status
Active as of 6/18–6/19. `ultimateAI.py` is superseded by `Spikeling_ai.py`
— keep for reference only.
