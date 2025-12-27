# Business Requirements - Phase 2 Decisions

**Date:** 2025-12-27
**Status:** ✅ Approved
**Phase:** Inventory Query System & Sales Engine

---

## Critical Business Decisions

### 1. Lead Age Calculation ✅ DECIDED

**Decision:** Lead age is calculated based on "Call In Date" from the CSV.

**Rationale:**
- "Call In Date" represents when the lead initially expressed interest
- This is the most relevant timestamp for determining lead freshness
- Aligns with the `created_at_utc` field in the domain model

**Implementation:**
```python
# domain/lead.py
created_at_utc: datetime  # Parsed from "Call In Date" CSV column

# Age calculation
age_days = (as_of_utc - lead.created_at_utc).days
```

**Alternative Considered:**
- Using "Sale Date" (mortgage origination) - Rejected because this represents loan closing date, not lead freshness

---

### 2. Pricing Strategy ✅ DECIDED

**Decision:** Implement flexible pricing with the `pricing_rules` table.

**Pricing Structure:**
- **Gold leads are more expensive** than Silver leads
- **Newer leads are more expensive** than older leads
- Pricing decreases as leads age

**Example Pricing (see `database/seed_pricing.sql` for full details):**

| Classification | Age Bucket | Price |
|---------------|------------|-------|
| Gold | MONTH_3_TO_5 | $150.00 |
| Gold | MONTH_6_TO_8 | $120.00 |
| Gold | MONTH_9_TO_11 | $90.00 |
| Gold | MONTH_12_TO_23 | $60.00 |
| Gold | MONTH_24_PLUS | $30.00 |
| Silver | MONTH_3_TO_5 | $75.00 |
| Silver | MONTH_6_TO_8 | $60.00 |
| Silver | MONTH_9_TO_11 | $45.00 |
| Silver | MONTH_12_TO_23 | $30.00 |
| Silver | MONTH_24_PLUS | $15.00 |

**Pricing Management:**
- Prices stored in `pricing_rules` table
- Historical pricing tracked with `effective_from` and `effective_to` dates
- Active pricing has `effective_to = NULL`
- Admin can update pricing without code changes

**Implementation:**
```sql
-- Query current price for a lead
SELECT base_price
FROM pricing_rules
WHERE classification = 'Gold'
  AND age_bucket = 'MONTH_3_TO_5'
  AND effective_to IS NULL  -- Active pricing
LIMIT 1;
```

---

### 3. Authentication Strategy ✅ DECIDED

**Decision:** Implement full JWT + OAuth2 authentication.

**Supported Authentication Methods:**
1. **OAuth2 Providers:**
   - Google
   - Microsoft
   - GitHub

2. **Local Authentication:**
   - Email + Password (bcrypt hashed)
   - Email verification required
   - Password reset flow

**JWT Token Management:**
- Access tokens: Short-lived (15 minutes)
- Refresh tokens: Long-lived (7 days), stored hashed in database
- Token rotation on refresh

**Client Account Fields:**
```sql
-- clients table
- auth_provider: 'local' | 'google' | 'microsoft' | 'github'
- auth_provider_user_id: OAuth provider's user ID (sub claim)
- password_hash: bcrypt hash (NULL for OAuth users)
- refresh_token_hash: Hashed refresh token
- email_verified: Email verification status
```

**Security Features:**
- Email verification before account activation
- Password reset tokens with expiration
- Account status management (active/suspended/closed)
- Refresh token rotation prevents replay attacks

**Implementation Notes:**
- Use `PyJWT` for token generation/verification
- Use `passlib + bcrypt` for password hashing
- Use `Authlib` or `python-social-auth` for OAuth2 integration

---

### 4. Inventory Generation Strategy ✅ DECIDED

**Decision:** Eager inventory generation via daily background job.

**Approach:**
- **Daily cron job** scans all leads and generates inventory records
- Creates `inventory` records for leads that have entered new age buckets
- Query performance is critical → pre-generate inventory for fast browsing

**Script:** `scripts/generate_inventory.py`

**Schedule:**
```bash
# Run daily at 1:00 AM UTC
0 1 * * * cd /app && python scripts/generate_inventory.py
```

**Logic:**
1. Query all leads from `leads` table
2. Calculate current age: `(today - created_at_utc).days`
3. Determine eligible age bucket
4. Check if `inventory` record exists for (lead_id, age_bucket)
5. If not exists, create new inventory record with `sold_at_utc = NULL`

**Alternative Considered:**
- Lazy (on-demand) inventory generation - Rejected due to query complexity and potential race conditions

---

## Implementation Summary

### Database Schema
✅ `leads` - Lead records with all CSV columns
✅ `clients` - Buyer accounts with OAuth2/JWT support
✅ `inventory` - Sellable eligibility tracking
✅ `sales` - Immutable sale records
✅ `pricing_rules` - Flexible pricing configuration

### Functions
✅ `execute_sale_atomic()` - Atomic purchase with race condition prevention

### Indexes
✅ Optimized for filtering: state, county, classification, age_bucket
✅ Partial indexes for available inventory (WHERE sold_at_utc IS NULL)
✅ OAuth provider indexes for fast authentication

---

## Next Steps

### Immediate (This Week)
1. ✅ Complete database schema
2. ✅ Document business decisions
3. ⬜ Apply schema to Supabase
4. ⬜ Seed initial pricing data
5. ⬜ Test atomic sale function

### Phase 2 (Week 2)
- Build inventory query repository
- Implement inventory generation script
- Create FastAPI endpoints for browsing

### Phase 3 (Week 3)
- Implement sales service with atomic purchases
- Build client management (registration, OAuth2)
- Create JWT authentication middleware

### Phase 4 (Week 4)
- Complete API layer with all endpoints
- Integrate payment processing (optional)
- Deploy to production

---

## Risk Mitigation

### Race Conditions ✅ MITIGATED
**Solution:** PostgreSQL row-level locking in `execute_sale_atomic()` function

### Pricing Flexibility ✅ ADDRESSED
**Solution:** `pricing_rules` table with historical tracking

### Authentication Security ✅ PLANNED
**Solution:** JWT + OAuth2 with refresh token rotation, email verification, bcrypt password hashing

### Query Performance ✅ OPTIMIZED
**Solution:** Eager inventory generation, optimized indexes, partial indexes for available inventory

---

## Open Questions / Future Considerations

1. **Bulk Purchase Discounts:** Should clients get discounts for buying multiple leads at once?
2. **Payment Integration:** Which payment processor (Stripe, PayPal)?
3. **Invoice Generation:** Should system auto-generate invoices?
4. **Client Tiers:** Premium vs. standard clients with different features?
5. **API Rate Limiting:** Prevent abuse of browsing/purchase endpoints?

---

**Approved By:** Jude
**Technical Review:** backend-architect-dev agent
**Implementation:** In Progress
