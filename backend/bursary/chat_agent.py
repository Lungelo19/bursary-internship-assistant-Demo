"""
PathwaySA AI Chat Agent

The LLM:
- understands student questions
- chooses tools
- interprets verified findings

The backend:
- authenticates the student
- stores profile information
- performs deterministic programme matching
- searches programme and bursary databases
- retrieves bursary details

The LLM must never calculate admission eligibility itself.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, OpenAI

from accounts.service import (
    get_student_profile as load_student_profile,
)

from bursary.recommendation import (
    get_bursary_by_id,
    search_by_field,
)

from bursary.translation import (
    translate_from_english,
    translate_to_english,
)

from programmes.matcher import recommend_programmes

from programmes.service import (
    search_programmes as search_programme_catalog,
)


try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


# =========================================================
# 1. ENVIRONMENT
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    ENV_FILE,
    override=True,
)


# =========================================================
# 2. SETTINGS
# =========================================================

LM_STUDIO_BASE_URL = os.environ.get(
    "LM_STUDIO_BASE_URL",
    "http://localhost:1234/v1",
).strip()


LM_STUDIO_API_KEY = os.environ.get(
    "LM_STUDIO_API_KEY",
    "lm-studio",
).strip()


MODEL_NAME = (
    os.environ.get("MODEL_NAME")
    or "ministral-3-3b-instruct-2512"
).strip()


MAX_HISTORY_USER_TURNS = 4

MAX_SEARCH_RESULTS = 5

MAX_PROGRAMME_RESULTS = 10

DEFAULT_PROGRAMME_RECOMMENDATION_RESULTS = 5

MAX_PROGRAMME_RECOMMENDATIONS = 20

MAX_WEB_RESULTS = 5


MAX_BURSARY_FIELD_CHARS = 350

MAX_BURSARY_ELIGIBILITY_CHARS = 1200

MAX_BURSARY_INSTRUCTIONS_CHARS = 1200

MAX_WEB_SNIPPET_CHARS = 500


INTERNAL_CONTEXT_PREFIX = (
    "[PATHWAYSA_INTERNAL_CONTEXT]"
)


ANSWER_READY_TOOLS = {
    "search_programmes",
    "recommend_programmes_for_student",
    "search_bursaries_by_course",
    "recommend_bursaries_for_student",
    "get_bursary_detail",
    "web_search",
}


print(
    "LM_STUDIO_BASE_URL =",
    LM_STUDIO_BASE_URL,
)

print(
    "MODEL_NAME =",
    MODEL_NAME,
)


# =========================================================
# 3. LM STUDIO CLIENT
# =========================================================

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key=LM_STUDIO_API_KEY,
)


# =========================================================
# 4. GENERAL HELPERS
# =========================================================

def _compact_text(
    value,
    max_chars,
):
    """
    Convert arbitrary values into compact text.
    """

    if value is None:
        return None


    if isinstance(
        value,
        str,
    ):
        text = value.strip()

    elif isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        text = ", ".join(
            str(item).strip()
            for item in value
            if item is not None
            and str(item).strip()
        )

    elif isinstance(
        value,
        dict,
    ):
        text = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )

    else:
        text = str(
            value
        ).strip()


    if not text:
        return None


    if len(text) <= max_chars:
        return text


    return (
        text[:max_chars].rstrip()
        + "..."
    )


def _remove_empty_fields(
    data,
):
    """
    Remove empty values before serialisation.
    """

    return {
        key: value
        for key, value
        in data.items()
        if value not in (
            None,
            "",
            [],
            {},
        )
    }


# =========================================================
# 5. STUDENT PROFILE
# =========================================================

def get_my_student_profile(
    user_id,
):
    """
    Retrieve authenticated student's saved profile.
    """

    if user_id is None:

        return json.dumps(
            {
                "error": (
                    "Authentication is required to access "
                    "the student profile."
                )
            }
        )


    profile = load_student_profile(
        user_id
    )


    if profile is None:

        return json.dumps(
            {
                "error": (
                    "Student profile not found."
                )
            }
        )


    return json.dumps(
        profile,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


# =========================================================
# 6. PROGRAMME SEARCH COMPACTION
# =========================================================

def _compact_programme_search_result(
    programme,
):
    """
    Compact one catalogue result.
    """

    if not isinstance(
        programme,
        dict,
    ):
        return programme


    requirements = (
        programme.get(
            "requirements"
        )
        or programme.get(
            "minimum_entry_requirements"
        )
        or programme.get(
            "raw_requirement"
        )
    )


    compact = {
        "offering_id": programme.get(
            "offering_id"
        ),

        "programme_name": programme.get(
            "programme_name"
        ),

        "programme_code": programme.get(
            "programme_code"
        ),

        "institution": programme.get(
            "institution"
        ),

        "institution_code": programme.get(
            "institution_code"
        ),

        "campus": programme.get(
            "campus"
        ),

        "career_direction": programme.get(
            "career_direction"
        ),

        "study_level": programme.get(
            "study_level"
        ),

        "course_duration": programme.get(
            "course_duration"
        ),

        "closing_date": programme.get(
            "closing_date"
        ),

        "entry_term": programme.get(
            "entry_term"
        ),

        "minimum_points": programme.get(
            "minimum_points"
        ),

        "requirements": _compact_text(
            requirements,
            700,
        ),

        "notes": _compact_text(
            programme.get(
                "notes"
            ),
            500,
        ),

        "source": programme.get(
            "source"
        ),
    }


    return _remove_empty_fields(
        compact
    )


# =========================================================
# 7. PROGRAMME SEARCH
# =========================================================

def search_programmes(
    search=None,
    institution=None,
    career=None,
    study_level=None,
    entry_term=None,
    limit=MAX_PROGRAMME_RESULTS,
):
    """
    Search PathwaySA programme catalogue.

    Does not evaluate personalised eligibility.
    """

    try:
        limit = int(
            limit
        )

    except (
        TypeError,
        ValueError,
    ):
        limit = MAX_PROGRAMME_RESULTS


    limit = max(
        1,
        min(
            limit,
            MAX_PROGRAMME_RESULTS,
        ),
    )


    results = search_programme_catalog(
        search=search,
        institution=institution,
        campus=None,
        career=career,
        study_level=study_level,
        entry_term=entry_term,
        limit=limit,
        offset=0,
    )


    if isinstance(
        results,
        list,
    ):

        compact_results = [
            _compact_programme_search_result(
                programme
            )
            for programme
            in results
        ]


        payload_data = {
            "returned": len(
                compact_results
            ),

            "programmes": (
                compact_results
            ),
        }


    elif isinstance(
        results,
        dict,
    ):

        raw_items = (
            results.get(
                "results"
            )
            or results.get(
                "items"
            )
            or results.get(
                "programmes"
            )
            or []
        )


        if isinstance(
            raw_items,
            list,
        ):

            compact_items = [
                _compact_programme_search_result(
                    programme
                )
                for programme
                in raw_items
            ]


            payload_data = {
                "returned": len(
                    compact_items
                ),

                "programmes": (
                    compact_items
                ),
            }

        else:

            payload_data = results


    else:

        payload_data = results


    payload = json.dumps(
        payload_data,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


    print(
        "[Programme search payload:]",
        f"{len(payload)} characters",
    )


    return payload


# =========================================================
# 8. PROGRAMME RECOMMENDATION COMPACTION
# =========================================================

def _compact_programme_recommendation(
    recommendation,
):
    """
    Convert matcher result into explicit compact fields.

    required_level:
        programme minimum

    student_level:
        student's achieved NSC level

    student_mark:
        student's percentage
    """

    requirement_check = (
        recommendation.get(
            "requirement_check"
        )
        or {}
    )


    points_check = (
        recommendation.get(
            "points_check"
        )
        or {}
    )


    subject_requirements = []

    other_requirement_checks = []


    for check in requirement_check.get(
        "checks",
        [],
    ):

        if not isinstance(
            check,
            dict,
        ):
            continue


        check_type = check.get(
            "type"
        )


        if check_type == "subject":

            subject_requirement = {
                "subject": check.get(
                    "subject"
                ),

                "required_level": check.get(
                    "required_level"
                ),

                "student_level": check.get(
                    "student_level"
                ),

                "student_mark": check.get(
                    "student_mark"
                ),

                "passed": check.get(
                    "passed"
                ),
            }


            subject_requirements.append(
                _remove_empty_fields(
                    subject_requirement
                )
            )

            continue


        compact_check = {
            "type": check_type,

            "passed": check.get(
                "passed"
            ),

            "message": check.get(
                "message"
            ),
        }


        compact_check = (
            _remove_empty_fields(
                compact_check
            )
        )


        if compact_check:

            other_requirement_checks.append(
                compact_check
            )


    compact = {
        "programme_name": recommendation.get(
            "programme_name"
        ),

        "programme_code": recommendation.get(
            "programme_code"
        ),

        "institution": recommendation.get(
            "institution"
        ),

        "institution_code": recommendation.get(
            "institution_code"
        ),

        "campus": recommendation.get(
            "campus"
        ),

        "study_level": recommendation.get(
            "study_level"
        ),

        "course_duration": recommendation.get(
            "course_duration"
        ),

        "closing_date": recommendation.get(
            "closing_date"
        ),

        "entry_term": recommendation.get(
            "entry_term"
        ),

        "match_status": recommendation.get(
            "match_status"
        ),

        "recommendation_group": recommendation.get(
            "recommendation_group"
        ),

        "student_cao_points": recommendation.get(
            "student_cao_points"
        ),

        "minimum_points": recommendation.get(
            "minimum_points"
        ),

        "points_check_passed": points_check.get(
            "passed"
        ),

        "minimum_entry_requirement": (
            requirement_check.get(
                "raw_requirement"
            )
        ),

        "subject_requirements": (
            subject_requirements
        ),

        "other_requirement_checks": (
            other_requirement_checks
        ),

        "review_required": (
            requirement_check.get(
                "review_required"
            )
        ),

        "notes": _compact_text(
            recommendation.get(
                "notes"
            ),
            500,
        ),

        "source": recommendation.get(
            "source"
        ),
    }


    # source_year intentionally omitted.
    # A handbook year must not be interpreted as
    # the application closing-date year.

    return _remove_empty_fields(
        compact
    )


# =========================================================
# 9. PERSONALISED PROGRAMME RECOMMENDATIONS
# =========================================================

def recommend_programmes_for_student(
    user_id,
    interest=None,
    limit=DEFAULT_PROGRAMME_RECOMMENDATION_RESULTS,
):
    """
    Run deterministic programme matcher using saved profile.
    """

    if user_id is None:

        return json.dumps(
            {
                "error": (
                    "Authentication is required for personalised "
                    "programme recommendations."
                )
            }
        )


    profile = load_student_profile(
        user_id
    )


    if profile is None:

        return json.dumps(
            {
                "error": (
                    "Student profile not found."
                )
            }
        )


    student_results = (
        profile.get(
            "subjects"
        )
        or {}
    )


    student_pass_type = (
        profile.get(
            "pass_type"
        )
    )


    if not student_results:

        return json.dumps(
            {
                "error": (
                    "The student's profile does not contain "
                    "subject marks yet."
                )
            }
        )


    if not student_pass_type:

        return json.dumps(
            {
                "error": (
                    "The student's profile does not contain "
                    "a pass type yet."
                )
            }
        )


    try:
        limit = int(
            limit
        )

    except (
        TypeError,
        ValueError,
    ):
        limit = (
            DEFAULT_PROGRAMME_RECOMMENDATION_RESULTS
        )


    limit = max(
        1,
        min(
            limit,
            MAX_PROGRAMME_RECOMMENDATIONS,
        ),
    )


    if (
        interest
        and str(
            interest
        ).strip()
    ):

        interests = [
            str(
                interest
            ).strip()
        ]

    else:

        interests = (
            profile.get(
                "interests"
            )
            or []
        )


    preferred_institutions = (
        profile.get(
            "preferred_institutions"
        )
        or []
    )


    result = recommend_programmes(
        student_results=student_results,
        student_pass_type=student_pass_type,
        interests=interests,
        preferred_institutions=(
            preferred_institutions
        ),
        preferred_study_levels=[],
        interest_limit=min(
            10,
            limit,
        ),
        limit=limit,
        include_gaps=False,
        include_uncertain=False,
    )


    recommendations = result.get(
        "recommendations",
        [],
    )


    compact_recommendations = [
        _compact_programme_recommendation(
            recommendation
        )
        for recommendation
        in recommendations
    ]


    compact_result = {
        "student_cao_points": result.get(
            "student_cao_points"
        ),

        "interests": result.get(
            "interests",
            [],
        ),

        "interest_matches_found": result.get(
            "interest_matches_found",
            0,
        ),

        "interest_matches_returned": result.get(
            "interest_matches_returned",
            0,
        ),

        "other_qualifying_found": result.get(
            "other_qualifying_found",
            0,
        ),

        "other_qualifying_returned": result.get(
            "other_qualifying_returned",
            0,
        ),

        "recommendations": (
            compact_recommendations
        ),
    }


    payload = json.dumps(
        compact_result,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


    print(
        "[Programme recommendation payload:]",
        f"{len(payload)} characters,"
        f" {len(compact_recommendations)} programmes",
    )


    return payload


# =========================================================
# 10. BURSARY SEARCH COMPACTION
# =========================================================

def _compact_bursary_search_result(
    bursary,
):
    """
    Compact one bursary search result.

    Database ID is retained internally for follow-up detail.
    """

    compact = {
        "id": bursary.get(
            "id"
        ),

        "title": bursary.get(
            "title"
        ),

        "fields_of_study": _compact_text(
            bursary.get(
                "fields_of_study"
            ),
            MAX_BURSARY_FIELD_CHARS,
        ),

        "availability_status": bursary.get(
            "availability_status"
        ),

        "availability_label": bursary.get(
            "availability_label"
        ),

        "closing_date": bursary.get(
            "closing_date"
        ),
    }


    return _remove_empty_fields(
        compact
    )


# =========================================================
# 11. BURSARY SEARCH
# =========================================================

def search_bursaries_by_course(
    course,
    include_expired=False,
    limit=MAX_SEARCH_RESULTS,
):
    """
    Search local bursary database by field of study.
    """

    if (
        not course
        or not str(
            course
        ).strip()
    ):

        return json.dumps(
            {
                "error": (
                    "A course or field of study is required."
                )
            }
        )


    selected_course = str(
        course
    ).strip()


    results = search_by_field(
        selected_course,
        include_expired=bool(
            include_expired
        ),
    )


    total_matches = len(
        results
    )


    try:
        limit = int(
            limit
        )

    except (
        TypeError,
        ValueError,
    ):
        limit = MAX_SEARCH_RESULTS


    limit = max(
        1,
        min(
            limit,
            MAX_SEARCH_RESULTS,
        ),
    )


    selected_results = results[
        :limit
    ]


    bursaries = [
        _compact_bursary_search_result(
            bursary
        )
        for bursary
        in selected_results
    ]


    result = {
        "searched_field": selected_course,

        "total_matches": total_matches,

        "returned": len(
            bursaries
        ),

        "bursaries": bursaries,
    }


    payload = json.dumps(
        result,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


    print(
        "[Bursary search payload:]",
        f"{len(payload)} characters,"
        f" {len(bursaries)} bursaries",
    )


    return payload


# =========================================================
# 12. PERSONALISED BURSARY SEARCH
# =========================================================

def recommend_bursaries_for_student(
    user_id,
    course=None,
    limit=MAX_SEARCH_RESULTS,
):
    """
    Find bursaries using explicit field or saved interest.
    """

    if user_id is None:

        return json.dumps(
            {
                "error": (
                    "Authentication is required for personalised "
                    "funding recommendations."
                )
            }
        )


    profile = load_student_profile(
        user_id
    )


    if profile is None:

        return json.dumps(
            {
                "error": (
                    "Student profile not found."
                )
            }
        )


    selected_course = None


    if (
        course
        and str(
            course
        ).strip()
    ):

        selected_course = (
            str(
                course
            ).strip()
        )


    if selected_course is None:

        interests = (
            profile.get(
                "interests"
            )
            or []
        )


        if interests:

            selected_course = (
                interests[0]
            )


    if not selected_course:

        return json.dumps(
            {
                "error": (
                    "No study interest is available in the "
                    "student's saved profile."
                )
            }
        )


    return search_bursaries_by_course(
        course=selected_course,
        include_expired=False,
        limit=limit,
    )


# =========================================================
# 13. BURSARY DETAIL COMPACTION
# =========================================================

def _compact_bursary_detail(
    bursary,
):
    """
    Compact detailed bursary record.
    """

    compact = {
        "id": bursary.get(
            "id"
        ),

        "title": bursary.get(
            "title"
        ),

        "type": bursary.get(
            "type"
        ),

        "fields_of_study": _compact_text(
            bursary.get(
                "fields_of_study"
            ),
            600,
        ),

        "eligibility": _compact_text(
            bursary.get(
                "eligibility"
            ),
            MAX_BURSARY_ELIGIBILITY_CHARS,
        ),

        "closing_date": bursary.get(
            "closing_date"
        ),

        "closing_dates": _compact_text(
            bursary.get(
                "closing_dates"
            ),
            500,
        ),

        "closing_status": bursary.get(
            "closing_status"
        ),

        "closing_date_text": _compact_text(
            bursary.get(
                "closing_date_text"
            ),
            500,
        ),

        "application_url": bursary.get(
            "application_url"
        ),

        "application_instructions": _compact_text(
            bursary.get(
                "application_instructions"
            ),
            MAX_BURSARY_INSTRUCTIONS_CHARS,
        ),

        "source": bursary.get(
            "source"
        ),

        "source_url": bursary.get(
            "source_url"
        ),
    }


    return _remove_empty_fields(
        compact
    )


# =========================================================
# 14. BURSARY DETAIL
# =========================================================

def get_bursary_detail(
    bursary_id,
):
    """
    Retrieve detailed bursary information by database ID.
    """

    try:
        bursary_id = int(
            bursary_id
        )

    except (
        TypeError,
        ValueError,
    ):

        return json.dumps(
            {
                "error": (
                    "bursary_id must be an integer."
                )
            }
        )


    bursary = get_bursary_by_id(
        bursary_id
    )


    if bursary is None:

        return json.dumps(
            {
                "error": (
                    f"No bursary found with id {bursary_id}"
                )
            }
        )


    compact_detail = (
        _compact_bursary_detail(
            bursary
        )
    )


    payload = json.dumps(
        compact_detail,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


    print(
        "[Bursary detail payload:]",
        f"{len(payload)} characters",
    )


    return payload


# =========================================================
# 15. WEB SEARCH
# =========================================================

def web_search(
    query,
    max_results=MAX_WEB_RESULTS,
):
    """
    Open-web fallback.
    """

    if DDGS is None:

        return json.dumps(
            {
                "error": (
                    "Web search is not available "
                    "in this environment."
                )
            }
        )


    if (
        not query
        or not str(
            query
        ).strip()
    ):

        return json.dumps(
            {
                "error": (
                    "A web search query is required."
                )
            }
        )


    try:
        max_results = int(
            max_results
        )

    except (
        TypeError,
        ValueError,
    ):
        max_results = MAX_WEB_RESULTS


    max_results = max(
        1,
        min(
            max_results,
            MAX_WEB_RESULTS,
        ),
    )


    results = []


    try:

        with DDGS() as ddgs:

            for result in ddgs.text(
                str(
                    query
                ).strip(),
                max_results=max_results,
            ):

                results.append(
                    {
                        "title": result.get(
                            "title"
                        ),

                        "url": result.get(
                            "href"
                        ),

                        "snippet": _compact_text(
                            result.get(
                                "body"
                            ),
                            MAX_WEB_SNIPPET_CHARS,
                        ),
                    }
                )


    except Exception as error:

        return json.dumps(
            {
                "error": str(
                    error
                )
            }
        )


    return json.dumps(
        results,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


# =========================================================
# 16. TOOL DEFINITIONS
# =========================================================

TOOLS = [
    {
        "type": "function",

        "function": {
            "name": "get_my_student_profile",

            "description": (
                "Retrieve the authenticated student's saved "
                "profile including subjects, marks, pass type, "
                "study interests and preferred institutions."
            ),

            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": "search_programmes",

            "description": (
                "Search PathwaySA's programme catalogue for "
                "general programme discovery. This tool does not "
                "determine whether the student qualifies."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "search": {
                        "type": "string",
                    },

                    "institution": {
                        "type": "string",
                    },

                    "career": {
                        "type": "string",
                    },

                    "study_level": {
                        "type": "string",
                    },

                    "entry_term": {
                        "type": "string",
                    },

                    "limit": {
                        "type": "integer",

                        "description": (
                            "Maximum 10 results."
                        ),
                    },
                },
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": (
                "recommend_programmes_for_student"
            ),

            "description": (
                "Generate personalised programme recommendations "
                "using the authenticated student's saved academic "
                "profile. PathwaySA's deterministic matcher performs "
                "the eligibility evaluation."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "interest": {
                        "type": "string",
                    },

                    "limit": {
                        "type": "integer",

                        "description": (
                            "Default 5. Maximum 20."
                        ),
                    },
                },
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": (
                "search_bursaries_by_course"
            ),

            "description": (
                "Search PathwaySA's local bursary database "
                "for a course or field of study."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "course": {
                        "type": "string",
                    },

                    "include_expired": {
                        "type": "boolean",
                    },

                    "limit": {
                        "type": "integer",

                        "description": (
                            "Maximum 5."
                        ),
                    },
                },

                "required": [
                    "course"
                ],
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": (
                "recommend_bursaries_for_student"
            ),

            "description": (
                "Find bursaries for the authenticated student. "
                "Use an explicitly stated study field when supplied; "
                "otherwise use the student's saved study interest."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "course": {
                        "type": "string",
                    },

                    "limit": {
                        "type": "integer",

                        "description": (
                            "Maximum 5."
                        ),
                    },
                },
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": "get_bursary_detail",

            "description": (
                "Retrieve detailed information about one specific "
                "bursary using its database ID. Use this when a "
                "student asks for more information, eligibility, "
                "application instructions, a deadline or application "
                "link for a previously listed bursary. Recent internal "
                "bursary context may contain the correct title and ID. "
                "Use that ID without asking the student for it."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "bursary_id": {
                        "type": "integer",
                    },
                },

                "required": [
                    "bursary_id"
                ],
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name": "web_search",

            "description": (
                "Use open-web search only when PathwaySA's local "
                "structured data cannot answer the question."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "query": {
                        "type": "string",
                    },

                    "max_results": {
                        "type": "integer",
                    },
                },

                "required": [
                    "query"
                ],
            },
        },
    },
]


# =========================================================
# 17. SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT_TEMPLATE = (
    "You are PathwaySA, an intelligent higher-education "
    "journey assistant for South African students. "
    "Initial study context: {course}.\n\n"

    "Rules:\n"

    "- Use PathwaySA tools for programme, admission, profile, "
    "bursary and funding information.\n"

    "- Never calculate programme eligibility yourself.\n"

    "- Use recommend_programmes_for_student when the student asks "
    "what they can study based on their marks.\n"

    "- Use search_programmes for general programme browsing.\n"

    "- Use recommend_bursaries_for_student when the student asks "
    "which bursaries are available for them.\n"

    "- Use search_bursaries_by_course for general bursary searches.\n"

    "- Use get_bursary_detail when the student asks for details, "
    "eligibility, closing information, application instructions "
    "or an application link for a specific bursary.\n"

    "- Trusted internal context may be appended below this system "
    "prompt. It can contain bursary titles and database IDs from "
    "previous PathwaySA search results.\n"

    "- When the student refers to a previously shown bursary by "
    "name, use its matching internal database ID with "
    "get_bursary_detail. Do not ask the student for the ID.\n"

    "- Never expose internal database IDs unless the student "
    "explicitly asks for technical information.\n"

    "- Prefer PathwaySA's local structured data over web search.\n"

    "- Never invent programmes, bursaries, requirements, dates, "
    "links or eligibility conditions.\n"

    "- Once a structured tool supplies enough information, stop "
    "searching and answer from that verified result.\n"

    "- Respond internally in English. Translation is handled "
    "separately.\n"
)


# =========================================================
# 18. INTERNAL BURSARY CONTEXT
# =========================================================

def _build_internal_tool_context(
    tool_messages,
):
    """
    Build a tiny title -> ID memory from bursary search results.

    This is stored server-side in chat history and is never
    returned directly to the student.
    """

    references = []


    for tool_message in tool_messages:

        content = tool_message.get(
            "content"
        )


        if not content:
            continue


        try:
            data = json.loads(
                content
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue


        if not isinstance(
            data,
            dict,
        ):
            continue


        bursaries = data.get(
            "bursaries"
        )


        if not isinstance(
            bursaries,
            list,
        ):
            continue


        for bursary in bursaries:

            if not isinstance(
                bursary,
                dict,
            ):
                continue


            bursary_id = bursary.get(
                "id"
            )

            title = bursary.get(
                "title"
            )


            if (
                bursary_id is None
                or not title
            ):
                continue


            references.append(
                {
                    "id": bursary_id,
                    "title": title,
                }
            )


    if not references:
        return None


    # Deduplicate.

    unique = {}

    for reference in references:

        unique[
            reference["id"]
        ] = reference


    references = list(
        unique.values()
    )


    return (
        f"{INTERNAL_CONTEXT_PREFIX}\n"
        "Recent bursary search references:\n"
        f"{json.dumps(references, ensure_ascii=False, separators=(',', ':'))}\n"
        "These IDs are internal PathwaySA database references. "
        "Use them when the student asks about one of these bursaries. "
        "Do not reveal them unless explicitly asked."
    )


def _is_internal_context_message(
    message,
):
    """
    Identify hidden PathwaySA context stored as an assistant message.
    """

    if message.get(
        "role"
    ) != "assistant":
        return False


    content = message.get(
        "content",
        "",
    )


    return content.startswith(
        INTERNAL_CONTEXT_PREFIX
    )


# =========================================================
# 19. HISTORY CLEANING
# =========================================================

def _clean_history(
    history,
):
    """
    Remove temporary tool calls and tool results.

    Internal PathwaySA context is preserved as an assistant
    message in stored history.
    """

    if not history:
        return []


    cleaned = []


    for message in history:

        role = message.get(
            "role"
        )


        if role == "system":

            cleaned.append(
                {
                    "role": "system",

                    "content": message.get(
                        "content",
                        "",
                    ),
                }
            )


        elif role == "user":

            cleaned.append(
                {
                    "role": "user",

                    "content": message.get(
                        "content",
                        "",
                    ),
                }
            )


        elif role == "assistant":

            if message.get(
                "tool_calls"
            ):
                continue


            cleaned.append(
                {
                    "role": "assistant",

                    "content": message.get(
                        "content",
                        "",
                    ),
                }
            )


        # tool-role messages are intentionally excluded.


    return cleaned


# =========================================================
# 20. HISTORY PREPARATION
# =========================================================

def _prepare_history(
    history,
    max_user_turns=MAX_HISTORY_USER_TURNS,
    for_model=False,
):
    """
    Prepare conversation history.

    Stored history:
        system
        user
        assistant
        ...
        special assistant internal-context message

    Model history:
        exactly ONE system message

        The latest internal context is merged INTO that original
        system message before inference.

        This avoids Ministral's chat-template error caused by
        sending a second system message.
    """

    cleaned = _clean_history(
        history
    )


    if not cleaned:
        return []


    base_system = None

    latest_internal_context = None

    dialogue_messages = []


    for message in cleaned:

        role = message.get(
            "role"
        )


        if role == "system":

            if base_system is None:

                base_system = (
                    message
                )

            continue


        if _is_internal_context_message(
            message
        ):

            latest_internal_context = (
                message
            )

            continue


        dialogue_messages.append(
            message
        )


    # -----------------------------------------------------
    # GROUP NORMAL DIALOGUE INTO TURNS
    # -----------------------------------------------------

    turns = []

    current_turn = []


    for message in dialogue_messages:

        role = message.get(
            "role"
        )


        if role == "user":

            if current_turn:

                turns.append(
                    current_turn
                )


            current_turn = [
                message
            ]

            continue


        if (
            role == "assistant"
            and current_turn
        ):

            current_turn.append(
                message
            )


    if current_turn:

        turns.append(
            current_turn
        )


    recent_turns = turns[
        -max_user_turns:
    ]


    prepared = []


    # -----------------------------------------------------
    # MODEL VERSION
    # -----------------------------------------------------

    if for_model:

        if base_system:

            system_content = (
                base_system.get(
                    "content",
                    "",
                )
            )


            if latest_internal_context:

                system_content += (
                    "\n\n"
                    "Trusted PathwaySA internal context:\n"
                    + latest_internal_context.get(
                        "content",
                        "",
                    )
                )


            prepared.append(
                {
                    "role": "system",

                    "content": (
                        system_content
                    ),
                }
            )


        for turn in recent_turns:

            prepared.extend(
                turn
            )


        return prepared


    # -----------------------------------------------------
    # STORED VERSION
    # -----------------------------------------------------

    if base_system:

        prepared.append(
            base_system
        )


    for turn in recent_turns:

        prepared.extend(
            turn
        )


    # Store latest hidden context as ASSISTANT, never SYSTEM.
    #
    # On the next model call it will be extracted and merged into
    # the single original system message.

    if latest_internal_context:

        prepared.append(
            latest_internal_context
        )


    return prepared


# =========================================================
# 21. MODEL CALL
# =========================================================

def _call_model(
    messages,
    retries=2,
    backoff_seconds=3,
    allow_tools=True,
):
    """
    Call configured local model.
    """

    last_error = None


    for attempt in range(
        1,
        retries + 2,
    ):

        try:

            request_kwargs = {
                "model": MODEL_NAME,

                "messages": messages,

                "temperature": 0.2,
            }


            if allow_tools:

                request_kwargs[
                    "tools"
                ] = TOOLS


            response = (
                client
                .chat
                .completions
                .create(
                    **request_kwargs
                )
            )


            return (
                response
                .choices[0]
                .message
            )


        except (
            APIError,
            APIConnectionError,
        ) as error:

            last_error = error


            status_code = getattr(
                error,
                "status_code",
                None,
            )


            if status_code == 400:
                break


            if attempt <= retries:

                time.sleep(
                    backoff_seconds
                )


    raise RuntimeError(
        "LM Studio did not respond successfully. "
        f"Model: {MODEL_NAME}. "
        f"Server: {LM_STUDIO_BASE_URL}. "
        f"Last error: {last_error}"
    )


# =========================================================
# 22. MODEL MESSAGE HELPERS
# =========================================================

def _message_to_dict(
    message,
):
    return message.model_dump(
        exclude_none=True
    )


def _clean_reply_text(
    content,
):
    if (
        not content
        or not content.strip()
    ):

        return (
            "I don't have a clear answer for that yet. "
            "Could you rephrase your question?"
        )


    return content.strip()


def _looks_like_tool_call_text(
    content,
):
    if not content:
        return False


    text = (
        content
        .strip()
        .lower()
    )


    suspicious_prefixes = (
        "[tool_calls]",
        "[tool_call]",
        "<tool_call>",
        "tool_calls",
    )


    return any(
        text.startswith(
            prefix
        )
        for prefix
        in suspicious_prefixes
    )


# =========================================================
# 23. TOOL EXECUTION
# =========================================================

def _execute_tool_call(
    tool_call,
    user_id=None,
):
    """
    Execute one model-requested tool.

    user_id is injected internally from JWT authentication.
    """

    name = (
        tool_call
        .function
        .name
    )


    try:

        args = json.loads(
            tool_call
            .function
            .arguments
            or "{}"
        )


    except json.JSONDecodeError:

        return json.dumps(
            {
                "error": (
                    f"Invalid JSON arguments for {name}."
                )
            }
        )


    try:

        if name == "get_my_student_profile":

            return get_my_student_profile(
                user_id=user_id,
            )


        if name == "search_programmes":

            return search_programmes(
                search=args.get(
                    "search"
                ),

                institution=args.get(
                    "institution"
                ),

                career=args.get(
                    "career"
                ),

                study_level=args.get(
                    "study_level"
                ),

                entry_term=args.get(
                    "entry_term"
                ),

                limit=args.get(
                    "limit",
                    MAX_PROGRAMME_RESULTS,
                ),
            )


        if (
            name
            == "recommend_programmes_for_student"
        ):

            return recommend_programmes_for_student(
                user_id=user_id,

                interest=args.get(
                    "interest"
                ),

                limit=args.get(
                    "limit",
                    DEFAULT_PROGRAMME_RECOMMENDATION_RESULTS,
                ),
            )


        if (
            name
            == "search_bursaries_by_course"
        ):

            return search_bursaries_by_course(
                course=args.get(
                    "course"
                ),

                include_expired=args.get(
                    "include_expired",
                    False,
                ),

                limit=args.get(
                    "limit",
                    MAX_SEARCH_RESULTS,
                ),
            )


        if (
            name
            == "recommend_bursaries_for_student"
        ):

            return recommend_bursaries_for_student(
                user_id=user_id,

                course=args.get(
                    "course"
                ),

                limit=args.get(
                    "limit",
                    MAX_SEARCH_RESULTS,
                ),
            )


        if name == "get_bursary_detail":

            return get_bursary_detail(
                bursary_id=args.get(
                    "bursary_id"
                ),
            )


        if name == "web_search":

            return web_search(
                query=args.get(
                    "query"
                ),

                max_results=args.get(
                    "max_results",
                    MAX_WEB_RESULTS,
                ),
            )


        return json.dumps(
            {
                "error": (
                    f"Unknown tool: {name}"
                )
            }
        )


    except Exception as error:

        return json.dumps(
            {
                "error": str(
                    error
                )
            }
        )


def _execute_tool_calls(
    message,
    user_id=None,
):
    """
    Execute all tools requested by model.
    """

    tool_messages = []


    for tool_call in (
        message.tool_calls
    ):

        tool_name = (
            tool_call
            .function
            .name
        )


        print(
            f"[Tool call: {tool_name}]"
        )


        result = _execute_tool_call(
            tool_call,
            user_id=user_id,
        )


        tool_messages.append(
            {
                "role": "tool",

                "tool_call_id": (
                    tool_call.id
                ),

                "content": result,
            }
        )


    return tool_messages


def _tool_calls_can_answer(
    message,
):
    if not message.tool_calls:
        return False


    return any(
        (
            tool_call
            .function
            .name
        )
        in ANSWER_READY_TOOLS

        for tool_call
        in message.tool_calls
    )


# =========================================================
# 24. FINAL GROUNDED RESPONSE
# =========================================================

def _generate_final_answer(
    original_question,
    tool_messages,
):
    """
    Produce student-facing response from verified backend data.
    """

    structured_results = []


    for tool_message in tool_messages:

        content = tool_message.get(
            "content",
            "",
        )


        if content:

            structured_results.append(
                content
            )


    structured_text = "\n".join(
        structured_results
    )


    print(
        "[Final structured payload:]",
        f"{len(structured_text)} characters",
    )


    final_messages = [
        {
            "role": "system",

            "content": (
                "You are PathwaySA, a student-friendly South African "
                "higher-education assistant. "

                "Write the FINAL response using only verified "
                "PathwaySA backend information. "

                "Do not call tools. "
                "Do not output tool syntax or JSON. "

                "Never invent programmes, bursaries, institutions, "
                "requirements, dates, eligibility conditions, "
                "application instructions or links. "

                "For programmes, required_level means the programme "
                "minimum. student_level means the student's achieved "
                "NSC level. student_mark means the student's mark. "

                "Never confuse required_level with student_level. "

                "POTENTIAL_MATCH means the encoded minimum academic "
                "requirements were met. It does not guarantee admission. "

                "INTEREST_MATCH means only that the programme relates "
                "to the student's interest. It is not a ranking. "

                "Do not call a programme best, strongest or most "
                "suitable unless the data explicitly says that. "

                "Never add a year to a programme closing date unless "
                "the year appears explicitly in closing_date. "

                "For bursaries, appearing in a field search means only "
                "that the bursary matched the study field. It does not "
                "prove that the student personally qualifies. "

                "Do not describe the entire bursary list as verified "
                "when some availability statuses require verification. "

                "Do not invent hidden requirements, documentation "
                "requirements or criteria. "

                "If a closing date is missing, state that it is "
                "not confirmed. "

                "When detailed bursary information is provided, "
                "explain the eligibility, deadline and application "
                "information actually supplied. "

                "Keep the answer concise and student-friendly."
            ),
        },

        {
            "role": "user",

            "content": (
                f"Student question:\n"
                f"{original_question}\n\n"

                f"Verified PathwaySA data:\n"
                f"{structured_text}\n\n"

                "Interpret the findings and answer the student's "
                "question."
            ),
        },
    ]


    message = _call_model(
        final_messages,
        allow_tools=False,
    )


    reply = _clean_reply_text(
        message.content
    )


    if _looks_like_tool_call_text(
        reply
    ):

        raise RuntimeError(
            "The model returned tool-call syntax instead "
            "of a normal final response."
        )


    return reply


# =========================================================
# 25. PUBLIC CHAT ENTRY POINT
# =========================================================

def run_chat_turn(
    course,
    history,
    user_message,
    user_id=None,
    max_tool_turns=4,
):
    """
    Run one authenticated PathwaySA chat turn.
    """

    (
        english_message,
        detected_language,
    ) = translate_to_english(
        user_message
    )


    conversation_history = (
        _clean_history(
            history
        )
    )


    # -----------------------------------------------------
    # ENSURE BASE SYSTEM PROMPT
    # -----------------------------------------------------

    has_system = any(
        message.get(
            "role"
        ) == "system"

        for message
        in conversation_history
    )


    if not has_system:

        conversation_history.insert(
            0,
            {
                "role": "system",

                "content": (
                    SYSTEM_PROMPT_TEMPLATE.format(
                        course=(
                            course
                            or "not specified"
                        )
                    )
                ),
            },
        )


    # -----------------------------------------------------
    # CURRENT USER MESSAGE
    # -----------------------------------------------------

    conversation_history.append(
        {
            "role": "user",

            "content": (
                english_message
            ),
        }
    )


    # IMPORTANT:
    #
    # Internal bursary context is merged into the one original
    # system prompt here. No second system message reaches
    # Ministral.

    model_messages = _prepare_history(
        conversation_history,
        for_model=True,
    )


    # -----------------------------------------------------
    # TOOL LOOP
    # -----------------------------------------------------

    for _ in range(
        max_tool_turns
    ):

        message = _call_model(
            model_messages,
            allow_tools=True,
        )


        # -------------------------------------------------
        # DIRECT RESPONSE
        # -------------------------------------------------

        if not message.tool_calls:

            english_reply = _clean_reply_text(
                message.content
            )


            if _looks_like_tool_call_text(
                english_reply
            ):

                english_reply = (
                    "I wasn't able to generate a normal response "
                    "from the available information."
                )


            conversation_history.append(
                {
                    "role": "assistant",

                    "content": (
                        english_reply
                    ),
                }
            )


            updated_history = _prepare_history(
                conversation_history,
                for_model=False,
            )


            final_reply = translate_from_english(
                english_reply,
                detected_language,
            )


            return (
                final_reply,
                updated_history,
            )


        # -------------------------------------------------
        # TOOL REQUEST
        # -------------------------------------------------

        model_messages.append(
            _message_to_dict(
                message
            )
        )


        tool_messages = _execute_tool_calls(
            message,
            user_id=user_id,
        )


        model_messages.extend(
            tool_messages
        )


        # -------------------------------------------------
        # ENOUGH DATA FOR FINAL ANSWER
        # -------------------------------------------------

        if _tool_calls_can_answer(
            message
        ):

            try:

                english_reply = _generate_final_answer(
                    original_question=(
                        english_message
                    ),

                    tool_messages=(
                        tool_messages
                    ),
                )


            except RuntimeError as error:

                print(
                    "[Final answer generation error:]",
                    error,
                )


                english_reply = (
                    "I found information in PathwaySA, but I could "
                    "not format it into a normal response. "
                    "Please try again."
                )


            conversation_history.append(
                {
                    "role": "assistant",

                    "content": (
                        english_reply
                    ),
                }
            )


            # -------------------------------------------------
            # SAVE TITLE -> ID MEMORY
            # -------------------------------------------------

            internal_context = (
                _build_internal_tool_context(
                    tool_messages
                )
            )


            if internal_context:

                # IMPORTANT:
                #
                # This is stored as ASSISTANT, not SYSTEM.
                #
                # _prepare_history(..., for_model=True)
                # will later extract it and merge it into the
                # original system prompt.

                conversation_history.append(
                    {
                        "role": "assistant",

                        "content": (
                            internal_context
                        ),
                    }
                )


                print(
                    "[Stored internal bursary context]"
                )


            updated_history = _prepare_history(
                conversation_history,
                for_model=False,
            )


            final_reply = translate_from_english(
                english_reply,
                detected_language,
            )


            return (
                final_reply,
                updated_history,
            )


    # -----------------------------------------------------
    # TOOL LOOP LIMIT
    # -----------------------------------------------------

    english_reply = (
        "I wasn't able to complete that request using the "
        "available PathwaySA tools. Please try asking the "
        "question more specifically."
    )


    conversation_history.append(
        {
            "role": "assistant",

            "content": (
                english_reply
            ),
        }
    )


    updated_history = _prepare_history(
        conversation_history,
        for_model=False,
    )


    final_reply = translate_from_english(
        english_reply,
        detected_language,
    )


    return (
        final_reply,
        updated_history,
    )