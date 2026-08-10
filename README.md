# HabotConnect LSA Service Booking Backend

**Python Backend Developer Hiring Project — HabotConnect**

A production-oriented Django REST Framework backend prototype for connecting parents with Learning Support Assistants (LSAs). The project demonstrates relational data modeling, optimized LSA search, safe booking creation, double-booking prevention, mock payment integration, payment webhooks, automated testing, and GitHub Actions CI.

---

## 1. Project Overview

The backend supports the following core workflow:

```text
Parent
  |
  | searches for suitable LSA
  v
GET /api/v1/lsas/search/
  |
  | selects available LSA + time slot
  v
POST /api/v1/bookings/
  |
  +--> validate request
  +--> lock selected LSA row
  +--> check overlapping active bookings
  +--> calculate session amount
  +--> create payment record
  +--> call mock payment provider
  |
  +--> payment success -> CONFIRMED
  |
  +--> payment failure -> PAYMENT_FAILED

Payment Provider
  |
  v
POST /api/v1/payments/webhook/
  |
  +--> lock payment
  +--> update Payment state
  +--> update Booking state
```

The implementation is intentionally structured so the main business rules live in service/selector code rather than being scattered across HTTP views.

---

## 2. Technology Stack

| Area | Technology |
|---|---|
| Language | Python |
| Web framework | Django |
| REST API | Django REST Framework |
| Production database | PostgreSQL |
| Local fallback | SQLite |
| HTTP integration | `requests` |
| Testing | Pytest + pytest-django |
| CI/CD | GitHub Actions |
| Version control | Git / GitHub |

---

## 3. Architecture — Django MVT

This project uses Django's **MVT (Model–View–Template)** architecture, with Django REST Framework providing the API layer.

For an API-only backend:

- **Model** → database entities and relationships.
- **View / APIView** → HTTP request/response handling.
- **Serializer** → request validation and response representation.
- **Selector** → optimized read/query logic.
- **Service** → business operations and third-party integration.
- **Template** → not required because this application exposes REST APIs rather than server-rendered HTML pages.

### Why Django?

Django provides:

- a mature ORM;
- database migrations;
- transaction support;
- validation infrastructure;
- a well-defined project structure.

DRF adds API-specific request parsing, serializers, status codes and API views.

---

## 4. Database Design

### Entities

- **Parent** — customer requesting a session.
- **LSAProfile** — Learning Support Assistant profile and hourly rate.
- **Skill** — normalized skill vocabulary.
- **Booking** — requested session, parent, LSA, amount, status and idempotency key.
- **Payment** — one-to-one payment record for a booking.

### Relationships

```text
Parent 1 ───────────────< Booking >────────────── 1 LSAProfile
                              |
                              |
                              1
                              |
                              v
                           Payment

LSAProfile >──────────────< Skill
             Many-to-Many
```

### Important fields

```text
Parent
------
id
name
email (unique)
phone
created_at

LSAProfile
----------
id
name
email (unique)
hourly_rate
is_active
created_at

Skill
-----
id
name (unique)

Booking
-------
id
parent_id
lsa_id
session_date
start_time
end_time
amount
status
idempotency_key (unique)
created_at
updated_at

Payment
-------
id
booking_id (one-to-one)
transaction_id (unique)
amount
status
provider_message
created_at
updated_at
```

### Indexing

Indexes support common access patterns including:

- parent email;
- active LSA lookup;
- LSA hourly rate;
- LSA/date/booking start-time lookup;
- booking status;
- parent/status;
- payment status;
- payment transaction ID.

The `Booking` model also has a database check constraint requiring:

```text
end_time > start_time
```

---

## 5. Double-Booking Prevention

This is one of the key production-safety rules in the project.

When a booking request arrives, the service:

1. starts a database transaction;
2. locks the selected LSA row using `select_for_update()`;
3. checks active bookings for the requested date;
4. detects interval overlap;
5. rejects the request if a conflict exists;
6. otherwise creates the booking.

The overlap condition is:

```text
existing.start_time < requested.end_time
AND
existing.end_time > requested.start_time
```

Example:

```text
Existing booking
12:00 ───────── 13:00

New request
        12:30 ───────── 13:30

Result: REJECTED
```

### Why the row lock matters

A simple:

```python
Booking.objects.filter(...).exists()
```

check can race when two requests arrive at almost the same time.

`select_for_update()` serializes booking decisions for the selected LSA within the transaction, preventing both requests from observing the same free slot and proceeding concurrently.

