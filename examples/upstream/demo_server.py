#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""

        payload = {
            "ok": True,
            "service": "demo-protected-api",
            "path": self.path,
            "received_body": body,
            "message": "Protected API received a ProofPath-approved request."
        }

        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 9797), Handler)
    print("Demo protected API listening on http://127.0.0.1:9797/protected")
    server.serve_forever()
