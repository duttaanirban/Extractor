from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from extraction.result_parser import parse_search_results
from extraction.website_fetcher import fetch_website
from extraction.contact_extractor import extract_contacts
from validation.email_validator import validate_email
from classification.gemini_classifier import classify_business
from discovery.buyer_discovery import discover_buyers
from database.buyer_repository import (
    get_all_buyers,
    get_buyer_by_id,
    update_buyer_outreach_status,
)
from outreach.email_composer import compose_personalized_email
from outreach.gmail_sender import send_gmail

from search.serper import search_buyers


app = FastAPI(title="EXPORT Automation API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BuyerSearchRequest(BaseModel):
    query: str
    num_results: int = 10


class ComposeEmailRequest(BaseModel):
    buyer: dict
    target_product: str = "Singing Bowls"
    sender_name: str = "Anirban"
    company_name: str = "our export team"


class SendBuyerEmailRequest(BaseModel):
    buyer_id: int
    force: bool = False


@app.get("/")
def root():
    return {"message": "EXPORT Automation API is running"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/buyers/search")
def search_buyer_api(request: BuyerSearchRequest):
    try:
        results = search_buyers(
            query=request.query,
            num_results=request.num_results,
        )

        buyers = parse_search_results(results)

        return {
            "success": True,
            "buyers": buyers,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@app.get("/api/extraction/website")
def extract_website(url: str):
    return fetch_website(url)

@app.get("/api/extraction/contacts")
def extract_contacts_api(text: str):
    return extract_contacts(text)

@app.get("/api/validation/email")
def validate_email_api(email: str):
    return validate_email(email)

@app.post("/api/outreach/compose")
def compose_email_api(request: ComposeEmailRequest):
    try:
        return {
            "success": True,
            "draft": compose_personalized_email(
                buyer=request.buyer,
                target_product=request.target_product,
                sender_name=request.sender_name,
                company_name=request.company_name,
            ),
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@app.post("/api/outreach/send-gmail")
def send_buyer_email_api(request: SendBuyerEmailRequest):
    buyer = get_buyer_by_id(request.buyer_id)

    if not buyer:
        raise HTTPException(
            status_code=404,
            detail="Buyer not found.",
        )

    if buyer.get("classification") != "BUYER":
        raise HTTPException(
            status_code=400,
            detail="Only confirmed BUYER records can be emailed.",
        )

    if (
        buyer.get("outreach_status") == "SENT"
        and not request.force
    ):
        raise HTTPException(
            status_code=409,
            detail="Buyer has already been contacted.",
        )

    emails = buyer.get("emails") or []

    if not emails:
        raise HTTPException(
            status_code=400,
            detail="Buyer has no validated email address.",
        )

    subject = buyer.get("email_subject") or ""
    body = buyer.get("email_body") or ""

    if not subject or not body:
        draft = compose_personalized_email(
            buyer=buyer,
            target_product=buyer.get(
                "target_product",
                "Singing Bowls",
            ),
        )
        subject = draft["subject"]
        body = draft["body"]

    send_result = send_gmail(
        to_email=emails[0],
        subject=subject,
        body=body,
    )

    if send_result.get("success"):
        update_buyer_outreach_status(
            buyer_id=request.buyer_id,
            outreach_status="SENT",
        )

        return {
            "success": True,
            "buyer_id": request.buyer_id,
            "to_email": emails[0],
            "outreach_status": "SENT",
        }

    update_buyer_outreach_status(
        buyer_id=request.buyer_id,
        outreach_status="FAILED",
        error=send_result.get(
            "error",
            "Unknown Gmail send failure.",
        ),
    )

    raise HTTPException(
        status_code=502,
        detail=send_result.get(
            "error",
            "Unknown Gmail send failure.",
        ),
    )

@app.post("/api/classification/business")
def classify_business_api(
    text: str,
    target_product: str = "Singing Bowls",
):
    try:
        return classify_business(
            text=text,
            target_product=target_product,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )
        
@app.post("/api/buyers/discover")
def discover_buyers_api(
    target_product: str,
    num_results: int = 10,
):
    try:
        return discover_buyers(
            target_product=target_product,
            num_results=num_results,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )

@app.get("/api/buyers")
def get_saved_buyers_api():
    try:
        buyers = get_all_buyers()

        return {
            "success": True,
            "count": len(buyers),
            "buyers": buyers,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )
