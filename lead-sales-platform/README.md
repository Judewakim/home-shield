# Lead Sales Platform - Backend

FastAPI backend for HomeShield mortgage protection lead marketplace. Handles inventory management, purchase processing, pricing, and CSV export with security protections.

## Architecture

```
lead-sales-platform/
├── api/                    # REST API layer
│   ├── routers/           # Endpoint definitions
│   │   ├── inventory.py   # Browse & locations
│   │   ├── purchases.py   # Purchase & download
│   │   └── quotes.py      # Price quotes (legacy)
│   └── models.py          # Pydantic request/response models
├── domain/                 # Business logic (ANCHOR-guarded)
│   ├── age_bucket.py      # Age classification enum
│   ├── lead.py            # Lead domain model
│   ├── sale.py            # Sale domain model
│   └── README.md          # Domain rules warning
├── repositories/           # Data access layer
│   ├── client.py          # Supabase client
│   ├── inventory_query_repository.py
│   ├── lead_repository.py
│   ├── pricing_repository.py
│   └── sale_repository.py
├── services/               # Application services
│   ├── csv_export_service.py
│   ├── inventory_allocation_service.py
│   ├── pricing_service.py
│   └── purchase_service.py
├── scripts/                # Utility scripts
│   ├── ingest_csv.py      # CSV data ingestion
│   ├── reset_test_inventory.py
│   └── check_inventory_status.py
├── tests/                  # Test suite
└── docs/                   # Authoritative specs
    ├── ANCHOR.md
    ├── behavior/
    ├── decisions/
    └── specs/
```

## Core Concepts

### Domain Models

**Lead** (`domain/lead.py`)
- Immutable classification (Gold/Silver)
- Contact information
- Mortgage details
- Location data
- Classification determined at CSV ingestion (never changes)

**Age Bucket** (`domain/age_bucket.py`)
- MONTH_3_TO_5
- MONTH_6_TO_8
- MONTH_9_TO_11
- MONTH_12_TO_23
- MONTH_24_PLUS

**Sale** (`domain/sale.py`)
- Links lead to client purchase
- Tracks purchase price and timestamp
- One sale per lead sold

### Services

**Inventory Allocation Service** (`services/inventory_allocation_service.py`)
- Criteria-based lead selection
- Transactional allocation (all-or-nothing)
- Insufficient inventory error handling with alternatives:
  - Partial purchase suggestions
  - Location filter removal suggestions
  - Age bucket alternatives

**Purchase Service** (`services/purchase_service.py`)
- Processes purchases
- Marks inventory as sold
- Creates sale records
- Automatic replacement for stale inventory references

**Pricing Service** (`services/pricing_service.py`)
- Fetches active pricing rules
- Calculates purchase quotes
- Supports time-limited quotes (15 min expiration)

**CSV Export Service** (`services/csv_export_service.py`)
- Generates CSV from sale records
- CSV injection prevention (strips dangerous characters)
- Authorization checks (client-only access)
- Audit logging for all exports

## API Endpoints

### Inventory Management

#### GET `/api/v1/inventory`
Browse available leads with optional filters.

**Query Parameters:**
- `state` (optional): Filter by state (e.g., "LA")
- `classification` (optional): Filter by "Gold" or "Silver"
- `age_bucket` (optional): Filter by age bucket
- `county` (optional): Filter by county
- `limit` (default: 100, max: 1000): Results limit

**Response:**
```json
{
  "items": [
    {
      "inventory_id": "uuid",
      "lead_id": "uuid",
      "age_bucket": "MONTH_6_TO_8",
      "state": "LA",
      "county": "Caddo",
      "classification": "Gold",
      "unit_price": "8.00",
      "first_name": "John",
      "city": "Shreveport"
    }
  ],
  "total": 150
}
```

#### GET `/api/v1/inventory/locations`
Get available states and counties from database.

**Response:**
```json
{
  "states": ["LA"],
  "counties_by_state": {
    "LA": ["Acadia", "Allen", "Ascension", ...]
  }
}
```

### Purchase Processing

#### POST `/api/v1/purchases/by-criteria`
Purchase leads by specifying filter criteria (recommended approach).

**Request:**
```json
{
  "client_id": "uuid",
  "criteria": [
    {
      "classification": "Gold",
      "age_bucket": "MONTH_6_TO_8",
      "quantity": 50,
      "state": "LA",
      "county": "Caddo"  // optional
    }
  ]
}
```

**Success Response (200):**
```json
{
  "success": true,
  "sale_ids": ["uuid1", "uuid2", ...],
  "total_paid": "400.00",
  "items_requested": 50,
  "items_purchased": 50,
  "items_replaced": 0,
  "errors": [],
  "message": "Purchase completed successfully."
}
```

**Insufficient Inventory Response (409):**
```json
{
  "detail": {
    "error": "insufficient_inventory",
    "requested": 50,
    "available": 22,
    "criteria": "Gold MONTH_6_TO_8 state=LA qty=50",
    "item_index": null,
    "is_multi_item": false,
    "alternatives": [
      {
        "description": "Purchase 22 available leads ($176.00)",
        "available_count": 22,
        "suggestion_type": "partial"
      },
      {
        "description": "Remove location filter (324 available without LA filter)",
        "available_count": 324,
        "suggestion_type": "no_location_filter"
      },
      {
        "description": "Try MONTH_9_TO_11 age bucket (156 available in LA)",
        "available_count": 156,
        "suggestion_type": "different_age_bucket"
      }
    ]
  }
}
```

