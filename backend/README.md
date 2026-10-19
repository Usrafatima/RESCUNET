# RescuNet Backend

AI-powered community emergency coordination system — FastAPI backend.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`.

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| POST | `/api/incidents` | Create a new incident |
| GET | `/api/incidents` | List all incidents |
| GET | `/api/incidents/{id}` | Get a specific incident |
| PATCH | `/api/incidents/{id}/status` | Update incident status |

## Incident Statuses

`queued` → `processing` → `awaiting_approval` → `approved` → `dispatched` → `resolved`

Also: `cancelled` (at any point)

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLite connection & schema
│   ├── models/
│   │   └── incident.py      # Pydantic models
│   ├── routes/
│   │   └── incidents.py     # API route handlers
│   └── services/
│       └── incident_service.py  # Business logic & DB operations
├── tests/
│   ├── conftest.py          # Test fixtures
│   └── test_api.py          # API tests
├── data/
│   └── rescunet.db          # SQLite database (auto-created)
├── requirements.txt
└── README.md
```

## Architecture

```
Citizen UI
     ↓
FastAPI
     ↓
Local/Edge Queue
     ↓
Strands Agent (future)
     ↓
Incident Analysis
     ↓
Resource Matching
     ↓
Response Recommendation
     ↓
Human Approval
     ↓
Dispatch
```
