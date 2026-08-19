import json
import os
import time
import requests

from bursary.scraper import get_bursary_links
from bursary.detail_scraper import scrape_bursary


# -----------------------------------------
# SETTINGS
# -----------------------------------------

MAX_BURSARIES = 10

CRAWL_DELAY = 30

OUTPUT_FILE = os.path.join(
    "data",
    "bursaries.json"
)


def build_unique_bursary_list(categories):
    """
    Convert bursaries grouped by categories
    into one unique list.

    If the same bursary occurs in several
    categories, keep it once and store all
    of its categories.
    """

    unique_bursaries = {}

    for category, bursaries in categories.items():

        for bursary in bursaries:

            url = bursary["url"]
            name = bursary["name"]

            # First time we see this URL
            if url not in unique_bursaries:

                unique_bursaries[url] = {
                    "name": name,
                    "url": url,
                    "categories": []
                }

            # Add category if not already saved
            if (
                category
                not in unique_bursaries[url]["categories"]
            ):
                unique_bursaries[url][
                    "categories"
                ].append(category)

    return list(
        unique_bursaries.values()
    )


def save_json(records):
    """
    Save collected bursaries to JSON.
    """

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            records,
            file,
            indent=4,
            ensure_ascii=False
        )


def collect_bursaries():
    """
    Main collection pipeline.
    """

    print("=" * 70)
    print("ZA BURSARIES DATA COLLECTOR")
    print("=" * 70)

    # -----------------------------------------
    # STEP 1:
    # Discover bursary URLs
    # -----------------------------------------

    print(
        "\n1. Downloading category page..."
    )

    categories = get_bursary_links()

    print(
        "Categories found:",
        len(categories)
    )

    # -----------------------------------------
    # STEP 2:
    # Remove duplicate bursaries
    # -----------------------------------------

    unique_bursaries = (
        build_unique_bursary_list(
            categories
        )
    )

    print(
        "Unique bursaries discovered:",
        len(unique_bursaries)
    )

    # -----------------------------------------
    # STEP 3:
    # Limit while developing
    # -----------------------------------------

    bursaries_to_scrape = (
        unique_bursaries[
            :MAX_BURSARIES
        ]
    )

    print(
        "Bursaries being scraped:",
        len(bursaries_to_scrape)
    )

    # We just requested the category page.
    # Wait before requesting the first
    # bursary detail page.
    print(
        f"\nWaiting {CRAWL_DELAY} seconds "
        "before the first detail request..."
    )

    time.sleep(
        CRAWL_DELAY
    )

    # -----------------------------------------
    # STEP 4:
    # Scrape bursary details
    # -----------------------------------------

    collected = []

    for index, bursary_info in enumerate(
        bursaries_to_scrape,
        start=1
    ):

        name = bursary_info["name"]
        url = bursary_info["url"]
        categories_list = (
            bursary_info["categories"]
        )

        print("\n")
        print("=" * 70)

        print(
            f"[{index}/{len(bursaries_to_scrape)}]"
        )

        print(
            "Scraping:",
            name
        )

        print(
            "URL:",
            url
        )

        try:

            bursary_data = scrape_bursary(
                url
            )

            # Add category information from
            # the category page.
            bursary_data["categories"] = (
                categories_list
            )

            collected.append(
                bursary_data
            )

            print(
                "Successfully collected."
            )

            print(
                "Fields:",
                len(
                    bursary_data[
                        "fields_of_study"
                    ]
                )
            )

            print(
                "Eligibility rules:",
                len(
                    bursary_data[
                        "eligibility"
                    ]
                )
            )

            print(
                "Closing date:",
                bursary_data[
                    "closing_date"
                ]
            )

            # Save after every successful
            # bursary.
            save_json(
                collected
            )

            print(
                "Progress saved."
            )

        except requests.RequestException as error:

            print(
                "Request failed:"
            )

            print(error)

        except ValueError as error:

            print(
                "Parsing failed:"
            )

            print(error)

        except Exception as error:

            print(
                "Unexpected error:"
            )

            print(error)

        # -------------------------------------
        # Respect crawl delay
        # -------------------------------------

        if index < len(
            bursaries_to_scrape
        ):

            print(
                f"\nWaiting {CRAWL_DELAY} seconds "
                "before the next request..."
            )

            time.sleep(
                CRAWL_DELAY
            )

    # -----------------------------------------
    # STEP 5:
    # Final save
    # -----------------------------------------

    save_json(
        collected
    )

    print("\n")
    print("=" * 70)
    print("COLLECTION COMPLETE")
    print("=" * 70)

    print(
        "Successfully collected:",
        len(collected)
    )

    print(
        "Saved to:",
        OUTPUT_FILE
    )


if __name__ == "__main__":

    try:

        collect_bursaries()

    except requests.RequestException as error:

        print(
            "\nFailed while downloading "
            "the category page:"
        )

        print(error)

    except ValueError as error:

        print(
            "\nFailed while processing "
            "the category page:"
        )

        print(error)