"""
Chat agent for the Bursary and Internship Assistant.

Flow:

    User message
        ↓
    Google Translation
        ↓
    English
        ↓
    Qwen via LM Studio
        ↓
    Database / Tools
        ↓
    English response
        ↓
    Google Translation
        ↓
    User response

The agent also limits database search results before sending them
to Qwen so large result sets do not exceed the model context window.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError

from bursary.recommendation import search_by_field, get_bursary_by_id
from bursary.translation import translate_to_english, translate_from_english

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


# =========================================================
# ENVIRONMENT
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)


# =========================================================
# SETTINGS
# =========================================================

LM_STUDIO_BASE_URL = os.environ.get(
    "LM_STUDIO_BASE_URL",
    "http://localhost:1234/v1"
).strip()

LM_STUDIO_API_KEY = os.environ.get(
    "LM_STUDIO_API_KEY",
    "lm-studio"
).strip()

MODEL_NAME = os.environ.get(
    "BONSAI_MODEL_NAME",
    "qwen2.5-7b-instruct"
).strip()


# Maximum number of previous user turns sent back to Qwen.
MAX_HISTORY_USER_TURNS = 4

# Maximum number of bursaries returned from one search.
MAX_SEARCH_RESULTS = 7


client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key=LM_STUDIO_API_KEY
)


# =========================================================
# TOOL IMPLEMENTATIONS
# =========================================================

def search_bursaries_by_course(
    course,
    include_expired=False,
    limit=MAX_SEARCH_RESULTS
):
    """
    Search the bursary database for opportunities related
    to a field or course of study.

    search_by_field() performs the course matching and
    availability/date filtering first.

    Only a limited number of results are then returned to Qwen
    to prevent large database results from filling the model's
    context window.
    """

    # -----------------------------------------------------
    # 1. SEARCH + AVAILABILITY FILTERING
    # -----------------------------------------------------

    results = search_by_field(
        course,
        include_expired=include_expired
    )

    total_matches = len(results)

    # -----------------------------------------------------
    # 2. LIMIT RESULTS SENT TO QWEN
    # -----------------------------------------------------

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = MAX_SEARCH_RESULTS

    # Never allow this tool to return more than 5 results.
    limit = max(1, min(limit, MAX_SEARCH_RESULTS))

    selected_results = results[:limit]

    # -----------------------------------------------------
    # 3. RETURN ONLY INFORMATION QWEN NEEDS
    # -----------------------------------------------------

    bursaries = [
        {
            "id": bursary["id"],
            "title": bursary["title"],
            "availability_status": bursary["availability_status"],
            "availability_label": bursary["availability_label"],
            "closing_date": bursary["closing_date"],
        }
        for bursary in selected_results
    ]

    return json.dumps({
        "total_matches": total_matches,
        "returned": len(bursaries),
        "bursaries": bursaries,
    })


def get_bursary_detail(bursary_id):
    """
    Retrieve full information for one bursary from the database.
    """

    bursary = get_bursary_by_id(bursary_id)

    if bursary is None:
        return json.dumps({
            "error": f"No bursary found with id {bursary_id}"
        })

    return json.dumps(bursary)


def web_search(query, max_results=5):
    """
    Search the open web when the local bursary database
    cannot answer the question.
    """

    if DDGS is None:
        return json.dumps({
            "error": "Web search is not available in this environment."
        })

    results = []

    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title"),
                    "url": result.get("href"),
                    "snippet": result.get("body"),
                })

    except Exception as error:
        return json.dumps({
            "error": str(error)
        })

    return json.dumps(results)


# =========================================================
# TOOL FUNCTION MAP
# =========================================================

TOOL_FUNCTIONS = {
    "search_bursaries_by_course": search_bursaries_by_course,
    "get_bursary_detail": get_bursary_detail,
    "web_search": web_search,
}


# =========================================================
# TOOL DEFINITIONS FOR QWEN
# =========================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_bursaries_by_course",
            "description": (
                "Search the local bursary database for currently relevant "
                "opportunities related to a field or course of study. "
                "The search returns at most 5 bursaries to keep responses "
                "short and prevent excessive model context usage. "
                "Use get_bursary_detail if more information about a "
                "specific bursary is required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course": {
                        "type": "string",
                        "description": (
                            "Field or course of study, for example "
                            "'Computer Science' or 'Data Science'."
                        ),
                    },
                    "include_expired": {
                        "type": "boolean",
                        "description": (
                            "Set true only if the student explicitly asks "
                            "for closed or expired bursaries."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Number of results to return. "
                            "Maximum allowed value is 5."
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
                "Retrieve complete information about one bursary from "
                "the local database using its ID. This includes eligibility "
                "requirements, closing dates, application instructions, "
                "application URL and source information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bursary_id": {
                        "type": "integer",
                        "description": "The bursary ID.",
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
                "Search the open web only when the local bursary database "
                "cannot answer the question. Examples include general "
                "funding concepts, information about an organisation, or "
                "opportunities not yet stored in our database."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_TEMPLATE = (
    "You are the Bursary and Internship Assistant, helping a student "
    "studying {course} understand bursary and internship opportunities.\n\n"

    "Ground rules:\n"

    "- Always prefer search_bursaries_by_course and get_bursary_detail "
    "over web_search or your own memory because these tools use our "
    "bursary database.\n"

    "- search_bursaries_by_course may report that more matches exist than "
    "were returned. Only discuss the bursaries actually included in the "
    "tool result.\n"

    "- Use get_bursary_detail when the student asks for eligibility, "
    "application instructions, application links or detailed information "
    "about a specific bursary.\n"

    "- Only use web_search when the local database cannot answer the "
    "question. Clearly tell the student when information comes from "
    "the open web rather than our database.\n"

    "- Never invent closing dates, eligibility requirements, application "
    "URLs or other bursary information. If information is missing, say "
    "that it is not confirmed.\n"

    "- Keep answers short, clear and student-friendly.\n"

    "- If nothing matches the student's course, say so rather than "
    "stretching an unrelated bursary to fit.\n"

    "- Always respond in English internally. The translation layer "
    "handles translation between English and the user's language.\n"

    "- Use light markdown. Bold a bursary's name the first time it is "
    "mentioned and use bullet points when listing multiple bursaries "
    "or requirements. Do not use tables or large headings."
)


# =========================================================
# HISTORY MANAGEMENT
# =========================================================

def _trim_history(history, max_user_turns=MAX_HISTORY_USER_TURNS):
    """
    Keep the system message and only the most recent user turns
    when sending conversation history back to Qwen.

    Complete turns are preserved so tool calls and tool results
    do not become separated.
    """

    if not history:
        return []

    system_message = None
    turns = []
    current_turn = []

    for message in history:
        role = message.get("role")

        if role == "system":
            if system_message is None:
                system_message = message
            continue

        if role == "user":
            if current_turn:
                turns.append(current_turn)

            current_turn = [message]
            continue

        if current_turn:
            current_turn.append(message)

    if current_turn:
        turns.append(current_turn)

    recent_turns = turns[-max_user_turns:]

    trimmed_history = []

    if system_message:
        trimmed_history.append(system_message)

    for turn in recent_turns:
        trimmed_history.extend(turn)

    return trimmed_history


# =========================================================
# MODEL CALL
# =========================================================

def _call_model(messages, retries=2, backoff_seconds=3):
    """
    Send the conversation and available tools to Qwen.
    """

    last_error = None

    for attempt in range(1, retries + 2):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
            )

            return response.choices[0].message

        except (APIError, APIConnectionError) as error:
            last_error = error

            if attempt <= retries:
                time.sleep(backoff_seconds)

    raise RuntimeError(
        "LM Studio did not respond after retrying. "
        f"Check that {MODEL_NAME} is loaded and that the server is "
        f"running at {LM_STUDIO_BASE_URL}. "
        f"Last error: {last_error}"
    )


# =========================================================
# MESSAGE HELPERS
# =========================================================

def _message_to_dict(message):
    """
    Convert an OpenAI SDK message into a normal dictionary.
    """

    return message.model_dump(exclude_none=True)


def _clean_reply_text(content):
    """
    Prevent empty model responses from being returned.
    """

    if not content or not content.strip():
        return (
            "I don't have a clear answer for that yet. "
            "Could you rephrase your question?"
        )

    return content.strip()


# =========================================================
# TOOL EXECUTION
# =========================================================

def _execute_tool_calls(message):
    """
    Execute all tools requested by Qwen and return
    the resulting tool messages.
    """

    tool_messages = []

    for tool_call in message.tool_calls:
        name = tool_call.function.name

        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            args = {}

        function = TOOL_FUNCTIONS.get(name)

        if function is None:
            result = json.dumps({
                "error": f"Unknown tool: {name}"
            })

        else:
            try:
                result = function(**args)
            except Exception as error:
                result = json.dumps({
                    "error": str(error)
                })

        tool_messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result),
        })

    return tool_messages


# =========================================================
# PUBLIC ENTRY POINT
# =========================================================

def run_chat_turn(course, history, user_message, max_tool_turns=6):
    """
    Run one multilingual conversation turn.

    Backend usage remains:

        reply, updated_history = run_chat_turn(
            course,
            history,
            user_message
        )
    """

    # -----------------------------------------------------
    # 1. TRANSLATE USER MESSAGE TO ENGLISH
    # -----------------------------------------------------

    english_message, detected_language = translate_to_english(user_message)

    # Full conversation history stored by the backend.
    updated_history = list(history)

    # Smaller context sent to Qwen.
    model_messages = _trim_history(history)

    # -----------------------------------------------------
    # 2. SYSTEM MESSAGE
    # -----------------------------------------------------

    if not updated_history:
        system_message = {
            "role": "system",
            "content": SYSTEM_PROMPT_TEMPLATE.format(course=course),
        }

        updated_history.append(system_message)
        model_messages.append(system_message)

    elif not model_messages:
        model_messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT_TEMPLATE.format(course=course),
        })

    # -----------------------------------------------------
    # 3. CURRENT USER MESSAGE
    # -----------------------------------------------------

    user_message_entry = {
        "role": "user",
        "content": english_message,
    }

    updated_history.append(user_message_entry)
    model_messages.append(user_message_entry)

    # -----------------------------------------------------
    # 4. QWEN + TOOL LOOP
    # -----------------------------------------------------

    for _ in range(max_tool_turns):
        message = _call_model(model_messages)

        # -------------------------------------------------
        # FINAL MODEL RESPONSE
        # -------------------------------------------------

        if not message.tool_calls:
            english_reply = _clean_reply_text(message.content)

            assistant_message = {
                "role": "assistant",
                "content": english_reply,
            }

            updated_history.append(assistant_message)

            final_reply = translate_from_english(
                english_reply,
                detected_language,
            )

            return final_reply, updated_history

        # -------------------------------------------------
        # TOOL CALL
        # -------------------------------------------------

        assistant_tool_message = _message_to_dict(message)

        model_messages.append(assistant_tool_message)
        updated_history.append(assistant_tool_message)

        tool_messages = _execute_tool_calls(message)

        model_messages.extend(tool_messages)
        updated_history.extend(tool_messages)

    # -----------------------------------------------------
    # 5. FALLBACK
    # -----------------------------------------------------

    english_fallback = (
        "I wasn't able to finish looking that up in time. "
        "Please try asking again with a more specific question."
    )

    updated_history.append({
        "role": "assistant",
        "content": english_fallback,
    })

    final_fallback = translate_from_english(
        english_fallback,
        detected_language,
    )

    return final_fallback, updated_history