import sqlite3

from datetime import date

from bursary.database import DATABASE_FILE


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    """
    Connect to the SQLite database.

    row_factory allows us to access values
    using column names such as:

        row["title"]

    instead of:

        row[0]
    """

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# GET CLOSING DATES
# =========================================================

def get_closing_dates(
    connection,
    bursary_id
):
    """
    Get all closing dates for a bursary.

    This is especially useful for bursaries
    such as Columbus Stainless that have more
    than one closing date.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            category,
            closing_date

        FROM closing_dates

        WHERE bursary_id = ?

        ORDER BY closing_date
        """,
        (
            bursary_id,
        )
    )

    rows = cursor.fetchall()

    closing_dates = []

    for row in rows:

        closing_dates.append(
            {
                "category": row["category"],
                "date": row["closing_date"]
            }
        )

    return closing_dates


# =========================================================
# AVAILABILITY CHECK
# =========================================================

def evaluate_availability(
    connection,
    bursary_id,
    closing_date,
    closing_status
):
    """
    Determine the current availability
    of a bursary.

    Returns structured information rather
    than only True or False.
    """

    today = date.today().isoformat()

    # -----------------------------------------------------
    # CASE 1:
    # One known closing date
    # -----------------------------------------------------

    if closing_status == "date_available":

        if closing_date is None:

            return {
                "status": "unknown",
                "label": (
                    "Availability could not "
                    "be confirmed"
                ),
                "verified": False
            }

        if closing_date >= today:

            return {
                "status": "verified_open",
                "label": "Closing date verified",
                "verified": True
            }

        return {
            "status": "expired",
            "label": "Closing date has passed",
            "verified": True
        }

    # -----------------------------------------------------
    # CASE 2:
    # Several closing dates
    # -----------------------------------------------------

    if (
        closing_status
        == "multiple_dates_available"
    ):

        closing_dates = get_closing_dates(
            connection,
            bursary_id
        )

        future_dates = []

        for item in closing_dates:

            if item["date"] >= today:

                future_dates.append(
                    item
                )

        if future_dates:

            return {
                "status": "verified_open",
                "label": (
                    "Multiple closing dates "
                    "available"
                ),
                "verified": True
            }

        return {
            "status": "expired",
            "label": (
                "All known closing dates "
                "have passed"
            ),
            "verified": True
        }

    # -----------------------------------------------------
    # CASE 3:
    # Site says applications are open,
    # but no closing date was supplied.
    # -----------------------------------------------------

    if (
        closing_status
        == "open_no_closing_date"
    ):

        return {
            "status": "needs_verification",
            "label": (
                "No closing date disclosed "
                "- verify before applying"
            ),
            "verified": False
        }

    # -----------------------------------------------------
    # CASE 4:
    # Closing date not confirmed
    # -----------------------------------------------------

    if (
        closing_status
        == "date_not_confirmed"
    ):

        return {
            "status": "needs_verification",
            "label": (
                "Closing date not confirmed "
                "- verify before applying"
            ),
            "verified": False
        }

    # -----------------------------------------------------
    # CASE 5:
    # Explicitly closed
    # -----------------------------------------------------

    if closing_status == "closed":

        return {
            "status": "closed",
            "label": "Applications closed",
            "verified": True
        }

    # -----------------------------------------------------
    # Anything else
    # -----------------------------------------------------

    return {
        "status": "unknown",
        "label": (
            "Availability unknown "
            "- verify before applying"
        ),
        "verified": False
    }


# =========================================================
# GET FIELDS OF STUDY
# =========================================================

def get_fields_for_bursary(
    connection,
    bursary_id
):
    """
    Get all study fields linked to a bursary.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT field

        FROM fields_of_study

        WHERE bursary_id = ?

        ORDER BY position
        """,
        (
            bursary_id,
        )
    )

    return [
        row["field"]
        for row in cursor.fetchall()
    ]


# =========================================================
# GET ELIGIBILITY REQUIREMENTS
# =========================================================

