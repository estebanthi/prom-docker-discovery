# --- server.py ---
import json
import os
import re
import time
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

TARGETS_DIR = os.getenv("TARGETS_DIR", "/etc/prometheus/targets")
TOKENS = os.getenv("VALID_TOKENS", "").split(",")  # Optional shared secrets
EXPIRE_SECONDS = int(os.getenv("TARGET_EXPIRATION_SECONDS", 3600))
META_FILE = os.path.join(TARGETS_DIR, ".meta.json")

os.makedirs(TARGETS_DIR, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Prometheus Target Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 1rem; background-color: #f5f5f5; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin-top: 1rem; background: #fff; }
        th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
        th { background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Prometheus Target Dashboard</h1>
    <p>Target directory: <code>{{ targets_dir }}</code></p>
    <table>
        <thead>
            <tr><th>Agent ID</th><th>Last Seen</th><th>Target File</th><th>Targets</th></tr>
        </thead>
        <tbody>
        {% for agent, info in agents.items() %}
        <tr>
            <td>{{ agent }}</td>
            <td>{{ info.last_seen }}</td>
            <td><code>{{ info.path }}</code></td>
            <td><pre>{{ info.targets }}</pre></td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""


def sanitize_filename(name):
    return re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", name)


def load_meta():
    try:
        with open(META_FILE) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}


def save_meta(meta):
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


@app.route("/targets/<agent_id>", methods=["POST"])
def receive_targets(agent_id):
    if TOKENS:
        token = request.headers.get("X-Agent-Token")
        if token not in TOKENS:
            return jsonify({"error": "unauthorized"}), 403

    try:
        targets = request.get_json(force=True)
        if not isinstance(targets, list):
            return jsonify({"error": "payload must be a list"}), 400

        safe_id = sanitize_filename(agent_id)
        path = os.path.join(TARGETS_DIR, f"{safe_id}.json")
        with open(path, "w") as f:
            json.dump(targets, f, indent=2)

        meta = load_meta()
        meta[safe_id] = time.time()
        save_meta(meta)

        return jsonify({"status": "ok", "written": path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cleanup", methods=["POST"])
def cleanup():
    deleted = []
    meta = load_meta()
    now = time.time()
    for agent_id, ts in list(meta.items()):
        if now - ts > EXPIRE_SECONDS:
            f = os.path.join(TARGETS_DIR, f"{agent_id}.json")
            if os.path.exists(f):
                os.remove(f)
                deleted.append(agent_id)
            del meta[agent_id]
    save_meta(meta)
    return {"deleted": deleted}


@app.route("/status")
def status():
    return load_meta()


@app.route("/")
def index():
    meta = load_meta()
    agents = {}
    for agent_id, ts in meta.items():
        path = os.path.join(TARGETS_DIR, f"{agent_id}.json")
        try:
            with open(path) as f:
                targets = json.load(f)
        except (IOError, json.JSONDecodeError):
            targets = []
        agents[agent_id] = {
            "last_seen": datetime.utcfromtimestamp(ts).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            "path": path,
            "targets": json.dumps(targets, indent=2),
        }
    return render_template_string(HTML_TEMPLATE, agents=agents, targets_dir=TARGETS_DIR)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
