# JURISCAN-AI

AI-powered legal document scanning and analysis tool.

Phases 1–3 (environment, frontend foundation, backend/database) are implemented.
Document processing, OCR and the Legal-BERT analysis pipeline are planned for later phases.

## Project Structure

```
JURISCAN-AI/
├── frontend/     # React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui
├── backend/      # FastAPI + SQLAlchemy + Alembic (Python venv at backend/.venv)
├── data/         # Datasets and local dev databases (gitignored)
├── models/       # Trained ML models (later phases)
├── scripts/      # Utility and automation scripts (later phases)
├── tests/        # Reserved for cross-cutting tests (backend tests live in backend/tests)
├── docs/         # Documentation (later phases)
└── docker/       # Docker configuration (later phases)
```

## Prerequisites

- Node.js 20.19+ and npm 10+
- Python 3.12+
- PostgreSQL 14+ (or a Docker Postgres instance)

## Getting Started

1. Copy `.env.example` to `.env` and fill in your database settings.
2. Run the migrations (see backend section).
3. Start the backend and frontend.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- Status (incl. database): http://localhost:8000/api/status

Tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server runs at http://localhost:5173. Configure the backend URL via
`VITE_API_BASE_URL` (see `frontend/.env.development` / `.env.example`).

Build / lint:

```powershell
npm run build
npm run lint
```

## License

Add license information here.
