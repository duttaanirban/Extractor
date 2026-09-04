from urllib.parse import urlparse

from search.serper import search_buyers
from extraction.website_fetcher import fetch_website
from extraction.contact_extractor import extract_contacts
from classification.ollama_classifier import classify_business


def generate_search_queries(target_product: str) -> dict:
    """
    Generate two types of searches:

    1. business_queries:
       Find businesses that may use the target product.

    2. intent_queries:
       Find pages containing explicit purchasing/sourcing language.

    Search results are discovery signals only.
    They are never treated as proof that a company is a buyer.
    """

    business_queries = [
        f'"{target_product}" "sound healing" studio',
        f'"{target_product}" "sound bath" studio',
        f'"{target_product}" "meditation center"',
        f'"{target_product}" "wellness center"',
        f'"{target_product}" "yoga studio"',
        f'"{target_product}" "therapy center"',
    ]

    intent_queries = [
        f'"{target_product}" "looking for a supplier"',
        f'"{target_product}" "seeking a supplier"',
        f'"{target_product}" "need a supplier"',
        f'"{target_product}" "looking for wholesale"',
        f'"{target_product}" "wholesale buyer"',
        f'"{target_product}" RFQ',
        f'"{target_product}" "request for quotation"',
        f'"{target_product}" "looking to buy"',
    ]

    return {
        "business_queries": business_queries,
        "intent_queries": intent_queries,
    }


def get_domain(url: str) -> str:
    try:
        return (
            urlparse(url)
            .netloc
            .lower()
            .replace("www.", "")
        )
    except Exception:
        return ""


def search_candidates(
    queries: list[str],
    num_results: int,
    seen_domains: set,
) -> list[dict]:

    candidates = []

    for query in queries:

        try:
            raw_results = search_buyers(
                query=query,
                num_results=num_results,
            )

        except Exception:
            continue

        for result in raw_results.get(
            "organic",
            [],
        ):

            url = result.get("link")

            if not url:
                continue

            domain = get_domain(url)

            if not domain:
                continue

            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            candidates.append({
                "title": result.get(
                    "title",
                    "",
                ),
                "website": url,
                "snippet": result.get(
                    "snippet",
                    "",
                ),
                "source": "serper",
                "source_url": url,
                "search_query": query,
            })

    return candidates


def discover_buyers(
    target_product: str,
    num_results: int = 3,
) -> dict:

    query_groups = generate_search_queries(
        target_product
    )

    seen_domains = set()

    # ==========================================
    # 1. BUSINESS DISCOVERY
    # ==========================================

    business_candidates = search_candidates(
        queries=query_groups["business_queries"],
        num_results=num_results,
        seen_domains=seen_domains,
    )

    # ==========================================
    # 2. BUYER-INTENT DISCOVERY
    # ==========================================

    intent_candidates = search_candidates(
        queries=query_groups["intent_queries"],
        num_results=num_results,
        seen_domains=seen_domains,
    )

    candidates = (
        business_candidates
        + intent_candidates
    )

    reviewed_candidates = []
    unreachable_candidates = []
    qualified_buyers = []

    # ==========================================
    # 3. PROCESS EVERY UNIQUE CANDIDATE
    # ==========================================

    for candidate in candidates:

        website = fetch_website(
            candidate["website"]
        )

        # --------------------------------------
        # Website unavailable
        # --------------------------------------

        if not website.get("success"):

            unreachable_candidates.append({
                **candidate,
                "status_code": website.get(
                    "status_code"
                ),
                "reason": website.get(
                    "error",
                    "Unable to fetch website.",
                ),
            })

            continue

        page_text = website.get(
            "text",
            "",
        )

        if not page_text:

            unreachable_candidates.append({
                **candidate,
                "reason": (
                    "Website contains no readable text."
                ),
            })

            continue

        # ==========================================
        # 4. AI CLASSIFICATION
        # ==========================================

        try:

            classification = classify_business(
                text=page_text[:12000],
                target_product=target_product,
            )

        except Exception as error:

            classification = {
                "classification": "UNCERTAIN",
                "confidence": 0,
                "reason": (
                    f"AI classification failed: {error}"
                ),
            }

        final_status = classification.get(
            "classification",
            "UNCERTAIN",
        )

        confidence = classification.get(
            "confidence",
            0,
        )

        reason = classification.get(
            "reason",
            "No reason provided.",
        )

        # ==========================================
        # 5. EXTRACT PUBLIC CONTACT INFORMATION
        # ==========================================

        try:

            contacts = extract_contacts(
                page_text
            )

        except Exception:

            contacts = {
                "emails": [],
                "phones": [],
            }

        result = {
            "company_name": candidate["title"],
            "website": candidate["website"],
            "emails": contacts.get(
                "emails",
                [],
            ),
            "phones": contacts.get(
                "phones",
                [],
            ),
            "classification": final_status,
            "confidence": confidence,
            "reason": reason,
            "source": candidate["source"],
            "source_url": candidate["source_url"],
            "search_query": candidate["search_query"],
        }

        reviewed_candidates.append(result)

        # ==========================================
        # 6. CONFIRMED BUYER
        # ==========================================

        if final_status == "BUYER":
            qualified_buyers.append(result)

    # ==========================================
    # 7. RETURN DISCOVERY REPORT
    # ==========================================

    return {
        "success": True,
        "target_product": target_product,

        "business_queries": query_groups[
            "business_queries"
        ],

        "intent_queries": query_groups[
            "intent_queries"
        ],

        "total_candidates_found": len(
            candidates
        ),

        "business_candidates_found": len(
            business_candidates
        ),

        "intent_candidates_found": len(
            intent_candidates
        ),

        "reviewed_candidates": (
            reviewed_candidates
        ),

        "unreachable_candidates": (
            unreachable_candidates
        ),

        "buyers": qualified_buyers,
    }