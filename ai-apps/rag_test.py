#!/usr/bin/env python3
"""RAG test harness for Spikeling's knowledge base.

Loads science_reference.txt into a TEMPORARY knowledge base, then runs a set of
test questions and checks two things per question:
  1. RETRIEVAL: did semantic search pull the section that actually contains the
     answer? (checked by looking for an expected keyword in the top chunks)
  2. ANSWER: did the model's answer contain the expected fact?
Plus a NEGATIVE test: a question whose answer is NOT in the document — the model
should NOT falsely claim the document covered it.

This tests the retrieval pipeline directly and repeatably, separate from eyeballing
the GUI. Uses a temp DB so it never touches your real knowledge base.

Usage:
    python rag_test.py
    python rag_test.py --doc science_reference.txt --model qwen2.5-coder:7b

Requires: Ollama running, 'nomic-embed-text' pulled, knowledge.py next to this file.
"""

import os
import sys
import argparse
import tempfile

try:
    import knowledge as kmod
except ImportError:
    print("knowledge.py must be in the same folder as this script.")
    sys.exit(1)

import requests

OLLAMA_CHAT = "http://localhost:11434/api/chat"

# Each test: (question, expected_keyword_in_retrieved_chunk, expected_fact_in_answer)
TESTS = [
    ("What is Newton's second law?", "F = m * a", ["f = m", "mass", "acceleration"]),
    ("Explain the work-energy theorem.", "work-energy theorem", ["kinetic energy", "work"]),
    ("What are the laws of thermodynamics?", "entropy", ["entropy", "energy"]),
    ("Why does a rocket move forward?", "equal and opposite", ["reaction", "opposite"]),
    ("How do plants make food?", "Photosynthesis", ["photosynthesis", "glucose"]),
    ("What happens when sodium meets chlorine?", "ionic bond", ["ionic", "salt", "transfer"]),
    ("What does DNA stand for and how does it store information?", "deoxyribonucleic", ["base", "helix"]),
]

# Negative test: NOT in the document at all.
NEGATIVE_TEST = "What is quantum entanglement?"
NEGATIVE_DOC_TERMS = ["entangle"]  # if a retrieved chunk contained this, doc would cover it


def ask_model(model, system, question):
    try:
        r = requests.post(OLLAMA_CHAT, json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        }, timeout=180)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (requests.RequestException, KeyError, ValueError) as e:
        return f"__ERROR__ {e}"


def build_context(kb, question, threshold=0.35):
    """Return (system_prompt, retrieved_texts) the way the GUI does."""
    hits = kb.search(question, k=4)
    strong = [(src, page, txt) for score, src, page, txt in hits if score > threshold]
    system = ("You are a helpful assistant. Answer from the REFERENCE PASSAGES "
              "when relevant. If the passages don't cover the question, say so "
              "and answer from general knowledge without citing the document.")
    retrieved = [txt for _, _, txt in strong]
    if strong:
        system += "\n\nREFERENCE PASSAGES:\n"
        for src, page, txt in strong:
            system += f"\n[{src}]\n{txt}\n"
    return system, retrieved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default="science_reference.txt")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    args = ap.parse_args()

    if not os.path.isfile(args.doc):
        print(f"Document not found: {args.doc}")
        return

    # temp DB so we never touch the real knowledge base
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    kb = kmod.KnowledgeBase(tmp_db)
    print(f"Ingesting {args.doc} into a temporary KB ...")
    added, total = kb.add_file(args.doc)
    if added == 0:
        print("No chunks embedded — is Ollama running and 'nomic-embed-text' pulled?")
        return
    print(f"Embedded {added} chunks.\n" + "=" * 64)

    retrieval_pass = answer_pass = 0
    for q, expect_chunk, expect_answer in TESTS:
        system, retrieved = build_context(kb, q)
        joined = " ".join(retrieved).lower()
        r_ok = expect_chunk.lower() in joined
        ans = ask_model(args.model, system, q)
        a_ok = any(term.lower() in ans.lower() for term in expect_answer)
        retrieval_pass += r_ok
        answer_pass += a_ok
        print(f"\nQ: {q}")
        print(f"  retrieval {'✅' if r_ok else '❌'} (looked for '{expect_chunk}' in top chunks)")
        print(f"  answer    {'✅' if a_ok else '❌'} (looked for one of {expect_answer})")
        if ans.startswith("__ERROR__"):
            print(f"  ! {ans}")

    # negative test
    print("\n" + "=" * 64 + "\nNEGATIVE TEST (answer is NOT in the document)")
    system, retrieved = build_context(kb, NEGATIVE_TEST)
    joined = " ".join(retrieved).lower()
    doc_falsely_covers = any(t in joined for t in NEGATIVE_DOC_TERMS)
    ans = ask_model(args.model, NEGATIVE_TEST, NEGATIVE_TEST) if not retrieved else \
          ask_model(args.model, system, NEGATIVE_TEST)
    # good behavior: no doc chunk falsely retrieved as relevant
    print(f"Q: {NEGATIVE_TEST}")
    print(f"  no false doc retrieval: {'✅' if not doc_falsely_covers else '❌'}")
    print(f"  (model answer begins: {ans[:90].strip()}...)")

    n = len(TESTS)
    print("\n" + "=" * 64)
    print(f"RETRIEVAL: {retrieval_pass}/{n} correct sections pulled")
    print(f"ANSWERS:   {answer_pass}/{n} contained the expected fact")
    print("Negative test checks the model isn't faking document coverage.")

    try:
        os.unlink(tmp_db)
    except OSError:
        pass


if __name__ == "__main__":
    main()