---

## 6. LSA Search and N+1 Optimization

### Endpoint

```text
GET /api/v1/lsas/search/
```

Example:

```text
/api/v1/lsas/search/?skills=Python,Math
```

Optional availability parameters:

```text
/api/v1/lsas/search/?skills=Python,Math&session_date=2026-08-12&start_time=10:00:00&end_time=11:00:00
```

### Multi-skill behavior

If the request contains:

```text
Python,Math
```

the LSA must have **both** skills.

The query performs case-insensitive skill matching and uses database-side filtering/annotation rather than loading all LSAs into Python.

### N+1 problem

Without eager loading:

```text
1 query -> LSAs
N queries -> skills for each LSA
```

With:

```python
prefetch_related("skills")
```

the related skills are fetched in a bounded number of queries and reused during serialization.

A regression test measures query growth so the optimization is protected against accidental future changes.

---

## 7. API Specification

### 7.1 Health endpoint

```http
GET /
```

Example response:

```json
{
  "project": "HabotConnect LSA Booking API",
  "status": "running",
  "version": "v1",
  "message": "Backend API is running successfully"
}
```

---

### 7.2 Search LSAs

```http
GET /api/v1/lsas/search/
```

Example:

```text
/api/v1/lsas/search/?skills=Python,Math
```

---

### 7.3 Create booking

```http
POST /api/v1/bookings/
Content-Type: application/json
```

Request:

```json
{
  "parent_id": 1,
  "lsa_id": 1,
  "session_date": "2026-08-12",
  "start_time": "12:00:00",
  "end_time": "13:00:00",
  "idempotency_key": "booking-demo-003"
}
```

The server calculates the amount from:

```text
hourly rate × session duration
```

A successful payment results in a confirmed booking.

---

### 7.4 Mock payment gateway

```http
POST /api/v1/mock-gateway/charge/
Content-Type: application/json
```

Request:

```json
{
  "booking_id": 2,
  "amount": 500,
  "customer_email": "parent@example.com"
}
```

Success response:

```json
{
  "success": true,
  "transaction_id": "MOCK-8C2731B8EB4349DA",
  "message": "Mock payment successful"
}
```

### Deterministic failure

For demonstration/testing, an email ending in:

```text
@fail.test
```

causes the mock provider to return a payment decline.

---

### 7.5 Payment webhook

```http
POST /api/v1/payments/webhook/
Content-Type: application/json
```

Success event:

```json
{
  "transaction_id": "MOCK-8C2731B8EB4349DA",
  "event": "payment.success",
  "message": "Payment confirmed by provider"
}
```

Failure event:

```json
{
  "transaction_id": "MOCK-8C2731B8EB4349DA",
  "event": "payment.failed",
  "message": "Payment declined by provider"
}
```

State transitions:

```text
payment.success
    -> Payment.SUCCESS
    -> Booking.CONFIRMED

payment.failed
    -> Payment.FAILED
    -> Booking.PAYMENT_FAILED
```

Webhook processing uses a transaction and `select_for_update()` on the payment record.

---

## 8. Project Structure

```text
habotconnect_lsa_booking/
│
├── .github/
│   └── workflows/
│       └── tests.yml
│
├── booking/
│   ├── migrations/
│   ├── models.py
│   ├── serializers.py
│   ├── selectors.py
│   ├── services.py
│   ├── validators.py
│   ├── views.py
│   └── urls.py
│
├── payments/
│   ├── services.py
│   ├── views.py
│   └── urls.py
│
├── tests/
│   ├── conftest.py
│   ├── test_bookings.py
│   ├── test_lsa_search.py
│   └── test_webhook.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. Local Setup

### Windows

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create environment file:

```powershell
Copy-Item .env.example .env
```

Run migrations:

```powershell
python manage.py migrate
```

Start the development server:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Expected:

```json
{
  "project": "HabotConnect LSA Booking API",
  "status": "running",
  "version": "v1",
  "message": "Backend API is running successfully"
}
```

If PowerShell blocks virtual-environment activation:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

---

## 10. Environment Variables

Example `.env`:

```text
DJANGO_SECRET_KEY=change-this-in-development
DJANGO_DEBUG=True
DATABASE_URL=
MOCK_PAYMENT_URL=http://127.0.0.1:8000/api/v1/mock-gateway/charge/
PAYMENT_TIMEOUT_SECONDS=5
```

For PostgreSQL:

```text
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/habotconnect
```

Do not commit the real `.env` file or secrets to GitHub.

---

## 11. Seed Development Data

Open Django shell:

```powershell
python manage.py shell
```

Then:

```python
from booking.models import Parent, LSAProfile, Skill

