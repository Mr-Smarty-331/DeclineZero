# DeclineZero — System Assumptions & Unverified Boundaries Catalog

This document provides a consolidated, transparent registry of every empirical heuristic, operational assumption, cost constant, and mock boundary utilized within the **DeclineZero AI Revenue Recovery Agent** (`Razorpay Track 03`).

---

## 1. Unit Economic & Monetization Assumptions

| Tag / Code Identifier | Value | File Location | Operational Rationale |
| :--- | :--- | :--- | :--- |
| `AVG_CUSTOMER_LTV_LOSS` | **₹3,500.00** | [`core/evaluator/baseline_comparator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/evaluator/baseline_comparator.py) | Estimated merchant customer lifetime value (LTV) destroyed when a sleeping-dog customer churns or files a spite chargeback. |
| `AVG_COMPLIANCE_PENALTY` | **₹5,000.00** | [`core/evaluator/baseline_comparator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/evaluator/baseline_comparator.py) | Estimated operational, ombudsman, and regulatory compliance remediation cost per RBI Digital Lending / Fair Practices violation. |
| `UNIT_OUTREACH_COST_WHATSAPP` | **₹0.50** | [`core/recovery_engine/actions.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/recovery_engine/actions.py) | Typical cost per template delivery via WhatsApp Business API in India. |
| `UNIT_OUTREACH_COST_SMS` | **₹0.20** | [`core/recovery_engine/actions.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/recovery_engine/actions.py) | Typical transactional SMS DLT carrier charge per delivery in India. |

---

## 2. Regulatory & Stopping Guardrails Assumptions

| Tag / Code Identifier | Value | File Location | Operational Rationale |
| :--- | :--- | :--- | :--- |
| `CONTACT_ATTEMPT_CAP_CHECKOUT` | **3 attempts** | [`core/stopping_rules/compliance.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/stopping_rules/compliance.py) | Instant checkout failure retries capped at 3 per transaction to prevent customer fatigue. |
| `CONTACT_ATTEMPT_CAP_SUBSCRIPTION` | **8 attempts / 30d** | [`core/stopping_rules/compliance.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/stopping_rules/compliance.py) | Aligned with standard 8-attempt card network / UPI auto-debit mandate renewal retry cycles over 30 days. |
| `CONTACT_ATTEMPT_CAP_RECEIVABLE` | **5 touches** | [`core/stopping_rules/compliance.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/stopping_rules/compliance.py) | Standard B2B overdue invoice follow-up touchpoint limit across a 45-day billing cycle. |
| `CONTACT_WINDOW_HOURS` | **08:00 to 19:00 IST** | [`core/stopping_rules/compliance.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/stopping_rules/compliance.py) | Strict RBI Digital Lending guidelines prohibiting promotional and collection contact before 8 AM and after 7 PM. |
| `SALARY_ALIGNED_DATES` | **1st & 7th of Month** | [`core/stopping_rules/compliance.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/stopping_rules/compliance.py) | Peak corporate salary credit dates in India; retrying `Z9` (Insufficient Funds) on these days maximizes conversion. |

---

## 3. Synthetic Data & Merchant Telemetry Assumptions

| Tag / Code Identifier | Distribution | File Location | Operational Rationale |
| :--- | :--- | :--- | :--- |
| `CATEGORY_WEIGHTS` | `checkout: 60%`, `subscription: 25%`, `receivable: 15%` | [`simulator/generator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/simulator/generator.py) | Representative volume mix for a multi-vertical Indian merchant platform. |
| `CHECKOUT_PAYMENT_METHODS` | `upi: 75%`, `card: 20%`, `netbanking: 5%` | [`simulator/generator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/simulator/generator.py) | Reflects real-world payment rail distributions in the Indian payments ecosystem. |
| `CUSTOMER_PAST_SUCCESS_RATE` | `Beta(5, 1.5) * 0.69 + 0.30` ($\in [0.30, 0.99]$) | [`simulator/generator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/simulator/generator.py) | Realistic historical payment success telemetry available to Razorpay at checkout time. |
| `AMBIGUOUS_CODE_RATE` | `~7.5%` (`ERR-BNK-0001` .. `ERR-BNK-0010`) | [`simulator/generator.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/simulator/generator.py) | Simulates unmapped legacy cooperative bank error strings requiring conformal prediction abstention. |

---

## 4. Live API & External Integration Boundaries

| Tag / Code Identifier | Integration | File Location | Status / Boundary |
| :--- | :--- | :--- | :--- |
| `# UNVERIFIED AGAINST LIVE API` | Razorpay Payment Links API (`POST /v1/payment_links`) | [`core/recovery_engine/actions.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/recovery_engine/actions.py) | Payload schema adheres to Razorpay API documentation (`amount` in paise, `currency: INR`, `customer` object, `notify`). Live sandbox requires merchant key credentials. |
| `# MOCK DISPATCH CHANNEL` | WhatsApp Business API & SMS Gateways | [`core/recovery_engine/actions.py`](file:///Users/ayushraj/Desktop/projects/Razorpay/revenue-recovery/core/recovery_engine/actions.py) | Logged deterministically with simulated sub-second delivery callbacks and unit cost attribution. |
