# HabotConnect LSA Service Booking Backend

**Python Backend Developer Hiring Project**

A production-oriented Django REST Framework prototype for connecting parents with Learning Support Assistants (LSAs), searching available LSAs, preventing double bookings, integrating with a mock payment provider, and processing payment webhooks.

## 1. Architecture

The project uses **Django + Django REST Framework** with a relational database. Django's MVT architecture is used because the assessment explicitly asks for Django MVT/Flask MVC awareness; for an API-only backend, the Django models represent the data layer, DRF serializers validate/transform API data, and API views coordinate HTTP behavior.

### Main flow

```text
Client
  |
  +--> POST /api/v1/bookings/
  |       |
  |       +--> validate request
  |       +--> transaction + LSA row lock
  |       +--> overlap check
  |       +--> create PENDING_PAYMENT booking
  |       +--> requests -> mock payment service
  |       +--> CONFIRMED / PAYMENT_FAILED
  |
  +--> GET /api/v1/lsas/search/
          |
          +--> DB-level skill filtering
          +--> overlap exclusion
          +--> prefetch_related(skills)
          +--> JSON response

Payment Provider
  |
  +--> POST /api/v1/payments/webhook/
          |
          +--> lock payment
          +--> update payment + booking state
```

## 2. Database

Entities:

- **Parent** – the customer requesting a session.
- **LSAProfile** – Learning Support Assistant profile and hourly rate.
- **Skill** – normalized skill vocabulary used in the many-to-many LSA relationship.
- **Booking** – requested session, parent, LSA, amount, status and idempotency key.
- **Payment** – one-to-one payment record for a booking.

Indexes are defined for parent email, LSA active status/rate, booking slot lookups, booking status and payment status/transaction ID.

## 3. Double-booking prevention

The booking service uses a database transaction and `select_for_update()` on the selected LSA row. While that row is locked, it checks for an existing active booking whose time interval overlaps the requested interval:

```text
existing.start < requested.end
AND
existing.end > requested.start
```

If an overlap exists, the request is rejected. Locking the LSA row is important because a simple application-level `exists()` check can race when two requests arrive at the same time.

## 4. N+1 query prevention

The LSA search uses database-side filtering and `prefetch_related("skills")`. The serializer then reads the already-prefetched skills instead of performing one SQL query per LSA.

For a search requiring multiple skills, the query uses an annotation/count to ensure an LSA matches all requested skills rather than merely any one skill.

## 5. API specification

### POST `/api/v1/bookings/`

Request:

```json
{
  "parent_id": 1,
  "lsa_id": 2,
  "session_date": "2026-08-12",
  "start_time": "10:00:00",
  "end_time": "11:00:00",
  "idempotency_key": "parent-1-20260812-1000"
}
```

Success: `201 Created`

The server calculates the booking amount from the LSA hourly rate and session duration.

### GET `/api/v1/lsas/search/`

Example:

```text
/api/v1/lsas/search/?skills=Python,Math&session_date=2026-08-12&start_time=10:00:00&end_time=11:00:00
```

The optional date/time parameters allow the API to exclude LSAs with overlapping active bookings.

### POST `/api/v1/payments/webhook/`

Request:

```json
{
  "transaction_id": "MOCK-ABC123",
  "event": "payment.success",
  "message": "settled"
}
```

Events supported:

- `payment.success` -> payment SUCCESS + booking CONFIRMED
- `payment.failed` -> payment FAILED + booking PAYMENT_FAILED

### POST `/api/v1/mock-gateway/charge/`

This is a local mock provider used to demonstrate the third-party integration. The booking service calls it through the `requests` library.

To demonstrate failure, use a customer email ending in `@fail.test`.

## 6. Setup

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

If PowerShell execution policy blocks activation, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

### PostgreSQL

Set `DATABASE_URL` in `.env`:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/habotconnect
```

The repository falls back to SQLite for quick local evaluation when `DATABASE_URL` is empty.

## 7. Seed test data

Use Django shell:

```powershell
python manage.py shell
```

```python
from booking.models import Parent, LSAProfile, Skill

parent = Parent.objects.create(name="Aarav Parent", email="aarav@example.com")
python_skill = Skill.objects.create(name="Python")
math_skill = Skill.objects.create(name="Math")
lsa = LSAProfile.objects.create(name="Sara LSA", email="sara@example.com", hourly_rate=500)
lsa.skills.add(python_skill, math_skill)
```

## 8. Testing

Run:

```powershell
pytest -q
```

The suite covers:

1. Successful booking/payment.
2. Invalid time range.
3. Overlapping booking rejection.
4. Payment failure state transition.
5. Payment provider exception handling.
6. Multi-skill LSA search.
7. Availability exclusion.
8. N+1 regression protection.
9. Payment webhook state transition.

## 9. CI/CD

`.github/workflows/tests.yml` runs on push and pull request. It starts PostgreSQL, installs dependencies, runs migrations and executes Pytest.

## 10. Production hardening discussion

For a production deployment, add:

- authenticated API access and role-based permissions;
- signed webhook verification and replay protection;
- idempotency enforcement at the API boundary;
- HTTPS and secure secrets management;
- structured JSON logging and monitoring;
- rate limiting;
- PostgreSQL as the production database;
- a real payment provider adapter;
- background jobs for non-critical provider work;
- API schema generation/OpenAPI;
- stronger database-level exclusion constraints if PostgreSQL range types are adopted.

## 11. Interview talking points

### Why Django MVT?

Django provides a mature ORM, migrations, transactions and an established application structure. DRF adds serializers, request parsing, status handling and API-oriented views. For this API-only project, templates are not needed, but the underlying Django separation still maps cleanly to the MVT architecture.

### Why `select_for_update()`?

Without a lock, two simultaneous booking requests could both observe an apparently free slot and create conflicting bookings. Locking the LSA row serializes booking decisions for that LSA inside the transaction.

### Why `prefetch_related()`?

Skills are a many-to-many relationship. Reading them individually for every LSA would create an N+1 query pattern. Prefetching retrieves the related rows in a bounded number of queries and joins them in Python.

### Why a webhook?

A payment result can change asynchronously after the original request. The webhook gives the payment provider a reliable mechanism to tell the backend about the final state.
