import re


CAO_POINT_BANDS = (
    (80, 7),
    (70, 6),
    (60, 5),
    (50, 4),
    (40, 3),
    (30, 2),
    (0, 1),
)

SUBJECT_ALIASES = {
    "english": "English",
    "engl": "English",
    "english home language": "English Home Language",
    "english hl": "English Home Language",
    "engl hl": "English Home Language",
    "english first additional language": "English First Additional Language",
    "english fal": "English First Additional Language",
    "engl fal": "English First Additional Language",
    "mathematics": "Mathematics",
    "maths": "Mathematics",
    "mathematical literacy": "Mathematical Literacy",
    "maths lit": "Mathematical Literacy",
    "math lit": "Mathematical Literacy",
    "technical mathematics": "Technical Mathematics",
    "tech maths": "Technical Mathematics",
    "physical sciences": "Physical Sciences",
    "physical science": "Physical Sciences",
    "phys sci": "Physical Sciences",
    "life sciences": "Life Sciences",
    "life science": "Life Sciences",
    "life sci": "Life Sciences",
    "life sc": "Life Sciences",
    "agricultural sciences": "Agricultural Sciences",
    "agricultural science": "Agricultural Sciences",
    "agric sci": "Agricultural Sciences",
    "accounting": "Accounting",
    "acc": "Accounting",
    "life orientation": "Life Orientation",
    "lo": "Life Orientation",
    "geography": "Geography",
    "geog": "Geography",
    "tourism": "Tourism",
    "economics": "Economics",
    "econ": "Economics",
    "business studies": "Business Studies",
    "information technology": "Information Technology",
    "it": "Information Technology",
    "computer applications technology": "Computer Applications Technology",
    "cat": "Computer Applications Technology",
    "technical sciences": "Technical Sciences",
    "technical science": "Technical Sciences",
    "tech sci": "Technical Sciences",
    "engineering graphics and design": "Engineering Graphics and Design",
    "eng graph & des": "Engineering Graphics and Design",
}

NORMALISATION_REPLACEMENTS = (
    (r"\bMaths Lit\b", "Mathematical Literacy"),
    (r"\bMath Lit\b", "Mathematical Literacy"),
    (r"\bTech Maths\b", "Technical Mathematics"),
    (r"\bPhys Sci\b", "Physical Sciences"),
    (r"\bLife Sci\b", "Life Sciences"),
    (r"\bLife Sc\b", "Life Sciences"),
    (r"\bAgric Sci\b", "Agricultural Sciences"),
    (r"\bTech Sci\b", "Technical Sciences"),
    (r"\bEng Graph\s*&\s*Des\b", "Engineering Graphics and Design"),
    (r"\bEngl\b", "English"),
    (r"\bAcc\b", "Accounting"),
    (r"\bGeog\b", "Geography"),
    (r"\bEcon\b", "Economics"),
    (r"\bMaths\b", "Mathematics"),
    (r"\bLO\b", "Life Orientation"),
)

SUBJECTS = [
    "Engineering Graphics and Design",
    "Computer Applications Technology",
    "English First Additional Language",
    "English Home Language",
    "Mathematical Literacy",
    "Technical Mathematics",
    "Agricultural Sciences",
    "Physical Sciences",
    "Technical Sciences",
    "Information Technology",
    "Business Studies",
    "Life Orientation",
    "Life Sciences",
    "Mathematics",
    "Accounting",
    "Geography",
    "Economics",
    "Tourism",
    "English",
]

SUBJECT_PATTERN = "(?:" + "|".join(
    re.escape(subject) for subject in SUBJECTS
) + ")"


def mark_to_nsc_level(mark):
    mark = float(mark)

    if mark >= 80:
        return 7
    if mark >= 70:
        return 6
    if mark >= 60:
        return 5
    if mark >= 50:
        return 4
    if mark >= 40:
        return 3
    if mark >= 30:
        return 2
    return 1


