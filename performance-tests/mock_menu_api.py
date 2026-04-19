"""Local mock API server for zero-cost JMeter testing.

Serves GET /api/menu with optional query filter so load tests can run without
calling paid cloud services.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


MENU = [
    {"id": 1, "name": "Tra sua truyen thong", "price": 28000},
    {"id": 2, "name": "Tra dao cam sa", "price": 35000},
    {"id": 3, "name": "Bun bo", "price": 45000},
    {"id": 4, "name": "Com ga", "price": 42000},
]


class MenuHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/menu":
            self._send_json(404, {"error": "not_found"})
            return

        params = parse_qs(parsed.query)
        query = (params.get("q", [""])[0] or "").strip().lower()

        if query:
            items = [item for item in MENU if query in item["name"].lower()]
        else:
            items = MENU

        payload = {
            "success": True,
            "count": len(items),
            "items": items,
        }
        self._send_json(200, payload)

    def log_message(self, format, *args):
        # Keep terminal output clean during load tests.
        return

    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 5000), MenuHandler)
    print("Mock menu API running at http://127.0.0.1:5000/api/menu")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
