def parse_search_results(data: dict) -> list[dict]:
    """
    Convert the raw Serper response into a simple,
    consistent structure for the rest of the application.
    """

    organic_results = data.get("organic", [])

    buyers = []

    for result in organic_results:
        buyers.append(
            {
                "title": result.get("title"),
                "website": result.get("link"),
                "snippet": result.get("snippet"),
                "source": "serper",
                "source_url": result.get("link"),
            }
        )

    return buyers