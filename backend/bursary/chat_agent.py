"""
Chat agent for the Bursary and Internship Assistant.

This talks to a local LM Studio server running Bonsai (or any other
OpenAI-tool-calling-compatible model) and gives it a *scoped* set of
tools:

    - search_bursaries_by_course : look up bursaries in OUR database
    - get_bursary_detail         : full detail for one bursary from OUR database
    - web_search                 : general web search, for questions the
                                    database can't answer (e.g. "what is
                                    a NSFAS loan", "does this company have
                                    other graduate programmes")

Unlike a general coding agent, this bot cannot write or edit files, run
code, or fetch arbitrary URLs. It only reads our bursary data and, when
that's not enough, searches the web for context. That keeps it aligned
with its actual job: answering a student's questions about the bursary
information the system already surfaced for them, for their course.
"""

import json
import os

from openai import OpenAI, APIError, APIConnectionError

from bursary.recommendation import search_by_field, get_bursary_by_id

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


# =========================================================
# LM STUDIO CLIENT
# =========================================================

LM_STUDIO_BASE_URL = os.environ.get(
    "LM_STUDIO_BASE_URL",
    "http://localhost:1234/v1"
)

MODEL_NAME = os.environ.get(
    "BONSAI_MODEL_NAME",
    "prism-ml/bonsai-27b"
)

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key="lm-studio"
)


# =========================================================
# TOOL IMPLEMENTATIONS
# =========================================================

def search_bursaries_by_course(course, include_expired=False):
    """
    Search our own bursary database for opportunities
    related to a field/course of study.
    """

    results = search_by_field(
        course,
        include_expired=include_expired
    )

    # Trim to what the model actually needs per result,
    # full detail is available via get_bursary_detail.
    trimmed = [
        {
            "id": bursary["id"],
            "title": bursary["title"],
            "fields_of_study": bursary["fields_of_study"],
            "availability_status": bursary["availability_status"],
            "availability_label": bursary["availability_label"],
            "closing_date": bursary["closing_date"],
        }
        for bursary in results
    ]

    return json.dumps(trimmed)


def get_bursary_detail(bursary_id):
    """
    Get full detail for one bursary from our database,
    by id.
    """

    bursary = get_bursary_by_id(bursary_id)

    if bursary is None:
        return json.dumps(
            {"error": f"No bursary found with id {bursary_id}"}
        )

    return json.dumps(bursary)


def web_search(query, max_results=5):
    """
    General web search, for questions our bursary database
    can't answer directly.
    """

    if DDGS is None:
        return json.dumps(
            {"error": "web search is not available in this environment"}
        )

    results = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title"),
                    "url": r.get("href"),
                    "snippet": r.get("body"),
                }
            )

    return json.dumps(results)