def get_eligibility_for_bursary(
    connection,
    bursary_id
):
    """
    Get all eligibility requirements
    for a bursary.
    """

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT requirement

        FROM eligibility_requirements

        WHERE bursary_id = ?

        ORDER BY position
        """,
        (
            bursary_id,
        )
    )

    return [
        row["requirement"]
        for row in cursor.fetchall()
    ]


# =========================================================
# RESULT PRIORITY
# =========================================================

def availability_priority(status):
    """
    Decide how results should be ordered.

    Lower number = higher priority.
    """

    priorities = {
        "verified_open": 1,
        "needs_verification": 2,
        "unknown": 3,
        "expired": 4,
        "closed": 5
    }

    return priorities.get(
        status,
        99
    )


# =========================================================
# SEARCH BY FIELD
# =========================================================

def search_by_field(
    field,
    include_expired=False
):
    """
    Search bursaries by field of study.

    By default:
    - verified opportunities are returned
    - opportunities needing verification
      are also returned
    - expired/closed opportunities are hidden
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT
            b.id,
            b.title,
            b.closing_date,
            b.closing_status,
            b.application_url,
            b.source,
            b.source_url

        FROM bursaries b

        JOIN fields_of_study f
            ON b.id = f.bursary_id

        WHERE LOWER(f.field)
            LIKE LOWER(?)
        """,
        (
            f"%{field}%",
        )
    )

    rows = cursor.fetchall()

    results = []

    for row in rows:

        availability = evaluate_availability(
            connection,
            row["id"],
            row["closing_date"],
            row["closing_status"]
        )

        # ---------------------------------
        # Hide expired/closed opportunities
        # unless specifically requested.
        # ---------------------------------

        if not include_expired:

            if availability["status"] in [
                "expired",
                "closed",
                "unknown"
            ]:
                continue

        closing_dates = get_closing_dates(
            connection,
            row["id"]
        )

        fields = get_fields_for_bursary(
            connection,
            row["id"]
        )

        bursary = {
            "id": row["id"],
            "title": row["title"],

            "fields_of_study":
                fields,

            "closing_date":
                row["closing_date"],

            "closing_dates":
                closing_dates,

            "closing_status":
                row["closing_status"],

            "availability_status":
                availability["status"],

            "availability_label":
                availability["label"],

            "verified":
                availability["verified"],

            "application_url":
                row["application_url"],

            "source":
                row["source"],

            "source_url":
                row["source_url"]
        }

        results.append(
            bursary
        )

    connection.close()

    # -----------------------------------------
    # Sort:
    #
    # 1. Verified opportunities
    # 2. Needs verification
    # 3. Everything else
    # -----------------------------------------

    results.sort(
        key=lambda bursary: (
            availability_priority(
                bursary[
                    "availability_status"
                ]
            ),
            bursary["title"]
        )
    )

    return results


# =========================================================
# PRINT CLOSING DATE
# =========================================================

def display_closing_dates(
    bursary
):
    """
    Display closing-date information
    in a user-friendly way.
    """

    closing_dates = bursary[
        "closing_dates"
    ]

    # -----------------------------------------
    # Multiple dates
    # -----------------------------------------

    if len(closing_dates) > 1:

        print(
            "   Closing dates:"
        )

        for item in closing_dates:

            print(
                "      -",
                item["category"] + ":",
                item["date"]
            )

        return

    # -----------------------------------------
    # One date
    # -----------------------------------------

    if len(closing_dates) == 1:

        print(
            "   Closing date:",
            closing_dates[0]["date"]
        )

        return

    # -----------------------------------------
    # No known date
    # -----------------------------------------

    print(
        "   Closing date:",
        "Not confirmed"
    )


# =========================================================
# DISPLAY SEARCH RESULTS
# =========================================================

def display_results(
    results
):
    """
    Print bursary recommendations in a
    beginner-friendly format.
    """

    if not results:

        print()
        print(
            "No currently suitable bursaries "
            "were found for this field."
        )

        return

    # Separate results into two groups.

    verified = []

    needs_verification = []

    for bursary in results:

        if (
            bursary[
                "availability_status"
            ]
            == "verified_open"
        ):

            verified.append(
                bursary
            )

        elif (
            bursary[
                "availability_status"
            ]
            == "needs_verification"
        ):

            needs_verification.append(
                bursary
            )

    # =====================================================
    # VERIFIED OPPORTUNITIES
    # =====================================================

    if verified:

        print()
        print("=" * 70)
        print("VERIFIED BY CLOSING DATE")
        print("=" * 70)

        for number, bursary in enumerate(
            verified,
            start=1
        ):

            print()
            print(
                f"{number}. "
                f"{bursary['title']}"
            )

            print(
                "   Status:",
                bursary[
                    "availability_label"
                ]
            )

            display_closing_dates(
                bursary
            )

            print(
                "   Apply:",
                bursary[
                    "application_url"
                ]
            )

            print(
                "   Source:",
                bursary[
                    "source_url"
                ]
            )

    # =====================================================
    # NEEDS VERIFICATION
    # =====================================================

    if needs_verification:

        print()
        print("=" * 70)
        print("REQUIRES VERIFICATION")
        print("=" * 70)

        for number, bursary in enumerate(
            needs_verification,
            start=1
        ):

            print()
            print(
                f"{number}. "
                f"{bursary['title']}"
            )

            print(
                "   Status:",
                bursary[
                    "availability_label"
                ]
            )

            display_closing_dates(
                bursary
            )

            print(
                "   Apply:",
                bursary[
                    "application_url"
                ]
            )

            print(
                "   Verify at:",
                bursary[
                    "source_url"
                ]
            )


# =========================================================
# MAIN PROGRAM
# =========================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("BURSARY SEARCH")
    print("=" * 70)

    field = input(
        "\nEnter your field of study: "
    ).strip()

    if not field:

        print(
            "\nPlease enter a field of study."
        )

    else:

        results = search_by_field(
            field
        )

        print(
            f"\nSearching for bursaries "
            f"related to: {field}"
        )

        print(
            f"Potential opportunities found: "
            f"{len(results)}"
        )

        display_results(
            results
        )