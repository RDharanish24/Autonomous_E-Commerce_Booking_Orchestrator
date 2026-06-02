import asyncio
import httpx
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings
from models.schemas import VendorOption

class VendorService:
    def __init__(self):
        # Connection pooling via a single AsyncClient
        self.client = httpx.AsyncClient(timeout=4.0)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def _fetch_from_vendor(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hits a specific vendor endpoint with user constraints.
        Retries on network timeouts or 5xx server errors.
        """
        print(f"[FETCH] Querying vendor endpoint: {url}")
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def fetch_all_vendors_concurrently(self, constraints: Dict[str, Any]) -> List[VendorOption]:
        """
        Fires requests to all vendor APIs simultaneously and aggregates the results.
        """
        vendors = [
            {"id": "vendor_alpha", "url": settings.VENDOR_A_URL},
            {"id": "vendor_beta", "url": settings.VENDOR_B_URL},
            {"id": "vendor_gamma", "url": settings.VENDOR_C_URL}
        ]

        tasks = [self._fetch_from_vendor(v["url"], constraints) for v in vendors]
        
        # return_exceptions=True ensures one failing API doesn't kill the whole batch
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validated_options: List[VendorOption] = []

        for idx, result in enumerate(results):
            vendor_meta = vendors[idx]
            
            if isinstance(result, Exception):
                print(f"[VENDOR WARNING] {vendor_meta['id']} failed permanently: {str(result)}")
                continue
            
            try:
                option = VendorOption(
                    vendor_id=vendor_meta["id"],
                    service_name=result.get("service_name", "Standard Service"),
                    price=float(result.get("price", 0.0)),
                    currency=result.get("currency", "USD"),
                    metadata=result.get("metadata", {})
                )
                validated_options.append(option)
            except Exception as parse_err:
                print(f"[PARSING ERROR] Failed to parse payload for {vendor_meta['id']}: {parse_err}")

        return validated_options

    async def close(self):
        """Clean up HTTP client session resources."""
        await self.client.aclose()