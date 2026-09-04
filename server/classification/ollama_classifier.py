import json
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"


def classify_business(
    text: str,
    target_product: str,
) -> dict:

    prompt = f"""You are a strict B2B lead classification assistant.
Your only job is to classify ONE business based on the text provided,
using the rules below exactly.

TARGET PRODUCT: {target_product}

Classify the business into exactly ONE category:
BUYER, SUPPLIER, IRRELEVANT, or UNCERTAIN.

=== DEFINITIONS ===

SUPPLIER:
The business manufactures, produces, sells, distributes, wholesales,
or otherwise supplies the target product or a close variant of it.

This includes retailers, wholesalers, manufacturers, and distributors.

Selling, stocking, or wholesaling the target product is SUPPLIER evidence,
NEVER buyer evidence.

BUYER:
The business or organization shows explicit evidence that IT wants to
purchase, source, procure, or find a supplier for the target product.

Examples of strong buyer evidence:
- Looking for a supplier
- Seeking a vendor
- Requesting manufacturers
- RFQ/RFP/tender
- "Need to buy"
- "Looking for..."
- "Seeking..."
- Explicit upcoming purchasing requirement

Do NOT classify a business as BUYER merely because it could use the
product or because it belongs to a relevant industry.

UNCERTAIN:
Use this when the business is related to the target product but there
is insufficient evidence of whether it is buying or supplying it.

IRRELEVANT:
Use this when there is no meaningful connection to the target product.

=== DECISION CHECKLIST ===

1. Does the text show the business manufactures, sells, distributes,
   or wholesales the target product?
   -> SUPPLIER

2. Does the text contain EXPLICIT purchasing, sourcing, or procurement
   intent for the target product?
   -> BUYER

3. Is there no meaningful connection to the target product?
   -> IRRELEVANT

4. Otherwise:
   -> UNCERTAIN

=== HARD RULES ===

- Never infer buyer intent merely because a business could use the product.
- Never classify a supplier as a buyer because it has customers.
- Never invent facts.
- If evidence is insufficient, choose UNCERTAIN.
- Confidence must reflect the strength of the evidence.
- The reason must be concise and evidence-based.

=== OUTPUT FORMAT ===

Return ONLY valid JSON:

{{
  "classification": "BUYER",
  "confidence": 0.0,
  "reason": "brief evidence-based explanation"
}}

=== BUSINESS TEXT ===

{text}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )

    response.raise_for_status()

    result = response.json()
    model_response = result.get("response", "")

    try:
        classification = json.loads(model_response)

        allowed = {
            "BUYER",
            "SUPPLIER",
            "IRRELEVANT",
            "UNCERTAIN",
        }

        if classification.get("classification") not in allowed:
            classification["classification"] = "UNCERTAIN"

        return classification

    except json.JSONDecodeError:
        return {
            "classification": "UNCERTAIN",
            "confidence": 0.0,
            "reason": "AI returned an invalid response format.",
        }