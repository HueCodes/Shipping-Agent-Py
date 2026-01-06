"""Parse shipping details from natural language input."""

import re
from dataclasses import dataclass


# US state abbreviations and names
STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    # Common abbreviations
    "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA", "co": "CO",
    "ct": "CT", "de": "DE", "fl": "FL", "ga": "GA", "hi": "HI", "id": "ID",
    "il": "IL", "in": "IN", "ia": "IA", "ks": "KS", "ky": "KY", "la": "LA",
    "me": "ME", "md": "MD", "ma": "MA", "mi": "MI", "mn": "MN", "ms": "MS",
    "mo": "MO", "mt": "MT", "ne": "NE", "nv": "NV", "nh": "NH", "nj": "NJ",
    "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH", "ok": "OK",
    "or": "OR", "pa": "PA", "ri": "RI", "sc": "SC", "sd": "SD", "tn": "TN",
    "tx": "TX", "ut": "UT", "vt": "VT", "va": "VA", "wa": "WA", "wv": "WV",
    "wi": "WI", "wy": "WY", "dc": "DC",
}

# Major cities for fuzzy matching
CITIES = {
    "la": "Los Angeles", "los angeles": "Los Angeles",
    "nyc": "New York", "new york": "New York", "new york city": "New York",
    "sf": "San Francisco", "san francisco": "San Francisco",
    "chicago": "Chicago", "chi": "Chicago",
    "houston": "Houston",
    "phoenix": "Phoenix",
    "philly": "Philadelphia", "philadelphia": "Philadelphia",
    "san antonio": "San Antonio",
    "san diego": "San Diego",
    "dallas": "Dallas",
    "austin": "Austin",
    "seattle": "Seattle",
    "denver": "Denver",
    "boston": "Boston",
    "vegas": "Las Vegas", "las vegas": "Las Vegas",
    "miami": "Miami",
    "atlanta": "Atlanta", "atl": "Atlanta",
    "portland": "Portland",
    "detroit": "Detroit",
}

# City to state mapping for common cities
CITY_STATES = {
    "los angeles": "CA", "san francisco": "CA", "san diego": "CA",
    "new york": "NY", "chicago": "IL", "houston": "TX", "dallas": "TX",
    "austin": "TX", "san antonio": "TX", "phoenix": "AZ", "philadelphia": "PA",
    "seattle": "WA", "denver": "CO", "boston": "MA", "las vegas": "NV",
    "miami": "FL", "atlanta": "GA", "portland": "OR", "detroit": "MI",
}


@dataclass
class ParsedShippingInfo:
    """Parsed shipping information from user input."""
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    weight_oz: float | None = None
    street: str | None = None
    service_level: str | None = None  # ground, express, overnight

    @property
    def has_destination(self) -> bool:
        """Check if we have enough destination info."""
        return bool(self.zip_code or (self.city and self.state))

    @property
    def has_weight(self) -> bool:
        """Check if we have weight info."""
        return self.weight_oz is not None

    def to_dict(self) -> dict:
        """Convert to dict for tool input."""
        result = {}
        if self.city:
            result["to_city"] = self.city
        if self.state:
            result["to_state"] = self.state
        if self.zip_code:
            result["to_zip"] = self.zip_code
        if self.weight_oz:
            result["weight_oz"] = self.weight_oz
        return result


def parse_weight(text: str) -> float | None:
    """Extract weight from text, return in ounces."""
    text = text.lower()

    # Match patterns like "2lb", "2 lb", "2 lbs", "2 pounds", "32oz", "32 oz"
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|pound|pounds)\b", 16),  # pounds to oz
        (r"(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)\b", 1),       # already oz
        (r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)\b", 35.274), # kg to oz
        (r"(\d+(?:\.\d+)?)\s*(?:g|gram|grams)\b", 0.035274),   # g to oz
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1)) * multiplier

    return None


def parse_zip(text: str) -> str | None:
    """Extract ZIP code from text."""
    # Match 5-digit or 5+4 digit ZIP
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
    return match.group(1) if match else None


def parse_state(text: str) -> str | None:
    """Extract state from text."""
    text_lower = text.lower()

    # Check for state names and abbreviations
    for name, abbrev in STATES.items():
        # Use word boundaries to avoid partial matches
        if re.search(rf"\b{re.escape(name)}\b", text_lower):
            return abbrev

    return None


def parse_city(text: str) -> tuple[str | None, str | None]:
    """Extract city from text. Returns (city, state) if state can be inferred."""
    text_lower = text.lower()

    # Check known cities
    for alias, city in CITIES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            state = CITY_STATES.get(city.lower())
            return city, state

    # Try to extract city from "to [City]" or "[City], [State]" patterns
    # Match "to Chicago" or "to Los Angeles"
    match = re.search(r"to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    if match:
        potential_city = match.group(1)
        # Verify it's not a state name
        if potential_city.lower() not in STATES:
            return potential_city, None

    return None, None


def parse_service_level(text: str) -> str | None:
    """Extract service level preference from text."""
    text_lower = text.lower()

    if any(word in text_lower for word in ["overnight", "next day", "rush"]):
        return "overnight"
    elif any(word in text_lower for word in ["express", "fast", "quick", "2 day", "two day"]):
        return "express"
    elif any(word in text_lower for word in ["ground", "cheap", "cheapest", "economy", "standard"]):
        return "ground"

    return None


def parse_shipping_input(text: str) -> ParsedShippingInfo:
    """Parse natural language shipping input into structured data."""
    info = ParsedShippingInfo()

    # Extract components
    info.weight_oz = parse_weight(text)
    info.zip_code = parse_zip(text)
    info.state = parse_state(text)
    info.service_level = parse_service_level(text)

    # Extract city (may also give us state)
    city, city_state = parse_city(text)
    if city:
        info.city = city
        if not info.state and city_state:
            info.state = city_state

    return info


def describe_parsed(info: ParsedShippingInfo) -> str:
    """Generate a human-readable description of what was parsed."""
    parts = []

    if info.weight_oz:
        if info.weight_oz >= 16:
            parts.append(f"{info.weight_oz / 16:.1f} lb package")
        else:
            parts.append(f"{info.weight_oz:.0f} oz package")

    dest_parts = []
    if info.city:
        dest_parts.append(info.city)
    if info.state:
        dest_parts.append(info.state)
    if info.zip_code:
        dest_parts.append(info.zip_code)

    if dest_parts:
        parts.append(f"to {', '.join(dest_parts)}")

    if info.service_level:
        parts.append(f"({info.service_level})")

    return " ".join(parts) if parts else "No shipping details detected"
