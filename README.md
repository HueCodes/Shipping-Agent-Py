# Shipping AI Agent

AI-powered shipping assistant. Natural language interface for rate shopping, address validation, and label generation.

## Status

**Phase 1**: CLI agent (current)

## Quick Start

### 1. Install dependencies

```bash
cd ~/Dev/Shipping-Agent
uv sync
```

### 2. Set up API keys

```bash
cp .env.example .env
# Edit .env with your keys
```

You need:
- **Anthropic API key**: https://console.anthropic.com
- **EasyPost API key**: https://www.easypost.com/account/api-keys (use TEST key)

### 3. Run the agent

```bash
uv run ship
```

Or:

```bash
uv run python -m src.cli
```

## Usage Examples

```
You: Get rates for a 2lb package to Los Angeles, CA 90001

Agent: Here are the available rates for shipping to Los Angeles, CA 90001:

1. USPS Ground Advantage: $8.50 (5-7 days)
2. UPS Ground: $12.30 (4-5 days)
3. FedEx Ground: $11.85 (4-5 days)
...

You: Use the cheapest option

Agent: I'll create a shipment with USPS Ground Advantage for $8.50.
Please confirm the recipient details...
```

## Project Structure

```
src/
  cli.py              # CLI entry point
  easypost_client.py  # EasyPost API wrapper
  agent/
    agent.py          # Claude agent with tool calling
    tools.py          # Tool definitions
docs/
  PLAN.md             # Full project plan
  ARCHITECTURE.md     # System design
  AGENT_TOOLS.md      # Tool specifications
  RESOURCES.md        # API links and references
```

## Roadmap

- [x] CLI agent with rate shopping
- [x] Address validation
- [x] Label generation
- [ ] Web chat interface
- [ ] Shopify integration
- [ ] Tracking aggregation

## Docs

- [Project Plan](./docs/PLAN.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Agent Tools](./docs/AGENT_TOOLS.md)
- [Resources](./docs/RESOURCES.md)
