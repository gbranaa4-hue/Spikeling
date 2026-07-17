"""Standalone worker process: loads the real code-minilm + FAISS index
(observe_pipeline.py / trit_app.py's SearchEngine, from the 012-ternary
repo) and runs ONE semantic search query, then exits.

Run as a SEPARATE PROCESS on purpose, never imported in-process by
voice_commands.py -- confirmed by direct testing (not guessed) that
pyttsx3.init() (Windows SAPI5, COM-based) and loading torch/FAISS into
the same process causes a hard segfault (exit 139). Isolating the load
into its own process sidesteps the conflict entirely.

Usage:
    python code_search_worker.py "<query>"        -> single top result dict, or null (back-compat: CMD_CODE_SEARCH)
    python code_search_worker.py "<query>" <k>     -> JSON LIST of up to k results (file search)

Each result dict carries the chunk fields from SearchEngine.search plus a
resolved "full_path" (base_dir + rel_path) so callers can show/open the
actual file. Only the LAST stdout line is trusted (loader noise -> stderr).
"""
import sys
import os
import json

OBSERVE_REPO = r"C:\Users\gbran\OneDrive\Documents\012-ternary"


def main():
    args = sys.argv[1:]
    query = args[0] if args else ""
    list_mode = len(args) > 1
    k = int(args[1]) if list_mode else 1
    if not query:
        print(json.dumps([] if list_mode else None))
        return

    sys.path.insert(0, OBSERVE_REPO)
    from observe_pipeline import load_engine
    engine = load_engine()
    results = engine.search(query, k=k)

    # Resolve full paths -- the chunk result only carries rel_path; base_dir
    # lives in the engine's path_table. First base_dir wins per rel_path.
    base_for = {}
    for p in getattr(engine, "path_table", None) or []:
        base_for.setdefault(p.get("rel_path"), p.get("base_dir"))
    for r in results:
        rp = r.get("path", "")
        bd = base_for.get(rp, "")
        r["full_path"] = os.path.normpath(os.path.join(bd, rp)) if bd else rp

    if list_mode:
        print(json.dumps(results))
    else:
        print(json.dumps(results[0] if results else None))


if __name__ == "__main__":
    main()
