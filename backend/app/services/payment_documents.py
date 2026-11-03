"""Receipt for an immutable persisted payment; no recalculated historic balance."""
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_payment_receipt(payment):
    invoice = payment.invoice
    styles = getSampleStyleSheet()
    output = BytesIO()
    number = f"RCP-{payment.id.hex.upper()}"

    def p(value, style="BodyText"):
        return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), styles[style])

    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=45,
                                 title=number, author=invoice.issuer_name)
    story = [p("PAYMENT RECEIPT", "Title"), p(number, "Heading2"), Spacer(1, 18),
        p(invoice.issuer_name, "Heading3"), p(f"Tax ID: {invoice.issuer_tax_id or '-'}"),
        p(", ".join(str(invoice.issuer_address[key]) for key in ("address_line1", "address_line2", "city", "state", "postal_code", "country") if invoice.issuer_address.get(key))),
        Spacer(1, 14), p(f"Received from: {invoice.customer_name}", "Heading3"),
        p(invoice.customer_company), p(invoice.customer_email), Spacer(1, 16)]
    rows = [("Invoice", invoice.number), ("Payment date", payment.payment_date.isoformat()),
            ("Payment method", payment.method.replace("_", " ")),
            ("Reference", payment.reference or "Not provided"),
            ("Amount received", f"{invoice.currency} {payment.amount:,.2f}")]
    table = Table([[p(label), p(value)] for label, value in rows], colWidths=[145, 370], hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaf0f8")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1"))]))
    story += [table, Spacer(1, 18), p("Payment note", "Heading3"), p(payment.note), Spacer(1, 20),
              p("This receipt records only the payment shown. Current invoice balances and payment history are available in the customer portal.")]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(40, 25, number)
        canvas.drawRightString(A4[0] - 40, 25, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
