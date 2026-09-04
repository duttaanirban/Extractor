import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


def fetch_website(url: str) -> dict:
    """
    Fetch a public webpage and extract its readable text.
    """

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=15,
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove elements that don't contain useful page content.
        for element in soup(
            ["script", "style", "noscript", "svg", "iframe"]
        ):
            element.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""

        text = soup.get_text(separator=" ", strip=True)

        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "url": url,
            "error": f"Unable to fetch website: {str(error)}",
        }