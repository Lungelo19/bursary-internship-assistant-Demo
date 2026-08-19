import json
import re
import time
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, urlparse


BASE_URL = "https://www.zabursaries.co.za"

HEADERS = {
    "User-Agent": "ZA-Bursaries-Educational-Scraper/1.0"
}


# =========================================================
# DOWNLOAD PAGE
# =========================================================

def fetch_page(url):
    """
    Download a webpage and return its HTML.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    return response.text


# =========================================================
# TEXT HELPERS
# =========================================================

def normalise_text(text):
    """
    Lowercase text and remove unnecessary spaces.
    """

    return " ".join(
        text.lower().split()
    )


def heading_level(element):
    """
    Convert h2, h3, h4 etc. to numbers.
    """

    if element.name in [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6"
    ]:
        return int(
            element.name[1]
        )

    return None


def is_probable_heading(element):
    """
    Detect normal headings and older
    bold/uppercase paragraph headings.
    """

    if heading_level(element) is not None:
        return True

    if element.name != "p":
        return False

    text = element.get_text(
        " ",
        strip=True
    )

    if not text:
        return False

    if len(text) > 180:
        return False

    if element.find(["strong", "b"]):
        return True

    letters = [
        character
        for character in text
        if character.isalpha()
    ]

    if not letters:
        return False

    uppercase_letters = sum(
        character.isupper()
        for character in letters
    )

    uppercase_ratio = (
        uppercase_letters / len(letters)
    )

    return uppercase_ratio >= 0.75


# =========================================================
# SECTION MATCHING
# =========================================================

def section_matches(text, section):
    """
    Check whether heading text represents
    one of the sections we need.
    """

    text = normalise_text(text)

    if section == "fields":

        return (
            "fields" in text
            and (
                "study" in text
                or "cover" in text
            )
        )

    if section == "eligibility":

        if "eligibility" in text:
            return True

        return (
            "requirements" in text
            and (
                "bursary" in text
                or "scholarship" in text
            )
            and "documents" not in text
        )

    if section == "application":

        return (
            "apply" in text
            and (
                "bursary" in text
                or "scholarship" in text
                or "programme" in text
            )
        )

    if section == "closing":

        return (
            "closing date" in text
        )

    return False


def find_heading(article, section):
    """
    Find the heading for a particular section.
    """

    headings = article.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "h6"
        ]
    )

    # First try real HTML headings
    for heading in headings:

        text = heading.get_text(
            " ",
            strip=True
        )

        if section_matches(
            text,
            section
        ):
            return heading

    # Fallback for older pages
    paragraphs = article.find_all("p")

    for paragraph in paragraphs:

        if not is_probable_heading(
            paragraph
        ):
            continue

        text = paragraph.get_text(
            " ",
            strip=True
        )

        if section_matches(
            text,
            section
        ):
            return paragraph

    return None


# =========================================================
# SECTION BOUNDARIES
# =========================================================

SECTION_BOUNDARY_WORDS = [
    "eligibility",
    "how to apply",
    "how can i apply",
    "closing date",
    "documents",
    "contact the bursary",
    "contact the scholarship",
    "coverage",
    "other opportunities",
    "what expenses",
    "programme cover"
]


def is_section_boundary(element):
    """
    Detect another major section.
    """

    if not is_probable_heading(element):
        return False

    text = normalise_text(
        element.get_text(
            " ",
            strip=True
        )
    )

    return any(
        phrase in text
        for phrase in SECTION_BOUNDARY_WORDS
    )


def get_section_elements(heading):
    """
    Get elements belonging to one section.
    """

    if heading is None:
        return []

    elements = []

    start_level = heading_level(
        heading
    )

    for sibling in heading.find_next_siblings():

        sibling_level = heading_level(
            sibling
        )

        if start_level is not None:

            if (
                sibling_level is not None
                and sibling_level <= start_level
            ):
                break

        else:

            if is_section_boundary(
                sibling
            ):
                break

        elements.append(
            sibling
        )

    return elements


# =========================================================
# SECTION TEXT
# =========================================================

def extract_section_text(heading):
    """
    Extract paragraphs and list items from
    a section.
    """

    content = []

    for element in get_section_elements(
        heading
    ):

        if element.name == "p":

            text = element.get_text(
                " ",
                strip=True
            )

            if (
                text
                and text not in content
            ):
                content.append(text)

            continue

        if element.name in ["ul", "ol"]:

            blocks = element.find_all(
                "li",
                recursive=False
            )

        else:

            blocks = element.find_all(
                ["p", "li"]
            )

        for block in blocks:

            # Do not separately collect nested
            # list items.
            if (
                block.name == "li"
                and block.find_parent("li")
            ):
                continue

            text = block.get_text(
                " ",
                strip=True
            )

            if (
                text
                and text not in content
            ):
                content.append(text)

    return content


# =========================================================
# ELIGIBILITY EXTRACTION
# =========================================================

def extract_list_items(heading):
    """
    Extract eligibility list items.

    Nested list items are NOT added separately.

    Example:

    You must study at one of these universities:
        Rhodes University
        UCT
        Wits

    becomes one eligibility rule rather than
    four separate records.
    """

    items = []

    for element in get_section_elements(
        heading
    ):

        if element.name == "li":

            candidates = [element]

        else:

            candidates = element.find_all(
                "li"
            )

        for item in candidates:

            # Ignore nested <li> elements.
            # Their text is already contained
            # in the parent <li>.
            if item.find_parent("li") is not None:
                continue

            text = item.get_text(
                " ",
                strip=True
            )

            if (
                text
                and text not in items
            ):
                items.append(text)

    return items


# =========================================================
# FIELDS OF STUDY
# =========================================================

FIELD_STOP_PHRASES = [
    "related bursaries",
    "selected universities",
    "selected tertiary institutes",
    "selected tertiary institutions",
    "funded at the following universities",
    "funded at the following selected universities"
]


def is_field_stop_text(text):
    """
    Detect text showing that we have moved
    beyond the real fields-of-study list.
    """

    text = normalise_text(text)

    return any(
        phrase in text
        for phrase in FIELD_STOP_PHRASES
    )


def looks_like_institution(text):
    """
    Detect obvious university names.
    """

    text = normalise_text(text)

    if text.startswith(
        "university of "
    ):
        return True

    if text.endswith(
        " university"
    ):
        return True

    if " university of technology" in text:
        return True

    return False


def clean_field(field):
    """
    Clean one field name.
    """

    return " ".join(
        field.split()
    ).strip()


def extract_fields_of_study(heading):
    """
    Extract fields of study.

    Supports:
    - multiple lists
    - nested HTML
    - undergraduate/postgraduate subheadings
    - older page layouts
    """

    if heading is None:
        return []

    fields = []

    article = heading.find_parent(
        "article"
    )

    if article is None:
        return []

    start_level = heading_level(
        heading
    )

    elements = heading.find_all_next(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "li"
        ]
    )

    for element in elements:

        # Make sure we remain inside
        # the same article.
        if article not in element.parents:
            break

        element_level = heading_level(
            element
        )

        # Stop when the next major heading begins.
        if (
            element_level is not None
            and start_level is not None
        ):

            if element_level <= start_level:
                break

            # Smaller subheadings are allowed,
            # for example:
            #
            # Undergraduate studies
            # Honours studies
            continue

        if element.name == "p":

            text = element.get_text(
                " ",
                strip=True
            )

            if is_field_stop_text(text):
                break

            continue

        if element.name == "li":

            field = element.get_text(
                " ",
                strip=True
            )

            if not field:
                continue

            field = clean_field(
                field
            )

            field_lower = normalise_text(
                field
            )

            # Stop at "View our other..."
            if field_lower.startswith(
                "view our other"
            ):
                break

            # Stop if a list of universities starts.
            if looks_like_institution(
                field
            ):

                if fields:
                    break

                continue

            if field not in fields:

                fields.append(
                    field
                )

    return fields


# =========================================================
# LINKS
# =========================================================

def extract_links(heading):
    """
    Extract links from a section.
    """

    links = []

    for element in get_section_elements(
        heading
    ):

        if element.name == "a":

            link_elements = [element]

        else:

            link_elements = element.find_all(
                "a",
                href=True
            )

        for link in link_elements:

            href = link.get("href")

            if not href:
                continue

            text = link.get_text(
                " ",
                strip=True
            )

            full_url = urljoin(
                BASE_URL,
                href
            )

            item = {
                "text": text,
                "url": full_url
            }

            if item not in links:
                links.append(item)

    return links


def choose_application_url(links):
    """
    Choose the most likely application URL.
    """

    if not links:
        return None

    # First preference:
    # explicit application links.
    for link in links:

        text = normalise_text(
            link["text"]
        )

        if (
            "application" in text
            and "instruction" not in text
        ):
            return link["url"]

    # Second preference:
    # external link.
    za_domain = urlparse(
        BASE_URL
    ).netloc

    for link in links:

        link_domain = urlparse(
            link["url"]
        ).netloc

        if (
            link_domain
            and link_domain != za_domain
        ):
            return link["url"]

    return None


# =========================================================
# CLOSING DATES
# =========================================================

DATE_PATTERN = re.compile(
    r"\b"
    r"(\d{1,2})"
    r"(?:st|nd|rd|th)?"
    r"\s+"
    r"(January|February|March|April|May|June|"
    r"July|August|September|October|November|December)"
    r"\s+"
    r"(\d{4})"
    r"\b",
    re.IGNORECASE
)


def parse_date_match(match):
    """
    Convert regex date match into YYYY-MM-DD.
    """

    date_string = (
        f"{match.group(1)} "
        f"{match.group(2)} "
        f"{match.group(3)}"
    )

    parsed_date = datetime.strptime(
        date_string,
        "%d %B %Y"
    )

    return parsed_date.date().isoformat()


def find_date_category(text, match):
    """
    Try to identify what a date belongs to.

    Example:

    Undergraduate bursary: 28 August 2026

    becomes:

    Undergraduate bursary
    """

    before_date = text[
        :match.start()
    ]

    colon_position = before_date.rfind(
        ":"
    )

    if colon_position == -1:
        return "General"

    # Find the beginning of the label.
    boundary_positions = [
        before_date.rfind(
            ".",
            0,
            colon_position
        ),
        before_date.rfind(
            ";",
            0,
            colon_position
        ),
        before_date.rfind(
            ",",
            0,
            colon_position
        )
    ]

    boundary = max(
        boundary_positions
    )

    label = before_date[
        boundary + 1:
        colon_position
    ].strip()

    if not label:
        return "General"

    # Avoid storing extremely long text
    # as a category.
    if len(label) > 80:
        return "General"

    return label


def extract_closing_dates(text_list):
    """
    Extract ALL closing dates.

    Examples:

    Amazon:
        30 September 2026

    becomes:

        [
            {
                "category": "General",
                "date": "2026-09-30"
            }
        ]


    Columbus:

        Undergraduate bursary: 28 August 2026
        Postgraduate bursary: 31 August 2026

    becomes:

        [
            {
                "category": "Undergraduate bursary",
                "date": "2026-08-28"
            },
            {
                "category": "Postgraduate bursary",
                "date": "2026-08-31"
            }
        ]
    """

    dates = []

    for text in text_list:

        matches = DATE_PATTERN.finditer(
            text
        )

        for match in matches:

            date = parse_date_match(
                match
            )

            category = find_date_category(
                text,
                match
            )

            item = {
                "category": category,
                "date": date
            }

            if item not in dates:
                dates.append(item)

    return dates


def choose_single_closing_date(
    closing_dates
):
    """
    Return a simple closing_date only when
    there is exactly one date.

    If a bursary has several dates, return None
    so that we do not accidentally show the
    wrong date to a student.
    """

    if len(closing_dates) == 1:

        return closing_dates[0][
            "date"
        ]

    return None


def determine_closing_status(
    closing_text,
    closing_dates
):
    """
    Determine the closing-date status.
    """

    text = normalise_text(
        " ".join(closing_text)
    )

    if len(closing_dates) > 1:
        return "multiple_dates_available"

    if len(closing_dates) == 1:
        return "date_available"

    if (
        "not confirmed" in text
        or "to be confirmed" in text
    ):
        return "date_not_confirmed"

    if (
        "currently open" in text
        and (
            "not been disclosed" in text
            or "no closing date" in text
        )
    ):
        return "open_no_closing_date"

    if (
        "applications are closed" in text
        or "applications have closed" in text
    ):
        return "closed"

    return "unknown"


# =========================================================
# MAIN SCRAPER
# =========================================================

def scrape_bursary(url):
    """
    Scrape one bursary page.
    """

    html = fetch_page(
        url
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    article = soup.find(
        "article"
    )

    if article is None:

        raise ValueError(
            "Could not find the main bursary article."
        )

    # ---------------------------------
    # Title
    # ---------------------------------

    title_heading = article.find(
        "h1"
    )

    title = (
        title_heading.get_text(
            " ",
            strip=True
        )
        if title_heading
        else None
    )

    # ---------------------------------
    # Find sections
    # ---------------------------------

    fields_heading = find_heading(
        article,
        "fields"
    )

    eligibility_heading = find_heading(
        article,
        "eligibility"
    )

    application_heading = find_heading(
        article,
        "application"
    )

    closing_heading = find_heading(
        article,
        "closing"
    )

    # ---------------------------------
    # Fields
    # ---------------------------------

    fields_of_study = (
        extract_fields_of_study(
            fields_heading
        )
    )

    # ---------------------------------
    # Eligibility
    # ---------------------------------

    eligibility = extract_list_items(
        eligibility_heading
    )

    # ---------------------------------
    # Application
    # ---------------------------------

    application_instructions = (
        extract_section_text(
            application_heading
        )
    )

    application_links = extract_links(
        application_heading
    )

    application_url = (
        choose_application_url(
            application_links
        )
    )

    # ---------------------------------
    # Closing date
    # ---------------------------------

    closing_date_text = (
        extract_section_text(
            closing_heading
        )
    )

    closing_dates = (
        extract_closing_dates(
            closing_date_text
        )
    )

    closing_date = (
        choose_single_closing_date(
            closing_dates
        )
    )

    closing_status = (
        determine_closing_status(
            closing_date_text,
            closing_dates
        )
    )

    # ---------------------------------
    # Final bursary
    # ---------------------------------

    return {
        "title": title,
        "type": "bursary",

        "fields_of_study":
            fields_of_study,

        "eligibility":
            eligibility,

        # Simple date for bursaries that
        # have exactly one closing date.
        "closing_date":
            closing_date,

        # Full representation.
        "closing_dates":
            closing_dates,

        "closing_status":
            closing_status,

        "closing_date_text":
            closing_date_text,

        "application_url":
            application_url,

        "application_instructions":
            application_instructions,

        "source":
            "ZA Bursaries",

        "source_url":
            url
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    TEST_URLS = [
        (
            "Amazon",
            "https://www.zabursaries.co.za/"
            "computer-science-it-bursaries-south-africa/"
            "amazon-bursary/"
        ),

        (
            "Columbus Stainless",
            "https://www.zabursaries.co.za/"
            "engineering-bursaries-south-africa/"
            "columbus-stainless-bursary/"
        ),

        (
            "Accenture",
            "https://www.zabursaries.co.za/"
            "general-bursaries-south-africa/"
            "accenture-scholarship-south-africa/"
        )
    ]

    for index, (name, url) in enumerate(
        TEST_URLS,
        start=1
    ):

        try:

            print("\n")
            print("=" * 80)
            print(f"TESTING: {name}")
            print("=" * 80)

            bursary = scrape_bursary(
                url
            )

            print(
                json.dumps(
                    bursary,
                    indent=4,
                    ensure_ascii=False
                )
            )

        except requests.RequestException as error:

            print(
                f"Failed to download {name}:"
            )

            print(error)

        except ValueError as error:

            print(
                f"Failed to parse {name}:"
            )

            print(error)

        if index < len(TEST_URLS):

            print(
                "\nWaiting 30 seconds "
                "before the next request..."
            )

            time.sleep(30)