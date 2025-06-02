# 📡 prom-docker-discovery

A lightweight Prometheus Docker discovery system. Agents detect labeled containers and push their scrape targets to a central server that writes Prometheus-compatible `file_sd_config` JSON files and serves a live dashboard.

---

## 🧱 Features

- 📦 Auto-discovers Docker containers by label
- 🔐 Token-based authentication for agent push
- ⚡ Real-time updates using Docker events
- 📉 Built-in Prometheus metrics for agent
- 🌐 Web dashboard showing all connected agents and targets
- 🧹 Optional expiration and cleanup of stale targets

---


## 🚀 Quick Start

### 1. Start the stack

```bash
docker compose up --build
```

### 2. Start your containers

```
docker run -d \
  --name test-nginx \
  -p 8080:80 \
  --label prometheus.enable=true \
  --label prometheus.port=80 \
  --label prometheus.job=nginx \
  nginx:alpine
```

## 📊 Interfaces
| Service         | URL                                                            |
| --------------- | -------------------------------------------------------------- |
| Dashboard       | [http://localhost:5000](http://localhost:5000)                 |
| Agent Metrics   | [http://localhost:9101/metrics](http://localhost:9101/metrics) |
| Nginx Test Page | [http://localhost:8080](http://localhost:8080)                 |


## ⚙️ Container Label Format

| Label                      | Description                      |
| -------------------------- | -------------------------------- |
| `prometheus.enable=true`   | Enables discovery                |
| `prometheus.port=80`       | Port to scrape                   |
| `prometheus.job=nginx`     | Job name in Prometheus           |
| `prometheus.label.env=dev` | Extra label passed to Prometheus |


## 🔧 Agent Configuration

| Variable             | Description                                      |
| -------------------- | ------------------------------------------------ |
| `HOST_IP`            | IP to use in targets                             |
| `AGENT_ID`           | Unique name for the agent                        |
| `SERVER_URL`         | Push endpoint (`http://server:5000/targets/...`) |
| `AGENT_TOKEN`        | Token for authentication                         |
| `DISCOVERY_INTERVAL` | Fallback poll interval (default 30s)             |
| `METRICS_PORT`       | Exposes `/metrics` for Prometheus                |


## 🔧 Server Configuration

| Variable                    | Description                             |
| --------------------------- | --------------------------------------- |
| `TARGETS_DIR`               | Path to write JSON targets              |
| `VALID_TOKENS`              | Comma-separated list of accepted tokens |
| `TARGET_EXPIRATION_SECONDS` | Time before stale targets are removed   |


## 🔍 Server API

| Method | Path            | Description                    |
| ------ | --------------- | ------------------------------ |
| POST   | `/targets/<id>` | Receive targets from agent     |
| GET    | `/status`       | Show last-seen timestamps      |
| POST   | `/cleanup`      | Manually clean expired targets |
| GET    | `/`             | Render dashboard UI            |


## 🛡 Security Tips

- Use HTTPS and a reverse proxy for the server
- Use long AGENT_TOKENs per-agent
- Run agents with read-only access to /var/run/docker.sock
