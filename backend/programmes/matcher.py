import argparse
import json
import re

from programmes.database import DB_PATH, get_connection
from programmes.requirements import (
    calculate_cao_points,
    evaluate_parsed_requirement,
    parse_nsc_requirement,
)

UNDERGRADUATE_LEVELS = {
    "DEGREE STUDY",
    "DIPLOMA STUDY",
    "CERTIFICATE STUDY",
    "N H CERT STUDY",
}

STATUS_SCORE = {
    "POTENTIAL_MATCH": 100,
    "POSSIBLE_MATCH_REVIEW": 80,
    "INSUFFICIENT_INFORMATION": 40,
    "REQUIREMENT_GAP": 0,
}

INTEREST_RULES = {
    # Specific interests: use a precise CAO category where safe, then
    # programme-name keywords to catch programmes placed in other categories.
    "computer science": {
        "career_directions": set(),
        "programme_keywords": {
            "computer science",
            "computer sciences",
            "computing",
        },
    },
    "information technology": {
        "career_directions": {
            "INFORMATION TECHNOLOGY (IT) & COMPUTER SCIENCE",
        },
        "programme_keywords": {
            "information technology",
        },
    },
    "it": {
        "career_directions": {
            "INFORMATION TECHNOLOGY (IT) & COMPUTER SCIENCE",
        },
        "programme_keywords": {
            "information technology",
        },
    },
    "software development": {
        "career_directions": set(),
        "programme_keywords": {
            "software development",
            "software engineering",
            "application development",
        },
    },
    "programming": {
        "career_directions": set(),
        "programme_keywords": {
            "programming",
            "software development",
            "software engineering",
        },
    },
    "nursing": {
        # Do not map Nursing to all PARA-MEDICAL programmes.
        "career_directions": set(),
        "programme_keywords": {
            "nursing",
            "nursing science",
        },
    },

    # Broad interests: matching the whole CAO career direction is reasonable.
    "teaching": {
        "career_directions": {"EDUCATION"},
        "programme_keywords": {"teaching", "education"},
    },
    "education": {
        "career_directions": {"EDUCATION"},
        "programme_keywords": {"education", "teaching"},
    },
    "engineering": {
        "career_directions": {"ENGINEERING"},
        "programme_keywords": {"engineering"},
    },
    "logistics": {
        # TRANSPORT is directly relevant. MANAGEMENT AND PLANNING is too broad,
        # so logistics programmes there must match by programme name.
        "career_directions": {"TRANSPORT"},
        "programme_keywords": {"logistics", "supply chain"},
    },
    "supply chain": {
        "career_directions": {"TRANSPORT"},
        "programme_keywords": {"supply chain", "logistics"},
    },
    "transport": {
        "career_directions": {"TRANSPORT"},
        "programme_keywords": {"transport"},
    },
    "human resources": {
        "career_directions": {
            "HUMAN RESOURCES AND INDUSTRIAL RELATIONS",
        },
        "programme_keywords": {
            "human resource",
            "human resources",
            "industrial relations",
        },
    },
    "hr": {
        "career_directions": {
            "HUMAN RESOURCES AND INDUSTRIAL RELATIONS",
        },
        "programme_keywords": {
            "human resource",
            "human resources",
            "industrial relations",
        },
    },
    "accounting": {
        "career_directions": {"ACCOUNTING, FINANCIAL MANAGEMENT"},
        "programme_keywords": {"accounting"},
    },
    "finance": {
        "career_directions": {"ACCOUNTING, FINANCIAL MANAGEMENT"},
        "programme_keywords": {"finance", "financial management"},
    },
    "business": {
        "career_directions": {
            "MANAGEMENT AND PLANNING",
            "ADMINISTRATION",
        },
        "programme_keywords": {
            "business",
            "management",
            "administration",
        },
    },
    "management": {
        "career_directions": {
            "MANAGEMENT AND PLANNING",
            "ADMINISTRATION",
        },
        "programme_keywords": {"management"},
    },
    "law": {
        "career_directions": {"SOCIAL SCIENCES/LEGAL SERVICES"},
        "programme_keywords": {"law", "legal"},
    },
    "legal": {
        "career_directions": {"SOCIAL SCIENCES/LEGAL SERVICES"},
        "programme_keywords": {"law", "legal"},
    },
    "medicine": {
        "career_directions": {"MEDICINE, MEDICAL TECHNOLOGY"},
        "programme_keywords": {"medicine", "medical"},
    },
    "health": {
        "career_directions": {
            "MEDICINE, MEDICAL TECHNOLOGY",
            "PARA-MEDICAL",
        },
        "programme_keywords": {"health", "medical"},
    },
    "agriculture": {
        "career_directions": {"AGRICULTURE/NATURE CONSERVATION"},
        "programme_keywords": {"agriculture", "agricultural"},
    },
    "nature conservation": {
        "career_directions": {"AGRICULTURE/NATURE CONSERVATION"},
        "programme_keywords": {"nature conservation", "conservation"},
    },
    "tourism": {
        "career_directions": {"TOURISM/HOSPITALITY"},
        "programme_keywords": {"tourism"},
    },
    "hospitality": {
        "career_directions": {"TOURISM/HOSPITALITY"},
        "programme_keywords": {"hospitality"},
    },
    "marketing": {
        "career_directions": {"PUBLIC RELATIONS/MARKETING"},
        "programme_keywords": {"marketing"},
    },
    "public relations": {
        "career_directions": {"PUBLIC RELATIONS/MARKETING"},
        "programme_keywords": {"public relations"},
    },
    "journalism": {
        "career_directions": {"COMMUNICATION/JOURNALISM"},
        "programme_keywords": {"journalism"},
    },
    "communication": {
        "career_directions": {"COMMUNICATION/JOURNALISM"},
        "programme_keywords": {"communication"},
    },
    "construction": {
        "career_directions": {"CONSTRUCTION/SURVEYING"},
        "programme_keywords": {"construction"},
    },
    "surveying": {
        "career_directions": {"CONSTRUCTION/SURVEYING"},
        "programme_keywords": {"surveying"},
    },
    "science": {
        "career_directions": {"SCIENCE AND MATHEMATICS"},
        "programme_keywords": {"science"},
    },
    "mathematics": {
        "career_directions": {"SCIENCE AND MATHEMATICS"},
        "programme_keywords": {"mathematics", "mathematical"},
    },
    "art": {
        "career_directions": {"VISUAL ARTS/DESIGN"},
        "programme_keywords": {"art", "visual art"},
    },
    "design": {
        "career_directions": {"VISUAL ARTS/DESIGN"},
        "programme_keywords": {"design"},
    },
}


