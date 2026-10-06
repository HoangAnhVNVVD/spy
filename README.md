# Windows Activity Tracker & Productivity Logger

> **Self-hosted, privacy-first personal productivity and time-tracking system for Windows with a Railway backend.**  
> An open-source, self-hosted alternative to ActivityWatch and RescueTime.

---

## 🌟 Overview

The **Windows Activity Tracker** is built specifically for individuals who want complete ownership and visibility into their computer usage and work productivity without exposing sensitive information to proprietary third-party clouds.

### Core Highlights
- **Native Windows Monitoring (Win32 API)**: Tracks foreground window process names, window titles, active durations, and detects idle/AFK states via native `GetLastInputInfo` (no bulky browser extensions required).
- **Client-Side Privacy Protection**: Sanitizes all window titles **before** data touches disk or the network. Automatically strips passwords, credit cards, emails, auth tokens, and private/incognito browsing markers. Supports custom process ignore lists (e.g., password managers like 1Password, KeePass).
- **Offline-First SQLite Buffer**: If your laptop is offline, disconnected from Wi-Fi, or the Railway backend is temporarily unreachable, events buffer locally in SQLite with zero data loss. Batches synchronize automatically once the network is restored.
- **Self-Hosted Railway Backend**: Built with **FastAPI** and **SQLAlchemy**, supporting SQLite or managed PostgreSQL with dynamic Railway port routing.
- **Interactive Productivity Dashboard**: Built-in, responsive dark-mode dashboard with **Chart.js** visualizations for hourly timelines, category distribution, top applications ranking, and searchable activity streams.
- **Railway Ready**: Pre-configured with `Dockerfile`, `railway.toml`, `Procfile`, and automated healthcheck probes.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       WINDOWS CLIENT                        │
│                                                             │
│  ┌───────────────────┐        ┌──────────────────────────┐  │
│  │   Win32 Monitor   │ ────►  │      Privacy Engine      │  │
│  │ (Active & Idle)   │        │ (Redaction & Ignore List)│  │
│  └───────────────────┘        └────────────┬─────────────┘  │
│                                            │                │
│                                            ▼                │
│                              ┌───────────────────────────┐  │
│                              │   Local SQLite Buffer     │  │
│                              │   (~/.win_activity_tracker)│  │
│                              └─────────────┬─────────────┘  │
│                                            │ (Bearer Auth)  │
│                                            ▼                │
│                              ┌───────────────────────────┐  │
│                              │    Batch Sync Engine      │  │
│                              └─────────────┬─────────────┘  │
└────────────────────────────────────────────┼────────────────┘
                                             │ HTTPS / POST batch
                                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   RAILWAY BACKEND SERVER                    │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ FastAPI App (Health, Activities, Analytics API)       │  │
│  └───────────┬───────────────────────────────┬───────────┘  │
│              │                               │              │
│              ▼                               ▼              │
│  ┌─────────────────────────┐   ┌─────────────────────────┐  │
│  │ Auto-Categorizer Engine │   │ SQLAlchemy Persistence  │  │
│  │ (Dev, Office, Media...) │   │ (SQLite / PostgreSQL)   │  │
│  └─────────────────────────┘   └─────────────────────────┘  │
│              │                                              │
│              ▼                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Single-Page Web Dashboard (Chart.js / Responsive UI)  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (Local Setup)

### 1. Requirements
- Python 3.10+ (Tested on Python 3.12 & 3.14 on Windows)
- Dependencies: `pip install -r requirements.txt`

### 2. Start the Backend Server
```powershell
# From the project root
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser to:
- **Interactive Dashboard**: `http://localhost:8000/`
- **Swagger API Documentation**: `http://localhost:8000/docs`
- **Health Probe**: `http://localhost:8000/health`

### 3. Run the Windows Client
Open a second terminal window:

```powershell
# Live probe (inspect active window detection & idle timer)
python -m client.cli probe

# Check local buffer & server connectivity
python -m client.cli status

# Start continuous tracking daemon
python -m client.cli run
```

---

## 🛡️ Privacy & Local Sanitization

All sensitive filtering executes **locally on your Windows PC** inside `client/privacy.py` before records enter the SQLite buffer or are transmitted to the server:

1. **Ignored Processes**: If an ignored process is in focus, it is recorded as `[Private App]` or dropped entirely. Default ignored processes include:
   - `1password.exe`, `keepass.exe`, `keepassxc.exe`, `bitwarden.exe`
   - `lockapp.exe`, `logonui.exe`, `credentialui.exe`, `screensaver.exe`
