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

    result = {}

    for row in rows:
        result.setdefault(row["programme_id"], []).append(
            {
                "exam_type": row["exam_type"],
                "minimum_points_raw": row["minimum_points_raw"],
                "minimum_points": row["minimum_points"],
                "raw_requirement": row["raw_requirement"],
            }
        )

    return result


def search_programmes(
    search=None,
    institution=None,
    campus=None,
    career=None,
    study_level=None,
    entry_term=None,
    limit=20,
    offset=0,
    db_path=DB_PATH,
):
    conditions = []
    params = []

    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            """
            (
                LOWER(p.programme_name) LIKE LOWER(?)
                OR LOWER(o.programme_code) LIKE LOWER(?)
                OR LOWER(i.name) LIKE LOWER(?)
                OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
                OR LOWER(cd.name) LIKE LOWER(?)
            )
            """
        )
        params.extend([pattern] * 5)

    if institution:
        conditions.append(
            """
            (
                LOWER(i.code) = LOWER(?)
                OR LOWER(i.name) = LOWER(?)
            )
            """
        )
        params.extend(
            [
                institution.strip(),
                institution.strip(),
            ]
        )

    if campus:
        conditions.append(
            """
            (
                LOWER(COALESCE(c.code, '')) = LOWER(?)
                OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
            )
            """
        )
        params.extend(
            [
                campus.strip(),
                f"%{campus.strip()}%",
            ]
        )

    if career:
        conditions.append(
            """
            (
                LOWER(cd.name) LIKE LOWER(?)
                OR LOWER(cd.raw_name) LIKE LOWER(?)
            )
            """
        )
        pattern = f"%{career.strip()}%"
        params.extend([pattern, pattern])

    if study_level:
        conditions.append(
            "LOWER(p.study_level) = LOWER(?)"
        )
        params.append(study_level.strip())

    if entry_term:
        conditions.append(
            "LOWER(o.entry_term) = LOWER(?)"
        )
        params.append(str(entry_term).strip())

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    count_sql = f"""
        SELECT COUNT(*)
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
    """

    data_sql = f"""
        SELECT
            o.id AS offering_id,
            p.id AS programme_id,
            p.programme_name,
            p.study_level,
            p.provider_category,
            p.source,
            p.source_year,
            p.source_pdf_page,
            p.source_handbook_page,

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
            COALESCE(c.name, ''),
            o.programme_code

        LIMIT ? OFFSET ?
    """

    with get_connection(db_path) as connection:
        total = connection.execute(
            count_sql,
            params,
        ).fetchone()[0]

        rows = connection.execute(
            data_sql,
            [*params, limit, offset],
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

    items = []

    for row in rows:
        item = dict(row)
        item["requirements"] = requirements.get(
            row["programme_id"],
            [],
        )
        items.append(item)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


def get_programme_offering(offering_id, db_path=DB_PATH):
    sql = """
        SELECT
            o.id AS offering_id,
            p.id AS programme_id,
            p.programme_name,
            p.study_level,
            p.provider_category,
            p.source,
            p.source_year,
            p.source_pdf_page,
            p.source_handbook_page,

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

        WHERE o.id = ?
    """

    with get_connection(db_path) as connection:
        row = connection.execute(
            sql,
            (offering_id,),
        ).fetchone()

        if row is None:
            return None

        requirements = _load_requirements(
            connection,
            [row["programme_id"]],
        )

    item = dict(row)
    item["requirements"] = requirements.get(
        row["programme_id"],
        [],
    )

    return item


def list_institutions(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                i.code,
                i.name,
                COUNT(o.id) AS offering_count
            FROM institutions i
            LEFT JOIN programme_offerings o
                ON o.institution_id = i.id
            GROUP BY i.id, i.code, i.name
            ORDER BY i.name
            """
        ).fetchall()

    return [dict(row) for row in rows]


def list_campuses(institution=None, db_path=DB_PATH):
    conditions = []
    params = []

    if institution:
        conditions.append(
            """
            (
                LOWER(i.code) = LOWER(?)
                OR LOWER(i.name) = LOWER(?)
            )
            """
        )
        params.extend(
            [
                institution.strip(),
                institution.strip(),
            ]
        )

    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            c.id,
            c.code,
            c.name,
            i.code AS institution_code,
            i.name AS institution,
            COUNT(o.id) AS offering_count
        FROM campuses c
        JOIN institutions i
            ON i.id = c.institution_id
        LEFT JOIN programme_offerings o
            ON o.campus_id = c.id
        {where_clause}
        GROUP BY
            c.id,
            c.code,
            c.name,
            i.code,
            i.name
        ORDER BY
            i.name,
            COALESCE(c.name, c.code)
    """

    with get_connection(db_path) as connection:
        rows = connection.execute(
            sql,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def list_career_directions(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                cd.direction_number,
                cd.name,
                cd.raw_name,
                COUNT(DISTINCT p.id) AS programme_count,
                COUNT(o.id) AS offering_count
            FROM career_directions cd
            LEFT JOIN programmes p
                ON p.career_direction_id = cd.id
            LEFT JOIN programme_offerings o
                ON o.programme_id = p.id
            GROUP BY
                cd.id,
                cd.direction_number,
                cd.name,
                cd.raw_name
            ORDER BY cd.direction_number
            """
        ).fetchall()

    return [dict(row) for row in rows]


def list_study_levels(db_path=DB_PATH):
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                p.study_level,
                COUNT(DISTINCT p.id) AS programme_count,
                COUNT(o.id) AS offering_count
            FROM programmes p
            LEFT JOIN programme_offerings o
                ON o.programme_id = p.id
            WHERE p.study_level IS NOT NULL
              AND TRIM(p.study_level) != ''
            GROUP BY p.study_level
            ORDER BY p.study_level
            """
        ).fetchall()

    return [dict(row) for row in rows]
