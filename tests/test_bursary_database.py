import sqlite3

from bursary.database import DATABASE_FILE


def get_connection():

    return sqlite3.connect(
        DATABASE_FILE
    )


# =========================================================
# TEST 1
# COUNT BURSARIES
# =========================================================

def test_bursary_count():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM bursaries"
    )

    count = cursor.fetchone()[0]

    connection.close()

    print(
        "Bursaries in database:",
        count
    )

    assert count == 10

    print("PASS")


# =========================================================
# TEST 2
# CHECK FOR EMPTY FIELDS
# =========================================================

def test_bursaries_have_fields():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            b.title,
            COUNT(f.id)
        FROM bursaries b

        LEFT JOIN fields_of_study f
            ON b.id = f.bursary_id

        GROUP BY b.id

        HAVING COUNT(f.id) = 0
    """)

    results = cursor.fetchall()

    connection.close()

    assert len(results) == 0

    print(
        "All bursaries have fields of study."
    )

    print("PASS")


# =========================================================
# TEST 3
# CHECK ELIGIBILITY
# =========================================================

def test_bursaries_have_eligibility():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            b.title,
            COUNT(e.id)
        FROM bursaries b

        LEFT JOIN eligibility_requirements e
            ON b.id = e.bursary_id

        GROUP BY b.id

        HAVING COUNT(e.id) = 0
    """)

    results = cursor.fetchall()

    connection.close()

    assert len(results) == 0

    print(
        "All bursaries have eligibility requirements."
    )

    print("PASS")


# =========================================================
# TEST 4
# SEARCH COMPUTER SCIENCE
# =========================================================

def test_computer_science_search():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT
            b.title

        FROM bursaries b

        JOIN fields_of_study f
            ON b.id = f.bursary_id

        WHERE LOWER(f.field)
            LIKE ?
        """,
        (
            "%computer science%",
        )
    )

    results = cursor.fetchall()

    connection.close()

    print(
        "Computer Science bursaries:"
    )

    for row in results:

        print(
            "-",
            row[0]
        )

    assert len(results) > 0

    print("PASS")


# =========================================================
# TEST 5
# AMAZON
# =========================================================

def test_amazon():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            title,
            closing_date,
            closing_status,
            application_url

        FROM bursaries

        WHERE title LIKE ?
        """,
        (
            "%Amazon Bursary%",
        )
    )

    amazon = cursor.fetchone()

    connection.close()

    assert amazon is not None

    assert amazon[1] == "2026-09-30"

    assert (
        amazon[2]
        == "date_available"
    )

    print(
        "Amazon:",
        amazon
    )

    print("PASS")


# =========================================================
# TEST 6
# COLUMBUS MULTIPLE DATES
# =========================================================

def test_columbus_dates():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            b.title,
            cd.category,
            cd.closing_date

        FROM bursaries b

        JOIN closing_dates cd
            ON b.id = cd.bursary_id

        WHERE b.title LIKE ?
        """,
        (
            "%Columbus Stainless%",
        )
    )

    results = cursor.fetchall()

    connection.close()

    print(
        "Columbus closing dates:"
    )

    for row in results:

        print(row)

    assert len(results) == 2

    print("PASS")


# =========================================================
# RUN TESTS
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("DATABASE TESTS")
    print("=" * 70)

    print(
        "\nTEST 1: Bursary count"
    )
    test_bursary_count()

    print(
        "\nTEST 2: Fields of study"
    )
    test_bursaries_have_fields()

    print(
        "\nTEST 3: Eligibility"
    )
    test_bursaries_have_eligibility()

    print(
        "\nTEST 4: Computer Science search"
    )
    test_computer_science_search()

    print(
        "\nTEST 5: Amazon"
    )
    test_amazon()

    print(
        "\nTEST 6: Columbus closing dates"
    )
    test_columbus_dates()

    print()
    print("=" * 70)
    print("ALL DATABASE TESTS PASSED")
    print("=" * 70)