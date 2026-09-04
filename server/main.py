from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from extraction.result_parser import parse_search_results
from extraction.website_fetcher import fetch_website
from extraction.contact_extractor import extract_contacts
from validation.email_validator import validate_email
from classification.gemini_classifier import classify_business
from discovery.buyer_discovery import discover_buyers
from database.buyer_repository import get_all_buyers

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
