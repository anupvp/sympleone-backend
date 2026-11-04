#!/usr/bin/env bash
# Make SympleOne live on this host in one command.
# Run on the server, from the uploaded API folder:
#   bash go-live.sh
#
# Expects this layout (what the FTP deploy creates):
#   .../amazon/            frontend files (index.html, assets/)
#   .../amazon/backend/    this script and the FastAPI app

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
PORT="${PORT:-8765}"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-https://amazon.globalitstaffing.com}"
PUBLIC_PREFIX="${PUBLIC_PREFIX:-/amazon}"
API_URL="${PUBLIC_ORIGIN}${PUBLIC_PREFIX}/api"
OLD_API_URL="${OLD_API_URL:-https://sympleone-api.onrender.com/api}"
PID_FILE="$BACKEND_DIR/uvicorn.pid"
LOG_FILE="$BACKEND_DIR/uvicorn.log"

if [[ ! -f "$WEB_DIR/index.html" ]]; then
  echo "Frontend not found at $WEB_DIR/index.html"
  echo "Upload the frontend into the parent of this backend folder first."
  exit 1
fi

pick_python() {
  local candidate
  for candidate in \
    /opt/alt/python312/bin/python3 \
    /opt/alt/python311/bin/python3 \
    /opt/alt/python310/bin/python3 \
    python3 \
    python
  do
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(pick_python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10 or newer was not found. In hPanel, enable Python 3.11 for this account, then run this script again."
  exit 1
fi

echo "Installing API dependencies in $BACKEND_DIR"
echo "Using $PYTHON ($("$PYTHON" -V))"
rm -rf "$BACKEND_DIR/.venv"
# Shared hosting blocks symlinks, so copy the interpreter into the virtualenv.
if ! "$PYTHON" -m venv --copies "$BACKEND_DIR/.venv"; then
  rm -rf "$BACKEND_DIR/.venv"
  if ! "$PYTHON" -m venv --copies --without-pip "$BACKEND_DIR/.venv"; then
    echo "Could not create a virtualenv with $PYTHON"
    exit 1
  fi
fi
# shellcheck disable=SC1091
source "$BACKEND_DIR/.venv/bin/activate"
if ! python -m pip --version >/dev/null 2>&1; then
  echo "Installing pip"
  curl -fsSL https://bootstrap.pypa.io/get-pip.py | python
fi
python -m pip install --upgrade pip
python -m pip install -r "$BACKEND_DIR/requirements.txt"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Stopping previous API process $old_pid"
    kill "$old_pid" || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

echo "Starting API on 127.0.0.1:$PORT"
cd "$BACKEND_DIR"
setsid nohup python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >>"$LOG_FILE" 2>&1 < /dev/null &
echo $! >"$PID_FILE"
disown || true

ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "API did not become healthy. Last log lines:"
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi

mkdir -p "$WEB_DIR/api"
cat >"$WEB_DIR/api/index.php" <<'PHP'
<?php
$forward = $_SERVER['PATH_INFO'] ?? ($_GET['__path'] ?? '');
if ($forward === '') {
    $uri = $_SERVER['REQUEST_URI'] ?? '/api';
    $forward = preg_replace('#^/amazon#', '', strtok($uri, '?'));
}
if ($forward === '' || $forward[0] !== '/') {
    $forward = '/' . ltrim($forward, '/');
}
$params = $_GET;
unset($params['__path']);
$qs = http_build_query($params);
$url = 'http://127.0.0.1:8765' . $forward . ($qs !== '' ? '?' . $qs : '');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 60);
$headers = [];
if (function_exists('getallheaders')) {
    foreach (getallheaders() as $name => $value) {
        if (strtolower($name) === 'host' || strtolower($name) === 'content-length') {
            continue;
        }
        $headers[] = $name . ': ' . $value;
    }
}
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
if (!in_array($method, ['GET', 'HEAD'], true)) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));
}
$response = curl_exec($ch);
if ($response === false) {
    http_response_code(502);
    header('Content-Type: application/json');
    echo json_encode(['detail' => 'API is not reachable', 'error' => curl_error($ch)]);
    exit;
}
$status = curl_getinfo($ch, CURLINFO_HTTP_CODE) ?: 502;
$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
curl_close($ch);
$rawHeaders = substr($response, 0, $headerSize);
$body = substr($response, $headerSize);
http_response_code($status);
foreach (preg_split("/\r\n|\n|\r/", $rawHeaders) as $line) {
    if ($line === '' || stripos($line, 'HTTP/') === 0) {
        continue;
    }
    $lower = strtolower($line);
    if (strpos($lower, 'transfer-encoding:') === 0 || strpos($lower, 'content-length:') === 0) {
        continue;
    }
    header($line, false);
}
echo $body;
PHP

# Keep the port in the PHP file aligned with this script.
sed -i "s#http://127.0.0.1:8765#http://127.0.0.1:${PORT}#g" "$WEB_DIR/api/index.php"

cat >"$WEB_DIR/api/.htaccess" <<'HT'
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^ index.php [L]
HT

cat >"$WEB_DIR/.htaccess" <<HT
AddType application/javascript .js .mjs
AddType text/css .css
<FilesMatch "\\.js$">
  ForceType application/javascript
</FilesMatch>

RewriteEngine On
RewriteBase ${PUBLIC_PREFIX}/
RewriteRule ^api/(.*)$ api/index.php/api/$1 [QSA,L]
RewriteRule ^index\\.html$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . ${PUBLIC_PREFIX}/index.html [L]
HT

if [[ -d "$WEB_DIR/assets" ]]; then
  echo "Pointing the frontend at $API_URL"
  find "$WEB_DIR/assets" -type f -name '*.js' -print0 |
    xargs -0 sed -i "s#${OLD_API_URL}#${API_URL}#g"
fi

echo
echo "Live: ${PUBLIC_ORIGIN}${PUBLIC_PREFIX}"
echo "API:  ${API_URL}"
echo "Logs: $LOG_FILE"
