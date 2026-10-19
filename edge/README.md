# RescuNet Edge Gateway

Lightweight local emergency packet ingestion, queue management, and synchronization layer.

## Setup

```bash
cd edge
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8001
```

The edge gateway starts at `http://127.0.0.1:8001`.

- Swagger UI: http://127.0.0.1:8001/docs
- ReDoc: http://127.0.0.1:8001/redoc

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8000` | URL of the main RescuNet backend |
| `EDGE_PORT` | `8001` | Port for the edge gateway |
| `SYNC_MAX_ATTEMPTS` | `5` | Max sync retries before skipping |
| `SYNC_TIMEOUT_SECONDS` | `10.0` | HTTP timeout for sync requests |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/edge/incidents` | Receive a local SOS packet |
| GET | `/edge/queue` | View queued packets (optional `?status=` filter) |
| GET | `/edge/connectivity` | Check connectivity status |
| POST | `/edge/connectivity` | Toggle ONLINE/OFFLINE mode |
| POST | `/edge/sync` | Trigger synchronization |
| GET | `/` | API information |
| GET | `/health` | Health check |

## Architecture

```
Citizen / Local Client
          │
          ▼
┌──────────────────────────────┐
│      RESCUNET EDGE           │
│                              │
│  Receive SOS                 │
│       ↓                      │
│  Validate packet             │
│       ↓                      │
│  Store locally               │
│       ↓                      │
│  status = QUEUED             │
└──────────────┬───────────────┘
               │
               ▼
       Local SQLite Queue
               │
               │ (when ONLINE + sync triggered)
               ▼
        FastAPI Backend (port 8000)
```

## Demo Flow

### Offline Mode
1. Set connectivity to OFFLINE
2. Submit SOS packets — they queue locally
3. Restart the edge gateway — packets persist

### Online Mode
1. Set connectivity to ONLINE
2. Trigger sync — packets sent to backend
3. Backend stores incidents with RSN- IDs
4. Edge queue shows SYNCED status

### Failure Handling
1. Submit packets while backend is down
2. Trigger sync — packets marked FAILED
3. Backend comes back online
4. Retry sync — packets sync successfully

## Testing

```bash
pip install pytest pytest-httpserver
pytest tests/ -v
```

## Project Structure

```
edge/
├── app/
│   ├── main.py              # FastAPI app with all endpoints
│   ├── models.py            # Pydantic models
│   ├── database.py          # SQLite connection & schema
│   ├── queue.py             # Queue management operations
│   ├── sync.py              # Synchronization engine
│   └── config.py            # Configuration from env vars
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_queue.py        # Queue operation tests
│   ├── test_sync.py         # Sync engine tests
│   └── test_edge_api.py     # API endpoint tests
├── data/
│   └── edge_queue.db        # SQLite queue (auto-created)
├── requirements.txt
└── README.md
```
