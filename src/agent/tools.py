"""Agent tool definitions for Claude."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID

from src.easypost_client import Address, EasyPostClient, Parcel, Rate

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from src.agent.context import CustomerContext

logger = logging.getLogger(__name__)


# Mock unfulfilled orders for testing
MOCK_ORDERS = [
    {
        "order_id": "ORD-1001",
        "order_number": "#1001",
        "recipient": "Alice Johnson",
        "destination": {"city": "Los Angeles", "state": "CA", "zip": "90001"},
        "item_count": 2,
        "weight_oz": 24,
        "created_at": "2025-01-03",
    },
    {
        "order_id": "ORD-1002",
        "order_number": "#1002",
        "recipient": "Bob Smith",
        "destination": {"city": "Austin", "state": "TX", "zip": "78701"},
        "item_count": 1,
        "weight_oz": 8,
        "created_at": "2025-01-04",
    },
    {
        "order_id": "ORD-1003",
        "order_number": "#1003",
        "recipient": "Carol Williams",
        "destination": {"city": "Seattle", "state": "WA", "zip": "98101"},
        "item_count": 3,
        "weight_oz": 48,
        "created_at": "2025-01-04",
    },
    {
        "order_id": "ORD-1004",
        "order_number": "#1004",
        "recipient": "David Brown",
        "destination": {"city": "Miami", "state": "FL", "zip": "33101"},
        "item_count": 1,
        "weight_oz": 12,
        "created_at": "2025-01-05",
    },
    {
        "order_id": "ORD-1005",
        "order_number": "#1005",
        "recipient": "Eve Martinez",
        "destination": {"city": "Denver", "state": "CO", "zip": "80201"},
        "item_count": 4,
        "weight_oz": 64,
        "created_at": "2025-01-05",
    },
    {
        "order_id": "ORD-1006",
        "order_number": "#1006",
        "recipient": "Frank Garcia",
        "destination": {"city": "San Francisco", "state": "CA", "zip": "94102"},
        "item_count": 2,
        "weight_oz": 32,
        "created_at": "2025-01-05",
    },
    {
        "order_id": "ORD-1007",
        "order_number": "#1007",
        "recipient": "Grace Lee",
        "destination": {"city": "New York", "state": "NY", "zip": "10001"},
        "item_count": 1,
        "weight_oz": 6,
        "created_at": "2025-01-06",
    },
    {
        "order_id": "ORD-1008",
        "order_number": "#1008",
        "recipient": "Henry Wilson",
        "destination": {"city": "Chicago", "state": "IL", "zip": "60601"},
        "item_count": 5,
        "weight_oz": 80,
        "created_at": "2025-01-06",
    },
]

# Simulated shipments for tracking (order_id -> shipment info)
MOCK_SHIPMENTS: dict[str, dict] = {}

# Rate cache expiry time in seconds (15 minutes)
RATE_CACHE_EXPIRY_SECONDS = 15 * 60


@dataclass
class CachedRates:
    """Cached rate information with metadata."""
    rates: list[Rate]
    destination_zip: str
    weight_oz: float
    timestamp: float

    def is_stale(self) -> bool:
        """Check if cache entry is older than expiry time."""
        return (time.time() - self.timestamp) > RATE_CACHE_EXPIRY_SECONDS

    def age_minutes(self) -> float:
        """Return age of cache entry in minutes."""
        return (time.time() - self.timestamp) / 60

# Tool definitions for Claude API
TOOLS = [
    {
        "name": "get_shipping_rates",
        "description": "Get shipping rates from multiple carriers for a package. Returns rates sorted by price with carrier, service, cost, and estimated delivery days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_name": {
                    "type": "string",
                    "description": "Recipient name",
                },
                "to_street": {
                    "type": "string",
                    "description": "Street address (e.g., '123 Main St')",
                },
                "to_city": {
                    "type": "string",
                    "description": "City name",
                },
                "to_state": {
                    "type": "string",
                    "description": "Two-letter state code (e.g., 'CA', 'NY')",
                },
                "to_zip": {
                    "type": "string",
                    "description": "ZIP code",
                },
                "weight_oz": {
                    "type": "number",
                    "description": "Package weight in ounces",
                },
                "length": {
                    "type": "number",
                    "description": "Package length in inches",
                    "default": 6,
                },
                "width": {
                    "type": "number",
                    "description": "Package width in inches",
                    "default": 4,
                },
                "height": {
                    "type": "number",
                    "description": "Package height in inches",
                    "default": 2,
                },
            },
            "required": ["to_city", "to_state", "to_zip", "weight_oz"],
        },
    },
    {
        "name": "validate_address",
        "description": "Validate a shipping address and get the corrected/standardized version. Use this before shipping to avoid delivery issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Recipient name",
                },
                "street": {
                    "type": "string",
                    "description": "Street address",
                },
                "city": {
                    "type": "string",
                    "description": "City",
                },
                "state": {
                    "type": "string",
                    "description": "Two-letter state code",
                },
                "zip": {
                    "type": "string",
                    "description": "ZIP code",
                },
            },
            "required": ["street", "city", "state", "zip"],
        },
    },
    {
        "name": "create_shipment",
        "description": "Create a shipment and purchase a label. Returns tracking number and label URL. Only call this after getting rates and confirming with the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_name": {
                    "type": "string",
                    "description": "Recipient name",
                },
                "to_street": {
                    "type": "string",
                    "description": "Street address",
                },
                "to_city": {
                    "type": "string",
                    "description": "City",
                },
                "to_state": {
                    "type": "string",
                    "description": "Two-letter state code",
                },
                "to_zip": {
                    "type": "string",
                    "description": "ZIP code",
                },
                "weight_oz": {
                    "type": "number",
                    "description": "Package weight in ounces",
                },
                "length": {
                    "type": "number",
                    "description": "Package length in inches",
                    "default": 6,
                },
                "width": {
                    "type": "number",
                    "description": "Package width in inches",
                    "default": 4,
                },
                "height": {
                    "type": "number",
                    "description": "Package height in inches",
                    "default": 2,
                },
                "rate_id": {
                    "type": "string",
                    "description": "The rate ID from get_shipping_rates to use",
                },
            },
            "required": ["to_name", "to_street", "to_city", "to_state", "to_zip", "weight_oz", "rate_id"],
        },
    },
    {
        "name": "get_tracking_status",
        "description": "Get the current tracking status and history for a shipment. Use tracking_number or order_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tracking_number": {
                    "type": "string",
                    "description": "The tracking number to look up",
                },
                "order_id": {
                    "type": "string",
                    "description": "Get tracking for this order's shipment",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_unfulfilled_orders",
        "description": "Get list of orders that need to be shipped. Returns order number, recipient name, destination city/state, item count, and total weight.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of orders to return",
                    "default": 20,
                },
                "search": {
                    "type": "string",
                    "description": "Search by order number, customer name, or destination",
                },
            },
            "required": [],
        },
    },
    {
        "name": "bulk_ship_orders",
        "description": "Ship multiple orders at once. Returns summary with count, total cost, and tracking numbers. IMPORTANT: Always summarize what will happen and get user confirmation before calling this tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of order IDs to ship",
                },
                "filter": {
                    "type": "object",
                    "description": "Filter orders instead of specifying IDs",
                    "properties": {
                        "max_weight_oz": {
                            "type": "number",
                            "description": "Only ship orders at or under this weight (in ounces)",
                        },
                        "destination_state": {
                            "type": "string",
                            "description": "Only ship orders going to this state",
                        },
                        "created_after": {
                            "type": "string",
                            "description": "Only ship orders created after this date (YYYY-MM-DD)",
                        },
                    },
                },
                "carrier": {
                    "type": "string",
                    "description": "Carrier to use for all shipments (e.g., 'USPS', 'UPS', 'FedEx')",
                },
                "service": {
                    "type": "string",
                    "description": "Service level to use (e.g., 'Ground', 'Priority')",
                },
                "cheapest": {
                    "type": "boolean",
                    "description": "Use cheapest available option for each order",
                    "default": False,
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Set to true to confirm execution. If false or missing, returns preview only.",
                    "default": False,
                },
            },
            "required": [],
        },
    },
]


class ToolExecutor:
    """Executes agent tools using EasyPost client."""

    def __init__(
        self,
        client: EasyPostClient,
        context: CustomerContext | None = None,
        db: Session | None = None,
    ):
        self.client = client
        self.context = context
        self.db = db

        # Initialize repositories if database is available
        self.order_repo = None
        self.shipment_repo = None
        self.customer_repo = None
        if db is not None:
            from src.db.repository import OrderRepository, ShipmentRepository, CustomerRepository
            self.order_repo = OrderRepository(db)
            self.shipment_repo = ShipmentRepository(db)
            self.customer_repo = CustomerRepository(db)

        # Improved rate cache: cache_key -> CachedRates
        self.rate_cache: dict[str, CachedRates] = {}
        # Map rate_id -> cache_key for quick lookup
        self._rate_id_to_cache_key: dict[str, str] = {}
        # Keep _last_rates for backward compatibility with tests
        self._last_rates: dict[str, Any] = {}

    def _rate_cache_key(self, destination_zip: str, weight_oz: float) -> str:
        """Create a cache key from shipment parameters."""
        return f"{destination_zip}:{weight_oz}"

    def _get_rate_by_id(self, rate_id: str) -> tuple[Rate | None, str | None]:
        """Look up a rate by ID and return (rate, warning_message)."""
        cache_key = self._rate_id_to_cache_key.get(rate_id)
        if not cache_key:
            return None, f"Rate ID '{rate_id}' not found in cache. Please request new rates."

        cached = self.rate_cache.get(cache_key)
        if not cached:
            return None, f"Rate cache expired for '{rate_id}'. Please request new rates."

        # Find the rate in the cached rates
        for rate in cached.rates:
            if rate.rate_id == rate_id:
                warning = None
                if cached.is_stale():
                    warning = (
                        f"Warning: These rates are {cached.age_minutes():.0f} minutes old "
                        "and may no longer be accurate. Consider requesting fresh rates."
                    )
                return rate, warning

        return None, f"Rate ID '{rate_id}' not found. Please request new rates."

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result as a string.

        Wraps tool execution in error handling to ensure graceful failure.
        Returns error messages instead of raising exceptions.
        """
        try:
            if tool_name == "get_shipping_rates":
                return self._get_rates(tool_input)
            elif tool_name == "validate_address":
                return self._validate_address(tool_input)
            elif tool_name == "create_shipment":
                return self._create_shipment(tool_input)
            elif tool_name == "get_tracking_status":
                return self._get_tracking_status(tool_input)
            elif tool_name == "get_unfulfilled_orders":
                return self._get_unfulfilled_orders(tool_input)
            elif tool_name == "bulk_ship_orders":
                return self._bulk_ship_orders(tool_input)
            else:
                return f"Unknown tool: {tool_name}"
        except KeyError as e:
            logger.error(
                "Missing required field in tool '%s': %s. Input: %s",
                tool_name, e, tool_input
            )
            return f"Error: Missing required field {e} for tool '{tool_name}'"
        except Exception as e:
            logger.error(
                "Tool '%s' failed with %s: %s. Input: %s",
                tool_name, type(e).__name__, e, tool_input
            )
            return f"Error executing tool '{tool_name}': {type(e).__name__}: {e}"

    def _get_rates(self, params: dict) -> str:
        to_address = Address(
            name=params.get("to_name", "Recipient"),
            street1=params.get("to_street", ""),
            city=params["to_city"],
            state=params["to_state"],
            zip_code=params["to_zip"],
        )
        parcel = Parcel(
            length=params.get("length", 6),
            width=params.get("width", 4),
            height=params.get("height", 2),
            weight=params["weight_oz"],
        )

        try:
            rates = self.client.get_rates(to_address, parcel)
            if not rates:
                return "No rates available for this shipment."

            # Create cache key
            cache_key = self._rate_cache_key(params["to_zip"], params["weight_oz"])

            # Clear any existing cache for this destination (rates may have changed)
            if cache_key in self.rate_cache:
                old_cached = self.rate_cache[cache_key]
                for rate in old_cached.rates:
                    self._rate_id_to_cache_key.pop(rate.rate_id, None)
                    self._last_rates.pop(rate.rate_id, None)

            # Cache rates with metadata
            self.rate_cache[cache_key] = CachedRates(
                rates=rates,
                destination_zip=params["to_zip"],
                weight_oz=params["weight_oz"],
                timestamp=time.time(),
            )

            # Update rate_id -> cache_key mapping and backward-compat cache
            for r in rates:
                self._rate_id_to_cache_key[r.rate_id] = cache_key
                self._last_rates[r.rate_id] = r

            # Format response
            lines = ["Available shipping rates (sorted by price):"]
            lines.append("")
            for i, r in enumerate(rates[:10], 1):  # Top 10
                days = f"{r.delivery_days} days" if r.delivery_days else "varies"
                lines.append(f"{i}. {r.carrier} {r.service}: ${r.rate:.2f} ({days}) [rate_id: {r.rate_id}]")

            return "\n".join(lines)
        except Exception as e:
            return f"Error getting rates: {e}"

    def _validate_address(self, params: dict) -> str:
        address = Address(
            name=params.get("name", ""),
            street1=params["street"],
            city=params["city"],
            state=params["state"],
            zip_code=params["zip"],
        )

        try:
            is_valid, corrected, message = self.client.validate_address(address)
            if is_valid and corrected:
                return (
                    f"Address is valid.\n"
                    f"Standardized: {corrected.street1}, {corrected.city}, {corrected.state} {corrected.zip_code}"
                )
            else:
                return f"Address validation failed: {message}"
        except Exception as e:
            return f"Error validating address: {e}"

    def _create_shipment(self, params: dict) -> str:
        to_address = Address(
            name=params["to_name"],
            street1=params["to_street"],
            city=params["to_city"],
            state=params["to_state"],
            zip_code=params["to_zip"],
        )
        parcel = Parcel(
            length=params.get("length", 6),
            width=params.get("width", 4),
            height=params.get("height", 2),
            weight=params["weight_oz"],
        )

        # Verify rate exists in cache and check for staleness/mismatches
        rate_id = params["rate_id"]
        cached_rate, warning = self._get_rate_by_id(rate_id)

        warnings = []
        if warning and not cached_rate:
            # Rate not found at all - this is an error
            return warning

        if warning and cached_rate:
            # Rate found but with a warning (e.g., stale)
            warnings.append(warning)

        # Check if destination/weight changed since rates were fetched
        if cached_rate:
            cache_key = self._rate_id_to_cache_key.get(rate_id)
            if cache_key:
                cached = self.rate_cache.get(cache_key)
                if cached:
                    if cached.destination_zip != params["to_zip"]:
                        warnings.append(
                            f"Warning: Destination ZIP changed from {cached.destination_zip} "
                            f"to {params['to_zip']} since rates were fetched."
                        )
                    if abs(cached.weight_oz - params["weight_oz"]) > 0.1:
                        warnings.append(
                            f"Warning: Package weight changed from {cached.weight_oz}oz "
                            f"to {params['weight_oz']}oz since rates were fetched."
                        )

        try:
            shipment = self.client.create_shipment(
                to_address=to_address,
                parcel=parcel,
                rate_id=rate_id,
            )

            # Save to database if available
            order_id = params.get("order_id")
            if self.shipment_repo and self.context and self.context.customer_id:
                # Parse order_id if it's a string UUID
                db_order_id = None
                if order_id:
                    try:
                        db_order_id = UUID(order_id) if isinstance(order_id, str) else order_id
                    except ValueError:
                        pass  # Invalid UUID, skip

                db_shipment = self.shipment_repo.create({
                    "customer_id": self.context.customer_id,
                    "order_id": db_order_id,
                    "easypost_shipment_id": shipment.id,
                    "carrier": shipment.carrier,
                    "service": shipment.service,
                    "tracking_number": shipment.tracking_number,
                    "label_url": shipment.label_url,
                    "rate_amount": shipment.rate,
                    "status": "created",
                })

                # Update order status if linked
                if db_order_id and self.order_repo:
                    self.order_repo.update_status(db_order_id, "shipped")

                # Increment label count
                if self.customer_repo:
                    self.customer_repo.increment_label_count(self.context.customer_id)
                    self.context.labels_used += 1

            result_lines = [
                "Shipment created successfully!",
                f"Tracking Number: {shipment.tracking_number}",
                f"Carrier: {shipment.carrier} {shipment.service}",
                f"Cost: ${shipment.rate:.2f}",
                f"Label URL: {shipment.label_url}",
            ]

            if warnings:
                result_lines.append("")
                result_lines.extend(warnings)

            return "\n".join(result_lines)
        except Exception as e:
            return f"Error creating shipment: {e}"

    def _get_tracking_status(self, params: dict) -> str:
        """Get tracking status for a shipment."""
        tracking_number = params.get("tracking_number")
        order_id = params.get("order_id")

        if not tracking_number and not order_id:
            return "Error: Please provide either tracking_number or order_id"

        carrier = None

        # Try database lookup first
        if self.shipment_repo:
            db_shipment = None

            if order_id and not tracking_number:
                # Try to parse as UUID
                try:
                    order_uuid = UUID(order_id) if isinstance(order_id, str) else order_id
                    db_shipment = self.shipment_repo.get_by_order_id(order_uuid)
                except ValueError:
                    pass  # Not a valid UUID, will fall back

            elif tracking_number:
                db_shipment = self.shipment_repo.get_by_tracking_number(tracking_number)

            if db_shipment:
                tracking_number = db_shipment.tracking_number
                carrier = db_shipment.carrier

        # Fallback to mock shipments if no database result
        if not tracking_number and order_id:
            shipment = MOCK_SHIPMENTS.get(order_id)
            if not shipment:
                return f"No shipment found for order {order_id}. The order may not have been shipped yet."
            tracking_number = shipment.get("tracking_number")
            carrier = shipment.get("carrier", "USPS")

        # Infer carrier from tracking number format if not known
        if not carrier:
            if tracking_number.startswith("1Z"):
                carrier = "UPS"
            elif tracking_number.startswith("94"):
                carrier = "USPS"
            elif tracking_number.startswith("78"):
                carrier = "FedEx"
            else:
                carrier = "USPS"

        try:
            tracking = self.client.get_tracking(tracking_number, carrier)

            lines = [
                f"Tracking: {tracking_number}",
                f"Status: {tracking.get('status', 'unknown').replace('_', ' ').title()}",
            ]

            if tracking.get("estimated_delivery"):
                lines.append(f"Estimated Delivery: {tracking['estimated_delivery']}")

            events = tracking.get("events", [])
            if events:
                lines.append("")
                lines.append("Recent Events:")
                for event in events[:5]:  # Show up to 5 events
                    event_time = event.get("datetime", "")
                    if event_time:
                        # Parse and format datetime
                        try:
                            dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                            event_time = dt.strftime("%b %d, %I:%M %p")
                        except ValueError:
                            pass
                    location = event.get("location", "")
                    message = event.get("message", event.get("status", ""))
                    lines.append(f"  - {event_time}: {message}")
                    if location:
                        lines.append(f"    Location: {location}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error getting tracking info: {e}"

    def _get_unfulfilled_orders(self, params: dict) -> str:
        """Get list of unfulfilled orders."""
        limit = params.get("limit", 20)
        search = params.get("search", "").lower() if params.get("search") else None

        # Use database if available and customer context has an ID
        if self.order_repo and self.context and self.context.customer_id:
            db_orders = self.order_repo.list_unfulfilled(
                customer_id=self.context.customer_id,
                limit=limit,
                search=search,
            )

            if not db_orders:
                if search:
                    return f"No unfulfilled orders found matching '{search}'."
                return "No unfulfilled orders found."

            lines = [f"Unfulfilled Orders ({len(db_orders)} total):"]
            lines.append("")

            for order in db_orders:
                addr = order.shipping_address or {}
                weight_lbs = (order.weight_oz or 0) / 16
                item_count = len(order.line_items) if order.line_items else 0
                lines.append(
                    f"{order.order_number} - {order.recipient_name}"
                )
                lines.append(
                    f"  {addr.get('city', '')}, {addr.get('state', '')} {addr.get('zip', '')} | "
                    f"{item_count} item(s) | {weight_lbs:.1f} lbs"
                )
                # Include order ID for reference in other tools
                lines.append(f"  [order_id: {order.id}]")

            return "\n".join(lines)

        # Fallback to mock data if no database
        orders = MOCK_ORDERS
        if search:
            orders = [
                o for o in orders
                if search in o["order_number"].lower()
                or search in o["recipient"].lower()
                or search in o["destination"]["city"].lower()
                or search in o["destination"]["state"].lower()
            ]

        # Apply limit
        orders = orders[:limit]

        if not orders:
            if search:
                return f"No unfulfilled orders found matching '{search}'."
            return "No unfulfilled orders found."

        lines = [f"Unfulfilled Orders ({len(orders)} total):"]
        lines.append("")

        for order in orders:
            dest = order["destination"]
            weight_lbs = order["weight_oz"] / 16
            lines.append(
                f"{order['order_number']} - {order['recipient']}"
            )
            lines.append(
                f"  {dest['city']}, {dest['state']} {dest['zip']} | "
                f"{order['item_count']} item(s) | {weight_lbs:.1f} lbs"
            )

        return "\n".join(lines)

    def _bulk_ship_orders(self, params: dict) -> str:
        """Ship multiple orders at once."""
        order_ids = params.get("order_ids", [])
        filter_params = params.get("filter", {})
        carrier = params.get("carrier")
        service = params.get("service")
        use_cheapest = params.get("cheapest", False)
        confirmed = params.get("confirmed", False)

        # Normalize order data structure for both DB and mock
        orders = []
        use_db = self.order_repo and self.context and self.context.customer_id

        if use_db:
            # Get orders from database
            if order_ids:
                # Parse UUIDs
                uuids = []
                for oid in order_ids:
                    try:
                        uuids.append(UUID(oid) if isinstance(oid, str) else oid)
                    except ValueError:
                        continue
                db_orders = self.order_repo.get_by_ids(uuids) if uuids else []
            else:
                db_orders = self.order_repo.list_unfulfilled(
                    customer_id=self.context.customer_id,
                    limit=100,
                )

            # Apply filters and normalize to common format
            for db_order in db_orders:
                addr = db_order.shipping_address or {}
                order_data = {
                    "id": db_order.id,
                    "order_id": str(db_order.id),
                    "order_number": db_order.order_number,
                    "recipient": db_order.recipient_name,
                    "destination": {
                        "street1": addr.get("street1", ""),
                        "city": addr.get("city", ""),
                        "state": addr.get("state", ""),
                        "zip": addr.get("zip", ""),
                    },
                    "weight_oz": db_order.weight_oz or 16,
                    "created_at": db_order.created_at.strftime("%Y-%m-%d") if db_order.created_at else "",
                    "is_db": True,
                }

                # Apply filters
                if filter_params:
                    max_weight = filter_params.get("max_weight_oz")
                    dest_state = filter_params.get("destination_state", "").upper()
                    created_after = filter_params.get("created_after")

                    if max_weight is not None and order_data["weight_oz"] > max_weight:
                        continue
                    if dest_state and order_data["destination"]["state"].upper() != dest_state:
                        continue
                    if created_after and order_data["created_at"] < created_after:
                        continue

                orders.append(order_data)
        else:
            # Get orders from mock data
            if order_ids:
                orders = [o for o in MOCK_ORDERS if o["order_id"] in order_ids]
            else:
                orders = list(MOCK_ORDERS)

            # Apply filters
            if filter_params:
                max_weight = filter_params.get("max_weight_oz")
                dest_state = filter_params.get("destination_state", "").upper()
                created_after = filter_params.get("created_after")

                if max_weight is not None:
                    orders = [o for o in orders if o["weight_oz"] <= max_weight]
                if dest_state:
                    orders = [o for o in orders if o["destination"]["state"].upper() == dest_state]
                if created_after:
                    orders = [o for o in orders if o["created_at"] >= created_after]

        if not orders:
            return "No orders match the specified criteria."

        # Calculate estimated costs
        total_cost = 0.0
        order_summaries = []

        for order in orders:
            # Get rates for this order
            dest = order["destination"]
            to_address = Address(
                name=order["recipient"],
                street1=dest.get("street1") or "123 Customer St",
                city=dest["city"],
                state=dest["state"],
                zip_code=dest["zip"],
            )
            parcel = Parcel(
                length=6, width=4, height=2,
                weight=order["weight_oz"],
            )

            try:
                rates = self.client.get_rates(to_address, parcel)
                if not rates:
                    order_summaries.append({
                        "order": order,
                        "error": "No rates available",
                    })
                    continue

                # Select rate based on criteria
                selected_rate = None
                if use_cheapest:
                    selected_rate = rates[0]  # Already sorted by price
                elif carrier and service:
                    for r in rates:
                        if r.carrier.upper() == carrier.upper() and service.lower() in r.service.lower():
                            selected_rate = r
                            break
                elif carrier:
                    for r in rates:
                        if r.carrier.upper() == carrier.upper():
                            selected_rate = r
                            break

                if not selected_rate:
                    selected_rate = rates[0]  # Fallback to cheapest

                order_summaries.append({
                    "order": order,
                    "rate": selected_rate,
                })
                total_cost += selected_rate.rate

            except Exception as e:
                order_summaries.append({
                    "order": order,
                    "error": str(e),
                })

        valid_orders = [s for s in order_summaries if "rate" in s]
        error_orders = [s for s in order_summaries if "error" in s]

        # If not confirmed, return preview
        if not confirmed:
            lines = ["Bulk Shipping Preview:"]
            lines.append(f"Orders to ship: {len(valid_orders)}")
            lines.append(f"Estimated total cost: ${total_cost:.2f}")
            lines.append("")

            if carrier or use_cheapest:
                method = f"{carrier} {service}" if carrier else "Cheapest available"
                lines.append(f"Shipping method: {method}")
                lines.append("")

            lines.append("Orders:")
            for summary in valid_orders[:10]:  # Show first 10
                order = summary["order"]
                rate = summary["rate"]
                lines.append(
                    f"  {order['order_number']}: {order['recipient']} -> "
                    f"{order['destination']['state']} | ${rate.rate:.2f} ({rate.carrier})"
                )

            if len(valid_orders) > 10:
                lines.append(f"  ... and {len(valid_orders) - 10} more orders")

            if error_orders:
                lines.append("")
                lines.append(f"Errors ({len(error_orders)} orders):")
                for summary in error_orders:
                    order = summary["order"]
                    lines.append(f"  {order['order_number']}: {summary['error']}")

            lines.append("")
            lines.append("To proceed, call bulk_ship_orders again with confirmed=true")

            return "\n".join(lines)

        # Execute shipping
        results = []
        labels_created = 0
        for summary in valid_orders:
            order = summary["order"]
            rate = summary["rate"]
            dest = order["destination"]

            to_address = Address(
                name=order["recipient"],
                street1=dest.get("street1") or "123 Customer St",
                city=dest["city"],
                state=dest["state"],
                zip_code=dest["zip"],
            )
            parcel = Parcel(
                length=6, width=4, height=2,
                weight=order["weight_oz"],
            )

            try:
                shipment = self.client.create_shipment(to_address, parcel, rate.rate_id)

                # Save to database if available
                if order.get("is_db") and self.shipment_repo and self.context:
                    db_shipment = self.shipment_repo.create({
                        "customer_id": self.context.customer_id,
                        "order_id": order["id"],
                        "easypost_shipment_id": shipment.id,
                        "carrier": shipment.carrier,
                        "service": shipment.service,
                        "tracking_number": shipment.tracking_number,
                        "label_url": shipment.label_url,
                        "rate_amount": shipment.rate,
                        "status": "created",
                    })

                    # Update order status
                    if self.order_repo:
                        self.order_repo.update_status(order["id"], "shipped")

                    labels_created += 1
                else:
                    # Store in mock shipments for tracking lookup
                    MOCK_SHIPMENTS[order["order_id"]] = {
                        "tracking_number": shipment.tracking_number,
                        "carrier": shipment.carrier,
                        "rate": shipment.rate,
                    }

                results.append({
                    "order": order,
                    "shipment": shipment,
                })
            except Exception as e:
                results.append({
                    "order": order,
                    "error": str(e),
                })

        # Update customer label count in bulk
        if labels_created > 0 and self.customer_repo and self.context and self.context.customer_id:
            self.customer_repo.increment_label_count(self.context.customer_id, labels_created)
            self.context.labels_used += labels_created

        successful = [r for r in results if "shipment" in r]
        failed = [r for r in results if "error" in r]
        actual_cost = sum(r["shipment"].rate for r in successful)

        lines = ["Bulk Shipping Complete!"]
        lines.append("")
        lines.append(f"Successfully shipped: {len(successful)} orders")
        lines.append(f"Total cost: ${actual_cost:.2f}")

        if failed:
            lines.append(f"Failed: {len(failed)} orders")

        lines.append("")
        lines.append("Tracking Numbers:")
        for result in successful:
            order = result["order"]
            shipment = result["shipment"]
            lines.append(
                f"  {order['order_number']}: {shipment.tracking_number} ({shipment.carrier})"
            )

        if failed:
            lines.append("")
            lines.append("Failed Orders:")
            for result in failed:
                order = result["order"]
                lines.append(f"  {order['order_number']}: {result['error']}")

        return "\n".join(lines)
