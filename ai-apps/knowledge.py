#!/usr/bin/env python3
"""Spikeling knowledge base — local RAG with embeddings.

Two uses:
  1. As a CLI to ingest files into the knowledge base:
       python knowledge.py add "C:\\path\\to\\godot_docs.txt"
       python knowledge.py add "C:\\books\\mybook.pdf" --tag book
       python knowledge.py list
       python knowledge.py search "how does trust decay"
       python knowledge.py clear

  2. Imported by the Spikeling GUI for retrieval at query time.

Stores chunk text + embedding vectors in SQLite. Embeddings come from Ollama's
local 'nomic-embed-text' model, so everything stays offline and free.

Setup (one-time):  ollama pull nomic-embed-text
PDF support needs:  pip install pypdf
"""

import os
import sys
import json
import math
import sqlite3
import argparse

import requests

EMBED_URL = os.environ.get("OLLAMA_EMBED_URL", "http://localhost:11434/api/embeddings")
EMBED_MODEL = os.environ.get("SPIKELING_EMBED_MODEL", "nomic-embed-text")
KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spikeling_knowledge.db")

CHUNK_CHARS = 1200       # ~250-300 words per chunk
CHUNK_OVERLAP = 200      # carry context across chunk boundaries


# ------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------
def embed(text):
    """Return an embedding vector for text, or None on failure."""
    try:
        r = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=120)
        r.raise_for_status()
        return r.json()["embedding"]
    except (requests.RequestException, KeyError, ValueError):
        return None


def cosine(a, b):
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ------------------------------------------------------------
# Text extraction + chunking
# ------------------------------------------------------------
def read_file(path):
    """Read .txt/.md directly; extract text from .pdf via pypdf."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("PDF support needs:  pip install pypdf")
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def read_file_pages(path):
    """Return a list of (page_number, text). For txt/md it's one 'page' (0).
    For PDFs, one entry per page so we can cite page numbers."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("PDF support needs:  pip install pypdf")
        reader = PdfReader(path)
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return [(0, f.read())]


def chunk_text(text):
    """Split into overlapping chunks on whitespace boundaries."""
    text = text.strip()
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + CHUNK_CHARS, n)
        if end < n:
            space = text.rfind(" ", i, end)
            if space > i:
                end = space
        chunk = text[i:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        i = max(end - CHUNK_OVERLAP, i + 1)
    return chunks


def chunk_pages(pages):
    """Chunk page-by-page, tagging each chunk with its page number.
    Returns list of (page_number, chunk_text)."""
    out = []
    for page_no, text in pages:
        for ch in chunk_text(text):
            out.append((page_no, ch))
    return out


# ------------------------------------------------------------
# Knowledge base
# ------------------------------------------------------------
class KnowledgeBase:
    def __init__(self, db_path=KB_PATH):
        self.c = sqlite3.connect(db_path, check_same_thread=False)
        with self.c:
            self.c.execute("""CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT, tag TEXT, page INTEGER DEFAULT 0,
                seq INTEGER DEFAULT 0, text TEXT, embedding TEXT)""")
        # migrate older DBs that lack the new columns
        cols = [r[1] for r in self.c.execute("PRAGMA table_info(chunks)").fetchall()]
        with self.c:
            if "page" not in cols:
                self.c.execute("ALTER TABLE chunks ADD COLUMN page INTEGER DEFAULT 0")
            if "seq" not in cols:
                self.c.execute("ALTER TABLE chunks ADD COLUMN seq INTEGER DEFAULT 0")

    def already_done(self, source):
        """How many chunks already stored for this source (for resume)."""
        return self.c.execute(
            "SELECT COUNT(*) FROM chunks WHERE source=?", (source,)).fetchone()[0]

    def add_file(self, path, tag="", progress=None, resume=True):
        """Embed a file into the KB. Resumable: if interrupted and re-run,
        skips chunks already stored for this source."""
        source = os.path.basename(path)
        pages = read_file_pages(path)
        page_chunks = chunk_pages(pages)        # list of (page_no, text)
        total = len(page_chunks)
        start_at = self.already_done(source) if resume else 0
        added = 0
        # batch inserts for speed (commit every N)
        batch = []
        BATCH = 16
        for idx in range(start_at, total):
            page_no, ch = page_chunks[idx]
            vec = embed(ch)
            if vec is None:
                continue
            batch.append((source, tag, page_no, idx, ch, json.dumps(vec)))
            if len(batch) >= BATCH:
                self._flush(batch); added += len(batch); batch = []
            if progress:
                progress(idx + 1, total)
        if batch:
            self._flush(batch); added += len(batch)
        return added, total

    def _flush(self, batch):
        with self.c:
            self.c.executemany(
                "INSERT INTO chunks (source, tag, page, seq, text, embedding) "
                "VALUES (?, ?, ?, ?, ?, ?)", batch)

    def search(self, query, k=4, source=None):
        """Return k most similar chunks as (score, source, page, text).
        If source is given, search only within that file (library mode)."""
        qvec = embed(query)
        if qvec is None:
            return []
        if source:
            rows = self.c.execute(
                "SELECT source, page, text, embedding FROM chunks WHERE source=?",
                (source,)).fetchall()
        else:
            rows = self.c.execute(
                "SELECT source, page, text, embedding FROM chunks").fetchall()
        scored = []
        for src, page, text, emb_json in rows:
            try:
                vec = json.loads(emb_json)
                scored.append((cosine(qvec, vec), src, page, text))
            except (ValueError, TypeError):
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def sources(self):
        rows = self.c.execute(
            "SELECT source, COUNT(*) FROM chunks GROUP BY source ORDER BY source").fetchall()
        return rows

    def delete_source(self, source):
        with self.c:
            self.c.execute("DELETE FROM chunks WHERE source=?", (source,))

    def clear(self):
        with self.c:
            self.c.execute("DELETE FROM chunks")


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("path"); a.add_argument("--tag", default="")
    sub.add_parser("list")
    s = sub.add_parser("search"); s.add_argument("query")
    sub.add_parser("clear")
    args = ap.parse_args()

    kb = KnowledgeBase()

    if args.cmd == "add":
        if not os.path.isfile(args.path):
            print(f"No such file: {args.path}"); return
        print(f"Ingesting {args.path} ...")
        def prog(done, total):
            print(f"\r  embedding chunk {done}/{total}", end="", flush=True)
        added, total = kb.add_file(args.path, args.tag, prog)
        print(f"\n✅ added {added}/{total} chunks")
    elif args.cmd == "list":
        srcs = kb.sources()
        if not srcs:
            print("Knowledge base is empty.")
        else:
            print("Sources in knowledge base:")
            for src, cnt in srcs:
                print(f"  {src}: {cnt} chunks")
    elif args.cmd == "search":
        hits = kb.search(args.query)
        if not hits:
            print("No results (is the KB populated and Ollama running?).")
        for score, src, page, txt in hits:
            loc = f"{src} p.{page}" if page else src
            print(f"\n[{score:.3f}] {loc}\n{txt[:300]}...")
    elif args.cmd == "clear":
        kb.clear()
        print("Knowledge base cleared.")


if __name__ == "__main__":
    main()
