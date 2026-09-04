import re
import socket


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def validate_email(email: str) -> dict:
    """
    Perform basic email syntax and domain validation.
    """

    email = email.strip().lower()

    if not EMAIL_PATTERN.match(email):
        return {
            "email": email,
            "valid": False,
            "reason": "Invalid email format",
        }

    domain = email.split("@", 1)[1]

    try:
        socket.gethostbyname(domain)

        return {
            "email": email,
            "valid": True,
            "reason": "Email format valid and domain resolves",
        }

    except socket.gaierror:
        return {
            "email": email,
            "valid": False,
            "reason": "Email domain does not resolve",
        }