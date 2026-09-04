<div align="center">

# Bursary and Internship Assistant 🎓

[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Frontend](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Model](https://img.shields.io/badge/Chatbot-Bonsai%20(via%20LM%20Studio)-8A2BE2)](https://lmstudio.ai/)
[![Scraping](https://img.shields.io/badge/Scraping-BeautifulSoup4-3776AB?logo=python&logoColor=white)](https://www.crummy.com/software/BeautifulSoup/)
[![Status](https://img.shields.io/badge/Status-Prototype-yellow)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

**Bursary and Internship Assistant** *(noun)*: a system that finds, verifies, and explains bursary and internship opportunities for students, matched to what they're actually studying.

An AI-powered system that scrapes bursary and internship listings, stores them in a structured local database, and lets a student search by course and ask follow-up questions through a chatbot grounded in that data.

</div>

---

## 1. Project Summary

Students looking for bursaries and internships usually have to manually trawl aggregator sites, most of which bury real deadlines and eligibility rules inside long, inconsistently formatted articles. This project automates that process end to end:

1. **Scrape** bursary/internship listings from a source site.
2. **Process** each listing into structured fields — eligibility, fields of study, closing dates, application steps — instead of raw paragraph text.
3. **Store** everything in a local SQLite database.
4. **Serve** it through a FastAPI backend that a student's course can be matched against.
5. **Chat** — a locally-hosted LLM (Bonsai, via LM Studio) answers follow-up questions about the results, using tools that query the same database, falling back to a scoped web search only when the database genuinely doesn't have the answer.

The scraping/processing pipeline is intentionally decoupled from the live app — it's meant to be run occasionally (e.g. daily/weekly) to refresh `data/bursaries.json`, not on every request.

---

## 2. Components

### 2.1 Scraping (`bursary/scraper.py`, `bursary/detail_scraper.py`, `bursary/collector.py`)

- `scraper.py` — fetches the category listing page and extracts bursary/internship names and links, grouped by category (e.g. "Computer Science / IT").
- `detail_scraper.py` — the heavy lifting. Given one bursary's URL, it parses the article's headings and sections to pull out:
  - fields of study
  - eligibility requirements
  - closing date(s), including bursaries with multiple deadlines (e.g. bursary vs. internship track)
  - the original closing-date text, kept for reference
  - application instructions and the application URL
  - a `closing_status` classification (`date_available`, `multiple_dates_available`, `open_no_closing_date`, `date_not_confirmed`, `closed`) since not every listing states a clean date
- `collector.py` — orchestrates the two above: crawls each category, de-duplicates bursaries that appear under more than one category (merging their category lists instead of creating duplicates), and writes the result to `data/bursaries.json`.

This layer is **not** run automatically by the web app. It's a separate, occasional job you run manually when you want fresh data.

### 2.2 Processing / Storage (`bursary/database.py`)

- `create_tables()` — defines the SQLite schema: a main `bursaries` table plus normalized child tables (`fields_of_study`, `eligibility_requirements`, `closing_dates`, `closing_date_text`, `application_instructions`, `categories`), all foreign-keyed back to `bursaries` with `ON DELETE CASCADE`.
- `import_bursaries()` — reads `data/bursaries.json` and loads it into `data/bursaries.db`, clearing old data first so re-imports don't duplicate rows.

The FastAPI app calls this automatically on startup **only if `bursaries.db` doesn't exist yet** — it never re-scrapes or re-imports on its own after that.

### 2.3 Recommendation logic (`bursary/recommendation.py`)

- `search_by_field(course, include_expired=False)` — matches a student's course against `fields_of_study`, evaluates each result's real-world availability (has the closing date passed? are there multiple dates, and is at least one still open?), and sorts results so verified-open opportunities surface first.
- `get_bursary_by_id(id)` — returns one bursary's complete record: fields of study, eligibility, closing dates, application steps, source. Used by both the API and the chatbot's tools, so they can never disagree about a bursary's details.
- `evaluate_availability()` — the core logic that turns a stored `closing_status` + `closing_date` into a human-readable status (`verified_open`, `needs_verification`, `expired`, `closed`, `unknown`) rather than a blind yes/no.

### 2.4 API (`app/main.py`)

A FastAPI app exposing:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/bursaries?course=...` | Search bursaries by field of study |
| `GET` | `/bursaries/{id}` | Full detail for one bursary |
| `POST` | `/chat` | One turn of the chatbot conversation |
| `GET` | `/health` | Liveness check |

Also builds `bursaries.db` from `bursaries.json` on first startup if it doesn't exist yet, and holds chat sessions in an in-memory dict keyed by `session_id` (fine for a single-instance prototype; swap for a real store before scaling).

### 2.5 Chatbot (`bursary/chat_agent.py`)

Wires Bonsai (running locally through LM Studio's OpenAI-compatible server) up to three scoped tools:

- `search_bursaries_by_course` — queries our own database
- `get_bursary_detail` — queries our own database
- `web_search` — general web search (via `ddgs`), only meant for questions the database can't answer (e.g. "what is NSFAS")

Unlike a general-purpose coding agent, this bot **cannot** write files, edit code, or run arbitrary commands — it can only read the bursary database and, when needed, search the open web. The system prompt explicitly tells the model to prefer the database, never invent details like closing dates or eligibility, and say plainly when it's relying on the open web rather than verified data.

### 2.6 Frontend (`Frontend/bursary-recommender`)

A React app (Create React App) with three views:

- **Search** (`/`) — enter a course, see matching bursaries with availability status
- **Detail** (`/bursaries/:id`) — full eligibility, closing dates, and application steps for one bursary
- **Chat** (`/chat`) — course-scoped conversation with the backend chatbot

All API calls go through `src/api.js`, pointed at the FastAPI backend via `REACT_APP_API_BASE` (defaults to `http://127.0.0.1:8000`).

---

## 3. Tools Used

| Layer | Tool / Library |
|---|---|
| Scraping | `requests`, `beautifulsoup4` |
| Database | `sqlite3` (standard library) |
| Backend API | `fastapi`, `uvicorn`, `pydantic` |
| Chatbot model | [Bonsai](https://lmstudio.ai/) served locally through [LM Studio](https://lmstudio.ai/) |
| Chatbot client | `openai` Python SDK (pointed at LM Studio's local OpenAI-compatible endpoint) |
| Chatbot web search | `ddgs` (DuckDuckGo search) |
| Frontend | React, `react-router-dom` |
| Testing | `pytest`, FastAPI's `TestClient` |
| Language | Python 3.12, JavaScript (ES6+) |

---

## 4. How to Run the Project

### 4.1 Prerequisites

- Python 3.10+
- Node.js + npm
- [LM Studio](https://lmstudio.ai/) installed, with the Bonsai model downloaded

### 4.2 Backend

```bash
# from the project root (where app/, bursary/, data/ live)
pip install -r requirements.txt

python -m uvicorn app.main:app --reload
```

- Runs at `http://127.0.0.1:8000`
- On first run, builds `data/bursaries.db` from `data/bursaries.json` automatically
- Interactive API docs at `http://127.0.0.1:8000/docs` — useful for testing `POST /chat` directly, since a browser address bar can't send POST requests

### 4.3 Chatbot model (LM Studio)

1. Open LM Studio, load the Bonsai model.
2. Go to the **Developer** tab and start the local server (defaults to `http://localhost:1234`).
3. Leave it running — the backend's `/chat` endpoint calls it on demand. No LM Studio running yet? `/chat` returns a clean `503` rather than crashing, so the rest of the app still works.

Environment variables (optional, set before starting the backend) if your setup differs from the defaults:

```bash
LM_STUDIO_BASE_URL=http://localhost:1234/v1
BONSAI_MODEL_NAME=prism-ml/bonsai-27b
```

### 4.4 Frontend

```bash
cd Frontend/bursary-recommender
npm install
npm start
```

- Runs at `http://localhost:3000`
- Talks to the backend at `http://127.0.0.1:8000` by default (override with a `.env` file setting `REACT_APP_API_BASE`)

### 4.5 Refreshing bursary data (optional, occasional)

```bash
python -m bursary.collector      # scrapes and rewrites data/bursaries.json
python -m bursary.database       # re-imports data/bursaries.json into data/bursaries.db
```

Not required for day-to-day running of the app — only run this when you want to pull in new listings.

### 4.6 Tests

```bash
pytest tests/ -v
```

---

## 5. What Is Done

- ✅ Scraper + detail parser that turns messy bursary listing pages into structured records (fields of study, eligibility, closing dates, application steps)
- ✅ De-duplication across categories in the collector
- ✅ Normalized SQLite schema with foreign keys and cascade deletes
- ✅ Availability evaluation logic that distinguishes verified-open, needs-verification, expired, and closed opportunities
- ✅ `search_by_field` and `get_bursary_by_id` recommendation functions
- ✅ FastAPI backend with `/bursaries`, `/bursaries/{id}`, `/chat`, `/health`
- ✅ Auto-build of the database on first startup (without re-scraping)
- ✅ Chatbot tool layer scoped to the bursary database + limited web search, with a system prompt discouraging invented details
- ✅ Chat sessions with multi-turn history (in-memory)
- ✅ React frontend: course search page, bursary detail page, chat page
- ✅ Basic automated tests for the database layer and the API layer
- ✅ Verified end-to-end: `/bursaries`, `/bursaries/{id}` work fully; `/chat` confirmed working against a live LM Studio + Bonsai server, including a successful tool call

## 6. What Still Needs to Be Done

- ⬜ Confirm Bonsai reliably prefers `search_bursaries_by_course` / `get_bursary_detail` over `web_search` for questions the database can answer — needs more real-conversation testing, since smaller local models can be inconsistent about tool preference
- ⬜ Persistent chat session storage (currently in-memory — resets on every backend restart, and won't work with multiple server workers)
- ⬜ Frontend polish: loading states, error boundaries, mobile responsiveness, and a proper design pass (current styling is intentionally minimal/functional)
- ⬜ Multilingual support (listed as a project goal, not yet implemented anywhere in scraping, storage, or chat)
- ⬜ Fine-tuning a lightweight model (listed as a project goal — currently using Bonsai as-is with tool calling, no fine-tuning)
- ⬜ Semantic search / embeddings-based retrieval (currently `LIKE`-based field matching, which won't catch course names phrased differently from how they appear in a listing)
- ⬜ Broader source coverage — scraper currently targets one category page on one site; expanding to more categories/sources means generalizing `collector.py` beyond a single `CATEGORY_URL`
- ⬜ Scheduled/automated re-scraping (currently a manual, on-demand script)
- ⬜ Authentication/user accounts, if the product direction needs students to save searches or track applications
- ⬜ Deployment setup (Dockerfile, hosting, production CORS config, environment-based secrets) — everything so far has been built and tested for local development only
