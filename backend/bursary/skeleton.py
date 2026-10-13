"""
Multilingual AI Agent Skeleton for the Bursary and Internship Assistant.

Flow:

    User
      ↓
    Google Translation
      ↓
    English
      ↓
    Local LLM via LM Studio
      ↓
    Database / Tools
      ↓
    English response
      ↓
    Google Translation
      ↓
    User's original language

Important protections:
    - Maximum 5 bursaries per database search
    - Maximum 5 web search results
    - Only recent conversation turns are sent to the model
    - Old tool calls/results are NOT stored in permanent history
    - Tool messages exist only while processing the current turn
"""

import json
import os
import time
from pathlib import Path

from ddgs import DDGS
from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError

from bursary.recommendation import search_by_field, get_bursary_by_id
from bursary.translation import (
    translate_to_english,
    translate_from_english,
    TranslationError,
)


# =========================================================
# 1. LOAD ENVIRONMENT VARIABLES
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)

LM_STUDIO_BASE_URL = os.environ.get(
    "LM_STUDIO_BASE_URL",
    "http://localhost:1234/v1",
).strip()

LM_STUDIO_API_KEY = os.environ.get(
    "LM_STUDIO_API_KEY",
    "lm-studio",
).strip()

# Prefer the new generic variable name.
# BONSAI_MODEL_NAME is kept temporarily for backwards compatibility.
MODEL_NAME = (
    os.environ.get("MODEL_NAME")
    or os.environ.get("BONSAI_MODEL_NAME")
    or "ministral-3-3b-instruct-2512"
).strip()

print("LM Studio URL:", LM_STUDIO_BASE_URL)
print("Model:", MODEL_NAME)


# =========================================================
# 2. AGENT SETTINGS
# =========================================================

# Maximum number of previous user turns kept in model context.
MAX_HISTORY_USER_TURNS = 4

# Maximum bursaries returned by a database search.
MAX_SEARCH_RESULTS = 5

# Maximum open-web search results.
MAX_WEB_RESULTS = 5


# =========================================================
# 3. LM STUDIO CLIENT
# =========================================================

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key=LM_STUDIO_API_KEY,
)


# =========================================================
# 4. DATABASE TOOL IMPLEMENTATIONS
# =========================================================

def search_bursaries_by_course(
    course,
    include_expired=False,
    limit=MAX_SEARCH_RESULTS,
):
    """
    Search the bursary database for opportunities related
    to a field or course of study.

    search_by_field() performs the matching and availability
    filtering before we apply the result limit.
    """

    if not course or not str(course).strip():
        return json.dumps({
            "error": "A course or field of study is required."
        })

    results = search_by_field(
        str(course).strip(),
        include_expired=bool(include_expired),
    )

    total_matches = len(results)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = MAX_SEARCH_RESULTS

    limit = max(1, min(limit, MAX_SEARCH_RESULTS))

    selected_results = results[:limit]

    bursaries = [
        {
            "id": bursary.get("id"),
            "title": bursary.get("title"),
            "availability_status": bursary.get(
                "availability_status"
            ),
            "availability_label": bursary.get(
                "availability_label"
            ),
            "closing_date": bursary.get("closing_date"),
        }
        for bursary in selected_results
    ]

    return json.dumps(
        {
            "total_matches": total_matches,
            "returned": len(bursaries),
            "bursaries": bursaries,
        },
        ensure_ascii=False,
        default=str,
    )


def get_bursary_detail(bursary_id):
    """
    Retrieve useful detailed information for one bursary.

    Only relevant fields are returned to the model so that the
    tool result does not unnecessarily consume the context window.
    """

    try:
        bursary_id = int(bursary_id)
    except (TypeError, ValueError):
        return json.dumps({
            "error": "bursary_id must be an integer."
        })

    bursary = get_bursary_by_id(bursary_id)

    if bursary is None:
        return json.dumps({
            "error": f"No bursary found with id {bursary_id}"
        })

    detail = {
        "id": bursary.get("id"),
        "title": bursary.get("title"),
        "type": bursary.get("type"),
        "fields_of_study": bursary.get("fields_of_study"),
        "eligibility": bursary.get("eligibility"),
        "closing_date": bursary.get("closing_date"),
        "closing_dates": bursary.get("closing_dates"),
        "closing_status": bursary.get("closing_status"),
        "closing_date_text": bursary.get("closing_date_text"),
        "application_url": bursary.get("application_url"),
        "application_instructions": bursary.get(
            "application_instructions"
        ),
        "source": bursary.get("source"),
        "source_url": bursary.get("source_url"),
    }

    # Remove fields that do not exist or are None.
    detail = {
        key: value
        for key, value in detail.items()
        if value is not None
    }

    return json.dumps(
        detail,
        ensure_ascii=False,
        default=str,
    )


