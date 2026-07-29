# GhostHire

AI-powered role-based candidate screening. GhostHire runs a structured technical interview where every question is generated on the fly by a RAG pipeline that grounds the model in three inputs: the candidate's resume, the selected role, and a role-specific textbook knowledge base.

## Why this exists

Traditional interview systems fall back on templated question banks — the same "explain overfitting" for every ML candidate, regardless of what their resume says or how deep the underlying material actually goes. GhostHire replaces that with a retrieval-augmented pipeline: questions are pulled from a real textbook via semantic search, calibrated to what the candidate claims to know, and traceable back to the source chunks that grounded them.

## Setup

### Prerequisites

| Tool     | Version  | Install (macOS)             |
| -------- | -------- | --------------------------- |
| Node     | 22.x     | `brew install node`         |
| pnpm     | 11.x     | `brew install pnpm`         |
| Python   | 3.12     | `brew install python@3.12`  |
| uv       | 0.11.x   | `brew install uv`           |

### Bootstrap

```bash
# Frontend deps
cd web && pnpm install --frozen-lockfile

# Backend deps + venv
cd ../api && uv sync --frozen

# Local secrets — copy template and fill in
cp api/.env.example api/.env
# Required: ANTHROPIC_API_KEY (from console.anthropic.com)
# Optional overrides: DATABASE_URL, EMBED_BACKEND, CHROMA_DB_PATH

# Ingest a textbook (one-time, offline)
cd api && uv run python -m scripts.ingest --role ai_ml --book books/hundred-page-ml.pdf
```

### Environment variables

See `api/.env.example` for the complete list with per-variable documentation. `ANTHROPIC_API_KEY` is required — the app raises a validation error at startup if it's absent. `EMBED_BACKEND` defaults to `local`; **do not change it after running ingestion** (embedding-model mismatch — see [Design Decisions](#design-decisions)).

## Architecture

### File structure

```
GhostHire/
├── web/                    # Next.js 14 App Router (candidate-facing screens)
│   └── src/app/            # Upload, interview, summary
├── api/                    # FastAPI backend + RAG pipeline
│   ├── main.py             # FastAPI app instance
│   ├── settings.py         # Typed config via pydantic-settings
│   ├── db.py               # SQLModel engine + session dependency
│   ├── models.py           # 4 SQLModel tables
│   ├── routers/            # HTTP layer — thin, delegates to services
│   ├── services/           # Business logic — no framework imports
│   ├── rag/                # Ingestion, retrieval, generation (the RAG core)
│   ├── scripts/            # Offline CLI tools (ingest.py, test_retrieval.py)
│   ├── books/              # Source textbooks (gitignored — large PDFs)
│   └── chroma_db/          # ChromaDB persistence directory (gitignored)
└── docs/                   # Architecture diagram
```

### System diagram

```
┌──────────────────────────────────────────────────────────┐
│ Browser — upload + role select / interview / summary     │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTPS, REST
                             ▼
┌──────────────────────────────────────────────────────────┐
│ Next.js 14  (web/)                                       │
│  - App Router; RSC default; client opt-in                │
│  - TanStack Query for all interview-flow state           │
│  - shadcn/ui copy-paste components                       │
└────────────────────────────┬─────────────────────────────┘
                             │ REST
                             ▼
┌──────────────────────────────────────────────────────────┐
│ FastAPI  (api/)                                          │
│  routers/ → services/ → rag/                             │
│  - session orchestration, pipeline coordination          │
│  - pydantic-settings typed config                        │
└──┬───────────────────────┬──────────────────────────────┬┘
   │                       │                              │
   ▼                       ▼                              ▼
┌────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ ChromaDB   │   │ LLM (Anthropic)      │   │ Postgres / SQLite    │
│ textbook   │   │ question generation  │   │ sessions, questions, │
│ chunks     │   │ + answer scoring     │   │ answers, documents   │
└────────────┘   └──────────────────────┘   └──────────────────────┘
```

*A polished diagram lands in `docs/architecture.pdf` before submission.*

### Tech stack