def _tokenise(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) > 2
    }


def _normalise_interest(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _get_interest_rule(interest):
    interest_key = _normalise_interest(interest)

    return INTEREST_RULES.get(
        interest_key,
        {
            "career_directions": set(),
            "programme_keywords": {interest_key} if interest_key else set(),
        },
    )


def _career_matches_interest(career_direction, interest):
    rule = _get_interest_rule(interest)
    career = str(career_direction or "").strip().upper()

    return career in rule["career_directions"]


def _text_matches_keyword(text, keyword):
    text = str(text or "").lower()
    keyword = _normalise_interest(keyword)

    if not keyword:
        return False

    if keyword in text:
        return True

    keyword_tokens = _tokenise(keyword)
    text_tokens = _tokenise(text)

    return bool(keyword_tokens) and keyword_tokens.issubset(text_tokens)


def _programme_name_matches_interest(programme_name, interest):
    rule = _get_interest_rule(interest)

    return any(
        _text_matches_keyword(programme_name, keyword)
        for keyword in rule["programme_keywords"]
    )


def is_interest_relevant(programme_name, career_direction, interests):
    for interest in interests or []:
        if _career_matches_interest(career_direction, interest):
            return True

        if _programme_name_matches_interest(programme_name, interest):
            return True

    return False


def _interest_score(programme_name, career_direction, interests):
    if not interests:
        return 0

    score = 0

    for interest in interests:
        if _career_matches_interest(career_direction, interest):
            score += 20

        # Programme-name matches are more precise than broad category matches.
        if _programme_name_matches_interest(programme_name, interest):
            score += 30

    return min(score, 50)


def _load_candidate_rows(db_path, institution_codes=None, study_levels=None):
    conditions = ["r.exam_type = 'NSC'"]
    params = []

    if study_levels:
        placeholders = ",".join("?" for _ in study_levels)
        conditions.append(f"p.study_level IN ({placeholders})")
        params.extend(study_levels)

    if institution_codes:
        codes = [code.upper() for code in institution_codes]
        placeholders = ",".join("?" for _ in codes)
        conditions.append(f"i.code IN ({placeholders})")
        params.extend(codes)

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            p.id AS programme_id,
            p.programme_name,
            p.study_level,
            p.provider_category,
            p.source,
            p.source_year,
            p.source_handbook_page,
            o.id AS offering_id,
            o.programme_code,
            o.closing_date_raw,
            o.entry_term,
            o.course_duration,
            o.access_route,
            o.notes,
            i.code AS institution_code,
            i.name AS institution,
            c.code AS campus_code,
            c.name AS campus,
            cd.name AS career_direction,
            r.minimum_points_raw,
            r.minimum_points,
            r.raw_requirement
        FROM programme_requirements r
        JOIN programmes p ON p.id = r.programme_id
        JOIN programme_offerings o ON o.programme_id = p.id
        JOIN institutions i ON i.id = o.institution_id
        LEFT JOIN campuses c ON c.id = o.campus_id
        JOIN career_directions cd ON cd.id = p.career_direction_id
        WHERE {where_clause}
        ORDER BY p.programme_name, i.name, c.name
    """

    with get_connection(db_path) as connection:
        return connection.execute(sql, params).fetchall()


def _evaluate_points(student_points, minimum_points, minimum_points_raw):
    if minimum_points is None:
        return {
            "passed": None,
            "required": minimum_points_raw,
            "student_points": student_points,
            "message": "No simple numeric minimum-points value was available for this requirement.",
        }

    passed = student_points >= minimum_points

    return {
        "passed": passed,
        "required": minimum_points,
        "student_points": student_points,
        "message": f"CAO points: {student_points}; minimum: {minimum_points}.",
    }


def _evaluate_candidate(
    row,
    student_results,
    student_pass_type,
    student_points,
    interests,
    preferred_institutions,
):
    parsed = parse_nsc_requirement(row["raw_requirement"])
    requirement_result = evaluate_parsed_requirement(
        parsed,
        student_results,
        student_pass_type,
    )

    points_result = _evaluate_points(
        student_points,
        row["minimum_points"],
        row["minimum_points_raw"],
    )

    status = requirement_result["status"]

    if points_result["passed"] is False:
        status = "REQUIREMENT_GAP"
    elif points_result["passed"] is None and status == "POTENTIAL_MATCH":
        status = "POSSIBLE_MATCH_REVIEW"

    interest_relevant = is_interest_relevant(
        row["programme_name"],
        row["career_direction"],
        interests,
    )

    ranking_score = STATUS_SCORE.get(status, 0)

    if interest_relevant:
        ranking_score += _interest_score(
            row["programme_name"],
            row["career_direction"],
            interests,
        )

    if (
        preferred_institutions
        and row["institution_code"] in preferred_institutions
    ):
        ranking_score += 10

    return {
        "offering_id": row["offering_id"],
        "programme_id": row["programme_id"],
        "programme_name": row["programme_name"],
        "programme_code": row["programme_code"],
        "institution_code": row["institution_code"],
        "institution": row["institution"],
        "campus_code": row["campus_code"],
        "campus": row["campus"],
        "career_direction": row["career_direction"],
        "study_level": row["study_level"],
        "closing_date": row["closing_date_raw"],
        "entry_term": row["entry_term"],
        "course_duration": row["course_duration"],
        "access_route": row["access_route"],
        "notes": row["notes"],
        "student_cao_points": student_points,
        "minimum_points": row["minimum_points"],
        "match_status": status,
        "interest_relevant": interest_relevant,
        "ranking_score": ranking_score,
        "points_check": points_result,
        "requirement_check": requirement_result,
        "source": row["source"],
        "source_year": row["source_year"],
        "source_handbook_page": row["source_handbook_page"],
    }


def _deduplicate(items):
    best = {}

    for item in items:
        key = item["offering_id"]
        existing = best.get(key)

        if existing is None or item["ranking_score"] > existing["ranking_score"]:
            best[key] = item

    return list(best.values())


def recommend_programmes(
    student_results,
    student_pass_type,
    interests=None,
    preferred_institutions=None,
    preferred_study_levels=None,
    interest_limit=10,
    limit=20,
    include_gaps=False,
    include_uncertain=False,
    db_path=DB_PATH,
):
    interests = interests or []
    preferred_institutions = [
        code.upper() for code in (preferred_institutions or [])
    ]
    study_levels = preferred_study_levels or sorted(UNDERGRADUATE_LEVELS)

    limit = max(1, int(limit))
    interest_limit = max(0, min(int(interest_limit), limit))

    student_points = calculate_cao_points(student_results)

    rows = _load_candidate_rows(
        db_path=db_path,
        institution_codes=preferred_institutions or None,
        study_levels=study_levels,
    )

    evaluated = [
        _evaluate_candidate(
            row=row,
            student_results=student_results,
            student_pass_type=student_pass_type,
            student_points=student_points,
            interests=interests,
            preferred_institutions=preferred_institutions,
        )
        for row in rows
    ]

    evaluated = _deduplicate(evaluated)

    allowed_statuses = {
        "POTENTIAL_MATCH",
        "POSSIBLE_MATCH_REVIEW",
    }

    if include_uncertain:
        allowed_statuses.add("INSUFFICIENT_INFORMATION")

    if include_gaps:
        allowed_statuses.add("REQUIREMENT_GAP")

    evaluated = [
        item
        for item in evaluated
        if item["match_status"] in allowed_statuses
    ]

    interest_matches = [
        item for item in evaluated if item["interest_relevant"]
    ]
    other_matches = [
        item for item in evaluated if not item["interest_relevant"]
    ]

    def sort_key(item):
        return (
            -item["ranking_score"],
            item["programme_name"].lower(),
            item["institution"].lower(),
            str(item["campus"] or "").lower(),
        )

    interest_matches.sort(key=sort_key)
    other_matches.sort(key=sort_key)

    selected_interest = interest_matches[:interest_limit]
    remaining_slots = limit - len(selected_interest)
    selected_other = other_matches[:remaining_slots]

    for item in selected_interest:
        item["recommendation_group"] = "INTEREST_MATCH"

    for item in selected_other:
        item["recommendation_group"] = "OTHER_QUALIFYING"

    return {
        "student_cao_points": student_points,
        "interests": interests,
        "interest_matches_found": len(interest_matches),
        "interest_matches_returned": len(selected_interest),
        "other_qualifying_found": len(other_matches),
        "other_qualifying_returned": len(selected_other),
        "recommendations": selected_interest + selected_other,
    }


def _parse_subject_argument(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "Use SUBJECT=MARK, for example 'Mathematics=72'."
        )

    subject, mark = value.split("=", 1)

    try:
        mark = float(mark)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid mark in {value!r}."
        ) from exc

    if mark < 0 or mark > 100:
        raise argparse.ArgumentTypeError(
            "Marks must be between 0 and 100."
        )

    return subject.strip(), mark


def main():
    parser = argparse.ArgumentParser(
        description="Match an NSC learner to CAO programmes."
    )

    parser.add_argument(
        "--subject",
        action="append",
        type=_parse_subject_argument,
        required=True,
    )
    parser.add_argument(
        "--pass-type",
        choices=["degree", "diploma", "higher_certificate"],
        required=True,
    )
    parser.add_argument("--interest", action="append", default=[])
    parser.add_argument("--institution", action="append", default=[])
    parser.add_argument("--interest-limit", type=int, default=10)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--include-gaps", action="store_true")
    parser.add_argument("--include-uncertain", action="store_true")
    parser.add_argument("--db", default=str(DB_PATH))

    args = parser.parse_args()

    output = recommend_programmes(
        student_results=dict(args.subject),
        student_pass_type=args.pass_type,
        interests=args.interest,
        preferred_institutions=args.institution,
        interest_limit=args.interest_limit,
        limit=args.limit,
        include_gaps=args.include_gaps,
        include_uncertain=args.include_uncertain,
        db_path=args.db,
    )

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
