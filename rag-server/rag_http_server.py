import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from rag_pipeline import refresh_corpus, retrieve_context, answer_question

HOST = "0.0.0.0"
PORT = 8001


class RagHttpHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            if self.path == "/refresh":
                result = refresh_corpus()
                self._send_json(200, result)

            elif self.path == "/retrieve":
                body = self._read_json_body()
                query = body.get("query", "")
                top_k = body.get("top_k", 5)
                result = retrieve_context(query, top_k)
                self._send_json(200, result)

            elif self.path == "/answer":
                body = self._read_json_body()
                query = body.get("query", "")
                top_k = body.get("top_k", 5)
                result = answer_question(query, top_k)
                self._send_json(200, result)

            else:
                self._send_json(404, {"error": "not found"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), RagHttpHandler)
    print(f"Starting RAG HTTP test server on http://{HOST}:{PORT}")
    print("Endpoints: GET /health, POST /refresh, POST /retrieve, POST /answer")
    server.serve_forever()