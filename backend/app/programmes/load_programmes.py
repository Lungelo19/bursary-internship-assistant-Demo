import argparse
import json
import re
from pathlib import Path

from app.programmes.database import (
    DB_PATH,
    database_summary,
    get_connection,
    init_db,
)


CAREER_DIRECTION_RE = re.compile(
    r"^\s*(\d+)\.\s*(.+?)\s*$"
)


def parse_career_direction(raw_name):
    """
    Split:
        '12. INFORMATION TECHNOLOGY (IT) & COMPUTER SCIENCE'

    into:
        (12, 'INFORMATION TECHNOLOGY (IT) & COMPUTER SCIENCE')
    """
    raw_name = (raw_name or "").strip()
    match = CAREER_DIRECTION_RE.match(raw_name)

    if not match:
        return None, raw_name

    return int(match.group(1)), match.group(2).strip()


def parse_minimum_points(value):
    """
    Convert a simple integer value such as '28' to 28.

    Complex or missing values are deliberately kept as raw text
    and return None here.
    """
    value = (value or "").strip()

    if value.isdigit():
        return int(value)

    return None


def get_or_create_institution(
    connection,
    code,
    name,
):
    row = connection.execute(
        """
        SELECT id
        FROM institutions
        WHERE code = ?
        """,
        (code,),
    ).fetchone()

    if row:
        return row["id"]

    cursor = connection.execute(
        """
        INSERT INTO institutions (code, name)
        VALUES (?, ?)
        """,
        (code, name),
    )

    return cursor.lastrowid


def get_or_create_campus(
    connection,
    institution_id,
    campus_code,
    campus_name,
):
    if not campus_code:
        return None

    row = connection.execute(
        """
        SELECT id
        FROM campuses
        WHERE institution_id = ?
          AND code = ?
        """,
        (institution_id, campus_code),
    ).fetchone()

    if row:
        if not row["id"]:
            return None
        return row["id"]

    cursor = connection.execute(
        """
        INSERT INTO campuses (
            institution_id,
            code,
            name
        )
        VALUES (?, ?, ?)
        """,
        (
            institution_id,
            campus_code,
            campus_name,
        ),
    )

    return cursor.lastrowid


def get_or_create_career_direction(
    connection,
    raw_name,
):
    row = connection.execute(
        """
        SELECT id
        FROM career_directions
        WHERE raw_name = ?
        """,
        (raw_name,),
    ).fetchone()

    if row:
        return row["id"]

    number, name = parse_career_direction(raw_name)

    cursor = connection.execute(
        """
        INSERT INTO career_directions (
            raw_name,
            direction_number,
            name
        )
        VALUES (?, ?, ?)
        """,
        (
            raw_name,
            number,
            name,
        ),
    )

    return cursor.lastrowid


