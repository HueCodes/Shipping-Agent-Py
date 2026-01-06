# Architecture

## System Overview

```
+-------------------------------------------------------------+
|                    SHOPIFY EMBEDDED APP                      |
|                  (React + App Bridge)                        |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                      API LAYER                               |
|                    (FastAPI)                                 |
|  +-----------+  +-----------+  +-------------------+        |
|  | Orders API|  |Shipping API|  | Agent/Chat API   |        |
|  +-----------+  +-----------+  +-------------------+        |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                   AGENT LAYER                                |
|  +------------------------------------------------------+   |
|  |              Claude-powered Shipping Agent            |   |
|  |  Tools: get_rates, create_label, track_package,      |   |
|  |         validate_address, get_order_details          |   |
|  +------------------------------------------------------+   |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                 INTEGRATION LAYER                            |
|  +------------+  +------------+  +------------+             |
|  |  EasyPost  |  |  Shopify   |  |  Stripe    |             |
|  | (carriers) |  |  (orders)  |  | (billing)  |             |
|  +------------+  +------------+  +------------+             |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                    DATA LAYER                                |
|  +------------------------------------------------------+   |
|  |  PostgreSQL (Supabase) - orders, shipments, convos   |   |
|  +------------------------------------------------------+   |
+-------------------------------------------------------------+
```

## Component Details

### API Layer (FastAPI)

**Orders API**
- `GET /orders` - List unfulfilled orders
- `GET /orders/{id}` - Get order details
- `POST /orders/{id}/fulfill` - Mark order as shipped

**Shipping API**
- `POST /rates` - Get shipping rates
- `POST /shipments` - Create shipment and label
- `GET /shipments/{id}/tracking` - Get tracking status
- `POST /addresses/validate` - Validate address

**Agent API**
- `POST /chat` - Send message to agent
- `GET /chat/history` - Get conversation history
- `WebSocket /chat/stream` - Streaming responses

### Agent Layer

The agent uses Claude's tool-calling capability to orchestrate shipping operations.

**Agent Loop**:
1. Receive user message
2. Load customer context (store, preferences, history)
3. Call Claude with tools and context
4. Execute tool calls (rates, labels, etc.)
5. Return results to Claude for synthesis
6. Stream response to user

**Memory**:
- Conversation history per customer
- Stored in PostgreSQL
- Loaded on each request for context

### Integration Layer

**EasyPost** (Carrier Aggregator)
- Rate shopping across carriers
- Label generation
- Address validation
- Tracking webhooks

**Shopify** (E-commerce)
- OAuth authentication
- Order sync (webhooks + polling)
- Fulfillment write-back
- App Bridge for embedded UI

**Stripe** (Billing)
- Subscription management
- Usage-based billing
- Customer portal

### Data Layer

**PostgreSQL via Supabase**
- Managed hosting
- Row-level security for multi-tenancy
- Real-time subscriptions (optional)

---

## Data Models

### Core Tables

```sql
-- Customers (Shopify stores)
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shopify_shop_domain TEXT UNIQUE NOT NULL,
    shopify_access_token TEXT NOT NULL,
    email TEXT,
    plan_tier TEXT DEFAULT 'free',
    labels_this_month INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Orders (synced from Shopify)
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    shopify_order_id TEXT NOT NULL,
    order_number TEXT,
    status TEXT DEFAULT 'unfulfilled',
    shipping_address JSONB,
    line_items JSONB,
    total_weight_grams INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(customer_id, shopify_order_id)
);

-- Shipments
CREATE TABLE shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    order_id UUID REFERENCES orders(id),
    easypost_shipment_id TEXT,
    carrier TEXT NOT NULL,
    service TEXT NOT NULL,
    tracking_number TEXT,
    label_url TEXT,
    rate_cents INT,
    status TEXT DEFAULT 'created',
    estimated_delivery TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations (agent chat history)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    messages JSONB[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tracking Events
CREATE TABLE tracking_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id),
    status TEXT NOT NULL,
    description TEXT,
    location JSONB,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Security

### Authentication
- Shopify OAuth for store owners
- Session tokens for embedded app
- API keys for programmatic access (future)

### Authorization
- Row-level security in Supabase
- Customer can only access their own data
- All queries scoped by customer_id

### Data Protection
- Shopify access tokens encrypted at rest
- No PII stored beyond shipping addresses
- Carrier credentials in environment variables

---

## Scalability Notes

**MVP (0-1000 labels/month)**
- Single Supabase instance
- Single Railway/Render deployment
- Synchronous agent responses

**Growth (1000-10000 labels/month)**
- Add Redis for caching rates
- Background job queue for webhooks
- Consider streaming responses

**Scale (10000+ labels/month)**
- Dedicated PostgreSQL
- Multiple API instances
- Direct carrier integrations for margin
