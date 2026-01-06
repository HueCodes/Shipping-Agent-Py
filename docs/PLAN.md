# Project Plan

## Context

- **Profile**: Solo founder, backend-focused, high execution capability
- **Validation**: Build first, validate in market
- **Goal**: Profitable business
- **Platform**: Shopify first
- **Geography**: US-only for MVP

## Strategic Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validation | Build first | Fast execution; real product gets real feedback |
| Carriers | EasyPost (aggregator) | AI is differentiator, not carrier plumbing |
| AI in MVP | Yes | Natural language interface is the moat |
| Platform | Shopify embedded | Clear distribution, better UX |
| Carrier accounts | Master account | Simpler; add BYOA later for enterprise |

---

## Development Phases

### Phase 1: Foundation (Weeks 1-2)

**Week 1: Core Infrastructure**
- Set up repo, CI/CD, dev environment
- PostgreSQL schema (customers, orders, shipments)
- EasyPost integration (rates, labels, tracking)
- Basic FastAPI endpoints

**Week 2: Shopify Integration**
- Shopify app scaffolding
- OAuth flow implementation
- Order sync (webhooks + polling)
- Fulfillment write-back

### Phase 2: Agent Core (Weeks 3-4)

**Week 3: AI Agent**
- Claude API integration
- Tool definitions for shipping operations
- Agent loop with conversation memory
- Error handling and retries

**Week 4: Agent Polish**
- Context loading (customer prefs, order history)
- Multi-turn conversations
- Bulk operations support
- Edge case handling

### Phase 3: Product (Weeks 5-6)

**Week 5: Frontend + UX**
- Shopify embedded app UI
- Chat interface for agent
- Order list with quick actions
- Label preview and download

**Week 6: Business Logic**
- Stripe billing integration
- Usage metering
- Subscription tiers
- Onboarding flow

### Phase 4: Launch Prep (Weeks 7-8)

**Week 7: Hardening**
- Error handling and monitoring
- Rate limiting
- Security review
- Load testing

**Week 8: Launch**
- Shopify App Store submission
- Documentation
- Support workflows
- First customers

---

## MVP Features

### Include

- [ ] Shopify OAuth + store connection
- [ ] Order import from Shopify
- [ ] AI agent with natural language interface
- [ ] Rate comparison (EasyPost - multiple carriers)
- [ ] Label purchase and generation
- [ ] Address validation
- [ ] Basic tracking status
- [ ] Stripe subscription billing

### Exclude (Phase 2+)

- Branded tracking pages
- Customer notification emails/SMS
- Analytics dashboard
- Carrier performance scoring
- Exception handling automation
- Returns processing
- Multiple e-commerce platforms

---

## Pricing Model

| Tier | Labels/Month | Features | Price |
|------|--------------|----------|-------|
| Free | 25 | 3 carriers, basic chat | $0 |
| Starter | 250 | All carriers, bulk ops | $49/mo |
| Growth | 2,500 | Priority support, analytics | $149/mo |
| Scale | Unlimited | Custom, dedicated support | $499/mo |

---

## Success Metrics

**Week 8 (Launch)**:
- 5 stores connected
- 100 labels generated
- 1 paying customer

**Month 3**:
- 50 stores connected
- 1000 labels/month
- $1K MRR
- Shopify App Store listed

**Month 6**:
- 200 stores
- 10K labels/month
- $10K MRR
- 90%+ retention

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Build wrong thing | High | Ship fast, get real users, iterate |
| EasyPost dependency | Medium | Abstract behind adapter; direct APIs at scale |
| LLM hallucinations | Medium | Structured outputs, validation before actions |
| Shopify app rejection | Medium | Follow guidelines, start review early |
| Carrier API failures | Low | Retry logic, fallback carriers |

---

## LLM Cost Estimate

- Claude Sonnet 4: ~$3/1M input, ~$15/1M output tokens
- Per shipping operation: ~$0.01-0.02
- At 1000 labels/month: ~$10-20 LLM cost

Sustainable even at Starter tier ($49/mo).
