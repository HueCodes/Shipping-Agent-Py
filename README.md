# Shipping Agent

AI-powered shipping assistant for Shopify merchants. Natural language interface for rate shopping, label generation, and order fulfillment.

## Features

- Claude-powered conversational interface
- Multi-carrier rate comparison (USPS, UPS, FedEx via EasyPost)
- Address validation and standardization
- Label generation and tracking
- Shopify OAuth integration
- REST API and WebSocket streaming

## Quick Start

```bash
# Install
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run server
uv run ship-server
```

Open http://localhost:8000

## Configuration

Required environment variables:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `EASYPOST_API_KEY` | EasyPost API key (use TEST key for development) |
| `SHOPIFY_API_KEY` | Shopify app API key |
| `SHOPIFY_API_SECRET` | Shopify app secret |
| `SECRET_KEY` | JWT signing key |

See `.env.example` for full configuration options.

## Development

```bash
# Run in mock mode (no API calls)
MOCK_MODE=1 uv run ship-server

# Run tests
MOCK_MODE=1 uv run pytest

# CLI mode
uv run ship
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Send message to agent |
| `/api/chat/stream` | WebSocket | Streaming chat |
| `/api/rates` | POST | Get shipping rates |
| `/api/shipments` | POST | Create shipment |
| `/api/orders` | GET | List orders |
| `/auth/shopify` | GET | Start OAuth flow |

## Project Structure

```
src/
  server.py           # FastAPI server
  cli.py              # CLI entry point
  agent/              # Claude agent and tools
  auth/               # OAuth and JWT
  db/                 # SQLAlchemy models and migrations
  static/             # Web UI
tests/
  integration/        # Integration tests
```

## License

MIT
