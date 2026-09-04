import re
from urllib.parse import urlparse


DEFAULT_SENDER_NAME = "Anirban"
DEFAULT_COMPANY_NAME = "our export team"


def clean_text(value: str | None) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip()


def clean_company_name(company_name: str | None, website: str | None) -> str:
    name = clean_text(company_name)

    if name:
        return name[:90]

    try:
        domain = urlparse(website or "").netloc.replace("www.", "")
        return domain or "your team"
    except Exception:
        return "your team"


def infer_buyer_context(buyer: dict) -> str:
    evidence = clean_text(
        buyer.get("evidence")
        or buyer.get("reason")
        or buyer.get("search_query")
    )

    if not evidence:
        return ""

    return evidence[:220]


def compose_personalized_email(
    buyer: dict,
    target_product: str = "Singing Bowls",
    sender_name: str = DEFAULT_SENDER_NAME,
    company_name: str = DEFAULT_COMPANY_NAME,
) -> dict:
    """
    Compose a short outreach draft.

    This creates a draft only. It does not send email.
    """

    buyer_name = clean_company_name(
        buyer.get("company_name"),
        buyer.get("website"),
    )
    product = clean_text(target_product) or "Singing Bowls"
    sender = clean_text(sender_name) or DEFAULT_SENDER_NAME
    company = clean_text(company_name) or DEFAULT_COMPANY_NAME
    context = infer_buyer_context(buyer)

    subject = f"{product} supply inquiry for {buyer_name}"

    context_line = ""

    if context:
        context_line = (
            "I noticed your team may be exploring sourcing for "
            f"{product.lower()} based on this public context: {context}"
        )
    else:
        context_line = (
            f"I noticed your team may be exploring sourcing for {product.lower()}."
        )

    body = "\n\n".join([
        f"Hi {buyer_name} team,",
        context_line,
        (
            f"I represent {company}. We can share export-ready options for "
            f"{product.lower()}, including product details, pricing, MOQ, "
            "packaging, and shipment support."
        ),
        (
            "I have attached our company presentation for a quick overview. "
            "If this is relevant, I would be happy to send a concise quotation "
            "or product catalog."
        ),
        f"Best regards,\n{sender}",
    ])

    return {
        "subject": subject,
        "body": body,
        "sender_name": sender,
        "company_name": company,
        "target_product": product,
    }

