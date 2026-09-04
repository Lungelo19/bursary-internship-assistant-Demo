"""
Bursary and Internship Assistant - FastAPI backend.

Run with:

    uvicorn app.main:app --reload

Endpoints:

    GET  /bursaries?course=Computer+Science   -> list matching bursaries
    GET  /bursaries/{bursary_id}              -> full detail for one bursary
    POST /chat                                -> chatbot turn (needs LM Studio running)

The database is not scraped on startup (per project setup - scraping
is treated as a separate, occasional job). If data/bursaries.db is
missing, it's built once from the existing data/bursaries.json so the
API has something to serve.
"""

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bursary.database import DATABASE_FILE, import_bursaries, ensure_schema
from bursary.recommendation import (
    search_by_field,
    get_bursary_by_id,
    list_distinct_fields,
)
from bursary.chat_agent import run_chat_turn


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Build the SQLite database from the existing bursaries.json the
    first time the app starts, if it hasn't been built yet. This does
    NOT scrape - it only imports whatever is already in
    data/bursaries.json, which the scraping/processing pipeline
    populates separately and occasionally.
    """

    if not os.path.exists(DATABASE_FILE):
        import_bursaries()
    else:
        # Database already exists (e.g. shipped in data/bursaries.db) -
        # don't touch the rows, but make sure it has the current
        # indexes. Cheap and idempotent, safe to run every startup.
        ensure_schema()

    yield


app = FastAPI(title="Bursary and Internship Assistant", lifespan=lifespan)

# Adjust in production - this is wide open for local/demo use so the
# frontend can be served from any dev port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# IN-MEMORY CHAT SESSIONS
# =========================================================
# Prototype-level session store. Fine for a demo / single-instance
# deployment; swap for Redis or a DB table before scaling to multiple
# workers or long-lived production traffic.

CHAT_SESSIONS = {}


# =========================================================
# SCHEMAS
# =========================================================

class BursarySummary(BaseModel):
    id: int
    title: str
    fields_of_study: list[str]
    closing_date: str | None
    closing_status: str
    availability_status: str
    availability_label: str
    verified: bool
    application_url: str | None
    source: str
    source_url: str


class ChatRequest(BaseModel):
    course: str
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str


# =========================================================
# BURSARY ROUTES
# =========================================================

@app.get("/bursaries", response_model=list[BursarySummary])
def list_bursaries(course: str, include_expired: bool = False):
    """
    Search bursaries by course/field of study.

    Example: GET /bursaries?course=Computer%20Science
    """

    if not course.strip():
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'course' is required.",
        )

    results = search_by_field(course, include_expired=include_expired)

    # search_by_field returns extra keys (closing_dates list) that
    # don't belong in the summary response - BursarySummary already
    # filters this via response_model, so no extra work needed here.
    return results


@app.get("/bursaries/{bursary_id}")
def get_bursary(bursary_id: int):
    """
    Full detail for one bursary: eligibility, closing dates,
    application instructions, source.
    """

    bursary = get_bursary_by_id(bursary_id)

    if bursary is None:
        raise HTTPException(
            status_code=404,
            detail=f"No bursary found with id {bursary_id}",
        )

    return bursary


@app.get("/fields", response_model=list[str])
def list_fields():
    """
    Distinct fields of study across all bursaries, for search
    suggestion chips on the frontend (e.g. "Engineering",
    "Computer Science"). One indexed query, no per-bursary work.
    """

    return list_distinct_fields()


# =========================================================
# CHAT ROUTE
# =========================================================

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    One turn of the bursary chatbot.

    Pass the student's course and message. On the first call, omit
    session_id - one is created and returned; pass it back on
    subsequent calls so the conversation keeps context.

    Requires LM Studio to be running locally with the Bonsai model
    loaded and its local server started (see bursary/chat_agent.py).
    """

    if not request.message.strip():
        raise HTTPException(
            status_code=400, detail="Field 'message' cannot be empty."
        )

    session_id = request.session_id or str(uuid.uuid4())
    history = CHAT_SESSIONS.get(session_id, [])

    try:
        reply, updated_history = run_chat_turn(
            course=request.course,
            history=history,
            user_message=request.message,
        )
    except RuntimeError as e:
        # LM Studio unreachable / model not loaded, etc.
        raise HTTPException(status_code=503, detail=str(e))

    CHAT_SESSIONS[session_id] = updated_history

    return ChatResponse(session_id=session_id, reply=reply)


@app.get("/health")
def health():
    return {"status": "ok"}
