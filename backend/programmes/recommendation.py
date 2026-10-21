import argparse
import json

from programmes.database import DB_PATH, get_connection


def _load_requirements(connection, programme_ids):
    if not programme_ids:
        return {}

    placeholders = ",".join("?" for _ in programme_ids)

    rows = connection.execute(
        f"""
        SELECT
            programme_id,
            exam_type,
            minimum_points_raw,
            minimum_points,
            raw_requirement
        FROM programme_requirements
        WHERE programme_id IN ({placeholders})
        ORDER BY programme_id, id
        """,
        programme_ids,
    ).fetchall()

    requirements = {}

    for row in rows:
        requirements.setdefault(row["programme_id"], []).append(
            {
                "exam_type": row["exam_type"],
                "minimum_points_raw": row["minimum_points_raw"],
                "minimum_points": row["minimum_points"],
                "requirement": row["raw_requirement"],
            }
        )

    return requirements


def list_institutions(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT code, name
            FROM institutions
            ORDER BY name
            """
        ).fetchall()

    return [dict(row) for row in rows]


def list_career_directions(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                direction_number,
                name
            FROM career_directions
            ORDER BY direction_number
            """
        ).fetchall()

    return [dict(row) for row in rows]


def search_programmes(
    query=None,
    institution_code=None,
    career_direction=None,
    study_level=None,
    limit=20,
    db_path=DB_PATH,
):
    conditions = []
    params = []

    if query:
        conditions.append(
            """
            (
                LOWER(p.programme_name) LIKE LOWER(?)
                OR LOWER(o.programme_code) LIKE LOWER(?)
            )
            """
        )

        pattern = f"%{query.strip()}%"
        params.extend([pattern, pattern])

    if institution_code:
        conditions.append("LOWER(i.code) = LOWER(?)")
        params.append(institution_code.strip())

    if career_direction:
        conditions.append(
            """
            (
                LOWER(cd.name) LIKE LOWER(?)
                OR LOWER(cd.raw_name) LIKE LOWER(?)
            )
            """
        )

        pattern = f"%{career_direction.strip()}%"
        params.extend([pattern, pattern])

    if study_level:
        conditions.append(
            "LOWER(p.study_level) LIKE LOWER(?)"
        )
        params.append(f"%{study_level.strip()}%")

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    limit = max(1, min(int(limit), 100))
    params.append(limit)

    query_sql = f"""
        SELECT
            p.id AS programme_id,
            p.programme_name,
            p.study_level,
            p.provider_category,
            p.source,
            p.source_year,
            p.source_pdf_page,
            p.source_handbook_page,

            o.id AS offering_id,
            o.programme_code,
            o.closing_date_raw,
            o.closing_date_iso,
            o.entry_term,
            o.course_duration,
            o.access_route,
            o.notes,

            i.code AS institution_code,
            i.name AS institution,

            c.code AS campus_code,
            c.name AS campus,

            cd.direction_number,
            cd.name AS career_direction

        FROM programme_offerings o

        JOIN programmes p
            ON p.id = o.programme_id

        JOIN institutions i
            ON i.id = o.institution_id

        LEFT JOIN campuses c
            ON c.id = o.campus_id

        JOIN career_directions cd
            ON cd.id = p.career_direction_id

        {where_clause}

        ORDER BY
            p.programme_name,
            i.name,
            c.name

        LIMIT ?
    """

    with get_connection(db_path) as connection:
        rows = connection.execute(
            query_sql,
            params,
        ).fetchall()

        programme_ids = list(
            dict.fromkeys(
                row["programme_id"]
                for row in rows
            )
        )

        requirements = _load_requirements(
            connection,
            programme_ids,
        )

    results = []

    for row in rows:
        item = dict(row)

        item["requirements"] = requirements.get(
            row["programme_id"],
            [],
        )

        results.append(item)

    return results


def get_programme_by_code(
    programme_code,
    db_path=DB_PATH,
):
    results = search_programmes(
        query=programme_code,
        limit=100,
        db_path=db_path,
    )

    exact_matches = [
        result
        for result in results
        if result["programme_code"].lower()
        == programme_code.lower()
    ]

    if not exact_matches:
        return None

    return exact_matches


def main():
    parser = argparse.ArgumentParser(
        description="Search CAO programme data."
    )

    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Programme name or programme code.",
    )

    parser.add_argument(
        "--institution",
        help="Institution code, e.g. ZU, KN, DU, MN.",
    )

    parser.add_argument(
        "--career",
        help="Career direction filter.",
    )

    parser.add_argument(
        "--level",
        help="Study level filter.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    results = search_programmes(
        query=args.query,
        institution_code=args.institution,
        career_direction=args.career,
        study_level=args.level,
        limit=args.limit,
    )

    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()