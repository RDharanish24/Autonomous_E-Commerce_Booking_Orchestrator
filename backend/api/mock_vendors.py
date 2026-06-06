import asyncio
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status

router = APIRouter()

def generate_mock_flights(vendor_name: str) -> list:
    """Generates structured flight options for testing purposes."""
    now = datetime.now(timezone.utc)
    # Different pricing and properties per vendor to make them realistic
    if vendor_name == "vendor-alpha":
        return [
            {
                "vendor": "vendor-alpha",
                "price": round(random.uniform(280.0, 360.0), 2),
                "departure_time": (now + timedelta(days=10, hours=8)).isoformat(),
                "layovers": 1
            },
            {
                "vendor": "vendor-alpha",
                "price": round(random.uniform(400.0, 480.0), 2),
                "departure_time": (now + timedelta(days=10, hours=14, minutes=30)).isoformat(),
                "layovers": 0
            }
        ]
    elif vendor_name == "vendor-beta":
        return [
            {
                "vendor": "vendor-beta",
                "price": round(random.uniform(300.0, 390.0), 2),
                "departure_time": (now + timedelta(days=10, hours=9, minutes=15)).isoformat(),
                "layovers": 1
            },
            {
                "vendor": "vendor-beta",
                "price": round(random.uniform(430.0, 520.0), 2),
                "departure_time": (now + timedelta(days=10, hours=16)).isoformat(),
                "layovers": 0
            }
        ]
    else:  # vendor-gamma
        return [
            {
                "vendor": "vendor-gamma",
                "price": round(random.uniform(250.0, 320.0), 2),
                "departure_time": (now + timedelta(days=10, hours=6, minutes=45)).isoformat(),
                "layovers": 2
            },
            {
                "vendor": "vendor-gamma",
                "price": round(random.uniform(380.0, 460.0), 2),
                "departure_time": (now + timedelta(days=10, hours=18, minutes=15)).isoformat(),
                "layovers": 0
            }
        ]

async def simulate_network_and_failures(vendor_name: str):
    """Simulates artificial network delays and failure rates."""
    # Realistic delay of 1-4 seconds
    delay = random.uniform(1.0, 4.0)
    await asyncio.sleep(delay)
    
    # 15% failure rate
    if random.random() < 0.15:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulated database / system crash on {vendor_name}"
        )

@router.get("/mock/vendor-alpha/flights")
async def get_flights_vendor_alpha():
    await simulate_network_and_failures("vendor-alpha")
    return generate_mock_flights("vendor-alpha")

@router.get("/mock/vendor-beta/flights")
async def get_flights_vendor_beta():
    await simulate_network_and_failures("vendor-beta")
    return generate_mock_flights("vendor-beta")

@router.get("/mock/vendor-gamma/flights")
async def get_flights_vendor_gamma():
    await simulate_network_and_failures("vendor-gamma")
    return generate_mock_flights("vendor-gamma")