| Layer            | Pick                                           | Why                                                                     |
| ---------------- | ---------------------------------------------- | ----------------------------------------------------------------------- |
| Backend          | FastAPI + SQLModel                             | Async fits LLM-heavy load; one class serves as DB row + API schema     |
| RAG framework    | LlamaIndex                                     | Purpose-built for ingest → chunk → embed → retrieve                     |
| Vector store     | ChromaDB (embedded, disk-persisted)            | Zero infra; would move to Qdrant/pgvector at scale                      |
| Embeddings       | `BAAI/bge-small-en-v1.5` (local)               | See [Design Decisions](#design-decisions)                               |
| LLM              | Anthropic Claude Sonnet                        | Strong reasoning for grounded question generation + answer scoring      |
| Resume parse     | pdfplumber + LLM extraction                    | More format-robust than named-entity recognition                        |
| Frontend         | Next.js 14 + TypeScript + Tailwind + shadcn/ui | Fast to compose four clean screens                                      |
| Frontend state   | TanStack Query                                 | Multi-step interview flow needs cache + coordination                    |
| Database         | SQLite (local) / Postgres via Neon (prod path) | See [Design Decisions](#design-decisions)                               |

### The two pipelines

The system runs on two conceptually distinct code paths — worth naming explicitly because conflating them is the most common source of design confusion for retrieval systems.

**Ingestion pipeline** (offline, one-time per textbook, via `scripts/ingest.py`):

```
textbook PDF → extract text → chunk → embed → store in ChromaDB
```

Never triggered by a live user request. Populates the vector store before any interview runs.

**Live request pipeline** (per candidate, runtime):

```
resume + role → parse → build queries → retrieve chunks
→ generate question → serve → store answer → (score → adapt difficulty) → next → summary
```

### Layered backend

`routers/` handle only HTTP concerns — parse the request, inject dependencies, shape the response, translate exceptions. `services/` hold business logic and carry zero framework imports (fully testable in pure Python without spinning up an HTTP client). `rag/` isolates ingestion, retrieval, and generation from web concerns entirely — the same modules power `scripts/ingest.py` and any future batch tools. The seam between the three layers is where most future changes land (swap the vector store, swap the LLM, add a background job) without cascading through the codebase.

## Running the app

```bash
# Backend (from api/)
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
# → curl http://127.0.0.1:8000/health  returns {"status":"ok"}
# → Swagger UI at http://127.0.0.1:8000/docs

# Frontend (from web/)
pnpm dev
# → http://localhost:3000

# One-time offline ingestion (from api/)
uv run python -m scripts.ingest --role ai_ml --book books/hundred-page-ml.pdf
```

## Data model

Four tables, defined together in `api/models.py`:

| Table       | Purpose                     | Notable columns                                                                                                              |
| ----------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `sessions`  | One interview per row       | `role`, `resume_text`, `resume_skills` (JSON: skills / technologies / domains), `status` enum                                |
| `questions` | Every generated question    | FK `session_id`, **`source_chunk_ids` (JSON — traceability to the retrieved chunks)**, `difficulty`, `topic`, `order_index` |
| `answers`   | Candidate responses         | FK `question_id`, `score` + `score_rationale` (optional scoring)                                                             |
| `documents` | Ingested corpus metadata    | `role`, `title`, `chunk_count`, `ingested_at`. Actual chunks + embeddings live in ChromaDB, not here.                        |

The `source_chunk_ids` field on `questions` is the traceability contract: for any generated question, you can look up exactly which textbook passages grounded it. This makes the RAG pipeline auditable end-to-end rather than a black box.

## Design decisions

### Embedding backend: local (`BAAI/bge-small-en-v1.5` via sentence-transformers)

Chosen over OpenAI's `text-embedding-3-small` for two reasons. First, zero API cost during iteration — the ingestion pipeline reruns as chunking parameters get tuned, and paying per-token across ~500 chunks × N iterations adds up quickly. Second, offline reproducibility — no network dependency at ingestion means the pipeline is deterministic across machines, which matters for demos and for anyone who wants to reproduce the corpus.

The cost: local embeddings trail OpenAI on retrieval benchmarks (MTEB) by roughly 35%. That gap is accepted for a system where architectural clarity is being evaluated more heavily than absolute top-line scores. Production would flip to `text-embedding-3-small` — but critically, only after re-ingesting the corpus. Vectors from different embedding models live in incompatible geometric spaces; comparing them either errors out on dimension mismatch (loud, easy to catch) or silently returns nonsense chunks (quiet, catastrophic). The warning is captured in-line in `api/.env.example` so future edits to `EMBED_BACKEND` hit it at exactly the moment they'd matter.

### Chunking strategy

<!-- Captured when the chunking pipeline lands. -->

### Retrieval strategy

<!-- Captured when retrieval and the sanity check land. Covers top-k value, whether reranking is applied, and how queries are built from resume + role. -->

### Grounding & generation

<!-- Captured when question generation lands. Covers how the generation prompt forces questions to come from retrieved context rather than model priors. -->

### Answer scoring

<!-- Captured when scoring lands (bonus feature). Covers how answers are evaluated against retrieved context to produce a score + rationale. -->

## Production-scale changes

Local-first choices that would need rethinking at scale:

- **Vector store swap.** ChromaDB embedded assumes a single writer process (SQLite serializes writes). Concurrent ingestion or multi-process serving would move to Qdrant or pgvector — both handle concurrent writes and horizontal scale-out cleanly, and the `rag/` layer's separation from web concerns means the swap is contained.
- **Database.** SQLite via SQLModel is fine for one candidate at a time; Postgres (Neon) becomes essential the moment multiple interview sessions run concurrently.
- **LLM call cost + latency.** Every interview burns roughly 5–15 Anthropic calls (question generation + answer scoring). Response caching for identical retrieval queries, plus streaming responses to the browser, would be the first two levers pulled.
- **Ingestion throughput.** The current CLI is single-threaded. At scale, chunk-batch parallelism for embedding, plus a job queue for triggering re-ingestions when new textbooks land, moves the pipeline from "run once locally" to "run on demand."
- **Observability.** Structured logging, per-request tracing (OpenTelemetry), and per-retrieval-call metrics (chunks returned, similarity distribution, LLM latency) become non-optional once the system serves more than the demo.

These are staged expansions of the current architecture rather than rewrites — the layering (`routers/` → `services/` → `rag/`) is already the seam along which most of these swaps happen.
