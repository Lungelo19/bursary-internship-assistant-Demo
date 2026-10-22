"""
PathwaySA FastAPI Backend

Run with:

    uvicorn app.main:app --reload

Main endpoints:

    Authentication
    --------------
    POST /auth/register
    POST /auth/login
    GET  /auth/me

    Student Profile
    ---------------
    GET  /profile/me
    PUT  /profile/me

    Programmes
    ----------
    GET  /programmes
    GET  /programmes/{offering_id}
    GET  /programmes/institutions
    GET  /programmes/campuses
    GET  /programmes/career-directions
    GET  /programmes/study-levels
    POST /programmes/recommend

    Funding
    -------
    GET  /bursaries?course=Computer+Science
    GET  /bursaries/{bursary_id}
    GET  /fields

    AI Assistant
    ------------
    POST /chat

The bursary database is not scraped on startup.

If data/bursaries.db does not exist, it is built from the existing
data/bursaries.json file.

The AI chat endpoint requires authentication and uses the authenticated
student's user ID when executing personalised programme, profile and
funding tools.
"""

import os
import uuid
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from accounts.routes import (
    auth_router,
    get_current_user,
    profile_router,
)

from bursary.chat_agent import run_chat_turn

from bursary.database import (
    DATABASE_FILE,
    ensure_schema,
    import_bursaries,
)

from bursary.recommendation import (
    get_bursary_by_id,
    list_distinct_fields,
    search_by_field,
)

from programmes.routes import (
    router as programmes_router,
)


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise the existing bursary database when necessary.

    This does NOT scrape websites.

    If bursaries.db does not yet exist, the existing processed
    bursaries.json file is imported.

    If the database already exists, only the schema/indexes are
    checked.
    """

    if not os.path.exists(DATABASE_FILE):
        import_bursaries()

    else:
        ensure_schema()

    yield


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="PathwaySA API",
    description=(
        "Backend API for PathwaySA, a South African "
        "higher-education journey companion."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# =========================================================
# ROUTERS
# =========================================================

# Programme discovery and recommendation.
app.include_router(
    programmes_router
)

# User authentication.
app.include_router(
    auth_router
)

# Student profile.
app.include_router(
    profile_router
)


# =========================================================
# CORS
# =========================================================

# Wide-open CORS is acceptable for the current local/demo
# environment.
#
# Restrict origins before production deployment.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# IN-MEMORY CHAT SESSIONS
# =========================================================

# Prototype session store.
#
# The key contains:
#
#     (authenticated_user_id, session_id)
#
# This prevents one authenticated student's session history from
# accidentally being reused by another student.
#
# Replace this with Redis/database storage before deploying
# multiple backend workers or requiring persistent chat history.

CHAT_SESSIONS = {}


# =========================================================
# API SCHEMAS
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
    """
    Request for one PathwaySA assistant conversation turn.

    course is optional because the authenticated student's saved
    profile can provide their interests when necessary.
    """

    course: str | None = None
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str


# =========================================================
# BURSARY ROUTES
# =========================================================

@app.get(
    "/bursaries",
    response_model=list[BursarySummary],
)
def list_bursaries(
    course: str,
    include_expired: bool = False,
):
    """
    Search bursaries by course or field of study.

    Example:

        GET /bursaries?course=Computer%20Science
    """

    if not course.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "Query parameter 'course' "
                "is required."
            ),
        )

    results = search_by_field(
        course,
        include_expired=include_expired,
    )

    return results


@app.get(
    "/bursaries/{bursary_id}"
)
def get_bursary(
    bursary_id: int,
):
    """
    Retrieve complete information about one bursary.
    """

    bursary = get_bursary_by_id(
        bursary_id
    )

    if bursary is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No bursary found "
                f"with id {bursary_id}"
            ),
        )

    return bursary


@app.get(
    "/fields",
    response_model=list[str],
)
def list_fields():
    """
    Return distinct bursary fields of study.

    Useful for frontend search suggestions/chips.
    """

    return list_distinct_fields()


# =========================================================
# AUTHENTICATED AI CHAT ROUTE
# =========================================================

@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    current_user=Depends(
        get_current_user
    ),
):
    """
    Run one authenticated PathwaySA assistant conversation turn.

    Authentication
    --------------

    The request must contain:

        Authorization: Bearer <JWT>

    The authenticated user's ID is obtained from the JWT.

    The client does NOT send a user_id.

    This user ID is passed internally to the AI tool layer so that
    personalised programme and funding tools can safely access the
    correct student's saved profile.

    Conversation Sessions
    ---------------------

    On the first request, session_id may be omitted.

    PathwaySA creates and returns one.

    Subsequent requests should send the same session_id to retain
    recent conversational context.
    """

    # -----------------------------------------------------
    # VALIDATE MESSAGE
    # -----------------------------------------------------

    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "Field 'message' cannot be empty."
            ),
        )

    # -----------------------------------------------------
    # IDENTIFY AUTHENTICATED STUDENT
    # -----------------------------------------------------

    user_id = current_user["id"]

    # -----------------------------------------------------
    # CHAT SESSION
    # -----------------------------------------------------

    session_id = (
        request.session_id
        or str(uuid.uuid4())
    )

    # Bind chat history to BOTH the authenticated user and
    # conversation session.
    session_key = (
        user_id,
        session_id,
    )

    history = CHAT_SESSIONS.get(
        session_key,
        [],
    )

    # -----------------------------------------------------
    # RUN PATHWAYSA AI AGENT
    # -----------------------------------------------------

    try:
        (
            reply,
            updated_history,
        ) = run_chat_turn(
            course=request.course,
            history=history,
            user_message=request.message,
            user_id=user_id,
        )

    except RuntimeError as error:
        # Examples:
        # - LM Studio unavailable
        # - configured model not loaded
        # - local model server failure
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    # -----------------------------------------------------
    # SAVE CHAT HISTORY
    # -----------------------------------------------------

    CHAT_SESSIONS[
        session_key
    ] = updated_history

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return ChatResponse(
        session_id=session_id,
        reply=reply,
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    """
    Simple backend health check.
    """

    return {
        "status": "ok",
        "service": "PathwaySA API",
    }