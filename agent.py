import hashlib
import json
import logging
import os
import threading
import time

import docker
import requests
from prometheus_client import Gauge, start_http_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

HOST_IP = os.getenv("HOST_IP")
AGENT_ID = os.getenv("AGENT_ID", HOST_IP)
SERVER_URL = os.getenv("SERVER_URL", f"http://localhost:5000/targets/{AGENT_ID}")
AGENT_TOKEN = os.getenv("AGENT_TOKEN")
DISCOVERY_INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", 30))
METRICS_PORT = int(os.getenv("METRICS_PORT", 9101))

_docker_client = docker.from_env()
_api_client = docker.APIClient()
_targets_cache_hash = None
_lock = threading.Lock()

# Prometheus metrics
sync_success = Gauge("agent_sync_success", "Was the last sync successful (1 or 0)")
sync_duration = Gauge("agent_sync_duration_seconds", "Duration of last sync")
target_count = Gauge("agent_target_count", "Number of targets discovered")


def get_targets_hash(targets: list[dict]) -> str:
    return hashlib.sha256(json.dumps(targets, sort_keys=True).encode()).hexdigest()


def discover_targets():
    try:
        containers = _docker_client.containers.list()
    except Exception as e:
        logging.error(f"Error accessing Docker: {e}")
        return []

    targets = []
    for container in containers:
        if container.name.startswith("prometheus-agent"):
            continue  # avoid self-discovery
        labels = container.labels
        if labels.get("prometheus.enable", "false").lower() != "true":
            continue

        port = labels.get("prometheus.port", "9100")
        job = labels.get("prometheus.job", "dockerfiles")
        extra_labels = {
            k.replace("prometheus.label.", ""): v
            for k, v in labels.items()
            if k.startswith("prometheus.label.")
        }

        targets.append(
            {
                "targets": [f"{HOST_IP}:{port}"],
                "labels": {
                    "job": job,
                    "container_name": container.name,
                    **extra_labels,
                },
            }
        )

    return targets


def sync_targets():
    global _targets_cache_hash

    with _lock:
        start = time.time()
        targets = discover_targets()
        duration = time.time() - start

        new_hash = get_targets_hash(targets)
        if new_hash != _targets_cache_hash:
            logging.info("Targets changed — sending update to server")
            url = SERVER_URL
            _targets_cache_hash = new_hash
            data = targets
        else:
            logging.debug("Targets unchanged — sending heartbeat only")
            url = SERVER_URL.replace("/targets/", "/heartbeat/")
            data = None  # no payload needed for heartbeat

        headers = {"Content-Type": "application/json"}
        if AGENT_TOKEN:
            headers["X-Agent-Token"] = AGENT_TOKEN

        try:
            res = requests.post(url, json=data, headers=headers, timeout=5)
            res.raise_for_status()
            sync_success.set(1)
        except Exception as e:
            logging.error(f"Error contacting server: {e}")
            sync_success.set(0)

        sync_duration.set(duration)
        target_count.set(len(targets))

        headers = {"Content-Type": "application/json"}
        if AGENT_TOKEN:
            headers["X-Agent-Token"] = AGENT_TOKEN

        try:
            res = requests.post(SERVER_URL, json=targets, headers=headers, timeout=5)
            res.raise_for_status()
            _targets_cache_hash = new_hash
            logging.info(f"Updated server with {len(targets)} targets")
            sync_success.set(1)
        except Exception as e:
            logging.error(f"Error sending targets: {e}")
            sync_success.set(0)

        sync_duration.set(duration)
        target_count.set(len(targets))


def poll_loop():
    while True:
        sync_targets()
        time.sleep(DISCOVERY_INTERVAL)


def docker_event_loop():
    debounce_timer = None

    def debounced_sync():
        nonlocal debounce_timer
        if debounce_timer:
            debounce_timer.cancel()
        debounce_timer = threading.Timer(1.0, sync_targets)
        debounce_timer.start()

    while True:
        try:
            for event in _api_client.events(decode=True):
                if event.get("Type") == "container" and event.get("Action") in (
                    "start",
                    "stop",
                    "die",
                    "destroy",
                ):
                    logging.info(
                        f"Docker event: {event['Action']} on {event.get('id', '')[:12]}"
                    )
                    debounced_sync()
        except Exception as e:
            logging.warning(f"Docker event stream error: {e} — retrying in 5s")
            time.sleep(5)


def main():
    logging.info("Starting Prometheus Docker agent with metrics + auth")
    start_http_server(METRICS_PORT)
    threading.Thread(target=poll_loop, daemon=True).start()
    docker_event_loop()


if __name__ == "__main__":
    main()
