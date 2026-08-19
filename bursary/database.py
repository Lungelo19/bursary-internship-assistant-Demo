import json
import os
import sqlite3


JSON_FILE = os.path.join(
    "data",
    "bursaries.json"
)

DATABASE_FILE = os.path.join(
    "data",
    "bursaries.db"
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    """
    Create and return a connection
    to the SQLite database.
    """

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    # Enable foreign key support
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# =========================================================
# CREATE TABLES
# =========================================================

def create_tables(connection):
    """
    Create all tables required to store
    our bursary data.
    """

    cursor = connection.cursor()

    # -----------------------------------------
    # Main bursary table
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bursaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            opportunity_type TEXT NOT NULL,
            closing_date TEXT,
            closing_status TEXT NOT NULL,
            application_url TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE
        )
    """)

    # -----------------------------------------
    # Fields of study
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fields_of_study (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            field TEXT NOT NULL,
            position INTEGER,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE,

            UNIQUE (bursary_id, field)
        )
    """)

    # -----------------------------------------
    # Eligibility requirements
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eligibility_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            requirement TEXT NOT NULL,
            position INTEGER,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------
    # Closing dates
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closing_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            closing_date TEXT NOT NULL,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------
    # Original closing-date text
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closing_date_text (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            position INTEGER,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------
    # Application instructions
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS application_instructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            instruction TEXT NOT NULL,
            position INTEGER,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------
    # ZA Bursaries categories
    # -----------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bursary_id INTEGER NOT NULL,
            category TEXT NOT NULL,

            FOREIGN KEY (bursary_id)
                REFERENCES bursaries(id)
                ON DELETE CASCADE,

            UNIQUE (bursary_id, category)
        )
    """)

    connection.commit()


# =========================================================
# CLEAR OLD DATA
# =========================================================

def clear_database(connection):
    """
    Remove existing bursary records.

    Child records are deleted automatically
    because of ON DELETE CASCADE.
    """

    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM bursaries"
    )

    connection.commit()


# =========================================================
# LOAD JSON
# =========================================================

def load_json():
    """
    Read bursaries.json.
    """

    with open(
        JSON_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# =========================================================
# INSERT ONE BURSARY
# =========================================================

def insert_bursary(
    connection,
    bursary
):
    """
    Insert one bursary and all of its
    related information.
    """

    cursor = connection.cursor()

    # -----------------------------------------
    # Main bursary
    # -----------------------------------------

    cursor.execute(
        """
        INSERT INTO bursaries (
            title,
            opportunity_type,
            closing_date,
            closing_status,
            application_url,
            source,
            source_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bursary["title"],
            bursary["type"],
            bursary.get("closing_date"),
            bursary["closing_status"],
            bursary.get("application_url"),
            bursary["source"],
            bursary["source_url"]
        )
    )

    bursary_id = cursor.lastrowid

    # -----------------------------------------
    # Fields of study
    # -----------------------------------------

    for position, field in enumerate(
        bursary.get(
            "fields_of_study",
            []
        ),
        start=1
    ):

        cursor.execute(
            """
            INSERT INTO fields_of_study (
                bursary_id,
                field,
                position
            )
            VALUES (?, ?, ?)
            """,
            (
                bursary_id,
                field,
                position
            )
        )

    # -----------------------------------------
    # Eligibility
    # -----------------------------------------

    for position, requirement in enumerate(
        bursary.get(
            "eligibility",
            []
        ),
        start=1
    ):

        cursor.execute(
            """
            INSERT INTO eligibility_requirements (
                bursary_id,
                requirement,
                position
            )
            VALUES (?, ?, ?)
            """,
            (
                bursary_id,
                requirement,
                position
            )
        )

    # -----------------------------------------
    # Closing dates
    # -----------------------------------------

    for closing_date in bursary.get(
        "closing_dates",
        []
    ):

        cursor.execute(
            """
            INSERT INTO closing_dates (
                bursary_id,
                category,
                closing_date
            )
            VALUES (?, ?, ?)
            """,
            (
                bursary_id,
                closing_date["category"],
                closing_date["date"]
            )
        )

    # -----------------------------------------
    # Original closing text
    # -----------------------------------------

    for position, text in enumerate(
        bursary.get(
            "closing_date_text",
            []
        ),
        start=1
    ):

        cursor.execute(
            """
            INSERT INTO closing_date_text (
                bursary_id,
                text,
                position
            )
            VALUES (?, ?, ?)
            """,
            (
                bursary_id,
                text,
                position
            )
        )

    # -----------------------------------------
    # Application instructions
    # -----------------------------------------

    for position, instruction in enumerate(
        bursary.get(
            "application_instructions",
            []
        ),
        start=1
    ):

        cursor.execute(
            """
            INSERT INTO application_instructions (
                bursary_id,
                instruction,
                position
            )
            VALUES (?, ?, ?)
            """,
            (
                bursary_id,
                instruction,
                position
            )
        )

    # -----------------------------------------
    # Categories
    # -----------------------------------------

    for category in bursary.get(
        "categories",
        []
    ):

        cursor.execute(
            """
            INSERT INTO categories (
                bursary_id,
                category
            )
            VALUES (?, ?)
            """,
            (
                bursary_id,
                category
            )
        )


# =========================================================
# IMPORT DATA
# =========================================================

def import_bursaries():
    """
    Import all bursaries from JSON
    into SQLite.
    """

    os.makedirs(
        "data",
        exist_ok=True
    )

    bursaries = load_json()

    connection = get_connection()

    try:

        create_tables(
            connection
        )

        clear_database(
            connection
        )

        print(
            f"Importing {len(bursaries)} "
            "bursaries..."
        )

        for bursary in bursaries:

            insert_bursary(
                connection,
                bursary
            )

            print(
                "Imported:",
                bursary["title"]
            )

        connection.commit()

        print()
        print("=" * 70)
        print("DATABASE IMPORT COMPLETE")
        print("=" * 70)

        print(
            "Database:",
            DATABASE_FILE
        )

        print(
            "Bursaries imported:",
            len(bursaries)
        )

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


if __name__ == "__main__":

    import_bursaries()