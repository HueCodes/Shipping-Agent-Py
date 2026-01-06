"""Mock implementations for testing without API keys."""

import random
from dataclasses import dataclass

from src.easypost_client import Address, Parcel, Rate, Shipment


# Realistic mock data
CARRIERS = [
    ("USPS", "Ground Advantage", 5, 7),
    ("USPS", "Priority Mail", 2, 3),
    ("USPS", "Priority Mail Express", 1, 2),
    ("UPS", "Ground", 4, 5),
    ("UPS", "3 Day Select", 3, 3),
    ("UPS", "2nd Day Air", 2, 2),
    ("UPS", "Next Day Air", 1, 1),
    ("FedEx", "Ground", 4, 5),
    ("FedEx", "Express Saver", 3, 3),
    ("FedEx", "2Day", 2, 2),
    ("FedEx", "Priority Overnight", 1, 1),
]


def _generate_rate_id() -> str:
    return f"rate_{random.randint(10000, 99999)}"


def _generate_tracking() -> str:
    carriers = ["1Z", "94", "78"]
    prefix = random.choice(carriers)
    return f"{prefix}{random.randint(100000000, 999999999)}"


class MockEasyPostClient:
    """Mock EasyPost client for testing."""

    def __init__(self, api_key: str | None = None):
        # Accept but ignore api_key
        self.from_address = Address(
            name="Test Shipper",
            street1="123 Test St",
            city="New York",
            state="NY",
            zip_code="10001",
            phone="5551234567",
        )

    def validate_address(self, address: Address) -> tuple[bool, Address | None, str]:
        """Mock address validation - always succeeds with standardized format."""
        corrected = Address(
            name=address.name.upper() if address.name else "",
            street1=address.street1.upper(),
            street2=address.street2.upper() if address.street2 else "",
            city=address.city.upper(),
            state=address.state.upper(),
            zip_code=address.zip_code.split("-")[0],  # Normalize to 5-digit
            country="US",
            phone=address.phone,
        )
        return True, corrected, "Address is valid"

    def get_rates(
        self,
        to_address: Address,
        parcel: Parcel,
        from_address: Address | None = None,
    ) -> list[Rate]:
        """Generate realistic mock rates based on weight and distance."""
        # Base rate calculation (simplified)
        weight_factor = parcel.weight / 16  # Convert oz to lbs
        base_cost = 5.0 + (weight_factor * 0.5)

        # Simulate distance factor based on state
        west_coast = ["CA", "WA", "OR", "NV", "AZ"]
        east_coast = ["NY", "NJ", "MA", "CT", "PA", "VA", "MD", "FL"]

        if to_address.state.upper() in west_coast:
            distance_factor = 1.5
        elif to_address.state.upper() in east_coast:
            distance_factor = 1.0
        else:
            distance_factor = 1.25

        rates = []
        for carrier, service, min_days, max_days in CARRIERS:
            # Faster = more expensive
            speed_factor = 1.0 / min_days
            rate = base_cost * distance_factor * (1 + speed_factor)

            # Add carrier variation
            if carrier == "UPS":
                rate *= 1.1
            elif carrier == "FedEx":
                rate *= 1.15

            rates.append(Rate(
                carrier=carrier,
                service=service,
                rate=round(rate, 2),
                delivery_days=max_days,
                rate_id=_generate_rate_id(),
            ))

        rates.sort(key=lambda x: x.rate)
        return rates

    def create_shipment(
        self,
        to_address: Address,
        parcel: Parcel,
        rate_id: str,
        from_address: Address | None = None,
    ) -> Shipment:
        """Create a mock shipment."""
        # Find a carrier based on rate_id pattern (in real impl, we'd look this up)
        carrier = random.choice(["USPS", "UPS", "FedEx"])
        service = "Ground"

        return Shipment(
            id=f"shp_{random.randint(10000, 99999)}",
            tracking_number=_generate_tracking(),
            label_url="https://example.com/labels/mock-label.pdf",
            carrier=carrier,
            service=service,
            rate=round(random.uniform(8, 25), 2),
        )

    def get_tracking(self, tracking_number: str, carrier: str) -> dict:
        """Return mock tracking info."""
        return {
            "status": "in_transit",
            "estimated_delivery": "2025-01-10",
            "events": [
                {
                    "status": "in_transit",
                    "message": "Package in transit to destination",
                    "location": "Chicago, IL",
                    "datetime": "2025-01-07T14:30:00Z",
                },
                {
                    "status": "accepted",
                    "message": "Package accepted at origin facility",
                    "location": "New York, NY",
                    "datetime": "2025-01-06T09:15:00Z",
                },
            ],
        }


# Simple mock agent responses for testing without Claude API
MOCK_RESPONSES = {
    "rates": """I found several shipping options for you:

1. **USPS Ground Advantage**: $8.45 (5-7 days)
2. **UPS Ground**: $12.30 (4-5 days)
3. **FedEx Ground**: $11.85 (4-5 days)
4. **USPS Priority Mail**: $15.20 (2-3 days)

The cheapest option is USPS Ground Advantage at $8.45. Would you like me to create a shipment with this rate?""",

    "validate": """The address has been validated and standardized:

**123 MAIN ST**
**LOS ANGELES, CA 90001**

The address looks good and is ready for shipping.""",

    "ship": """Shipment created successfully!

- **Tracking Number**: 1Z999AA10123456784
- **Carrier**: USPS Ground Advantage
- **Cost**: $8.45
- **Estimated Delivery**: 5-7 business days

Your label is ready to download. The tracking number has been saved.""",

    "default": """I can help you with:

- **Get rates**: "What are the rates to ship a 2lb package to Los Angeles?"
- **Validate address**: "Is 123 Main St, LA, CA 90001 a valid address?"
- **Create shipment**: "Ship it with the cheapest option"

What would you like to do?""",
}


def get_mock_response(user_input: str) -> str:
    """Return a mock response based on user input keywords."""
    lower = user_input.lower()

    if any(word in lower for word in ["rate", "cost", "price", "ship to", "how much"]):
        return MOCK_RESPONSES["rates"]
    elif any(word in lower for word in ["valid", "check address", "verify"]):
        return MOCK_RESPONSES["validate"]
    elif any(word in lower for word in ["ship it", "create", "buy", "purchase", "use the"]):
        return MOCK_RESPONSES["ship"]
    else:
        return MOCK_RESPONSES["default"]
