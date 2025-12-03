from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import pandas as pd
from google_play_scraper import reviews, Sort
import io
from typing import Optional

app = FastAPI(
    title="Google Play Reviews Scraper API",
    description="API to scrape reviews from Google Play Store for LLM apps",
    version="1.0.0"
)

# --- Hardcoded Top LLM Apps ---
LLM_APPS = {
    "ChatGPT": "com.openai.chatgpt",
    "Claude": "com.anthropic.claude",
    "Gemini": "com.google.android.apps.bard",
    "Microsoft Copilot": "com.microsoft.copilot",
    "Perplexity": "ai.perplexity.app.android",
    "Meta AI": "com.meta.ai.app",
    "Grok": "com.x.grok"
}

# --- Request Model ---
class ScrapeRequest(BaseModel):
    app_name: str = Field(..., description="Name of the LLM app (e.g., 'ChatGPT', 'Claude')")
    count: int = Field(1000, ge=100, le=100000, description="Number of reviews to scrape")
    lang: str = Field("en", description="Language code")
    country: str = Field("us", description="Country code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "app_name": "ChatGPT",
                "count": 1000
            }
        }

# --- Root Endpoint ---
@app.get("/")
def root():
    return {
        "message": "Google Play Reviews Scraper API",
        "available_apps": list(LLM_APPS.keys()),
        "endpoints": {
            "scrape": "/scrape (POST)",
            "apps": "/apps (GET)"
        }
    }

# --- Get Available Apps ---
@app.get("/apps")
def get_apps():
    """Get list of available LLM apps"""
    return {
        "apps": [
            {"name": name, "package_id": package_id}
            for name, package_id in LLM_APPS.items()
        ]
    }

# --- Scrape Endpoint ---
@app.post("/scrape")
def scrape_reviews(request: ScrapeRequest):
    """
    Scrape reviews from Google Play Store and return CSV file
    
    Parameters:
    - app_name: Name of the app (must be from available apps list)
    - count: Number of reviews to scrape (100-100000)
    - lang: Language code (default: 'en')
    - country: Country code (default: 'us')
    
    Returns: CSV file with scraped reviews
    """
    
    # Validate app name
    if request.app_name not in LLM_APPS:
        raise HTTPException(
            status_code=400,
            detail=f"App '{request.app_name}' not found. Available apps: {list(LLM_APPS.keys())}"
        )
    
    package_id = LLM_APPS[request.app_name]
    
    try:
        # Scrape reviews
        result, _ = reviews(
            package_id,
            lang=request.lang,
            country=request.country,
            sort=Sort.NEWEST,
            count=request.count
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="No reviews found for this app")
        
        # Add app name to each review
        for r in result:
            r['app_name'] = request.app_name
        
        # Convert to DataFrame
        result_df = pd.DataFrame(result)
        
        # Select useful columns
        cols_to_keep = ['at', 'app_name', 'score', 'content', 'thumbsUpCount', 'reviewId']
        final_cols = [c for c in cols_to_keep if c in result_df.columns]
        result_df = result_df[final_cols]
        
        # Convert to CSV
        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        # Create filename
        file_name = f"{request.app_name.lower().replace(' ', '_')}_reviews.csv"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during scraping: {str(e)}")

# --- Health Check ---
@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)