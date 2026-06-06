import asyncio
import random
import logging
import httpx
from typing import List, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)

async def fetch_with_retry(
    client: httpx.AsyncClient, 
    vendor_id: str, 
    url: str, 
    constraints: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetches flights from a single vendor with exponential backoff retries.
    
    Retries up to 3 times (4 attempts total) on network timeout, connection errors,
    or a 500 Internal Server Error status code.
    """
    max_retries = 3
    base_delay = 0.5
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(
                "[%s] Querying endpoint. Attempt %d/%d. URL: %s", 
                vendor_id, attempt + 1, max_retries + 1, url
            )
            # Pass constraints as query parameters
            response = await client.get(url, params=constraints, timeout=5.0)
            
            # Simulated 500 error handling
            if response.status_code == 500:
                raise httpx.HTTPStatusError(
                    "Vendor returned simulated 500 Internal Server Error",
                    request=response.request,
                    response=response
                )
                
            response.raise_for_status()
            data = response.json()
            logger.info("[%s] Fetch successful. Found %d options.", vendor_id, len(data))
            return data
            
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            if attempt == max_retries:
                logger.error(
                    "[%s] Permanent failure: failed after %d retries. Error: %s", 
                    vendor_id, max_retries, exc
                )
                raise exc
            
            # Calculate exponential backoff: delay = base_delay * 2^attempt
            delay = base_delay * (2 ** attempt)
            # Add small random jitter (0 to 100ms) to prevent thunderous herd problem
            delay += random.uniform(0, 0.1)
            
            logger.warning(
                "[%s] Attempt %d failed: %s. Retrying in %.2fs...",
                vendor_id, attempt + 1, exc, delay
            )
            await asyncio.sleep(delay)

async def fetch_flights_concurrently(constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fires asynchronous requests to all mock travel vendor APIs simultaneously.
    Uses asyncio.gather and handles failures gracefully by dropping failing vendors.
    """
    vendors = [
        {"id": "vendor-alpha", "url": settings.VENDOR_ALPHA_URL},
        {"id": "vendor-beta", "url": settings.VENDOR_BETA_URL},
        {"id": "vendor-gamma", "url": settings.VENDOR_GAMMA_URL}
    ]
    
    logger.info("Initializing concurrent fetch for %d vendors with constraints: %s", len(vendors), constraints)
    
    # Use a single AsyncClient to enable HTTP connection pooling
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_with_retry(client, vendor["id"], vendor["url"], constraints)
            for vendor in vendors
        ]
        
        # return_exceptions=True ensures that if one task fails permanently, 
        # the others still complete and we can process successful results.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        aggregated_results = []
        for idx, result in enumerate(results):
            vendor_id = vendors[idx]["id"]
            if isinstance(result, Exception):
                logger.warning("[%s] Dropped from aggregated results due to permanent failure.", vendor_id)
            else:
                aggregated_results.extend(result)
                
        logger.info("Concurrency fetch completed. Aggregated %d total options.", len(aggregated_results))
        return aggregated_results
