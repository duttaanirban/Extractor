import re


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?\d{1,3}[\s.-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.-]?)?"
    r"\d{3,4}[\s.-]\d{3,4}"
    r"(?!\d)"
)


def extract_contacts(text: str) -> dict:
    """
    Extract publicly visible contact information from page text.
    """

    emails = sorted(
        {
            email.lower().rstrip(".,;:")
            for email in EMAIL_PATTERN.findall(text)
        }
    )

    phones = sorted(
        {
            phone.strip()
            for phone in PHONE_PATTERN.findall(text)
        }
    )

    return {
        "emails": emails,
        "phones": phones,
    }