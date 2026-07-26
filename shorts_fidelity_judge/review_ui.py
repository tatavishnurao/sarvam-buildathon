"""Small local reviewer UI; writes only append-only JSONL labels."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    labels = args.report.parent / "annotations.jsonl"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            options = "".join(f'<option>{x}</option>' for x in ["true_issue", "acceptable_adaptation", "false_alarm", "cannot_judge"])
            prior = [json.loads(line) for line in labels.read_text(encoding="utf-8").splitlines()] if labels.exists() else []
            latest = {item["issue_index"]: item["label"] for item in prior}
            judged = [label for label in latest.values() if label != "cannot_judge"]
            precision = sum(label == "true_issue" for label in judged) / len(judged) if judged else None
            compression = len(latest) / len(report["findings"]) if report["findings"] else None
            metrics = f"<p>Issue precision: {precision:.2%}</p>" if precision is not None else "<p>Issue precision: pending labels</p>"
            metrics += f"<p>Review compression: {compression:.2%}</p>" if compression is not None else "<p>Review compression: no findings</p>"
            rows = "".join(f'<form method="post"><b>{i}: {f["category"]}</b><br>{f["evidence"]}<input type="hidden" name="issue" value="{i}"><select name="label">{options}</select><button>Save</button></form><hr>' for i, f in enumerate(report["findings"]))
            self.send_response(200); self.end_headers(); self.wfile.write(f"<html><body><h1>Reviewer</h1>{metrics}{rows}</body></html>".encode())
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"]); data = self.rfile.read(length).decode(); parts = dict(x.split("=", 1) for x in data.split("&"))
            record = {"at": datetime.now(UTC).isoformat(), "issue_index": int(parts["issue"]), "label": parts["label"].replace("+", "_")}
            with labels.open("a", encoding="utf-8") as file: file.write(json.dumps(record) + "\n")
            self.send_response(303); self.send_header("Location", "/"); self.end_headers()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