parent, _ = Parent.objects.get_or_create(
    email="parent@example.com",
    defaults={
        "name": "Rahul Sharma",
        "phone": "9876543210",
    },
)

python_skill, _ = Skill.objects.get_or_create(name="Python")
math_skill, _ = Skill.objects.get_or_create(name="Math")
english_skill, _ = Skill.objects.get_or_create(name="English")

lsa1, _ = LSAProfile.objects.get_or_create(
    email="lsa1@example.com",
    defaults={
        "name": "Priya Singh",
        "hourly_rate": 500,
        "is_active": True,
    },
)

lsa1.skills.set([python_skill, math_skill])

lsa2, _ = LSAProfile.objects.get_or_create(
    email="lsa2@example.com",
    defaults={
        "name": "Amit Kumar",
        "hourly_rate": 400,
        "is_active": True,
    },
)

lsa2.skills.set([english_skill])
```

Exit:

```python
exit()
```

---

## 12. Testing

Run:

```powershell
pytest -q
```

The current local project has been verified with:

```text
10 passed
```

The test coverage includes:

- successful booking/payment;
- invalid time range;
- overlapping booking rejection;
- payment failure transition;
- payment provider exception handling;
- multi-skill LSA search;
- availability exclusion;
- N+1 query regression protection;
- payment webhook state transition.

---

## 13. CI/CD

GitHub Actions workflow:

```text
.github/workflows/tests.yml
```

The workflow:

1. checks out the repository;
2. starts PostgreSQL 16 as a service;
3. configures CI environment variables;
4. installs Python dependencies;
5. runs Django migrations;
6. executes Pytest.

The workflow runs on:

- push;
- pull request.

### Current CI result

The repository has successfully completed a GitHub Actions run for the initial backend commit.

---

## 14. Production Hardening

This project is a hiring-project prototype. For production, additional controls would be appropriate:

- authentication and authorization;
- role-based API permissions;
- signed webhook verification;
- webhook replay protection;
- stronger idempotency handling;
- HTTPS;
- secure secret management;
- structured JSON logging;
- monitoring and alerting;
- API rate limiting;
- PostgreSQL as the production database;
- real payment-provider adapter;
- asynchronous jobs where appropriate;
- OpenAPI schema/documentation;
- stronger PostgreSQL-specific concurrency constraints where suitable.

---

## 15. Key Design Decisions

### Why `select_for_update()`?

It protects the booking decision from concurrent requests for the same LSA.

### Why `prefetch_related()`?

`LSAProfile.skills` is a many-to-many relationship. Prefetching prevents a separate skill query for every returned LSA.

### Why a selector layer?

Read/query logic is isolated from HTTP handling, making query optimization easier to test and maintain.

### Why a service layer?

Business operations such as booking/payment coordination and third-party integration should not be tightly coupled to API views.

### Why a webhook?

Payment state can change asynchronously. The webhook gives the provider a mechanism to communicate the final payment event to the backend.

### Why MVT rather than MVC?

Django's native architecture is MVT. For this API-only backend, templates are not used, while models, views and DRF serializers/services provide a clean separation of responsibilities.

---

## 16. Interview Demonstration Checklist

During the project interview, demonstrate:

```text
1. GET /api/v1/lsas/search/
2. Multi-skill filtering
3. POST /api/v1/bookings/
4. Successful payment
5. Overlapping booking rejection
6. Payment failure
7. Payment webhook
8. Database state transition
9. N+1 query test
10. pytest -q
11. GitHub Actions result
```

Be prepared to explain:

- the database relationships;
- transaction boundaries;
- `select_for_update()`;
- overlap detection;
- `prefetch_related()`;
- N+1 queries;
- service vs selector responsibilities;
- payment failure handling;
- webhook state transitions;
- CI workflow.

---

## 17. Repository

GitHub:

**https://github.com/Farman002/habotconnect-lsa-booking**

---

## 18. Submission Deliverables

The repository should contain:

- Python/Django codebase;
- database models and migrations;
- API routes;
- automated tests;
- GitHub Actions workflow;
- README documentation;
- project presentation.

Before final submission, verify that the repository is public and that the latest GitHub Actions run is green.

