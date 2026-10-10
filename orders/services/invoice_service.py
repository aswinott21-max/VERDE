from io import BytesIO

from django.http import FileResponse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Register fonts that support the Indian Rupee symbol (₹).
pdfmetrics.registerFont(
    TTFont(
        "DejaVuSans",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    )
)

pdfmetrics.registerFont(
    TTFont(
        "DejaVuSans-Bold",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    )
)


def generate_invoice_pdf(order):
    # Create an in-memory buffer for the PDF.
    buffer = BytesIO()

    # Configure the invoice page.
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # Use Unicode fonts throughout the invoice.
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVuSans"
    styles["Title"].fontName = "DejaVuSans-Bold"
    styles["Heading2"].fontName = "DejaVuSans-Bold"
    styles["Heading3"].fontName = "DejaVuSans-Bold"

    elements = []

    # Invoice heading.
    elements.append(Paragraph("VERDÉ", styles["Title"]))
    elements.append(Paragraph("INVOICE", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    # Order information.
    customer_name = (
        order.user.full_name
        if order.user
        else "Guest"
    )

    order_info = [
        ["Order Number", str(order.order_number)],
        ["Order Date", order.created_at.strftime("%d %b %Y")],
        ["Status", str(order.status)],
        ["Customer", str(customer_name)],
        ["Delivery Method", str(order.delivery_method)],
        ["Payment Method", str(order.payment_method)],
    ]

    info_table = Table(
        order_info,
        colWidths=[45 * mm, 125 * mm],
    )

    info_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("FONTNAME", (0, 0), (0, -1), "DejaVuSans-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # Shipping address.
    elements.append(
        Paragraph("Shipping Address", styles["Heading3"])
    )

    if order.address:
        address = order.address

        address_fields = [
            getattr(address, "full_name", None),
            getattr(address, "address_line", None),
            getattr(address, "city", None),
            getattr(address, "state", None),
            getattr(address, "pincode", None),
            getattr(address, "phone", None),
        ]

        address_text = "<br/>".join(
            str(value)
            for value in address_fields
            if value
        )

        if address_text:
            elements.append(
                Paragraph(address_text, styles["Normal"])
            )

    elements.append(Spacer(1, 15))

    # Order items.
    elements.append(Paragraph("Items", styles["Heading3"]))

    item_rows = [
        ["Product", "Qty", "Unit Price", "Total", "Status"]
    ]

    for item in order.items.all():
        product_name = str(item.product_name)

        # Add pot variant details when available.
        if item.product_variant:
            variant_parts = [
                item.product_variant.color,
                item.product_variant.size,
            ]

            variant_text = " / ".join(
                str(value)
                for value in variant_parts
                if value
            )

            if variant_text:
                product_name = f"{product_name} ({variant_text})"

        item_rows.append([
            product_name,
            str(item.quantity),
            f"₹{item.unit_price:.2f}",
            f"₹{item.total_price:.2f}",
            str(item.item_status),
        ])

    items_table = Table(
        item_rows,
        colWidths=[
            70 * mm,
            15 * mm,
            30 * mm,
            30 * mm,
            25 * mm,
        ],
        repeatRows=1,
    )

    items_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0E8")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(items_table)
    elements.append(Spacer(1, 15))

    # Payment summary.
    elements.append(
        Paragraph("Payment Summary", styles["Heading3"])
    )

    summary_rows = [
        ["Subtotal", f"₹{order.subtotal:.2f}"],
        ["Discount", f"₹{order.discount_amount:.2f}"],
        ["Shipping", f"₹{order.shipping_amount:.2f}"],
        ["Tax", f"₹{order.tax_amount:.2f}"],
        ["Total Amount", f"₹{order.total_amount:.2f}"],
    ]

    summary_table = Table(
        summary_rows,
        colWidths=[120 * mm, 50 * mm],
    )

    summary_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
            ("FONTNAME", (0, -1), (-1, -1), "DejaVuSans-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(summary_table)

    # Generate the PDF.
    document.build(elements)
    buffer.seek(0)

    # Return the invoice as a downloadable PDF.
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"{order.order_number}.pdf",
        content_type="application/pdf",
    )