# =========================================================
# 5. WEB SEARCH TOOL
# =========================================================

def web_search(query, max_results=MAX_WEB_RESULTS):
    """
    Search the open web only when the local database
    cannot answer the student's question.
    """

    if not query or not str(query).strip():
        return json.dumps({
            "error": "A web search query is required."
        })

    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = MAX_WEB_RESULTS

    max_results = max(
        1,
        min(max_results, MAX_WEB_RESULTS),
    )

    results = []

    try:
        with DDGS() as ddgs:
            for result in ddgs.text(
                str(query).strip(),
                max_results=max_results,
            ):
                results.append({
                    "title": result.get("title"),
                    "url": result.get("href"),
                    "snippet": result.get("body"),
                })

    except Exception as error:
        return json.dumps({
            "error": str(error)
        })

    return json.dumps(
        results,
        ensure_ascii=False,
        default=str,
    )


# =========================================================
# 6. TOOLS GIVEN TO THE MODEL
# =========================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_bursaries_by_course",
            "description": (
                "Search the local bursary database for bursaries "
                "related to a student's field or course. "
                "Use this before web_search. "
                "It returns bursary IDs and brief summaries. "
                "Use get_bursary_detail afterwards if detailed "
                "information about one bursary is required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course": {
                        "type": "string",
                        "description": (
                            "Student's field or course, for example "
                            "Computer Science or Data Science."
                        ),
                    },
                    "include_expired": {
                        "type": "boolean",
                        "description": (
                            "Set true only if the student explicitly "
                            "asks for expired or closed bursaries."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Number of bursaries to return. "
                            "Maximum is 5."
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
                "Get detailed information about one bursary from "
                "the local database using its bursary ID. "
                "Use this for eligibility requirements, closing dates, "
                "application instructions, links, and other details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bursary_id": {
                        "type": "integer",
                        "description": (
                            "ID of the bursary returned by "
                            "search_bursaries_by_course."
                        ),
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
                "Search the open web only when the local bursary "
                "database cannot answer the student's question."
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
                        "description": (
                            "Maximum number of web results. "
                            "Maximum is 5."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# =========================================================
# 7. SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_TEMPLATE = (
    "You are the Bursary and Internship Assistant. "
    "The student's initial course is {course}.\n\n"

    "Ground rules:\n"

    "- Use the local database as the main source of bursary "
    "information.\n"

    "- Always prefer search_bursaries_by_course and "
    "get_bursary_detail over web_search or your own memory.\n"

    "- When the student asks you to find bursaries, call "
    "search_bursaries_by_course instead of answering from memory.\n"

    "- If the student asks about one specific bursary and you "
    "already know its ID, use get_bursary_detail.\n"

    "- If the student names a specific bursary but you do not "
    "know its database ID, search the database first to find it, "
    "then use get_bursary_detail when necessary.\n"

    "- search_bursaries_by_course may report more matches than "
    "were returned. Only discuss bursaries actually returned "
    "by the tool.\n"

    "- Use web_search only when the local database cannot answer "
    "the question.\n"

    "- Never invent bursaries, closing dates, eligibility "
    "requirements, application instructions, or application links.\n"

    "- If information is missing from the database, clearly say "
    "that the information is not confirmed.\n"

    "- If no bursary matches the student's field, say so instead "
    "of inventing results.\n"

    "- The course supplied at the beginning of the session is "
    "initial context. If the student later explicitly states a "
    "different course, use the student's latest stated course.\n"

    "- Keep responses concise, clear, and student-friendly.\n"

    "- Always respond internally in English. "
    "The translation layer handles the user's language."
)


# =========================================================
# 8. HISTORY MANAGEMENT
# =========================================================

def _clean_history(history):
    """
    Remove old tool calls and old tool results from permanent
    conversation history.

    Permanent history should contain only:

        system
        user
        assistant
        user
        assistant

    Tool calls and tool results are temporary and are used only
    while processing the current turn.
    """

    if not history:
        return []

    cleaned = []

    for message in history:
        role = message.get("role")

        if role == "system":
            cleaned.append({
                "role": "system",
                "content": message.get("content", ""),
            })

        elif role == "user":
            cleaned.append({
                "role": "user",
                "content": message.get("content", ""),
            })

        elif role == "assistant":
            # Do not permanently store assistant tool-call messages.
            if message.get("tool_calls"):
                continue

            cleaned.append({
                "role": "assistant",
                "content": message.get("content", ""),
            })

        # Ignore role="tool" completely.

    return cleaned


def _trim_history(
    history,
    max_user_turns=MAX_HISTORY_USER_TURNS,
):
    """
    Keep the system message and only the most recent complete
    normal conversation turns.

    Tool calls/results have already been removed.
    """

    cleaned = _clean_history(history)

    if not cleaned:
        return []

    system_message = None
    turns = []
    current_turn = []

    for message in cleaned:
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

        if role == "assistant" and current_turn:
            current_turn.append(message)

    if current_turn:
        turns.append(current_turn)

    recent_turns = turns[-max_user_turns:]

    trimmed = []

    if system_message:
        trimmed.append(system_message)

    for turn in recent_turns:
        trimmed.extend(turn)

    return trimmed


# =========================================================
# 9. CALL LOCAL MODEL THROUGH LM STUDIO
# =========================================================

def _call_model(
    messages,
    retries=2,
    backoff_seconds=3,
):
    """
    Send the current conversation and tools to the configured
    local model through LM Studio.
    """

    last_error = None

    for attempt in range(1, retries + 2):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                temperature=0.2,
            )

            return response.choices[0].message

        except (APIError, APIConnectionError) as error:
            last_error = error

            # Retrying a malformed request will not fix it.
            status_code = getattr(
                error,
                "status_code",
                None,
            )

            if status_code == 400:
                break

            if attempt <= retries:
                time.sleep(backoff_seconds)

    raise RuntimeError(
        "LM Studio did not respond successfully. "
        f"Model: {MODEL_NAME}. "
        f"Server: {LM_STUDIO_BASE_URL}. "
        f"Last error: {last_error}"
    )


# =========================================================
# 10. MODEL MESSAGE CONVERSION
# =========================================================

def _message_to_dict(message):
    """
    Convert an OpenAI SDK assistant message into a dictionary.
    """

    return message.model_dump(exclude_none=True)


# =========================================================
# 11. CLEAN FINAL RESPONSE
# =========================================================

def _clean_reply_text(content):
    """
    Prevent empty assistant responses.
    """

    if not content:
        return "I don't have a clear answer for that yet."

    content = content.strip()

    if not content:
        return "I don't have a clear answer for that yet."

    return content


# =========================================================
# 12. EXECUTE ONE TOOL CALL
# =========================================================

def _execute_tool_call(tool_call):
    """
    Execute one model-requested tool.

    Arguments are deliberately extracted per tool so that an
    unexpected model-generated argument does not break the call.
    """

    name = tool_call.function.name

    try:
        args = json.loads(
            tool_call.function.arguments or "{}"
        )
    except json.JSONDecodeError:
        return json.dumps({
            "error": (
                f"The arguments supplied for tool '{name}' "
                "were not valid JSON."
            )
        })

    try:
        if name == "search_bursaries_by_course":
            return search_bursaries_by_course(
                course=args.get("course"),
                include_expired=args.get(
                    "include_expired",
                    False,
                ),
                limit=args.get(
                    "limit",
                    MAX_SEARCH_RESULTS,
                ),
            )

        if name == "get_bursary_detail":
            return get_bursary_detail(
                bursary_id=args.get("bursary_id"),
            )

        if name == "web_search":
            return web_search(
                query=args.get("query"),
                max_results=args.get(
                    "max_results",
                    MAX_WEB_RESULTS,
                ),
            )

        return json.dumps({
            "error": f"Unknown tool: {name}"
        })

    except Exception as error:
        return json.dumps({
            "error": str(error)
        })


# =========================================================
# 13. RUN TOOL CALLS
# =========================================================

def _run_tool_calls(message, model_messages):
    """
    Execute every tool requested by the model.

    Results are added only to the temporary model context.
    They are NOT added to permanent conversation history.
    """

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name

        print(f"[Tool call: {tool_name}]")

        result = _execute_tool_call(tool_call)

        model_messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        })


# =========================================================
# 14. ENGLISH AI AGENT
# =========================================================

def run_chat_turn(
    course,
    history,
    user_message,
    max_tool_turns=6,
):
    """
    Run one English conversation turn.

    Permanent history:
        system
        user
        assistant
        user
        assistant

    Temporary current-turn model context may additionally contain:
        assistant tool_call
        tool result

    Those temporary messages are discarded after the final
    assistant response is produced.
    """

    # -----------------------------------------------------
    # Permanent conversation history
    # -----------------------------------------------------

    conversation_history = _clean_history(history)

    if not conversation_history:
        conversation_history.append({
            "role": "system",
            "content": SYSTEM_PROMPT_TEMPLATE.format(
                course=course
            ),
        })

    conversation_history.append({
        "role": "user",
        "content": user_message,
    })

    # -----------------------------------------------------
    # Temporary model context
    # -----------------------------------------------------

    model_messages = _trim_history(
        conversation_history
    )

    # -----------------------------------------------------
    # Model/tool loop
    # -----------------------------------------------------

    for _ in range(max_tool_turns):
        message = _call_model(model_messages)

        # ---------------------------------------------
        # Final normal response
        # ---------------------------------------------

        if not message.tool_calls:
            reply = _clean_reply_text(
                message.content
            )

            conversation_history.append({
                "role": "assistant",
                "content": reply,
            })

            # Keep permanent history clean and bounded.
            stored_history = _trim_history(
                conversation_history
            )

            return reply, stored_history

        # ---------------------------------------------
        # Temporary tool request
        # ---------------------------------------------

        model_messages.append(
            _message_to_dict(message)
        )

        _run_tool_calls(
            message,
            model_messages,
        )

    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    fallback = (
        "I wasn't able to finish looking that up in time. "
        "Please try asking again."
    )

    conversation_history.append({
        "role": "assistant",
        "content": fallback,
    })

    stored_history = _trim_history(
        conversation_history
    )

    return fallback, stored_history


# =========================================================
# 15. MULTILINGUAL WRAPPER
# =========================================================

def run_multilingual_chat_turn(
    course,
    history,
    user_message,
):
    """
    Full multilingual conversation flow.

    User message
        ↓
    Google Translation
        ↓
    English
        ↓
    Local model + tools
        ↓
    English response
        ↓
    Google Translation
        ↓
    User's language
    """

    english_message, detected_language = (
        translate_to_english(user_message)
    )

    print(
        f"\n[Detected language: "
        f"{detected_language}]"
    )

    if detected_language != "en":
        print(
            f"[Translated to English: "
            f"{english_message}]"
        )

    english_reply, updated_history = (
        run_chat_turn(
            course=course,
            history=history,
            user_message=english_message,
        )
    )

    final_reply = translate_from_english(
        english_reply,
        detected_language,
    )

    return (
        final_reply,
        updated_history,
        detected_language,
    )


# =========================================================
# 16. TERMINAL CHAT
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BURSARY AI ASSISTANT")
    print("=" * 60)

    course = input(
        "Enter your course: "
    ).strip()

    history = []

    while True:
        user_message = input(
            "\nYou: "
        ).strip()

        if user_message.lower() == "exit":
            print("\nGoodbye!")
            break

        if not user_message:
            continue

        try:
            reply, history, language = (
                run_multilingual_chat_turn(
                    course=course,
                    history=history,
                    user_message=user_message,
                )
            )

            print(
                "\nAssistant:",
                reply,
            )

        except TranslationError as error:
            print(
                "\nTranslation error:",
                error,
            )

        except Exception as error:
            print(
                "\nError:",
                error,
            )