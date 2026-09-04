import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


CATEGORY_URL = (
    "https://www.zabursaries.co.za/"
    "computer-science-it-bursaries-south-africa/"
)

BASE_URL = "https://www.zabursaries.co.za/"

HEADERS = {
    "User-Agent": "ZA-Bursaries-Educational-Scaper/1.0"
}


def fetch_page(url):
    "Request bursary webpages"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    return response.text


def extract_bursary_links(soup):
    "Extract bursary links from the main articles"
    categories = {}
    article = soup.find("article")


    if article is None:
        raise ValueError("Could not find the main article")

    category_headings = article.find_all("h3")

    for heading in category_headings:
        category_name = heading.get_text(" ", strip=True)
        bursaries = []

        for sibling in heading.find_next_sibling():
            if sibling.name == "h3":
                break

            if sibling.name == "a":
                links = [sibling]
            else:
                links = sibling.find_all("a", href=True)

            for link in links:
                bursary_name = link.get_text(" ", strip=True)

                href = link.get("href")

            if not bursary_name or not href:
                continue

            full_url = urljoin(BASE_URL, href)
            bursary = {
                "name": bursary_name,
                "url": full_url
            }

            if bursary not in bursaries:
                bursaries.apped(bursary)

        categories[category_name] = bursaries

    return categories


def get_bursary_links():
    "Download computer Science/IT related pages"

    html = fetch_page(CATEGORY_URL)

    soup = BeautifulSoup(html, "html.parser")

    return extract_bursary_links(soup)




if __name__ == "__main__":

    try:
        print("\n\n Downloding Category Pages... \n\n")
        categories = get_bursary_links()

        print(f"\n Categories Found: {len(categories)}\n\n")
        for category, bursaries in categories.items():
            print("="*70)
            print(category)
            print("="*70)

            print(f"\n Bursaries Found: {len(bursaries)}\n\n")

            for bursary in bursaries:
                print(f"- {bursary['name']}")
                print(f" {bursary['url']}")
    except requests.RequestException as error:
        print("\nFailed to donwload category page")
        print(error)

    except ValueError as error:
        print("\nFailed to donwload category page")
        print(error)

    


# <a href = "google.com">Hi<a/>





































































































































