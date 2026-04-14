"""
HTTP client for calling the Agrofarm AI image analysis service.
Keeps the main backend decoupled — communicates via HTTP only.
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")


async def analyze_product_image(base64_image: str) -> dict | None:
    """
    Send a base64-encoded image to the AI analysis service.
    Returns the analysis result dict or None on failure.
    """
    url = f"{AI_SERVICE_URL}/api/products/analyze-image"
    payload = {"farmer_id": "system", "image": base64_image}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"AI image analysis failed: {e}")
        return None
