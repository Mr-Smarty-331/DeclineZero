"""
Core Decline-Code Taxonomy for Razorpay Track 03: AI Revenue Recovery.

Strict taxonomy of real NPCI / Razorpay decline codes across payment failure modes:
- UPI:
  - U69: Collect request expired (timing / customer inattention)
  - Z9: Insufficient funds in customer account
  - U28: Bank-side technical glitch / PSP communication timeout
  - Risk Flagged: U16, 34, 59, K1, S1, S2, S3 (mandatory human escalation, never auto-retried)
- Subscriptions:
  - mandate_expired: Mandate lapsed
  - mandate_paused: Mandate temporarily suspended
- Receivables:
  - overdue_no_dispute: Invoice past due date with no dispute flag
  - overdue_with_dispute_flag: Invoice past due date with active dispute
"""
from enum import Enum

class UPIDeclineCode(str, Enum):
    U69 = "U69"  # Collect expired — timing issue
    Z9 = "Z9"    # Insufficient funds
    U28 = "U28"  # Bank-side technical issue
    U16 = "U16"  # Risk / fraud flagged
    CODE_34 = "34"   # Risk / fraud flagged
    CODE_59 = "59"   # Risk / fraud flagged
    K1 = "K1"    # Risk / fraud flagged
    S1 = "S1"    # Risk / fraud flagged
    S2 = "S2"    # Risk / fraud flagged
    S3 = "S3"    # Risk / fraud flagged

class SubscriptionDeclineCode(str, Enum):
    MANDATE_EXPIRED = "mandate_expired"
    MANDATE_PAUSED = "mandate_paused"

class ReceivableDeclineCode(str, Enum):
    OVERDUE_NO_DISPUTE = "overdue_no_dispute"
    OVERDUE_WITH_DISPUTE_FLAG = "overdue_with_dispute_flag"

# Grouped categories for deterministic routing & verification
RISK_FLAGGED_CODES = frozenset({"U16", "34", "59", "K1", "S1", "S2", "S3"})

UPI_CODES = frozenset(code.value for code in UPIDeclineCode)
SUBSCRIPTION_CODES = frozenset(code.value for code in SubscriptionDeclineCode)
RECEIVABLE_CODES = frozenset(code.value for code in ReceivableDeclineCode)

ALL_VALID_CODES = UPI_CODES | SUBSCRIPTION_CODES | RECEIVABLE_CODES
