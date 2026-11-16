"""Run the local AI usage data-agent prototype: python3 app.py"""

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError

from agent import answer, load_data


WEB = Path(__file__).parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def serve(rows, port, model=None):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, body, content_type, status=HTTPStatus.OK):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, status=HTTPStatus.OK):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_bytes(body, "application/json; charset=utf-8", status)

        def do_GET(self):
            if self.path == "/api/status":
                self.send_json({
                    "records": len(rows),
                    "dataset": "AI_Usage_and_Impact_Cleaned.csv",
                    "mode": f"Local LLM · {model}" if model else "Rule-based",
                })
                return
            if self.path in ASSETS:
                filename, content_type = ASSETS[self.path]
                self.send_bytes((WEB / filename).read_bytes(), content_type)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self):
            if self.path != "/api/query":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("Send a question of up to 500 characters.")
                payload = json.loads(self.rfile.read(length))
                question = payload.get("question") if isinstance(payload, dict) else None
                if not isinstance(question, str):
                    raise ValueError("The request must include a question.")
                self.send_json(answer(question, rows, model))
            except (URLError, TimeoutError) as error:
                self.send_json(
                    {"error": f"The local model did not respond. Check that llama-server is running on port 8081. ({error})"},
                    HTTPStatus.BAD_GATEWAY,
                )
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)

        def log_message(self, format, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Data agent ready at http://127.0.0.1:{port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", help="Model alias served by llama-server on port 8081")
    args = parser.parse_args()
    serve(load_data(), args.port, args.model)
