"""Dependency-free local reviewer UI: python -m shorts_fidelity_judge.reviewer_ui report.json annotations.jsonl."""
from __future__ import annotations

import html
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

LABELS = {"true_issue", "acceptable_adaptation", "false_alarm", "cannot_judge"}


def serve(report_path: Path, annotations_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            findings = report["findings"]
            forms = "".join(f"<form method='post'><input type='hidden' name='i' value='{i}'><p><b>{html.escape(f['category'])}</b>: {html.escape(f['evidence'])}<br><select name='label'>{''.join(f'<option>{x}</option>' for x in sorted(LABELS))}</select> <button>Save</button></p></form>" for i, f in enumerate(findings))
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(f"<h1>Reviewer</h1>{forms}".encode())
        def do_POST(self) -> None:  # noqa: N802
            from urllib.parse import parse_qs
            fields = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            label, index = fields.get("label", [""])[0], int(fields.get("i", ["-1"])[0])
            if label in LABELS and 0 <= index < len(report["findings"]):
                annotations_path.parent.mkdir(parents=True, exist_ok=True)
                with annotations_path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps({"finding_index": index, "category": report["findings"][index]["category"], "label": label}, ensure_ascii=False) + "\n")
            self.send_response(303); self.send_header("Location", "/"); self.end_headers()
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()


if __name__ == "__main__":
    serve(Path(sys.argv[1]), Path(sys.argv[2]))
