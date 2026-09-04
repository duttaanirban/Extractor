from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

        return {
            "success": True,
            "results": results,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )