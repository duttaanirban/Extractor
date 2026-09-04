import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

CONTACT_KEYWORDS = (
    "contact",
    "about",
    "get in touch",
    "reach us",
)


def extract_emails(soup: BeautifulSoup) -> set[str]:
    emails = set()

    text = soup.get_text(separator=" ", strip=True)

    for email in EMAIL_PATTERN.findall(text):
        emails.add(email.lower().rstrip(".,;:"))

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if href.lower().startswith("mailto:"):
            email = href[7:].split("?", 1)[0].strip().lower()

            if EMAIL_PATTERN.fullmatch(email):
                emails.add(email)

    return emails


def fetch_page(url: str):
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=10,
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup(
            ["script", "style", "noscript", "svg", "iframe"]
        ):
            element.decompose()

        return soup

    except requests.RequestException:
        return None


def discover_contact_pages(base_url: str, soup: BeautifulSoup) -> list[str]:
    """
    Find likely contact/about pages belonging to the same domain.
    """

    base_domain = urlparse(base_url).netloc

    pages = []

    for link in soup.find_all("a", href=True):

        href = link["href"]

        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue

        absolute_url = urljoin(base_url, href)

        parsed = urlparse(absolute_url)

        if parsed.netloc != base_domain:
            continue

        link_text = link.get_text(" ", strip=True).lower()
        path = parsed.path.lower()

        if any(
            keyword in link_text or keyword in path
            for keyword in CONTACT_KEYWORDS
        ):
            pages.append(absolute_url)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(pages))[:5]


def discover_buyer_contacts(url: str) -> dict:
    """
    Discover publicly visible contact information from a buyer source page
    and likely contact/about pages on the same website.

    Never generates or guesses email addresses.
    """

    visited = set()
    emails = set()

    # ---------------------------------
    # 1. Fetch original page
    # ---------------------------------

    soup = fetch_page(url)

    if soup is None:
        return {
            "success": False,
            "url": url,
            "emails": [],
            "phones": [],
            "contact_pages_checked": [],
            "error": "Unable to fetch buyer page",
        }

    visited.add(url)

    emails.update(extract_emails(soup))

    # ---------------------------------
    # 2. Find contact/about pages
    # ---------------------------------

    contact_pages = discover_contact_pages(url, soup)

    for contact_url in contact_pages:

        if contact_url in visited:
            continue

        visited.add(contact_url)

        contact_soup = fetch_page(contact_url)

        if contact_soup is None:
            continue

        emails.update(extract_emails(contact_soup))

    return {
        "success": True,
        "url": url,
        "emails": sorted(emails),
        "phones": [],
        "contact_pages_checked": contact_pages,
    }