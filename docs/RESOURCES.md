# Resources and API Links

## Carrier APIs

### EasyPost (Recommended Aggregator)
- **Docs**: https://www.easypost.com/docs/api
- **Dashboard**: https://www.easypost.com/account
- **Pricing**: $0.05/label, free sandbox
- **Carriers**: 100+ including UPS, FedEx, USPS, DHL

### Direct Carrier APIs (Future)
| Carrier | Docs | Notes |
|---------|------|-------|
| UPS | https://developer.ups.com | OAuth 2.0, REST |
| FedEx | https://developer.fedex.com | REST, good docs |
| USPS | https://www.usps.com/business/web-tools-apis | XML legacy, REST beta |
| DHL | https://developer.dhl.com | Multiple APIs by service |

---

## E-commerce

### Shopify
- **Partner Dashboard**: https://partners.shopify.com
- **API Docs**: https://shopify.dev/docs/api
- **App Bridge**: https://shopify.dev/docs/api/app-bridge
- **Webhooks**: https://shopify.dev/docs/api/admin-rest/webhooks

Key APIs:
- Orders API - sync unfulfilled orders
- Fulfillment API - mark orders shipped
- OAuth - store authentication

---

## AI/LLM

### Claude API
- **Docs**: https://docs.anthropic.com
- **Console**: https://console.anthropic.com
- **Pricing**: Sonnet 4 - $3/1M input, $15/1M output

Key features:
- Tool calling for agent actions
- Streaming for real-time responses
- 200K context window

### Claude Agent SDK
- For production agent workflows
- Built-in tool orchestration
- Memory management

---

## Infrastructure

### Supabase (Database + Auth)
- **Docs**: https://supabase.com/docs
- **Dashboard**: https://app.supabase.com
- **Free tier**: 500MB database, 50K monthly active users

### Railway (Hosting)
- **Docs**: https://docs.railway.app
- **Dashboard**: https://railway.app
- **Free tier**: $5 credit

### Render (Alternative Hosting)
- **Docs**: https://render.com/docs
- **Dashboard**: https://dashboard.render.com
- **Free tier**: 750 hours/month

---

## Billing

### Stripe
- **Docs**: https://stripe.com/docs
- **Dashboard**: https://dashboard.stripe.com
- **Billing Portal**: https://stripe.com/docs/billing/subscriptions/customer-portal

Key features:
- Subscriptions for tiers
- Usage-based billing (metered)
- Customer portal for self-service

---

## Development Tools

### Python Libraries
```
fastapi           # Web framework
uvicorn           # ASGI server
httpx             # Async HTTP client
easypost          # EasyPost SDK
shopifyapi        # Shopify SDK
stripe            # Stripe SDK
anthropic         # Claude SDK
supabase          # Supabase client
pydantic          # Data validation
python-dotenv     # Environment variables
```

### Frontend
```
react             # UI framework
@shopify/app-bridge-react  # Shopify embedded app
@shopify/polaris  # Shopify design system
```

---

## Useful References

### Shipping
- USPS Zone Chart: https://postcalc.usps.com/
- Dimensional weight calculator
- Carrier transit time maps

### Shopify App Development
- App review guidelines: https://shopify.dev/docs/apps/launch/app-requirements
- Embedded app best practices
- Polaris design system: https://polaris.shopify.com

### AI Agents
- Anthropic tool use guide: https://docs.anthropic.com/claude/docs/tool-use
- Agent design patterns
- Prompt engineering best practices