#### GET `/api/v1/purchases/download`
Download CSV export for purchased leads.

**Query Parameters:**
- `sale_ids`: Comma-separated sale UUIDs
- `client_id`: Client UUID for authorization

**Response:** CSV file download

**CSV Fields (33 total):**
- Sale info: purchase_price, purchase_date, age_bucket_at_purchase
- Lead info: All contact and mortgage fields
- Security: CSV injection prevention applied

### Pricing (Legacy)

#### POST `/api/v1/quotes`
Generate price quote for specific inventory IDs.

**Request:**
```json
{
  "inventory_item_ids": ["uuid1", "uuid2"]
}
```

## Database Schema

### Tables

**leads**
- `lead_id` (PK): UUID
- `classification`: Gold | Silver (immutable)
- Contact fields: first_name, last_name, phone, etc.
- Mortgage fields: amount, lender, sale_date
- Location: state, county, city, zip
- `created_at_utc`: Timestamp

**inventory**
- `inventory_id` (PK): UUID
- `lead_id` (FK): References leads
- `age_bucket`: Enum (MONTH_3_TO_5, etc.)
- `sold_at_utc`: NULL = available, NOT NULL = sold
- `created_at_utc`: Timestamp

**sales**
- `sale_id` (PK): UUID
- `lead_id` (FK): References leads
- `inventory_id` (FK): References inventory
- `client_id`: UUID
- `purchase_price`: Decimal
- `age_bucket_at_purchase`: Enum
- `purchased_at_utc`: Timestamp

**pricing**
- `price_id` (PK): UUID
- `classification`: Gold | Silver
- `age_bucket`: Enum
- `price_per_lead`: Decimal
- `effective_from_utc`: Timestamp
- `effective_until_utc`: NULL = active

## Setup & Configuration

### Prerequisites
- Python 3.12+
- Supabase account
- PostgreSQL 15+ (via Supabase)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Create `.env` file:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### Database Initialization

```bash
# Run migrations (if applicable)
# Or manually create tables using Supabase dashboard

# Ingest CSV data
python scripts/ingest_csv.py path/to/leads.csv
```

### Running the Server

```bash
# Development server with auto-reload
python run_api.py

# Production (using uvicorn directly)
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Server runs at: http://localhost:8000

API Documentation: http://localhost:8000/docs

## Development

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_csv_ingestion.py
```

### Utility Scripts

**Reset Test Data**
```bash
python scripts/reset_test_inventory.py
```
Marks all sold inventory as available (dev/testing only).

**Check Inventory Status**
```bash
python scripts/check_inventory_status.py
```
Shows inventory counts by status, classification, and age bucket.

**CSV Ingestion**
```bash
python scripts/ingest_csv.py path/to/leads.csv
```
Ingests leads from CSV with automatic classification and inventory creation.

## Domain Rules (ANCHOR)

⚠️ **All domain logic is governed by authoritative documents:**

- `docs/ANCHOR.md` - Behavioral contract
- `docs/behavior/lead_classification_and_inventory.md`

**Do not modify** logic related to:
- Age buckets
- Lead classification (immutability)
- Inventory eligibility
- Sale constraints

Unless documents are updated first. Deviations are bugs, not features.

## Security

### CSV Injection Prevention
- Strips dangerous prefixes: `=`, `+`, `-`, `@`, `\t`, `\r`
- Logs all stripping events for audit
- Applied to all CSV exports

### Authorization
- Client-only access to purchases (by client_id)
- Sale records verify ownership before CSV export
- Returns 403 if client attempts unauthorized access

### Input Validation
- Pydantic models enforce type safety
- Quantity limits: 1-1000 per criteria
- UUID validation on all IDs
- Enum validation for classifications and age buckets

## Performance Considerations

### Database Queries
- Partial index on `inventory(sold_at_utc IS NULL)` for available inventory
- Inner joins minimize data transfer
- `.limit()` instead of `.range()` for offset=0 (Supabase pagination bug workaround)

### Pagination
- Large result sets use pagination with 1000-item page size
- Efficient counting with `count="exact"`

### Caching
- None currently implemented
- Future: Redis for pricing rules and inventory counts

## API Versioning

Current version: `/api/v1/`

Breaking changes will use new version prefix (e.g., `/api/v2/`).

## Troubleshooting

### Common Issues

**"Insufficient inventory" errors**
- Check actual inventory with: `python scripts/check_inventory_status.py`
- Reset test data if needed: `python scripts/reset_test_inventory.py`

**CSV download returns empty file**
- Verify sale_ids are correct
- Check client_id authorization
- Review backend logs for security errors

**Supabase connection errors**
- Verify SUPABASE_URL and SUPABASE_KEY in `.env`
- Check Supabase project is active
- Verify network connectivity

## Contributing

1. Update authoritative docs first (`docs/`)
2. Implement code changes
3. Add tests
4. Verify domain rules compliance
5. Submit PR with doc references

## License

Proprietary - All rights reserved

---

© 2025 HomeShield. All rights reserved.