TOOL_FUNCTIONS = {
    "search_bursaries_by_course": search_bursaries_by_course,
    "get_bursary_detail": get_bursary_detail,
    "web_search": web_search,
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_bursaries_by_course",
            "description": (
                "Search our bursary database for opportunities related "
                "to a field or course of study, e.g. 'Computer Science' "
                "or 'Mechanical Engineering'. Returns a short list "
                "(id, title, fields of study, availability). Use "
                "get_bursary_detail to get full information on any "
                "specific result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course": {
                        "type": "string",
                        "description": "Field/course of study to search for",
                    },
                    "include_expired": {
                        "type": "boolean",
                        "description": (
                            "Set true only if the student explicitly "
                            "asks about closed/expired bursaries too. "
                            "Defaults to false."
                        ),
                    },
                },
                "required": ["course"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bursary_detail",
            "description": (
                "Get full detail for one bursary from our database by "
                "id: eligibility requirements, closing dates, application "
                "instructions, application URL, and source. Use this "
                "before answering specific questions about a bursary "
                "found via search_bursaries_by_course."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bursary_id": {
                        "type": "integer",
                        "description": "The bursary's id",
                    },
                },
                "required": ["bursary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the open web. Only use this for questions our "
                "bursary database cannot answer, e.g. general funding "
                "concepts (what is NSFAS), background on a sponsoring "
                "company, or bursaries/internships not yet in our "
                "database. Do not use it to answer questions about a "
                "bursary already found via search_bursaries_by_course "
                "or get_bursary_detail — use our own data for those."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {
                        "type": "integer",
                        "description": "Defaults to 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


SYSTEM_PROMPT_TEMPLATE = (
    "You are the Bursary and Internship Assistant, helping a student "
    "studying {course} understand bursary and internship opportunities.\n\n"
    "Ground rules:\n"
    "- Always prefer search_bursaries_by_course and get_bursary_detail "
    "over web_search or your own memory: they read our verified database.\n"
    "- Only use web_search for questions our database can't answer "
    "(general funding concepts, background on a company, opportunities "
    "not yet in our database). Say clearly when information comes from "
    "the open web rather than our database, since it hasn't been "
    "verified the same way.\n"
    "- Never invent a closing date, eligibility requirement, or "
    "application URL. If a detail isn't in the tool results, say it "
    "isn't confirmed and point the student to the source_url to check.\n"
    "- Keep answers short and student-friendly. Use plain language, "
    "avoid jargon.\n"
    "- If nothing matches the student's course, say so plainly rather "
    "than stretching a loosely related result to fit.\n"
    "- Formatting: use light markdown so the chat UI can render it - "
    "**bold** a bursary's name the first time you mention it, and use "
    "'- ' bullet lines when listing more than one bursary or more "
    "than one requirement. Don't use headings or tables. Write plain "
    "closing dates and URLs as-is; the UI turns them into links."
)


# =========================================================
# MODEL CALL
# =========================================================

def _call_model(messages, retries=2, backoff_seconds=3):
    """
    Call LM Studio with a couple of retries, mirroring the resilience
    of the original local agent script (the local server can fail
    transiently under load or mid model-reload).
    """

    import time

    last_error = None

    for attempt in range(1, retries + 2):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
            )
            return response.choices[0].message

        except (APIError, APIConnectionError) as e:
            last_error = e
            if attempt <= retries:
                time.sleep(backoff_seconds)

    raise RuntimeError(
        "LM Studio did not respond after retrying. Check that LM "
        f"Studio is running with {MODEL_NAME} loaded and the local "
        f"server started at {LM_STUDIO_BASE_URL}. "
        f"Last error: {last_error}"
    )


def _message_to_dict(message):
    """
    Convert an OpenAI ChatCompletionMessage into a plain dict before
    it goes into `messages`/CHAT_SESSIONS.

    Two reasons this matters instead of storing the SDK object
    directly: it keeps every entry in the session history the same
    shape (plain dict, matching the user/tool messages already being
    appended), and it's what makes CHAT_SESSIONS safe to serialize
    later if the in-memory store gets swapped for Redis or a DB
    table, per the note in app/main.py.
    """

    return message.model_dump(exclude_none=True)


def _clean_reply_text(content):
    """
    Normalize the model's final answer before it's sent to the
    frontend: guard against None/empty content (the model can return
    an empty string after a tool round it considers "done"), and trim
    stray whitespace so chat bubbles don't render with dangling
    blank lines.
    """

    if not content or not content.strip():
        return (
            "I don't have a clear answer for that yet - could you "
            "rephrase, or ask about a specific bursary?"
        )

    return content.strip()


def _run_tool_calls(message, messages):
    """
    Execute every tool call attached to a model message and append
    the results to the running message list.
    """

    for tool_call in message.tool_calls:
        name = tool_call.function.name

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}

        fn = TOOL_FUNCTIONS.get(name)

        if fn is None:
            result = json.dumps({"error": f"Unknown tool: {name}"})
        else:
            try:
                result = fn(**args)
            except Exception as e:
                result = json.dumps({"error": str(e)})

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result),
            }
        )


# =========================================================
# PUBLIC ENTRY POINT
# =========================================================

def run_chat_turn(course, history, user_message, max_tool_turns=6):
    """
    Run one user turn of the conversation.

    `history` is a list of OpenAI-style chat messages from earlier in
    the session (may be empty on the first call). This function
    appends the new user message, lets the model call tools as many
    times as it needs (bounded by max_tool_turns), and returns:

        (reply_text, updated_history)

    `updated_history` should be passed back in on the next call so the
    conversation carries context across turns.
    """

    messages = list(history)

    if not messages:
        messages.append(
            {
                "role": "system",
                "content": SYSTEM_PROMPT_TEMPLATE.format(course=course),
            }
        )

    messages.append({"role": "user", "content": user_message})

    for _ in range(max_tool_turns):
        message = _call_model(messages)

        if not message.tool_calls:
            reply = _clean_reply_text(message.content)
            messages.append({"role": "assistant", "content": reply})
            return reply, messages

        # Store the assistant message (including its tool_calls) so
        # the tool results that follow have something to respond to.
        # Stored as a plain dict (see _message_to_dict) rather than
        # the raw SDK object, so every entry in `messages` is the
        # same shape.
        messages.append(_message_to_dict(message))
        _run_tool_calls(message, messages)

    fallback = (
        "I wasn't able to finish looking that up in time. Could you "
        "try asking again, maybe a bit more specifically?"
    )
    messages.append({"role": "assistant", "content": fallback})
    return fallback, messages
