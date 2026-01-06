# Agent Tools Specification

The shipping agent uses Claude's tool-calling to execute shipping operations. Each tool is a function the agent can invoke.

## Tool Definitions

### get_unfulfilled_orders

Get list of orders that need to be shipped.

```json
{
    "name": "get_unfulfilled_orders",
    "description": "Get list of orders that need to be shipped. Returns order number, recipient name, destination city/state, item count, and total weight.",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of orders to return",
                "default": 20
            },
            "search": {
                "type": "string",
                "description": "Search by order number, customer name, or address"
            }
        },
        "required": []
    }
}
```

**Example usage**:
- "Show me orders that need to ship"
- "Find the Johnson order"
- "List orders going to California"

---

### get_shipping_rates

Get rates from all available carriers for a shipment.

```json
{
    "name": "get_shipping_rates",
    "description": "Get shipping rates from all carriers for an order. Returns carrier, service, price, and estimated delivery for each option.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The order ID to get rates for"
            },
            "service_level": {
                "type": "string",
                "enum": ["ground", "express", "overnight", "all"],
                "description": "Filter by service level",
                "default": "all"
            }
        },
        "required": ["order_id"]
    }
}
```

**Example usage**:
- "What are the rates for order 1234?"
- "Show me overnight options for the Smith order"
- "Cheapest way to ship order 5678?"

---

### validate_address

Validate and correct a shipping address.

```json
{
    "name": "validate_address",
    "description": "Validate a shipping address and return corrected version if needed. Identifies issues like missing apartment numbers, incorrect zip codes, etc.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Validate the shipping address for this order"
            },
            "address": {
                "type": "object",
                "description": "Address to validate (if not using order_id)",
                "properties": {
                    "street1": {"type": "string"},
                    "street2": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip": {"type": "string"},
                    "country": {"type": "string", "default": "US"}
                }
            }
        },
        "required": []
    }
}
```

**Example usage**:
- "Is the address on order 1234 valid?"
- "Check the shipping address for the recent orders"

---

### create_shipment

Purchase a label and create a shipment.

```json
{
    "name": "create_shipment",
    "description": "Purchase a shipping label and create the shipment. Returns tracking number and label URL.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The order to ship"
            },
            "rate_id": {
                "type": "string",
                "description": "The rate ID from get_shipping_rates to use"
            },
            "carrier": {
                "type": "string",
                "description": "Carrier name (if not using rate_id)"
            },
            "service": {
                "type": "string",
                "description": "Service level (if not using rate_id)"
            }
        },
        "required": ["order_id"]
    }
}
```

**Example usage**:
- "Ship order 1234 with the cheapest option"
- "Ship order 5678 via UPS Ground"
- "Use FedEx overnight for the Johnson order"

---

### get_tracking_status

Get current tracking status for a shipment.

```json
{
    "name": "get_tracking_status",
    "description": "Get the current tracking status and history for a shipment.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tracking_number": {
                "type": "string",
                "description": "The tracking number to look up"
            },
            "order_id": {
                "type": "string",
                "description": "Get tracking for this order's shipment"
            }
        },
        "required": []
    }
}
```

**Example usage**:
- "Where is order 1234?"
- "Track 1Z999AA10123456784"
- "What's the status of the Smith shipment?"

---

### bulk_ship_orders

Ship multiple orders with specified criteria.

```json
{
    "name": "bulk_ship_orders",
    "description": "Ship multiple orders at once using specified carrier and service. Returns list of created shipments with tracking numbers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of order IDs to ship"
            },
            "filter": {
                "type": "object",
                "description": "Filter orders instead of specifying IDs",
                "properties": {
                    "max_weight_oz": {"type": "number"},
                    "destination_state": {"type": "string"},
                    "created_after": {"type": "string", "format": "date"}
                }
            },
            "carrier": {
                "type": "string",
                "description": "Carrier to use for all shipments"
            },
            "service": {
                "type": "string",
                "description": "Service level to use"
            },
            "cheapest": {
                "type": "boolean",
                "description": "Use cheapest available option for each order",
                "default": false
            }
        },
        "required": []
    }
}
```

**Example usage**:
- "Ship all orders under 1lb via USPS First Class"
- "Ship everything going to California with UPS Ground"
- "Ship all pending orders with the cheapest option"

---

## Agent System Prompt

```
You are a shipping assistant for {store_name}. You help the merchant manage their shipping operations through natural conversation.

You have access to tools for:
- Viewing unfulfilled orders
- Getting shipping rates from multiple carriers
- Validating addresses
- Creating shipments and labels
- Tracking packages
- Bulk shipping operations

Guidelines:
- Always confirm before purchasing labels (spending money)
- Proactively validate addresses before shipping
- When showing rates, highlight the best value option
- For bulk operations, summarize what will happen and confirm
- If an address has issues, explain and suggest corrections

Current context:
- Store: {store_name}
- Plan: {plan_tier}
- Labels this month: {labels_used}/{labels_limit}
```

---

## Example Conversations

### Simple rate check
```
User: What's the cheapest way to ship order 1234?

Agent: [calls get_shipping_rates(order_id="1234")]

Let me check the rates for order #1234 going to Austin, TX.

Here are your options:
- USPS Ground Advantage: $8.50 (5-7 days)
- UPS Ground: $12.30 (4-5 days)
- FedEx Ground: $11.85 (4-5 days)

USPS Ground Advantage is cheapest at $8.50. Want me to ship it?
```

### Bulk shipping
```
User: Ship all orders under 1lb with USPS

Agent: [calls get_unfulfilled_orders()]
       [filters for weight < 16oz]

I found 12 orders under 1lb. Using USPS Ground Advantage, the total cost would be approximately $95.40.

Should I proceed with shipping all 12 orders?

User: Yes

Agent: [calls bulk_ship_orders with cheapest USPS option]

Done! I've created 12 shipments:
- 12 labels generated
- Total cost: $94.20
- All tracking numbers sent to customers

Here's the summary... [shows tracking numbers]
```

### Address issue
```
User: Ship order 5678 overnight

Agent: [calls validate_address(order_id="5678")]

I found an issue with the shipping address for order #5678:

The address "123 Main St, Apt, New York, NY 10001" appears incomplete - there's no apartment number specified.

Would you like me to:
1. Ship anyway (may be returned)
2. Update the address first

User: The apartment is 4B

Agent: [updates address, calls get_shipping_rates]

Updated. Here are overnight options:
- FedEx Priority Overnight: $45.20 (by 10:30am tomorrow)
- UPS Next Day Air: $48.50 (by 10:30am tomorrow)

Which would you like?
```
