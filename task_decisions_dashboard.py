#!/usr/bin/env python3
"""
task_decisions_dashboard.py — minimal local web dashboard for task_decisions.jsonl.

Usage:
    python task_decisions_dashboard.py            # serves on http://localhost:8765
    python task_decisions_dashboard.py --port 9000
    python task_decisions_dashboard.py --file /path/to/task_decisions.jsonl

The page re-reads the file on every request, so new entries appear on refresh.
"""

import argparse
import collections
import datetime
import html
import json
import os
import pathlib
import http.server
import socketserver

DEFAULT_PORT = 8765
DEFAULT_FILE = pathlib.Path(__file__).parent / "task_decisions.jsonl"


def load_records(path: pathlib.Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def build_page(records: list[dict]) -> str:
    if not records:
        return _wrap_body("<p>No records found in task_decisions.jsonl.</p>")

    total = len(records)
    corrector_count = sum(1 for r in records if "Corrector" in r.get("fired", []))
    clarified_count = sum(1 for r in records if r.get("clarified", False))

    # Per-task-text stats (collapse by task text for the summary table)
    by_task: dict[str, list[dict]] = collections.defaultdict(list)
    for r in records:
        key = r.get("task", "").strip() or "(empty)"
        by_task[key].append(r)

    # Dynamic specialists: records that used each, and total invocations (from fired[])
    specialist_records: collections.Counter = collections.Counter()
    specialist_firings: collections.Counter = collections.Counter()
    for r in records:
        fired = r.get("fired", [])
        for s in r.get("dynamic_specialists", []):
            specialist_records[s] += 1
            specialist_firings[s] += fired.count(s)

    # Review gate events (from review_gates field, which may be populated in future)
    review_gate_counter: collections.Counter = collections.Counter()
    for r in records:
        for rg in r.get("review_gates", []):
            review_gate_counter[str(rg)] += 1

    # Time span
    timestamps = [r["ts"] for r in records if "ts" in r]
    if timestamps:
        first = datetime.datetime.fromtimestamp(min(timestamps)).strftime("%Y-%m-%d %H:%M:%S")
        last = datetime.datetime.fromtimestamp(max(timestamps)).strftime("%Y-%m-%d %H:%M:%S")
        time_span = f"{first} → {last}"
    else:
        time_span = "unknown"

    parts = []

    # --- Summary banner ---
    parts.append("<h2>Summary</h2>")
    parts.append("<table class='summary'>")
    parts.append(f"<tr><td>Total decisions</td><td>{total}</td></tr>")
    parts.append(f"<tr><td>Time span</td><td>{html.escape(time_span)}</td></tr>")
    parts.append(f"<tr><td>Clarifier triggered (ambiguous task routed away)</td><td>{clarified_count} ({100*clarified_count//total}%)</td></tr>")
    parts.append(f"<tr><td>Corrector triggered (review gate found issues)</td><td>{corrector_count} ({100*corrector_count//total}%)</td></tr>")
    parts.append(f"<tr><td>Distinct task texts</td><td>{len(by_task)}</td></tr>")
    parts.append("</table>")

    # --- Agent fire frequency ---
    agent_fired_total: collections.Counter = collections.Counter()
    for r in records:
        agent_fired_total.update(r.get("fired", []))

    parts.append("<h2>Agent fire frequency (all records)</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Agent</th><th>Times fired</th><th>% of records</th></tr>")
    for agent, count in agent_fired_total.most_common():
        pct = 100 * count // total
        parts.append(f"<tr><td>{html.escape(agent)}</td><td>{count}</td><td>{pct}%</td></tr>")
    parts.append("</table>")

    # --- Dynamic specialists ---
    parts.append("<h2>Dynamically-spawned specialists</h2>")
    if specialist_records:
        parts.append("<table>")
        parts.append("<tr><th>Specialist</th><th>Total firings (from fired[])</th><th>Records that used it</th></tr>")
        for sp, rec_count in specialist_records.most_common():
            parts.append(f"<tr><td>{html.escape(sp)}</td><td>{specialist_firings[sp]}</td><td>{rec_count}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>None logged yet.</p>")

    # --- Review gate events ---
    parts.append("<h2>Review gate events</h2>")
    if review_gate_counter:
        parts.append("<table>")
        parts.append("<tr><th>Event</th><th>Count</th></tr>")
        for event, cnt in review_gate_counter.most_common():
            parts.append(f"<tr><td>{html.escape(event)}</td><td>{cnt}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>No review_gate events logged yet (Corrector firings are counted above).</p>")

    # --- Per-task routing table ---
    parts.append("<h2>Per-task routing (grouped by task text)</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Task</th><th>Runs</th><th>Avg agents</th><th>Clarified</th><th>Corrector</th><th>Specialists</th><th>Most-fired agents</th></tr>")

    sorted_tasks = sorted(by_task.items(), key=lambda kv: -len(kv[1]))
    for task_text, recs in sorted_tasks:
        runs = len(recs)
        avg_agents = sum(r.get("agents_run", 0) for r in recs) / runs
        clarified = sum(1 for r in recs if r.get("clarified", False))
        corrector = sum(1 for r in recs if "Corrector" in r.get("fired", []))
        specs: set[str] = set()
        for r in recs:
            specs.update(r.get("dynamic_specialists", []))
        agent_counts: collections.Counter = collections.Counter()
        for r in recs:
            agent_counts.update(r.get("fired", []))
        top_agents = ", ".join(a for a, _ in agent_counts.most_common(4))
        task_display = html.escape(task_text[:80] + ("…" if len(task_text) > 80 else ""))
        specs_display = html.escape(", ".join(sorted(specs)) if specs else "—")
        parts.append(
            f"<tr><td class='task'>{task_display}</td>"
            f"<td>{runs}</td>"
            f"<td>{avg_agents:.1f}</td>"
            f"<td>{clarified}</td>"
            f"<td>{corrector}</td>"
            f"<td>{specs_display}</td>"
            f"<td>{html.escape(top_agents)}</td></tr>"
        )
    parts.append("</table>")

    # --- Recent 20 raw records ---
    parts.append("<h2>Recent decisions (last 20)</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Time</th><th>Task</th><th>Agents run</th><th>Fired</th><th>Clarified</th><th>Specialists</th></tr>")
    for r in sorted(records, key=lambda x: x.get("ts", 0), reverse=True)[:20]:
        ts = r.get("ts")
        time_str = datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S") if ts else "?"
        task_str = html.escape((r.get("task", "") or "(empty)")[:60])
        fired_str = html.escape(", ".join(r.get("fired", [])))
        clarified_str = "yes" if r.get("clarified") else ""
        specs_str = html.escape(", ".join(r.get("dynamic_specialists", [])) or "—")
        agents_run = r.get("agents_run", "?")
        parts.append(
            f"<tr><td class='mono'>{time_str}</td>"
            f"<td class='task'>{task_str}</td>"
            f"<td>{agents_run}</td>"
            f"<td class='mono'>{fired_str}</td>"
            f"<td>{clarified_str}</td>"
            f"<td>{specs_str}</td></tr>"
        )
    parts.append("</table>")

    return _wrap_body("\n".join(parts))


def _wrap_body(content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Task Decisions Dashboard</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #f8f9fa; color: #212529; }}
  h1 {{ border-bottom: 2px solid #dee2e6; padding-bottom: .4rem; }}
  h2 {{ margin-top: 2rem; color: #495057; font-size: 1.1rem; text-transform: uppercase; letter-spacing: .05em; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; background: #fff; font-size: .9rem; }}
  th, td {{ border: 1px solid #dee2e6; padding: .4rem .7rem; text-align: left; }}
  th {{ background: #e9ecef; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #f8f9fa; }}
  table.summary td:first-child {{ font-weight: 600; width: 50%; }}
  .task {{ max-width: 30ch; word-break: break-word; }}
  .mono {{ font-family: monospace; font-size: .82rem; }}
  .footer {{ margin-top: 2rem; font-size: .8rem; color: #868e96; }}
</style>
</head>
<body>
<h1>Task Decisions Dashboard</h1>
{content}
<p class="footer">Reads task_decisions.jsonl on every page load — refresh to see new data.</p>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    jsonl_path: pathlib.Path = DEFAULT_FILE

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return
        records = load_records(self.jsonl_path)
        page = build_page(records)
        encoded = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="Serve a task_decisions.jsonl dashboard.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    args = parser.parse_args()

    Handler.jsonl_path = args.file

    class ReusingServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusingServer(("", args.port), Handler) as srv:
        print(f"Dashboard running at http://localhost:{args.port}/")
        print(f"Reading: {args.file}")
        print("Ctrl-C to stop.")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
