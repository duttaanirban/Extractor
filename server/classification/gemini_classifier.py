import os
import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

def classify_business(
    text: str,
    target_product: str,
) -> dict:
    """
    Classify whether a business is a genuine buyer
    of the requested target product.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {
            "classification": "UNCERTAIN",
            "confidence": 0,
            "reason": "GEMINI_API_KEY is not configured.",
            "evidence": "",
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are a strict B2B buyer-intent classifier.

Target product:
{target_product}

Analyze the following business webpage text.

Your task is to determine whether the business is a
GENUINE BUYER of the target product.

Important rules:

1. A business USING the product is NOT automatically a buyer.
2. A business OFFERING services using the product is NOT automatically a buyer.
3. A business SELLING the product is a SUPPLIER, not a buyer.
4. A blog/article discussing how to buy the product is NOT automatically a buyer.
5. A marketplace, comparison page, news page, or generic article is NOT a buyer.
6. BUYER requires credible evidence that the business itself wants to
   purchase, source, procure, wholesale-buy, or find a supplier/manufacturer
   for the target product.
7. Do not infer purchasing intent merely because the business uses the product.
8. If evidence is insufficient, classify as UNCERTAIN.

Return ONLY valid JSON in exactly this structure:

{{
    "classification": "BUYER",
    "confidence": 0.0,
    "reason": "short explanation",
    "evidence": "specific purchasing evidence, or an empty string"
}}

Allowed classifications:

BUYER
SUPPLIER
SERVICE_PROVIDER
INFORMATIONAL
IRRELEVANT
UNCERTAIN

Confidence must be between 0 and 1.

Business webpage text:
{text[:12000]}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        raw_text = response.text.strip()

        # Remove markdown code fences if Gemini returns them.
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```json", "")
            raw_text = raw_text.replace("```", "")
            raw_text = raw_text.strip()

        result = json.loads(raw_text)

        return {
            "classification": result.get(
                "classification",
                "UNCERTAIN",
            ),
            "confidence": float(
                result.get("confidence", 0)
            ),
            "reason": result.get(
                "reason",
                "No reason provided.",
            ),
            "evidence": result.get(
                "evidence",
                "",
            ),
        }

    except Exception as error:

        return {
            "classification": "UNCERTAIN",
            "confidence": 0,
            "reason": f"Gemini classification failed: {error}",
            "evidence": "",
        }
