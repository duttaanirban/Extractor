from urllib.parse import urlparse
import re

from search.serper import search_buyers
from extraction.website_fetcher import fetch_website
from extraction.contact_extractor import extract_contacts
from classification.ollama_classifier import classify_business
from extraction.buyer_contact_discovery import discover_buyer_contacts
from database.connection import get_db_connection


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
        f'"{target_product}" "looking for supplier"',
        f'"{target_product}" "seeking supplier"',
        f'"{target_product}" "need supplier"',
        f'"{target_product}" "looking for a manufacturer"',
        f'"{target_product}" "seeking manufacturer"',
        f'"{target_product}" "looking to purchase"',
        f'"{target_product}" "looking to buy"',
        f'"{target_product}" "want to purchase"',
        f'"{target_product}" RFQ',
        f'"{target_product}" "request for quotation"',
        f'"{target_product}" "purchase inquiry"',
        f'"{target_product}" "buying inquiry"',
        f'"{target_product}" "procurement"',
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


# ============================================================
# PRODUCT RELEVANCE VALIDATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for product matching.
    """

    return re.sub(
        r"\s+",
        " ",
        text.lower(),
    ).strip()


def is_target_product_relevant(
    page_text: str,
    target_product: str,
) -> bool:
    """
    Make sure the buyer is actually interested in the
    requested product and not only an accessory.

    Example:

    Target:
        Singing Bowls

    Reject:
        Looking for silicone mallets for singing bowls

    Accept:
        Looking for crystal singing bowls
        RFQ for Tibetan singing bowls
        Seeking supplier of singing bowls
    """

    text = normalize_text(page_text)
    product = normalize_text(target_product)

    # --------------------------------------------------------
    # Direct target product match
    # --------------------------------------------------------

    if product not in text:

        # Handle common singular/plural variation.
        product_without_s = product.rstrip("s")

        if product_without_s not in text:
            return False

    # --------------------------------------------------------
    # Accessory-only purchasing language
    # --------------------------------------------------------

    accessory_terms = [
        "mallet",
        "mallets",
        "striker",
        "strikers",
        "case",
        "cases",
        "bag",
        "bags",
        "stand",
        "stands",
        "holder",
        "holders",
        "cushion",
        "cushions",
        "ring",
        "rings",
        "pouch",
        "pouches",
        "accessories",
        "accessory",
    ]

    # Strong accessory purchasing phrases.
    accessory_patterns = [
        r"looking for (?:a |an )?(?:manufacturer|supplier|vendor).{0,120}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"seeking (?:a |an )?(?:manufacturer|supplier|vendor).{0,120}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"need (?:a |an )?(?:manufacturer|supplier|vendor).{0,120}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"looking to (?:buy|purchase).{0,100}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"want to (?:buy|purchase).{0,100}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"rfq.{0,100}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"request for quotation.{0,100}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
        r"purchase inquiry.{0,100}(mallet|striker|case|bag|stand|holder|cushion|ring|pouch)",
    ]

    for pattern in accessory_patterns:

        if re.search(
            pattern,
            text,
            re.IGNORECASE,
        ):
            return False

    # --------------------------------------------------------
    # Accessory dominance check
    # --------------------------------------------------------

    product_keywords = [
        "singing bowl",
        "singing bowls",
    ]

    accessory_count = sum(
        text.count(term)
        for term in accessory_terms
    )

    product_count = sum(
        text.count(term)
        for term in product_keywords
    )

    # If the page barely mentions the product but heavily
    # focuses on accessories, don't classify it as a buyer.
    if (
        product_count <= 1
        and accessory_count >= 2
    ):
        return False

    return True


def extract_buyer_name(
    page_text: str,
    page_title: str,
) -> str:
    """
    Try to obtain a cleaner buyer/company name.

    This is intentionally conservative. If we cannot
    confidently identify a name, return the search title.
    """

    text = page_text[:8000]

    patterns = [
        r"(?:company|business|organization|organisation)\s*(?:name)?\s*[:\-]\s*([A-Z][A-Za-z0-9&.,' \-]{2,80})",
        r"(?:buyer|purchaser|importer)\s*(?:name)?\s*[:\-]\s*([A-Z][A-Za-z0-9&.,' \-]{2,80})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:

            name = match.group(1).strip()

            if len(name) >= 3:
                return name

    return page_title

def save_buyer_to_database(
    result: dict,
    target_product: str,
) -> bool:
    """
    Save a confirmed buyer to PostgreSQL.

    Duplicate buyers are updated instead of inserted again.
    """

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        emails = list(
            dict.fromkeys(
                result.get("emails", [])
                + result.get("buyer_contact_emails", [])
            )
        )

        phones = list(
            dict.fromkeys(
                result.get("phones", [])
            )
        )

        query = """
            INSERT INTO buyers (
                company_name,
                website,
                target_product,
                emails,
                phones,
                classification,
                confidence,
                reason,
                source,
                source_url,
                search_query
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                company_name,
                website,
                target_product
            )
            DO UPDATE SET
                emails = EXCLUDED.emails,
                phones = EXCLUDED.phones,
                classification = EXCLUDED.classification,
                confidence = EXCLUDED.confidence,
                reason = EXCLUDED.reason,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                search_query = EXCLUDED.search_query
        """

        cursor.execute(
            query,
            (
                result.get("company_name"),
                result.get("website"),
                target_product,
                emails,
                phones,
                result.get(
                    "classification",
                    "BUYER",
                ),
                result.get(
                    "confidence",
                    0,
                ),
                result.get(
                    "reason",
                    "",
                ),
                result.get(
                    "source",
                    "",
                ),
                result.get(
                    "source_url",
                    "",
                ),
                result.get(
                    "search_query",
                    "",
                ),
            ),
        )

        connection.commit()

        return True

    except Exception as error:

        print(
            f"Database error while saving buyer: {error}"
        )

        if connection:
            connection.rollback()

        return False

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

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
        # 5. HARD PRODUCT RELEVANCE CHECK
        # ==========================================

        if final_status == "BUYER":

            product_relevant = (
                is_target_product_relevant(
                    page_text=page_text,
                    target_product=target_product,
                )
            )

            if not product_relevant:

                final_status = "IRRELEVANT"

                reason = (
                    "The page shows purchasing intent for "
                    "an accessory or related item rather "
                    "than the requested target product."
                )

        # ==========================================
        # 6. EXTRACT PUBLIC CONTACT INFORMATION
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

        company_name = extract_buyer_name(
            page_text=page_text,
            page_title=candidate["title"],
        )

        result = {
            "company_name": company_name,
            "page_title": candidate["title"],
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
        # 7. CONFIRMED BUYER
        # ==========================================

        if final_status == "BUYER":

            try:

                buyer_contact = (
                    discover_buyer_contacts(
                        candidate["website"]
                    )
                )

                buyer_contact_emails = (
                    buyer_contact.get(
                        "emails",
                        [],
                    )
                )

            except Exception:

                buyer_contact_emails = []

            result["buyer_contact_emails"] = (
                buyer_contact_emails
            )

            result["email_available"] = bool(
                buyer_contact_emails
                or result["emails"]
            )

            # ------------------------------------------
            # SAVE CONFIRMED BUYER TO POSTGRESQL
            # ------------------------------------------

            database_saved = save_buyer_to_database(
                result=result,
                target_product=target_product,
            )

            result["database_saved"] = database_saved

            qualified_buyers.append(result)

    # ==========================================
    # 8. RETURN DISCOVERY REPORT
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