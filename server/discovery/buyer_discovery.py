from urllib.parse import urlparse
import re

from search.serper import search_buyers
from extraction.website_fetcher import fetch_website
from extraction.contact_extractor import extract_contacts
from classification.gemini_classifier import classify_business
from extraction.buyer_contact_discovery import discover_buyer_contacts
from validation.email_validator import validate_email
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
                "search_score": score_search_result(
                    title=result.get("title", ""),
                    url=url,
                    snippet=result.get("snippet", ""),
                    query=query,
                ),
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


def score_search_result(
    title: str,
    url: str,
    snippet: str,
    query: str,
) -> int:
    """Prefer pages with real procurement signals."""

    text = normalize_text(
        " ".join([title, url, snippet, query])
    )

    score = 0

    positive_patterns = {
        r"\brfq\b": 8,
        r"\brequest for quotation\b": 8,
        r"\bpurchase inquiry\b": 7,
        r"\bbuying inquiry\b": 7,
        r"\blooking for (?:a )?(?:supplier|manufacturer|vendor)\b": 6,
        r"\bseeking (?:a )?(?:supplier|manufacturer|vendor)\b": 6,
        r"\bneed (?:a )?(?:supplier|manufacturer|vendor)\b": 5,
        r"\bprocurement\b": 5,
        r"\bsourcing\b": 5,
        r"\bimporter\b": 3,
    }

    negative_patterns = {
        r"\bshop\b": 5,
        r"\bstore\b": 5,
        r"\bwholesale\b": 5,
        r"\bmanufacturer\b": 4,
        r"\bsupplier\b": 3,
        r"\bblog\b": 4,
        r"\bguide\b": 4,
        r"\breview\b": 4,
        r"\bbest\b": 3,
    }

    for pattern, weight in positive_patterns.items():
        if re.search(pattern, text):
            score += weight

    for pattern, weight in negative_patterns.items():
        if re.search(pattern, text):
            score -= weight

    return score


