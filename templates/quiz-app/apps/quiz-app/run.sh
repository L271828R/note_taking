#!/usr/bin/env bash
# Launches both quiz apps for this topic.
# Edit questions.json to update your question bank.

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENGINE_DIR="$(cd "$ROOT/../../../../../quiz-engine" 2>/dev/null && pwd)"

# Fallback: locate engine relative to NOTES_FOLDERS_PATH env var
if [ -z "$ENGINE_DIR" ] || [ ! -d "$ENGINE_DIR" ]; then
  ENGINE_DIR="${NOTES_FOLDERS_PATH:+$(cd "${NOTES_FOLDERS_PATH}/../projects/notes/quiz-engine" 2>/dev/null && pwd)}"
fi

if [ -z "$ENGINE_DIR" ] || [ ! -d "$ENGINE_DIR" ]; then
  echo "Error: quiz-engine not found. Expected at $ROOT/../../../../../quiz-engine" >&2
  exit 1
fi

echo ""
echo "  Quiz Apps — $(basename "$ROOT")"
echo "  ─────────────────────────────────────────"
echo "  1) React quiz  (browser)"
echo "  2) Flappy quiz (pygame)"
echo ""
read -r -p "  Pick [1/2, default 1]: " choice

case "$choice" in
  2)
    echo ""
    echo "  Launching Flappy Quiz…"
    exec python3 "$ENGINE_DIR/flappy-quiz.py" --bank "$ROOT/questions.json"
    ;;
  *)
    PORT=8744
    echo ""
    echo "  Serving React quiz at http://localhost:$PORT"

    # Serve ENGINE_DIR so react-quiz.html can fetch questions.json via a relative path
    # We pass the absolute path to questions.json via a query param handled by a tiny shim
    cd "$ENGINE_DIR"
    python3 - "$ROOT/questions.json" "$PORT" <<'PYEOF'
import sys, os, http.server, urllib.parse, json, pathlib

bank_path = sys.argv[1]
port      = int(sys.argv[2])
engine_dir = pathlib.Path(__file__).parent if '__file__' in dir() else pathlib.Path.cwd()

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass   # silence request log

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        # Serve questions.json from its real location regardless of URL
        if parsed.path == "/questions.json":
            data = pathlib.Path(bank_path).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

os.chdir(engine_dir)

import threading, webbrowser, time
def _open():
    time.sleep(0.5)
    webbrowser.open(f"http://localhost:{port}/react-quiz.html")
threading.Thread(target=_open, daemon=True).start()

print(f"  Open: http://localhost:{port}/react-quiz.html")
print("  Press Ctrl+C to stop.\n")
with http.server.HTTPServer(("", port), Handler) as srv:
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
PYEOF
    ;;
esac
