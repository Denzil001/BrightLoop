"""Local PDF rendering of persisted invoice snapshots only."""
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_invoice_pdf(invoice):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    body = ParagraphStyle("InvoiceBody", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=5)
    small = ParagraphStyle("InvoiceSmall", parent=body, fontSize=8, leading=11)
    right = ParagraphStyle("InvoiceRight", parent=small, alignment=TA_RIGHT)

    def p(text, style=body):
        return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)

    def money(value):
        return f"{invoice.currency} {value:,.2f}"

    def address(values):
        return "\n".join(str(values[key]) for key in ("address_line1", "address_line2", "city", "state", "postal_code", "country") if values.get(key))

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=38, bottomMargin=42,
                            title=invoice.number, author=invoice.issuer_name)
    status = "DRAFT PREVIEW" if invoice.state == "DRAFT" else "CANCELLED" if invoice.state == "CANCELLED" else "INVOICE"
    story = [p(status, styles["Title"]), p(invoice.number, styles["Heading2"]), Spacer(1, 10)]
    parties = Table([[p(f"FROM\n{invoice.issuer_name}\nTax ID: {invoice.issuer_tax_id or '-'}\n{address(invoice.issuer_address)}"),
                      p(f"BILL TO\n{invoice.customer_name}\n{invoice.customer_company or ''}\n{invoice.customer_email}\n{address(invoice.customer_address)}")]], colWidths=[261, 261])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 14)]))
    story += [parties, Spacer(1, 14), p(f"Invoice date: {invoice.invoice_date}    Due date: {invoice.due_date}"),
              p(f"Service period: {invoice.period_start} to {invoice.period_end} (end exclusive)"), p(f"Status: {invoice.state}"), Spacer(1, 10)]
    if invoice.service_days != invoice.full_period_days:
        story += [p(f"Partial service period: {invoice.service_days}/{invoice.full_period_days} days. Unit prices show agreed full-period rates; base amounts are prorated."), Spacer(1, 8)]
    headings = ["Charge", "Qty", "Unit price", "Base", "Discount", "Tax", "Total"]
    rows = [[p(title, small) for title in headings]]
    for line in sorted(invoice.lines, key=lambda item: item.ordinal):
        tax_detail = "; ".join(f"{tax.snapshot_name} {tax.snapshot_rate.normalize()}%" for tax in line.taxes)
        rows.append([p(line.snapshot_description + (f"\n{tax_detail}" if tax_detail else ""), small),
                     p(line.quantity, right), p(f"{line.unit_price:,.2f}", right), p(f"{line.subtotal:,.2f}", right),
                     p(f"{line.discount_amount:,.2f}", right), p(f"{line.tax_amount:,.2f}", right), p(f"{line.total:,.2f}", right)])
    table = Table(rows, colWidths=[174, 26, 65, 65, 60, 57, 75], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#94a3b8")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#cbd5e1"))]))
    story += [table, Spacer(1, 16)]
    totals = Table([[p(label), p(money(value), right)] for label, value in (
        ("Subtotal", invoice.subtotal), ("Discount", invoice.discount_total), ("Tax", invoice.tax_total), ("Invoice total", invoice.total))], colWidths=[130, 150], hAlign="RIGHT")
    totals.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#2563eb")),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    ending = [p("Invoice summary", styles["Heading3"]), totals, Spacer(1, 12)]
    if invoice.state == "CANCELLED":
        ending.append(p("This invoice is cancelled and is not payable. Retained as a historical document."))
    elif invoice.state == "DRAFT":
        ending.append(p("Internal draft preview. This document has not been issued and is not a payment request."))
    else:
        ending.append(p("Contact the team for payment arrangements. This document records the original invoice amount; current payment history and balance are available in your portal."))
    story.append(KeepTogether(ending))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(36, 24, f"{invoice.number} | {invoice.state}")
        canvas.drawRightString(A4[0] - 36, 24, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