def extract_relevant_evidence(
    page_text: str,
    target_product: str,
    max_windows: int = 8,
    window_size: int = 260,
) -> str:
    """Build a compact text sample around product and intent signals."""

    text = normalize_text(page_text)
    product = normalize_text(target_product).rstrip("s")
    terms = [
        product,
        "singing bowl",
        "singing bowls",
        "looking for",
        "seeking",
        "supplier",
        "manufacturer",
        "procurement",
        "purchase inquiry",
        "buying inquiry",
        "request for quotation",
        "rfq",
        "sourcing",
    ]

    windows = []
    seen = set()

    for term in terms:
        for match in re.finditer(re.escape(term), text):
            start = max(match.start() - window_size, 0)
            end = min(match.end() + window_size, len(text))
            key = (start // 80, end // 80)

            if key in seen:
                continue

            seen.add(key)
            windows.append(text[start:end].strip())

            if len(windows) >= max_windows:
                return "\n---\n".join(windows)

    return text[:2500]


def has_supplier_evidence(
    page_text: str,
    target_product: str,
) -> bool:
    text = normalize_text(page_text)
    product_pattern = re.escape(
        normalize_text(target_product).rstrip("s")
    ) + r"s?"

    if not re.search(product_pattern, text):
        return False

    supplier_patterns = [
        r"\b(?:we|our|shop|store|retailer|manufacturer|distributor|brand)"
        r"\b.{0,140}\b(?:sell|selling|manufactur|distribut|wholesal|"
        r"retail|stock|supply)\w*\b",
        r"\b(?:sell|selling|manufactur|distribut|wholesal|retail|stock|"
        r"supply)\w*\b.{0,140}\b(?:singing bowl|singing bowls|our)\b",
        r"\b(?:add to cart|shop now|wholesale price|bulk order|"
        r"product catalog)\b",
    ]

    return any(
        re.search(pattern, text)
        for pattern in supplier_patterns
    )


def is_service_provider_page(page_text: str) -> bool:
    text = normalize_text(page_text)

    service_patterns = [
        r"\b(?:sound bath|sound healing|meditation|yoga|therapy|wellness)\b",
        r"\b(?:classes|workshops|sessions|training|retreats?)\b",
    ]

    return any(
        re.search(pattern, text)
        for pattern in service_patterns
    )


def is_informational_page(
    page_text: str,
    page_title: str,
    website: str,
) -> bool:
    text = normalize_text(page_text)
    title = normalize_text(page_title)
    url = normalize_text(website)

    informational_patterns = [
        r"/(?:blog|news|article|guide|comparison|review)(?:/|$)",
        r"\b(?:how to|guide|tips|best|comparison|review|choosing|choose|"
        r"demand and supply|market|news)\b",
        r"\b(?:buyers should|buyer demand|consumer demand)\b",
        r"\b(?:directory|membership listing|marketplace)\b",
    ]

    return any(
        re.search(pattern, url)
        or re.search(pattern, title)
        or re.search(pattern, text)
        for pattern in informational_patterns
    )


def has_organizational_purchase_intent(
    page_text: str,
    target_product: str,
) -> bool:
    text = normalize_text(page_text)
    product_pattern = re.escape(
        normalize_text(target_product).rstrip("s")
    ) + r"s?"

    return bool(
        re.search(
            rf"\b(?:we|our|us|company|business|organization|organisation|"
            r"studio|center|centre|department|team|importer|buyer)\b"
            r".{0,220}\b(?:looking for|seeking|need(?:s)?|want(?:s)? to|"
            r"looking to|sourcing|source|procure|procurement|purchase|"
            r"purchasing|buying|buy|rfq|request for quotation)\b"
            rf".{{0,220}}{product_pattern}",
            text,
            re.IGNORECASE,
        )
        or re.search(
            rf"{product_pattern}.{{0,220}}\b(?:looking for|seeking|"
            r"need(?:s)?|sourcing|procurement|purchase inquiry|"
            r"buying inquiry|rfq|request for quotation)\b.{0,220}"
            r"\b(?:we|our|us|company|business|organization|organisation|"
            r"studio|center|centre|importer|buyer)\b",
            text,
            re.IGNORECASE,
        )
    )


def pre_classify_candidate(
    page_text: str,
    page_title: str,
    website: str,
    target_product: str,
) -> dict | None:
    """
    Classify obvious cases without using the LLM.

    Return None only when there is buyer-intent signal worth sending
    to Gemini for judgment.
    """

    evidence = extract_relevant_evidence(
        page_text=page_text,
        target_product=target_product,
    )

    if not is_target_product_relevant(
        page_text=page_text,
        target_product=target_product,
    ):
        return {
            "classification": "IRRELEVANT",
            "confidence": 0.95,
            "reason": (
                "The page is not clearly about buying Singing Bowls, "
                "or it focuses on accessories instead."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    explicit_intent = has_explicit_purchase_intent(
        page_text=page_text,
        target_product=target_product,
    )

    if has_supplier_evidence(
        page_text=page_text,
        target_product=target_product,
    ):
        return {
            "classification": "SUPPLIER",
            "confidence": 0.9,
            "reason": (
                "The page indicates that the business sells, supplies, "
                "manufactures, or wholesales Singing Bowls."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    if is_informational_page(
        page_text=page_text,
        page_title=page_title,
        website=website,
    ) and not has_organizational_purchase_intent(
        page_text=page_text,
        target_product=target_product,
    ):
        return {
            "classification": "INFORMATIONAL",
            "confidence": 0.85,
            "reason": (
                "The page appears to be informational and does not show "
                "the organization's own procurement intent."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    if is_service_provider_page(page_text) and not explicit_intent:
        return {
            "classification": "SERVICE_PROVIDER",
            "confidence": 0.9,
            "reason": (
                "The page describes sound healing, wellness, classes, "
                "or sessions using Singing Bowls, not procurement intent."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    if not explicit_intent:
        return {
            "classification": "UNCERTAIN",
            "confidence": 0.65,
            "reason": (
                "The page mentions Singing Bowls but does not contain "
                "explicit buying, sourcing, RFQ, or procurement evidence."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    if has_organizational_purchase_intent(
        page_text=page_text,
        target_product=target_product,
    ):
        return {
            "classification": "BUYER",
            "confidence": 0.86,
            "reason": (
                "The page contains explicit organizational purchasing "
                "or sourcing intent for Singing Bowls."
            ),
            "evidence": evidence,
            "classification_source": "rules",
        }

    return None


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


def has_explicit_purchase_intent(
    page_text: str,
    target_product: str,
) -> bool:
    """Return True only when purchasing language is tied to the product."""

    text = normalize_text(page_text)
    product = normalize_text(target_product)

    product_pattern = re.escape(product.rstrip("s")) + r"s?"
    intent_pattern = (
        r"(?:looking for|seeking|need(?:s)?|want(?:s)? to|"
        r"looking to|trying to|planning to|intend(?:s)? to|"
        r"sourcing|source|procure|procurement of|purchase|purchasing|"
        r"buying|buy|rfq|request for quotation|requesting quotations?)"
    )

    return bool(
        re.search(
            rf"{intent_pattern}.{{0,180}}{product_pattern}",
            text,
            re.IGNORECASE,
        )
        or re.search(
            rf"{product_pattern}.{{0,180}}{intent_pattern}",
            text,
            re.IGNORECASE,
        )
    )


def classify_candidate_evidence(
    page_text: str,
    page_title: str,
    website: str,
    classification: str,
    reason: str,
    target_product: str,
) -> tuple[str, str]:
    """Apply deterministic rules after AI classification."""

    text = normalize_text(page_text)
    reason_text = normalize_text(reason)
    url_text = normalize_text(website)
    title_text = normalize_text(page_title)
    product_pattern = re.escape(
        normalize_text(target_product).rstrip("s")
    ) + r"s?"

    supplier_patterns = [
        r"\b(?:we|our|the company|business|shop|store|retailer|manufacturer|"
        r"distributor|brand)\b.{0,120}\b(?:sell|selling|manufactur|"
        r"distribut|wholesal|retail|stock|supply)\w*\b",
        r"\b(?:sell|selling|manufactur|distribut|wholesal|retail|stock|"
        r"supply)\w*\b.{0,120}\b(?:our|the|these|target)\b",
        r"\b(?:we are|our business is|the company is)\s+(?:a\s+)?"
        r"(?:supplier|seller)\b.{0,180}",
    ]
    service_patterns = [
        r"\b(?:sound bath|sound healing|meditation|yoga|therapy|wellness)\b",
        r"\b(?:classes|workshops|sessions|training|retreats?)\b",
    ]
    negative_reason_patterns = [
        r"not a buyer",
        r"service provider",
        r"does not explicitly mention purchasing",
        r"no evidence of purchasing intent",
        r"uses singing bowls",
        r"offers sound healing",
        r"provides sound bath",
        r"provides services",
    ]
    informational_patterns = [
        r"/(?:blog|news|article|guide|comparison|review)(?:/|$)",
        r"\b(?:how to|guide|tips|best|comparison|review|choosing|choose|"
        r"demand and supply|market|news)\b",
        r"\b(?:buyers should|buyer demand|consumer demand)\b",
        r"\b(?:directory|membership listing|marketplace)\b",
    ]

    explicit_intent = has_explicit_purchase_intent(
        page_text=page_text,
        target_product=target_product,
    )

    organizational_intent = bool(
        re.search(
            rf"\b(?:we|our|us|the company|business|organization|"
            r"studio|center|department|team)\b.{0,220}\b(?:looking for|"
            r"seeking|need(?:s)?|want(?:s)? to|looking to|sourcing|source|"
            r"procure|procurement|purchase|purchasing|buying|buy|rfq|"
            rf"request for quotation)\b.{{0,220}}{product_pattern}",
            text,
            re.IGNORECASE,
        )
    )

    if (
        re.search(product_pattern, text)
        and any(
            re.search(pattern, text)
            for pattern in supplier_patterns
        )
    ):
        return "SUPPLIER", "The page indicates that the business supplies the target product."

    supplier_reason = any(
        re.search(pattern, reason_text)
        for pattern in (
            r"supplier",
            r"seller",
            r"sells",
            r"supplies",
        )
    )
    contradictory_supplier_reason = supplier_reason and (
        not explicit_intent
        or any(
            re.search(pattern, reason_text)
            for pattern in (r"not a buyer", r"rather than", r"not seeking")
        )
    )

    if contradictory_supplier_reason:
        return "SUPPLIER", "The classification evidence describes the business as a supplier or seller."

    if any(re.search(pattern, reason_text) for pattern in negative_reason_patterns):
        if any(re.search(pattern, reason_text) for pattern in (r"service provider", r"sound healing", r"sound bath", r"provides services", r"uses singing bowls")):
            return "SERVICE_PROVIDER", "The classification evidence describes services using the target product, not procurement intent."
        return "UNCERTAIN", "The page does not provide credible purchasing intent for the target product."

    if not explicit_intent and any(re.search(pattern, text) for pattern in service_patterns):
        return "SERVICE_PROVIDER", "The page describes services using the target product without procurement evidence."

    is_informational = any(
        re.search(pattern, url_text) or re.search(pattern, title_text) or re.search(pattern, text)
        for pattern in informational_patterns
    )

    if is_informational and not organizational_intent:
        return "INFORMATIONAL", "The page is informational and does not show the organization's own procurement intent."

    if classification == "BUYER" and not explicit_intent:
        return "UNCERTAIN", "No explicit purchasing, sourcing, or procurement evidence is tied to the target product."

    return classification, reason


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


def validate_emails(
    emails: list[str],
) -> tuple[list[str], list[dict]]:
    """
    Validate extracted emails and return valid emails plus invalid details.
    """

    valid_emails = []
    invalid_emails = []

    for email in dict.fromkeys(emails):

        try:

            validation = validate_email(email)

        except Exception as error:

            validation = {
                "email": email,
                "valid": False,
                "reason": f"Email validation failed: {error}",
            }

        if validation.get("valid"):
            valid_emails.append(validation["email"])
        else:
            invalid_emails.append(validation)

    return valid_emails, invalid_emails


CONTACT_BLOCKING_STATUSES = {
    "QUEUED",
    "SENT",
    "CONTACTED",
}


def ensure_buyer_outreach_columns(cursor) -> None:
    """
    Add outreach tracking columns when an existing DB lacks them.
    """

    cursor.execute(
        """
        ALTER TABLE buyers
        ADD COLUMN IF NOT EXISTS outreach_status TEXT DEFAULT 'NOT_CONTACTED',
        ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS contact_attempts INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_contact_error TEXT
        """
    )


def get_existing_buyer_status(
    result: dict,
    target_product: str,
) -> dict:
    """
    Check whether this buyer already exists and was contacted.
    """

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        ensure_buyer_outreach_columns(cursor)

        cursor.execute(
            """
            SELECT
                id,
                outreach_status,
                last_contacted_at,
                contact_attempts,
                last_contact_error
            FROM buyers
            WHERE company_name = %s
              AND website = %s
              AND target_product = %s
            LIMIT 1
            """,
            (
                result.get("company_name"),
                result.get("website"),
                target_product,
            ),
        )

        row = cursor.fetchone()
        connection.commit()

        if not row:
            return {
                "duplicate_buyer": False,
                "already_contacted": False,
                "outreach_status": "NOT_CONTACTED",
                "last_contacted_at": None,
                "contact_attempts": 0,
                "last_contact_error": None,
            }

        outreach_status = (
            row[1]
            or "NOT_CONTACTED"
        )

        return {
            "buyer_id": row[0],
            "duplicate_buyer": True,
            "already_contacted": outreach_status in CONTACT_BLOCKING_STATUSES,
            "outreach_status": outreach_status,
            "last_contacted_at": row[2],
            "contact_attempts": row[3] or 0,
            "last_contact_error": row[4],
        }

    except Exception as error:

        if connection:
            connection.rollback()

        return {
            "duplicate_buyer": False,
            "already_contacted": False,
            "outreach_status": "UNKNOWN",
            "last_contacted_at": None,
            "contact_attempts": 0,
            "last_contact_error": str(error),
        }

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


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

        ensure_buyer_outreach_columns(cursor)

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
    # 1. BUYER-INTENT DISCOVERY
    # ==========================================

    intent_candidates = search_candidates(
        queries=query_groups["intent_queries"],
        num_results=num_results,
        seen_domains=seen_domains,
    )

    # ==========================================
    # 2. BUSINESS DISCOVERY
    # ==========================================

    business_candidates = search_candidates(
        queries=query_groups["business_queries"],
        num_results=num_results,
        seen_domains=seen_domains,
    )

    candidates = (
        intent_candidates
        + business_candidates
    )

    candidates.sort(
        key=lambda candidate: candidate.get(
            "search_score",
            0,
        ),
        reverse=True,
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

        page_title = (
            website.get("title")
            or candidate["title"]
        )

        # ==========================================
        # 4. RULE-FIRST CLASSIFICATION
        # ==========================================

        classification = pre_classify_candidate(
            page_text=page_text,
            page_title=page_title,
            website=candidate["website"],
            target_product=target_product,
        )

        if classification is None:

            ai_context = "\n\n".join([
                f"Page title: {page_title}",
                f"URL: {candidate['website']}",
                f"Search snippet: {candidate.get('snippet', '')}",
                "Relevant page evidence:",
                extract_relevant_evidence(
                    page_text=page_text,
                    target_product=target_product,
                ),
            ])

            try:

                classification = classify_business(
                    text=ai_context[:4000],
                    target_product=target_product,
                )

                classification["classification_source"] = "gemini"

            except Exception as error:

                classification = {
                    "classification": "UNCERTAIN",
                    "confidence": 0,
                    "reason": (
                        f"AI classification failed: {error}"
                    ),
                    "evidence": extract_relevant_evidence(
                        page_text=page_text,
                        target_product=target_product,
                    ),
                    "classification_source": "fallback",
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

        evidence = classification.get(
            "evidence",
            "",
        )

        final_status, reason = classify_candidate_evidence(
            page_text=page_text,
            page_title=page_title,
            website=candidate["website"],
            classification=final_status,
            reason=reason,
            target_product=target_product,
        )

        # ==========================================
        # 5. HARD PRODUCT RELEVANCE CHECK
        # ==========================================

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
            page_title=page_title,
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
            "evidence": evidence,
            "classification_source": classification.get(
                "classification_source",
                "unknown",
            ),
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

            valid_emails, invalid_emails = validate_emails(
                result.get("emails", [])
                + buyer_contact_emails
            )

            result["raw_emails"] = result.get(
                "emails",
                [],
            )

            result["raw_buyer_contact_emails"] = (
                buyer_contact_emails
            )

            result["invalid_emails"] = invalid_emails

            result["emails"] = valid_emails

            result["buyer_contact_emails"] = (
                []
            )

            result["email_available"] = bool(
                valid_emails
            )

            buyer_status = get_existing_buyer_status(
                result=result,
                target_product=target_product,
            )

            result.update(buyer_status)

            result["ready_for_outreach"] = (
                result["email_available"]
                and not result["already_contacted"]
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
