"""
Flask REST API for uv-prefetch-poc
Wraps the existing Python prefetcher modules into a web-accessible API
with Server-Sent Events for real-time progress streaming.
"""

import sys
import os
import json
import time
import threading
import logging
import queue
from io import StringIO

# Add parent dir so we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS

from parser import parse_uv_lock
from downloader import get_package_url, download_artifact
from sbom import generate_sbom

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# --- State ---
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
SBOM_FILE = os.path.join(os.path.dirname(__file__), '..', 'sbom.json')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')

current_packages = []
prefetch_status = {
    "running": False,
    "total": 0,
    "completed": 0,
    "failed": 0,
    "log": []
}

# SSE event queues for connected clients
sse_clients = []


def broadcast_sse(event, data):
    """Send an SSE event to all connected clients."""
    dead = []
    for q in sse_clients:
        try:
            q.put_nowait((event, data))
        except:
            dead.append(q)
    for q in dead:
        sse_clients.remove(q)


# --- Routes ---

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/parse', methods=['POST'])
def api_parse():
    """Accept a uv.lock file upload and return parsed packages."""
    global current_packages, prefetch_status

    if 'lockfile' not in request.files:
        # Check if raw text was sent
        if request.is_json and 'content' in request.json:
            # Save content to temp file
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            tmp_path = os.path.join(UPLOAD_DIR, 'uv.lock')
            with open(tmp_path, 'w') as f:
                f.write(request.json['content'])
        else:
            return jsonify({"error": "No lockfile provided"}), 400
    else:
        file = request.files['lockfile']
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        tmp_path = os.path.join(UPLOAD_DIR, 'uv.lock')
        file.save(tmp_path)

    packages = parse_uv_lock(tmp_path)
    current_packages = packages

    # Reset status
    prefetch_status = {
        "running": False,
        "total": len(packages),
        "completed": 0,
        "failed": 0,
        "log": []
    }

    return jsonify({
        "success": True,
        "count": len(packages),
        "packages": packages
    })


@app.route('/api/prefetch', methods=['POST'])
def api_prefetch():
    """Trigger prefetching in a background thread, return immediately."""
    global prefetch_status

    if not current_packages:
        return jsonify({"error": "No packages parsed yet. Upload a lockfile first."}), 400

    if prefetch_status["running"]:
        return jsonify({"error": "Prefetch already in progress."}), 409

    os.makedirs(CACHE_DIR, exist_ok=True)

    prefetch_status = {
        "running": True,
        "total": len(current_packages),
        "completed": 0,
        "failed": 0,
        "log": []
    }

    def _log(msg, level="info"):
        entry = {"time": time.strftime("%H:%M:%S"), "level": level, "message": msg}
        prefetch_status["log"].append(entry)
        broadcast_sse("log", entry)

    def run_prefetch():
        global prefetch_status
        _log(f"Starting prefetch for {len(current_packages)} packages...")

        for pkg in current_packages:
            name = pkg["name"]
            version = pkg["version"]
            hashes = pkg.get("hashes", [])

            _log(f"Resolving {name}=={version}...")

            url, specific_hash = get_package_url(name, version, hashes)

            # Retry without SSL if first attempt fails (macOS cert issue)
            if not url:
                url, specific_hash = get_package_url(name, version, hashes, verify_ssl=False)

            if url:
                _log(f"Downloading {name}=={version} from PyPI...")
                result = download_artifact(url, name, version, CACHE_DIR, specific_hash, verify_ssl=False)
                if result:
                    prefetch_status["completed"] += 1
                    _log(f"✓ {name}=={version} downloaded & verified", "success")
                else:
                    prefetch_status["failed"] += 1
                    _log(f"✗ Hash mismatch for {name}=={version}", "error")
            else:
                prefetch_status["failed"] += 1
                _log(f"✗ Could not resolve URL for {name}=={version}", "error")

            broadcast_sse("progress", {
                "completed": prefetch_status["completed"],
                "failed": prefetch_status["failed"],
                "total": prefetch_status["total"]
            })

        # Generate SBOM
        _log("Generating SBOM...")
        generate_sbom(current_packages, CACHE_DIR, SBOM_FILE)
        _log("✓ SBOM generated successfully", "success")

        prefetch_status["running"] = False
        broadcast_sse("done", {"completed": prefetch_status["completed"], "failed": prefetch_status["failed"]})
        _log(f"Prefetch complete: {prefetch_status['completed']} succeeded, {prefetch_status['failed']} failed.")

    thread = threading.Thread(target=run_prefetch, daemon=True)
    thread.start()

    return jsonify({"success": True, "message": "Prefetch started"})


@app.route('/api/status')
def api_status():
    """Return current prefetch status."""
    return jsonify(prefetch_status)


@app.route('/api/sbom')
def api_sbom():
    """Return the generated SBOM JSON."""
    if os.path.exists(SBOM_FILE):
        with open(SBOM_FILE) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No SBOM generated yet. Run prefetch first."}), 404


@app.route('/api/packages')
def api_packages():
    """Return the current parsed packages."""
    return jsonify({"packages": current_packages, "count": len(current_packages)})


@app.route('/api/cache')
def api_cache():
    """Return list of cached artifacts."""
    if not os.path.exists(CACHE_DIR):
        return jsonify({"files": []})

    files = []
    for fname in os.listdir(CACHE_DIR):
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.isfile(fpath):
            files.append({
                "name": fname,
                "size": os.path.getsize(fpath),
                "size_human": _human_size(os.path.getsize(fpath))
            })
    return jsonify({"files": files, "count": len(files)})


@app.route('/api/stream')
def api_stream():
    """SSE endpoint for real-time progress updates."""
    q = queue.Queue()
    sse_clients.append(q)

    def event_stream():
        try:
            # Send initial status
            yield f"event: status\ndata: {json.dumps(prefetch_status)}\n\n"
            while True:
                try:
                    event, data = q.get(timeout=30)
                    yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield f"event: ping\ndata: {{}}\n\n"
        except GeneratorExit:
            if q in sse_clients:
                sse_clients.remove(q)

    return Response(event_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def _human_size(nbytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("\n🚀 uv-prefetch-poc Web Dashboard")
    print("   Open http://localhost:8080 in your browser\n")
    app.run(debug=True, host='0.0.0.0', port=8080, threaded=True)
