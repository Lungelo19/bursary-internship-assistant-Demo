import json
import sqlite3

from .database import get_connection
from .security import hash_password, verify_password


def create_user(
    email: str,
    password: str,
    full_name: str,
):
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO users (
                email,
                password_hash
            )
            VALUES (?, ?)
            """,
            (
                email.strip().lower(),
                hash_password(password),
            ),
        )

        user_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO student_profiles (
                user_id,
                full_name
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                full_name.strip(),
            ),
        )

        connection.commit()

        return get_user_by_id(user_id)

    except sqlite3.IntegrityError:
        connection.rollback()
        return None

    finally:
        connection.close()


def get_user_by_email(email: str):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                u.id,
                u.email,
                u.password_hash,
                p.full_name
            FROM users u
            LEFT JOIN student_profiles p
                ON p.user_id = u.id
            WHERE LOWER(u.email) = LOWER(?)
            """,
            (email.strip(),),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def get_user_by_id(user_id: int):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                u.id,
                u.email,
                p.full_name
            FROM users u
            LEFT JOIN student_profiles p
                ON p.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()


def authenticate_user(
    email: str,
    password: str,
):
    user = get_user_by_email(email)

    if not user:
        return None

    if not verify_password(
        password,
        user["password_hash"],
    ):
        return None

    return user


def get_student_profile(user_id: int):
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                u.id AS user_id,
                u.email,
                p.full_name,
                p.province,
                p.education_level,
                p.pass_type,
                p.subjects_json,
                p.interests_json,
                p.preferred_institutions_json,
                p.funding_required
            FROM users u
            LEFT JOIN student_profiles p
                ON p.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return None

        result = dict(row)

        result["subjects"] = json.loads(
            result.pop("subjects_json") or "{}"
        )

        result["interests"] = json.loads(
            result.pop("interests_json") or "[]"
        )

        result["preferred_institutions"] = json.loads(
            result.pop(
                "preferred_institutions_json"
            )
            or "[]"
        )

        result["funding_required"] = bool(
            result["funding_required"]
        )

        return result

    finally:
        connection.close()


def update_student_profile(
    user_id: int,
    profile,
):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO student_profiles (
                user_id,
                full_name,
                province,
                education_level,
                pass_type,
                subjects_json,
                interests_json,
                preferred_institutions_json,
                funding_required,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

            ON CONFLICT(user_id)
            DO UPDATE SET
                full_name = excluded.full_name,
                province = excluded.province,
                education_level = excluded.education_level,
                pass_type = excluded.pass_type,
                subjects_json = excluded.subjects_json,
                interests_json = excluded.interests_json,
                preferred_institutions_json =
                    excluded.preferred_institutions_json,
                funding_required =
                    excluded.funding_required,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                profile.full_name,
                profile.province,
                profile.education_level,
                profile.pass_type,
                json.dumps(profile.subjects),
                json.dumps(profile.interests),
                json.dumps(
                    profile.preferred_institutions
                ),
                int(profile.funding_required),
            ),
        )

        connection.commit()

        return get_student_profile(user_id)

    finally:
        connection.close()