# Idempotency-Gateway (The "Pay-Once" Protocol)

Welcome to the **Idempotency-Gateway** repository—a robust robust middleware service simulating a real-world payment processing environment with comprehensive idempotency guarantees.

## 1. Business Context & Objective

In high-concurrency e-commerce environments, network drops or client delays can trigger automated payment request retries. For payment processors like _FinSafe Transactions Ltd._, this can lead to catastrophic double-charge scenarios, resulting in poor customer experience, support overhead, and regulatory issues.

This API acts as an **Idempotency Layer**. It processes a unique `Idempotency-Key` sent via HTTP headers on every payment request to ensure that a transaction is evaluated and charged exactly _once_, no matter how many duplicate attempts arrive from the client.

---

## 2. Architecture & Logic Flow

This logical flowchart outlines the architectural idempotency flow taken when any payment request hits the `POST /api/v1/process-payment/` endpoint.

![Architecture Flowchart](./flowchart.png)

---

## 3. Setup Instructions

The project is built on **Python 3.x** and **Django REST Framework (DRF)**. A standard SQLite database is utilized by default to persist the idempotency records reliably.

### Prerequisites

- Python 3.10+
- `pip` package manager
- `git`

### Installation Steps

1. **Clone the Repository** (Or fork depending on your workflow)

   ```bash
   git clone <your-fork-url>
   cd Idempotency-Gateway
   ```

2. **Create and Activate a Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment Variables**
   Rename the provided `.env-example` file to `.env` and update the variables if necessary.

   ```bash
   cp .env-example .env
   ```

5. **Run Database Migrations**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```
   _The server should now be running locally at `http://127.0.0.1:8000/`._

---

## 4. API Documentation

Because modern financial platforms require security, the gateway incorporates Token-Based Authentication. You must first register a user and obtain a token before processing payments.

### A. Authentication Endpoints

#### `POST /api/v1/auth/register/`

Create a new client/user account.

- **Body:**
  ```json
  {
    "email": "store@example.com",
    "password": "strongpassword123",
    "first_name": "Store",
    "last_name": "Owner"
  }
  ```
- **Response (201 Created):**
  ```json
  {
      "user": { ... },
      "token": "a1b2c3d4e5f6g7h8i9j0"
  }
  ```

#### `POST /api/v1/auth/login/`

Login to receive your Auth Token.

- **Body:**
  ```json
  {
    "email": "store@example.com",
    "password": "strongpassword123"
  }
  ```

---

### B. Payment Endpoint

#### `POST /api/v1/process-payment/`

Process a payment idempotently.

- **Headers:**
  - `Authorization: Token <your-auth-token>`
  - `Idempotency-Key: <valid-uuid-v4>` (Required)
  - `Content-Type: application/json`

- **Request Body:**
  ```json
  {
    "amount": "100.50",
    "currency": "GHS"
  }
  ```

#### Expected Behaviors & Responses

1. **The First Transaction (Happy Path)**
   - **Scenario**: A completely new UUIDv4 `Idempotency-Key` is sent.
   - **Response (`201 Created`)**: (Takes ~2 seconds processing time)
     ```json
     {
       "status": "success",
       "message": "Charged 100.50 GHS",
       "amount": "100.50",
       "currency": "GHS",
       "idempotency_key": "c35e9f82-...-9a8f4c"
     }
     ```

2. **The Duplicate Attempt (Idempotency Logic)**
   - **Scenario**: The exact same key and payload are posted again.
   - **Response (`201 Created`)**: (Returns **instantly**; no 2-second delay).
   - **Header**: Includes `X-Cache-Hit: true`
   - **Body**: _Same output as the first request._

3. **Different Request, Same Key (Fraud/Error Check)**
   - **Scenario**: An existing key is used, but the payload amount has changed.
   - **Response (`422 Unprocessable Entity`)**:
     ```json
     {
       "error": "Idempotency key already used for a different request body."
     }
     ```

4. **Simultaneous Requests (The "In-Flight" Protocol)**
   - **Scenario**: Two requests with the same key arrive at the exact millisecond (Race condition).
   - **Outcome**: The database unique constraint is caught (`IntegrityError`), and the secondary request actively polls and blocks (`_wait_for_in_flight_request`) until the first request completes processing, returning the exact same response cleanly without triggering duplicates or raising a `409 Conflict`.

---

## 5. Design Decisions

- **Relational Storage over In-Memory Cache**:
  While a fast in-memory store like Redis is excellent for speed, `SQLite/PostgreSQL` was chosen to preserve transactional durability. If an API pod restarts, we do not want to lose idempotency records resulting in a double charge.
- **Idempotency Scope**:
  The idempotency tracking is scoped uniquely to `("user", "key")` pairs (`unique_together` index in the model). This prevents "Client A" from accidentally clashing with "Client B" if they coincidentally happen to generate identical keys.

- **Atomic Database Locks & Constraint Catching**:
  Instead of utilizing complex distributed memory locks just for the `in-flight` validation check, we lean on database `IntegrityError` catches during record creation, then transition gracefully to a thread-level sleep/polling loop. This gracefully manages concurrent Race Conditions (User Story 4).

---

## 6. The "Developer's Choice" Challenge

In this implementation, **two notable undocumented safety mechanisms** were developed to fortify the gateway dynamically for a "real-world Sandbox Fintech" company.

### 1) UUIDv4 Strict Enforcement for Idempotency-Keys

**What it is:**
The API actively blocks any `Idempotency-Key` headers that are not strictly valid Version 4 UUIDs (raising a `400 Bad Request`).
**Why it was added:**
In real-world systems, if you allow clients to dictate their own raw strings (e.g., `Idempotency-Key: payment-1`, `payment-2`), you open the door to disastrous overlapping collisons. A client might reset their internal database, start generating keys from `payment-1` again, and suddenly their legitimate _new_ payments will be rejected as duplicates. Enforcing UUIDv4 guarantees high entropy and mathematical uniqueness globally.

### 2) Token-Based Authorization & Tenant Isolation

**What it is:**
I fully implemented a custom User model (`accounts` app) along with DRF `TokenAuthentication`. Payment records in the database have a `Foreign Key` relating back to the requesting client/user.
**Why it was added:**
Idempotency is a massive security risk if unauthenticated. If Client X learns that Client Y is going to send a payment with `Idempotency-Key=123`, Client X could pre-emptively fire that request with malicious data. By tying authentication directly to the Idempotency scope natively within the endpoint, the infrastructure behaves exactly like Stripe/PayPal's multi-tenant architecture, securely partitioning data.