2. **Private Browsing Detection**: Window titles containing `InPrivate`, `Incognito`, `Private Browsing`, or `Tor Browser` are automatically replaced with `[Private Browsing]`.
3. **Structured Pattern Redaction**:
   - **Credit Card Numbers**: Matches 13–19 digit patterns $\rightarrow$ `[REDACTED]`
   - **Email Addresses**: Replaced with `[REDACTED]`
   - **URL Tokens & Credentials**: URL query strings like `token=xyz`, `password=xyz`, or `api_key=xyz` are masked.
4. **Keyword Masking**: Words like `password`, `passcode`, `secret`, `ssn`, `cvv` are sanitized.
5. **Full Masking Mode (`mask_all_titles`)**: If enabled, only the process executable name is recorded (e.g. `[code.exe]`), stripping all window titles entirely.

### Raw Mode (Disable Privacy Filtering & Redaction)
If you want to record **100% raw details without any filtering, redaction, or process exclusions**, you can pass the `--raw-mode` flag or set the `ACTIVITY_RAW_MODE=true` environment variable:
```bash
python -m client.cli run --raw-mode
```
In Raw Mode:
- No process is ignored or dropped.
- Window titles are kept 100% verbatim without any `[REDACTED]` or `[Private Browsing]` masking.


---

## ☁️ Deploying to Railway

### Option A: Railway CLI / GitHub Repository
1. Push this repository to your GitHub account or link via Railway CLI:
   ```bash
   railway login
   railway init
   railway up
   ```
2. In Railway Dashboard, set your **Environment Variables**:
   | Variable | Value | Description |
   |---|---|---|
   | `PORT` | `8000` | Railway automatically assigns a port |
   | `API_KEY` | `your-secret-random-token` | Bearer token for client authentication |
   | `DATABASE_URL` | *(Optional)* | Connect a Railway PostgreSQL plugin, or leave blank to use SQLite |
   | `REQUIRE_AUTH_FOR_READS` | `false` | Set `true` if you want dashboard reads to also require the token |

3. Attach storage:
   - **With PostgreSQL**: Click **+ New** $\rightarrow$ **Database** $\rightarrow$ **Add PostgreSQL**. Railway automatically populates `DATABASE_URL`.
   - **With SQLite**: Add a Railway Volume mounted to `/app/data` to persist data across deployments.

### Option B: Pre-configured Docker Deployment
The included `Dockerfile` and `railway.toml` are optimized with lightweight `python:3.12-slim`:
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"
healthcheckPath = "/health"
```

---

## 💻 Client CLI Reference

| Command | Description | Example |
|---|---|---|
| `python -m client.cli run` | Starts the active window tracker loop with optional CLI overrides | `python -m client.cli run --server-url http://localhost:8000 --api-token my-token` |
| `python -m client.cli probe` | Live console probe of window titles, idle seconds, and privacy tags | `python -m client.cli probe` |
| `python -m client.cli status` | Displays local buffer record counts and server health | `python -m client.cli status` |
| `python -m client.cli sync` | Manually triggers immediate sync of pending records | `python -m client.cli sync` |
| `python -m client.cli config` | Inspects current config or saves a default template | `python -m client.cli config --save-default config.json` |

---

## 📡 API Reference

### 1. Batch Ingest
`POST /api/v1/activities/batch`  
**Headers**: `Authorization: Bearer <API_KEY>`  
**Payload**:
```json
{
  "client_id": "laptop-thinkpad",
  "activities": [
    {
      "start_time": "2026-10-06T08:00:00Z",
      "end_time": "2026-10-06T08:30:00Z",
      "duration_seconds": 1800.0,
      "process_name": "code.exe",
      "window_title": "app.py - win-activity-tracker",
      "category": "Development",
      "is_idle": false
    }
  ]
}
```

### 2. Query Analytics Summary
`GET /api/v1/analytics/summary?date_from=2026-10-06&date_to=2026-10-07`  
Returns total tracked seconds, active work time, idle time, productivity score, top 10 applications, and category breakdown.

### 3. Hourly Activity Timeline
`GET /api/v1/analytics/timeline?date_from=2026-10-06&bucket_hours=1`  
Returns hourly bucketed active and idle durations for timeline graphing.

### 4. Health Check
`GET /health`  
Returns `{"status": "ok", "service": "...", "database": "ok", "timestamp": "..."}`.

---

## 🧪 Running Automated Tests

Run the complete test suite with edge cases:

```powershell
python -m pytest tests -v
```

All 43 tests cover:
- Win32 API monitoring, 64-bit safe ctypes declarations & tick overflow wrapping
- Privacy redactions (Vietnamese incognito, JWT tokens, credit cards, emails) & regex edge cases
- SQLite local buffer thread-safety & offline queueing
- Activity coalescing state machine, single-snapshot retention & screen lock idle handling
- Backend API authentication, full-day date filtering & UTC ISO normalization
- Active productivity score calculation & adaptive timeline bucket labeling
- Complete Client -> Buffer -> Offline -> Server Sync E2E workflow
