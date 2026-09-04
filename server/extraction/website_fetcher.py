import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def fetch_website(url: str) -> dict:
    """
    Fetch a public webpage and extract readable text.

    A blocked/unreachable website is returned as a failed result
    instead of raising an exception.
    """

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=15,
            allow_redirects=True,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        # Remove elements that don't contain useful content.
        for element in soup(
            ["script", "style", "noscript", "svg", "iframe"]
        ):
            element.decompose()

        title = (
            soup.title.get_text(strip=True)
            if soup.title
            else ""
        )

        text = soup.get_text(
            separator=" ",
            strip=True,
        )

        return {
            "success": True,
            "url": response.url,
            "title": title,
            "text": text,
            "status_code": response.status_code,
        }

    except requests.RequestException as error:
        status_code = None

        if getattr(error, "response", None) is not None:
            status_code = error.response.status_code

        return {
            "success": False,
            "url": url,
            "status_code": status_code,
            "error": str(error),
        }