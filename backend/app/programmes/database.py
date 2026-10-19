import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "programmes.db"


def get_connection(db_path=DB_PATH):
    """
    Open the programmes SQLite database with foreign keys enabled.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db(db_path=DB_PATH):
    """
    Create the programme database schema if it does not already exist.
    """
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS institutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                UNIQUE(institution_id, code),
                FOREIGN KEY (institution_id)
                    REFERENCES institutions(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS career_directions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_name TEXT NOT NULL UNIQUE,
                direction_number INTEGER,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS programmes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programme_name TEXT NOT NULL,
                career_direction_id INTEGER NOT NULL,
                provider_category TEXT,
                study_level TEXT,
                source TEXT NOT NULL,
                source_year INTEGER NOT NULL,
                source_pdf_page INTEGER,
                source_handbook_page INTEGER,
                FOREIGN KEY (career_direction_id)
                    REFERENCES career_directions(id)
                    ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS programme_offerings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programme_id INTEGER NOT NULL,
                programme_code TEXT NOT NULL,
                institution_id INTEGER NOT NULL,
                campus_id INTEGER,
                campus_code TEXT,
                closing_date_raw TEXT NOT NULL DEFAULT '',
                closing_date_iso TEXT,
                entry_term TEXT NOT NULL DEFAULT '',
                course_duration TEXT,
                access_route TEXT,
                notes TEXT,
                UNIQUE(
                    programme_code,
                    entry_term,
                    closing_date_raw
                ),
                FOREIGN KEY (programme_id)
                    REFERENCES programmes(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (institution_id)
                    REFERENCES institutions(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (campus_id)
                    REFERENCES campuses(id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS programme_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programme_id INTEGER NOT NULL,
                exam_type TEXT NOT NULL,
                minimum_points_raw TEXT NOT NULL DEFAULT '',
                minimum_points INTEGER,
                raw_requirement TEXT NOT NULL,
                UNIQUE(
                    programme_id,
                    exam_type,
                    minimum_points_raw,
                    raw_requirement
                ),
                FOREIGN KEY (programme_id)
                    REFERENCES programmes(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_programmes_name
                ON programmes(programme_name);

            CREATE INDEX IF NOT EXISTS idx_offerings_code
                ON programme_offerings(programme_code);

            CREATE INDEX IF NOT EXISTS idx_offerings_institution
                ON programme_offerings(institution_id);

            CREATE INDEX IF NOT EXISTS idx_requirements_exam_type
                ON programme_requirements(exam_type);
            """
        )


def database_summary(db_path=DB_PATH):
    """
    Return row counts for the main programme tables.
    """
    with get_connection(db_path) as connection:
        tables = [
            "institutions",
            "campuses",
            "career_directions",
            "programmes",
            "programme_offerings",
            "programme_requirements",
        ]

        return {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in tables
        }


if __name__ == "__main__":
    init_db()
    print(database_summary())