def insert_programme(
    connection,
    record,
    career_direction_id,
):
    cursor = connection.execute(
        """
        INSERT INTO programmes (
            programme_name,
            career_direction_id,
            provider_category,
            study_level,
            source,
            source_year,
            source_pdf_page,
            source_handbook_page
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get("programme_name"),
            career_direction_id,
            record.get("provider_category"),
            record.get("study_level"),
            record.get("source", "CAO Handbook 2027"),
            record.get("source_year", 2027),
            record.get("source_pdf_page"),
            record.get("source_handbook_page"),
        ),
    )

    return cursor.lastrowid


def insert_requirements(
    connection,
    programme_id,
    requirements,
):
    inserted = 0

    for requirement in requirements:
        raw_requirement = (
            requirement.get("raw_requirement")
            or ""
        ).strip()

        if not raw_requirement:
            continue

        minimum_points_raw = (
            requirement.get("minimum_points_raw")
            or ""
        ).strip()

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO programme_requirements (
                programme_id,
                exam_type,
                minimum_points_raw,
                minimum_points,
                raw_requirement
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                programme_id,
                requirement.get("exam_type", "Other"),
                minimum_points_raw,
                parse_minimum_points(
                    minimum_points_raw
                ),
                raw_requirement,
            ),
        )

        if cursor.rowcount:
            inserted += 1

    return inserted


def insert_offerings(
    connection,
    programme_id,
    offerings,
):
    inserted = 0
    skipped_duplicates = 0

    for offering in offerings:
        institution_code = offering.get(
            "institution_code"
        )
        institution_name = offering.get(
            "institution"
        )

        if not institution_code or not institution_name:
            raise ValueError(
                "Offering is missing institution data: "
                f"{offering}"
            )

        institution_id = get_or_create_institution(
            connection,
            institution_code,
            institution_name,
        )

        campus_code = (
            offering.get("campus_code")
            or ""
        ).strip()

        campus_name = offering.get("campus")

        campus_id = get_or_create_campus(
            connection,
            institution_id,
            campus_code,
            campus_name,
        )

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO programme_offerings (
                programme_id,
                programme_code,
                institution_id,
                campus_id,
                campus_code,
                closing_date_raw,
                closing_date_iso,
                entry_term,
                course_duration,
                access_route,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                programme_id,
                offering.get("programme_code"),
                institution_id,
                campus_id,
                campus_code,
                (
                    offering.get("closing_date_raw")
                    or ""
                ).strip(),
                None,
                (
                    offering.get("entry_term")
                    or ""
                ).strip(),
                (
                    offering.get("course_duration")
                    or ""
                ).strip(),
                (
                    offering.get("access_route")
                    or ""
                ).strip(),
                (
                    offering.get("notes")
                    or ""
                ).strip(),
            ),
        )

        if cursor.rowcount:
            inserted += 1
        else:
            skipped_duplicates += 1

    return inserted, skipped_duplicates


def load_programmes(
    json_path,
    db_path=DB_PATH,
    reset=False,
):
    json_path = Path(json_path)
    db_path = Path(db_path)

    if not json_path.exists():
        raise FileNotFoundError(
            f"Programme JSON file not found: {json_path}"
        )

    if reset and db_path.exists():
        db_path.unlink()

    init_db(db_path)

    with json_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "Expected the programme JSON file "
            "to contain a list."
        )

    programme_count = 0
    offering_count = 0
    requirement_count = 0
    duplicate_offerings = 0

    with get_connection(db_path) as connection:
        for record in records:
            raw_career = (
                record.get("career_direction")
                or "Unknown"
            ).strip()

            career_direction_id = (
                get_or_create_career_direction(
                    connection,
                    raw_career,
                )
            )

            programme_id = insert_programme(
                connection,
                record,
                career_direction_id,
            )

            programme_count += 1

            inserted_requirements = insert_requirements(
                connection,
                programme_id,
                record.get("requirements", []),
            )

            requirement_count += inserted_requirements

            (
                inserted_offerings,
                skipped_duplicates,
            ) = insert_offerings(
                connection,
                programme_id,
                record.get("offerings", []),
            )

            offering_count += inserted_offerings
            duplicate_offerings += skipped_duplicates

    return {
        "source_records": len(records),
        "programmes_inserted": programme_count,
        "offerings_inserted": offering_count,
        "duplicate_offerings_skipped": duplicate_offerings,
        "requirements_inserted": requirement_count,
        "database": str(db_path),
        "database_summary": database_summary(db_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Load extracted CAO programme data "
            "into SQLite."
        )
    )

    parser.add_argument(
        "json_path",
        help="Path to cao_programmes_2027_raw.json",
    )

    parser.add_argument(
        "--db",
        default=str(DB_PATH),
        help=(
            "SQLite output path. "
            f"Default: {DB_PATH}"
        ),
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Delete the existing database before "
            "loading the programme data."
        ),
    )

    args = parser.parse_args()

    result = load_programmes(
        json_path=args.json_path,
        db_path=args.db,
        reset=args.reset,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
