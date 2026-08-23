"""
Razorpay Webhook Payload Emitter for AI Revenue Recovery.

Converts generated synthetic transaction records into realistic Razorpay webhook payloads
matching the exact nested schema documented in Razorpay Webhooks API documentation:
- Checkout failures: `payment.failed`
- Successful recoveries: `payment.captured`
- Subscription failures: `subscription.charged` / `payment.failed`
- Overdue invoices: `invoice.expired` / `invoice.overdue`
"""
import time
import json
from typing import Dict, Any, Iterator, List


def transaction_to_razorpay_webhook(txn: Dict[str, Any], event_type: str = None) -> Dict[str, Any]:
    """
    Converts a single synthetic transaction into a standard Razorpay webhook event payload.
    Razorpay amounts are in smallest currency sub-units (paise: INR 1.00 = 100 paise).
    """
    txn_id = str(txn.get("transaction_id", "pay_default"))
    # Sanitize prefix for realistic Razorpay IDs
    clean_id = txn_id.replace("-", "")[:14]
    pay_id = f"pay_{clean_id}"
    order_id = f"order_{clean_id}"
    sub_id = f"sub_{clean_id}"
    inv_id = f"inv_{clean_id}"
    
    amount_in_paise = int(round(float(txn.get("amount", 100.0)) * 100))
    category = txn.get("category", "checkout")
    method = txn.get("payment_method", "upi")
    decline_code = str(txn.get("decline_code", "U69"))
    
    # ASSUMPTION: Account ID representing the merchant account on Razorpay
    account_id = "acc_RZPMerchantDemo01"
    created_at = int(time.time()) - (txn.get("hour_of_day", 12) * 3600)

    # 1. Checkout Payment Failure
    if category == "checkout":
        resolved_event = event_type or "payment.failed"
        
        # ASSUMPTION: Error source and step mapping derived from decline code classification
        if decline_code == "U69":
            error_source = "customer"
            error_step = "payment_authentication"
            error_reason = "payment_timed_out_by_customer"
            error_desc = "UPI collect request timed out on customer device"
        elif decline_code == "Z9":
            error_source = "bank"
            error_step = "payment_authorization"
            error_reason = "insufficient_funds"
            error_desc = "Account balance insufficient to complete debit"
        elif decline_code == "U28":
            error_source = "gateway"
            error_step = "payment_authorization"
            error_reason = "bank_technical_error"
            error_desc = "Issuer bank switch timed out or returned technical glitch"
        elif decline_code in ("U16", "34", "59", "K1", "S1", "S2", "S3"):
            error_source = "risk_engine"
            error_step = "payment_authentication"
            error_reason = "security_risk_threshold_exceeded"
            error_desc = "Transaction flagged by risk engine for high dispute/fraud likelihood"
        else:  # Ambiguous legacy error
            error_source = "issuer_legacy"
            error_step = "payment_authorization"
            error_reason = "unmapped_bank_response"
            error_desc = f"Legacy cooperative bank switch returned unmapped status {decline_code}"

        return {
            "entity": "event",
            "account_id": account_id,
            "event": resolved_event,
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": pay_id,
                        "entity": "payment",
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "status": "failed" if resolved_event == "payment.failed" else "captured",
                        "order_id": order_id,
                        "invoice_id": None,
                        "international": False,
                        "method": method,
                        "amount_refunded": 0,
                        "refund_status": None,
                        "captured": False if resolved_event == "payment.failed" else True,
                        "description": "Checkout Payment Failure Event",
                        "card_id": None if method != "card" else f"card_{clean_id}",
                        "bank": "HDFC" if method == "netbanking" else None,
                        "wallet": None,
                        "vpa": "customer@upi" if "upi" in method else None,
                        "email": "customer@example.com",
                        "contact": "+919876543210",
                        "fee": None,
                        "tax": None,
                        "error_code": decline_code if resolved_event == "payment.failed" else None,
                        "error_description": error_desc if resolved_event == "payment.failed" else None,
                        "error_source": error_source if resolved_event == "payment.failed" else None,
                        "error_step": error_step if resolved_event == "payment.failed" else None,
                        "error_reason": error_reason if resolved_event == "payment.failed" else None,
                        "acquirer_data": {
                            "rrn": f"RRN{clean_id[:8]}",
                            "upi_transaction_id": f"UPI{clean_id[:10]}" if "upi" in method else None
                        },
                        "created_at": created_at
                    }
                }
            },
            "created_at": created_at
        }

    # 2. Subscription Mandate Failure
    elif category == "subscription":
        resolved_event = event_type or "subscription.charged"
        return {
            "entity": "event",
            "account_id": account_id,
            "event": resolved_event,
            "contains": ["subscription", "payment"],
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "entity": "subscription",
                        "plan_id": f"plan_{clean_id[:6]}",
                        "customer_id": f"cust_{clean_id[:6]}",
                        "status": "halted" if decline_code == "mandate_paused" else "active",
                        "current_start": created_at - (30 * 86400),
                        "current_end": created_at,
                        "ended_at": None,
                        "quantity": 1,
                        "notes": {"reason": decline_code},
                        "charge_at": created_at,
                        "start_at": created_at - (90 * 86400),
                        "end_at": created_at + (365 * 86400),
                        "auth_attempts": 1,
                        "total_count": 12,
                        "paid_count": 3,
                        "customer_notify": True,
                        "created_at": created_at - (90 * 86400)
                    }
                },
                "payment": {
                    "entity": {
                        "id": pay_id,
                        "entity": "payment",
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "status": "failed",
                        "order_id": None,
                        "method": method,
                        "error_code": decline_code,
                        "error_description": f"Subscription auto-debit failed: {decline_code}",
                        "error_source": "mandate_engine",
                        "error_step": "recurring_execution",
                        "error_reason": "mandate_invalid_or_expired" if decline_code == "mandate_expired" else "mandate_paused_by_user",
                        "created_at": created_at
                    }
                }
            },
            "created_at": created_at
        }

    # 3. Receivable / Invoice Overdue Event
    else:
        resolved_event = event_type or "invoice.expired"
        return {
            "entity": "event",
            "account_id": account_id,
            "event": resolved_event,
            "contains": ["invoice"],
            "payload": {
                "invoice": {
                    "entity": {
                        "id": inv_id,
                        "entity": "invoice",
                        "customer_id": f"cust_{clean_id[:6]}",
                        "customer_name": "Acme Corp B2B",
                        "customer_email": "billing@acme.com",
                        "customer_contact": "+919812345678",
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "status": "expired",
                        "order_id": order_id,
                        "short_url": f"https://rzp.io/i/{clean_id[:8]}",
                        "type": "invoice",
                        "date": created_at - (15 * 86400),
                        "terms": None,
                        "notes": {"dispute_status": "disputed" if "dispute" in decline_code else "none"},
                        "expire_by": created_at - (1 * 86400),
                        "issued_at": created_at - (15 * 86400),
                        "paid_at": None,
                        "cancelled_at": None,
                        "expired_at": created_at,
                        "sms_status": "sent",
                        "email_status": "sent",
                        "decline_code": decline_code
                    }
                }
            },
            "created_at": created_at
        }


def emit_batch_as_webhooks(transactions: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    Yields realistic Razorpay webhook payloads for a list of synthetic transactions.
    """
    for txn in transactions:
        yield transaction_to_razorpay_webhook(txn)
