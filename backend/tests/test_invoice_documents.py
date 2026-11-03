from io import BytesIO
from pathlib import Path
from datetime import date
from decimal import Decimal

from pypdf import PdfReader
from sqlalchemy import select

from app.models.billing import EmailAttempt
from app.models.catalog import Product, ProductVariant
from app.models.invoices import Invoice
from app.services import email
from app.services.billing import process_next_period
from app.services.invoice_documents import render_invoice_pdf
from test_billing import contract
from test_invoices import command, generate
from test_subscriptions import draft_data, headers


def test_snapshot_pdf_and_customer_authorization(db, client, admin_auth, customer_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    endpoint = f"/api/v1/invoices/{invoice.id}/document"
    assert client.get(endpoint, headers=headers(customer_auth)).status_code == 404
    draft = client.get(endpoint, headers=headers(admin_auth))
    assert draft.status_code == 200
    assert draft.headers["content-type"] == "application/pdf"
    assert "DRAFT PREVIEW" in PdfReader(BytesIO(draft.content)).pages[0].extract_text()
    command(client, admin_auth, invoice, "CONFIRM")
    issued = client.get(f"{endpoint}?download=true", headers=headers(customer_auth))
    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "private, no-store"
    assert issued.headers["content-disposition"].startswith("attachment")
    reader = PdfReader(BytesIO(issued.content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert invoice.number in text
    assert "Subscription owner" in text
    assert "INR 1,416.00" in text
    assert "DRAFT PREVIEW" not in text
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    (output / "invoice-sample.pdf").write_bytes(issued.content)


def test_email_failure_is_persisted_and_retry_attaches_snapshot_pdf(db, client, admin_auth, customer_auth, draft_data, monkeypatch):
    invoice = generate(db, admin_auth, draft_data)
    endpoint = f"/api/v1/invoices/{invoice.id}/send"
    assert client.post(endpoint, headers=headers(customer_auth)).status_code == 403
    assert client.post(endpoint, headers=headers(admin_auth)).status_code == 409
    command(client, admin_auth, invoice, "CONFIRM")
    monkeypatch.setattr(email, "send_email", lambda *args, **kwargs: False)
    response = client.post(endpoint, headers=headers(admin_auth))
    assert response.status_code == 503
    attempt = db.scalar(select(EmailAttempt))
    assert attempt.status == "FAILED"
    assert attempt.safe_error_code == "SMTP_DELIVERY_FAILED"
    sent = []

    def capture(*args, **kwargs):
        sent.append((args, kwargs))
        return True

    monkeypatch.setattr(email, "send_email", capture)
    response = client.post(endpoint, headers=headers(admin_auth))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SENT"
    assert sent[0][0][0] == invoice.customer_email
    filename, content, mime = sent[0][1]["attachments"][0]
    assert filename == f"{invoice.number}.pdf"
    assert mime == "application/pdf"
    assert "INR 1,416.00" in PdfReader(BytesIO(content)).pages[0].extract_text()
    attempts = db.scalars(select(EmailAttempt).order_by(EmailAttempt.attempt_count)).all()
    assert [row.status for row in attempts] == ["FAILED", "SENT"]
    assert [row.attempt_count for row in attempts] == [1, 2]


def test_long_catalog_descriptions_paginate_without_losing_invoice_lines(db, admin_auth, draft_data):
    product = Product(name="Long product " + "module " * 32, type="ADDON", sales_price=Decimal("200.00"), cost_price=Decimal("80.00"))
    db.add(product)
    db.flush()
    variant = ProductVariant(product_id=product.id, name="High memory " + "capacity " * 25, price_adjustment=Decimal("560.00"))
    db.add(variant)
    db.commit()
    subscription = contract(db, admin_auth["user"], draft_data, lines=[{
        "product_id": product.id, "variant_id": variant.id, "quantity": 1} for _ in range(6)])
    result = process_next_period(db, subscription.id, date(2025, 1, 31))
    db.commit()
    invoice = db.get(Invoice, result.invoice_id)
    document = render_invoice_pdf(invoice)
    reader = PdfReader(BytesIO(document))
    assert len(reader.pages) >= 2
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert text.count("Long product") == 6
    assert "INR 5,976.00" in text
    for index, page in enumerate(reader.pages, 1):
        assert f"Page {index}" in page.extract_text()
    Path("test-results/invoice-long.pdf").write_bytes(document)
