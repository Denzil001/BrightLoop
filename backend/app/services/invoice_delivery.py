"""Explicit invoice email attempts, persisted before SMTP and after its result."""
from sqlalchemy import func, select

from app.models.audit import AuditEvent
from app.models.billing import EmailAttempt
from app.services import email
from app.services.invoice_documents import render_invoice_pdf
from app.services.subscriptions import fail


def send_invoice(db, invoice, actor):
    if invoice.issued_at is None or invoice.state == "CANCELLED":
        fail("Only issued, non-cancelled invoices can be sent.")
    attempt_number = 1 + (db.scalar(select(func.count()).select_from(EmailAttempt).where(EmailAttempt.invoice_id == invoice.id)) or 0)
    attempt = EmailAttempt(invoice_id=invoice.id, kind="INVOICE_SEND", status="PENDING", attempt_count=attempt_number)
    db.add(attempt)
    try:
        document = render_invoice_pdf(invoice)
    except Exception:
        attempt.status = "FAILED"
        attempt.safe_error_code = "DOCUMENT_GENERATION_FAILED"
        db.commit()
        fail("The invoice document could not be prepared. Retry after checking the delivery history.", 503)
    recipient, filename = invoice.customer_email, f"{invoice.number}.pdf"
    subject = f"Brightloop invoice {invoice.number}"
    body = (f"Hello {invoice.customer_name},\n\nAttached is invoice {invoice.number} for service "
            f"{invoice.period_start} to {invoice.period_end} (end exclusive).\n"
            f"Invoice total: {invoice.currency} {invoice.total:.2f}. Due date: {invoice.due_date}.\n"
            "Please check your portal for the current balance and contact the team for payment arrangements.\n")
    invoice_id = invoice.id
    db.flush()
    attempt_id = attempt.id
    db.commit()  # SMTP is outside the invoice/attempt creation transaction.
    try:
        sent = email.send_email(recipient, subject, body, attachments=[(filename, document, "application/pdf")])
    except Exception:
        sent = False
    attempt = db.get(EmailAttempt, attempt_id)
    attempt.status = "SENT" if sent else "FAILED"
    attempt.safe_error_code = None if sent else "SMTP_DELIVERY_FAILED"
    db.add(AuditEvent(actor_id=actor.id, action="INVOICE_EMAIL_SENT" if sent else "INVOICE_EMAIL_FAILED",
                      target_type="invoice", target_id=str(invoice_id), payload={"attempt_id": str(attempt_id)}))
    db.commit()
    if not sent:
        fail("Invoice delivery was not confirmed. Review the delivery history and retry.", 503)
    return {"attempt_id": attempt_id, "status": "SENT"}
