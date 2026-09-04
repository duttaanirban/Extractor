import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


SERVER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SERVER_DIR / ".env")

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def get_gmail_settings() -> dict:
    return {
        "address": os.getenv("GMAIL_ADDRESS", "").strip(),
        "app_password": os.getenv("GMAIL_APP_PASSWORD", "").strip(),
        "sender_name": os.getenv("GMAIL_SENDER_NAME", "").strip(),
    }


def send_gmail(
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Send a plain text email through Gmail SMTP.

    Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in server/.env.
    """

    settings = get_gmail_settings()
    from_email = settings["address"]
    app_password = settings["app_password"]
    sender_name = settings["sender_name"]

    if not from_email or not app_password:
        return {
            "success": False,
            "error": (
                "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be configured."
            ),
        }

    message = EmailMessage()
    message["From"] = (
        f"{sender_name} <{from_email}>"
        if sender_name
        else from_email
    )
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            GMAIL_SMTP_HOST,
            GMAIL_SMTP_PORT,
            timeout=30,
        ) as server:
            server.starttls()
            server.login(from_email, app_password)
            server.send_message(message)

        return {
            "success": True,
            "to_email": to_email,
        }

    except Exception as error:
        return {
            "success": False,
            "to_email": to_email,
            "error": str(error),
        }