def mark_to_cao_points(mark):
    mark = float(mark)

    for lower_bound, points in CAO_POINT_BANDS:
        if mark >= lower_bound:
            return points

    return 0


def canonical_subject_name(name):
    key = re.sub(r"\s+", " ", str(name).strip().lower())
    return SUBJECT_ALIASES.get(key, str(name).strip())


def normalise_results(results):
    """
    Convert:
        {"Maths": 72, "English": 67}

    into canonical result objects.
    """
    normalised = {}

    for raw_name, raw_mark in results.items():
        name = canonical_subject_name(raw_name)
        mark = float(raw_mark)

        normalised[name] = {
            "subject": name,
            "mark": mark,
            "level": mark_to_nsc_level(mark),
            "cao_points": mark_to_cao_points(mark),
        }

    return normalised


def calculate_cao_points(results):
    """
    CAO default points calculation:
    use the best six subjects, excluding Life Orientation.
    """
    normalised = normalise_results(results)

    points = [
        value["cao_points"]
        for name, value in normalised.items()
        if name != "Life Orientation"
    ]

    return sum(sorted(points, reverse=True)[:6])


def normalise_requirement_text(text):
    text = str(text or "")
    text = re.sub(r"\s+", " ", text).strip()

    for pattern, replacement in NORMALISATION_REPLACEMENTS:
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    # Keep the wording readable while making operators predictable.
    text = re.sub(r"\bAND\b", "and", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOR\b", "or", text, flags=re.IGNORECASE)
    return text


def _required_pass_type(text):
    lowered = text.lower()

    if "nsc deg" in lowered:
        return "degree"
    if "nsc dip" in lowered:
        return "diploma"
    if "nsc h cert" in lowered or "nsc cert" in lowered:
        return "higher_certificate"
    if re.search(r"\bnsc\b", lowered):
        return "nsc"

    return None


def _add_rule(rules, seen, rule):
    key = repr(rule)

    if key not in seen:
        rules.append(rule)
        seen.add(key)


def parse_nsc_requirement(raw_requirement):
    """
    Parse the common CAO NSC requirement patterns into deterministic rules.

    The raw requirement is always preserved. If the parser sees wording that
    it cannot safely interpret, it reports that through `review_required`
    instead of guessing.
    """
    text = normalise_requirement_text(raw_requirement)
    rules = []
    seen = set()
    matched_spans = []

    pass_type = _required_pass_type(text)

    if pass_type:
        _add_rule(
            rules,
            seen,
            {
                "type": "pass_type",
                "required": pass_type,
            },
        )

    def remember(match):
        matched_spans.append(match.span())

    # English HL 3/FAL 4
    pattern = re.compile(
        r"English\s+HL\s*([1-7])\s*/\s*FAL\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        _add_rule(
            rules,
            seen,
            {
                "type": "any_of",
                "options": [
                    {
                        "subject": "English Home Language",
                        "min_level": int(match.group(1)),
                    },
                    {
                        "subject": "English First Additional Language",
                        "min_level": int(match.group(2)),
                    },
                ],
            },
        )
        remember(match)

    # English HL/FAL 4
    pattern = re.compile(
        r"English\s+HL\s*/\s*FAL\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        level = int(match.group(1))
        _add_rule(
            rules,
            seen,
            {
                "type": "any_of",
                "options": [
                    {
                        "subject": "English Home Language",
                        "min_level": level,
                    },
                    {
                        "subject": "English First Additional Language",
                        "min_level": level,
                    },
                ],
            },
        )
        remember(match)

    # Mathematics 3 / Mathematical Literacy 5
    # Mathematics / Technical Mathematics 3 / Mathematical Literacy 5
    pattern = re.compile(
        r"Mathematics"
        r"(?:\s*/\s*Technical Mathematics)?"
        r"\s*([1-7])\s*/\s*"
        r"Mathematical Literacy\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        mathematics_level = int(match.group(1))
        literacy_level = int(match.group(2))

        options = [
            {
                "subject": "Mathematics",
                "min_level": mathematics_level,
            },
            {
                "subject": "Mathematical Literacy",
                "min_level": literacy_level,
            },
        ]

        if "Technical Mathematics" in match.group(0):
            options.insert(
                1,
                {
                    "subject": "Technical Mathematics",
                    "min_level": mathematics_level,
                },
            )

        _add_rule(
            rules,
            seen,
            {
                "type": "any_of",
                "options": options,
            },
        )
        remember(match)

    # Shared-level OR group:
    # Agricultural Sciences or Life Sciences or Physical Sciences 4
    pattern = re.compile(
        rf"({SUBJECT_PATTERN}(?:\s+or\s+{SUBJECT_PATTERN})+)\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        names = re.split(
            r"\s+or\s+",
            match.group(1),
            flags=re.IGNORECASE,
        )
        level = int(match.group(2))

        _add_rule(
            rules,
            seen,
            {
                "type": "any_of",
                "options": [
                    {
                        "subject": canonical_subject_name(name),
                        "min_level": level,
                    }
                    for name in names
                ],
            },
        )
        remember(match)

    # Shared-level AND group:
    # English and Life Orientation 4
    # Mathematics and Physical Sciences 6
    pattern = re.compile(
        rf"({SUBJECT_PATTERN}(?:\s+and\s+{SUBJECT_PATTERN})+)\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        names = re.split(
            r"\s+and\s+",
            match.group(1),
            flags=re.IGNORECASE,
        )
        level = int(match.group(2))

        for name in names:
            _add_rule(
                rules,
                seen,
                {
                    "type": "subject",
                    "subject": canonical_subject_name(name),
                    "min_level": level,
                },
            )

        remember(match)

    # Simple single-subject level rules.
    pattern = re.compile(
        rf"({SUBJECT_PATTERN})\s*([1-7])",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        # If this exact text sits inside a more specific rule, adding the
        # subject rule again would incorrectly turn an OR into an AND.
        start, end = match.span()
        inside_specific = any(
            start >= span_start and end <= span_end
            for span_start, span_end in matched_spans
        )

        if inside_specific:
            continue

        _add_rule(
            rules,
            seen,
            {
                "type": "subject",
                "subject": canonical_subject_name(match.group(1)),
                "min_level": int(match.group(2)),
            },
        )
        remember(match)

    # We deliberately flag general subject-count wording for later refinement.
    review_phrases = [
        r"\b(?:two|three|four|five)\s+20\s+credit\s+subjects\b",
        r"\bany\s+[2345]\s+subjects\b",
        r"\bsubjects?\s+level\s+[1-7]\b",
        r"\bequivalent\b",
        r"\bconsult institution\b",
        r"\bbelow\s+\d+%",
        r"\bminimum\s+\d+%",
    ]

    review_required = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in review_phrases
    )

    # If no useful subject/pass rule was extracted from a non-trivial
    # requirement, do not pretend the parser understood it.
    if len(rules) <= (1 if pass_type else 0):
        stripped = re.sub(
            r"NSC(?:\s+(?:Deg|Dip|H Cert|Cert))?"
            r"(?:\s+endorsement)?(?:\s+with)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" ,.-")

        if stripped:
            review_required = True

    return {
        "raw_requirement": raw_requirement,
        "normalised_requirement": text,
        "rules": rules,
        "review_required": review_required,
    }


PASS_TYPE_RANK = {
    "higher_certificate": 1,
    "diploma": 2,
    "degree": 3,
}


def _pass_type_satisfies(student_pass_type, required):
    if required == "nsc":
        return bool(student_pass_type)

    if not student_pass_type:
        return None

    student_rank = PASS_TYPE_RANK.get(student_pass_type)
    required_rank = PASS_TYPE_RANK.get(required)

    if student_rank is None or required_rank is None:
        return None

    return student_rank >= required_rank


def _subject_result(results, subject):
    if subject in results:
        return results[subject]

    # Generic English rules can use either English variant.
    if subject == "English":
        for option in (
            "English",
            "English Home Language",
            "English First Additional Language",
        ):
            if option in results:
                return results[option]

    return None


def evaluate_parsed_requirement(
    parsed,
    student_results,
    student_pass_type=None,
):
    results = normalise_results(student_results)
    checks = []
    failed = False
    missing = False

    for rule in parsed["rules"]:
        if rule["type"] == "pass_type":
            passed = _pass_type_satisfies(
                student_pass_type,
                rule["required"],
            )

            if passed is None:
                missing = True
                checks.append(
                    {
                        "type": "pass_type",
                        "passed": None,
                        "message": (
                            f"NSC pass type needed: {rule['required']}."
                        ),
                    }
                )
            elif passed:
                checks.append(
                    {
                        "type": "pass_type",
                        "passed": True,
                        "message": (
                            f"NSC pass type meets the "
                            f"{rule['required']} requirement."
                        ),
                    }
                )
            else:
                failed = True
                checks.append(
                    {
                        "type": "pass_type",
                        "passed": False,
                        "message": (
                            f"Requires an NSC {rule['required']} pass."
                        ),
                    }
                )

        elif rule["type"] == "subject":
            subject = rule["subject"]
            required_level = rule["min_level"]
            result = _subject_result(results, subject)

            if result is None:
                missing = True
                checks.append(
                    {
                        "type": "subject",
                        "subject": subject,
                        "passed": None,
                        "message": (
                            f"{subject} is required at Level "
                            f"{required_level}, but no result was supplied."
                        ),
                    }
                )
            else:
                passed = result["level"] >= required_level

                if not passed:
                    failed = True

                checks.append(
                    {
                        "type": "subject",
                        "subject": subject,
                        "passed": passed,
                        "required_level": required_level,
                        "student_level": result["level"],
                        "student_mark": result["mark"],
                        "message": (
                            f"{subject}: Level {result['level']} "
                            f"(required Level {required_level})."
                        ),
                    }
                )

        elif rule["type"] == "any_of":
            option_checks = []

            for option in rule["options"]:
                result = _subject_result(
                    results,
                    option["subject"],
                )

                if result is None:
                    option_checks.append(
                        {
                            "subject": option["subject"],
                            "required_level": option["min_level"],
                            "student_level": None,
                            "passed": False,
                        }
                    )
                else:
                    option_checks.append(
                        {
                            "subject": option["subject"],
                            "required_level": option["min_level"],
                            "student_level": result["level"],
                            "student_mark": result["mark"],
                            "passed": (
                                result["level"]
                                >= option["min_level"]
                            ),
                        }
                    )

            passed = any(
                option["passed"]
                for option in option_checks
            )

            if not passed:
                # If the student supplied none of the alternatives,
                # treat it as missing information rather than a confirmed fail.
                supplied_any = any(
                    option["student_level"] is not None
                    for option in option_checks
                )

                if supplied_any:
                    failed = True
                else:
                    missing = True

            labels = " OR ".join(
                f"{option['subject']} Level "
                f"{option['required_level']}"
                for option in option_checks
            )

            checks.append(
                {
                    "type": "any_of",
                    "passed": (
                        True if passed
                        else False if failed
                        else None
                    ),
                    "options": option_checks,
                    "message": f"Requires one of: {labels}.",
                }
            )

    if failed:
        status = "REQUIREMENT_GAP"
    elif missing:
        status = "INSUFFICIENT_INFORMATION"
    elif parsed["review_required"]:
        status = "POSSIBLE_MATCH_REVIEW"
    else:
        status = "POTENTIAL_MATCH"

    return {
        "status": status,
        "checks": checks,
        "review_required": parsed["review_required"],
        "raw_requirement": parsed["raw_requirement"],
    }
