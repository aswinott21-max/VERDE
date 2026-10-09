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


def generate_invoice_pdf(order):
    """
    Generate a PDF invoice using the existing Order data.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph("VERDÉ", styles["Title"]))
    elements.append(Paragraph("INVOICE", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    # Order information
    order_info = [
        ["Order Number", order.order_number],
        ["Order Date", order.created_at.strftime("%d %b %Y")],
        ["Status", order.status],
        ["Customer", order.user.full_name if order.user else "Guest"],
        ["Delivery Method", order.delivery_method],
        ["Payment Method", order.payment_method],
    ]

    table = Table(order_info, colWidths=[45 * mm, 125 * mm])

    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 10))

    # Shipping address
    elements.append(Paragraph("Shipping Address", styles["Heading3"]))

    if order.address:
        address = order.address

        address_text = "<br/>".join(
            value
            for value in [
                getattr(address, "full_name", None),
                getattr(address, "address_line", None),
                getattr(address, "city", None),
                getattr(address, "state", None),
                getattr(address, "pincode", None),
                getattr(address, "phone", None),
            ]
            if value
        )

        elements.append(Paragraph(address_text, styles["Normal"]))

    elements.append(Spacer(1, 15))

    # Items
    elements.append(Paragraph("Items", styles["Heading3"]))

    item_rows = [
        ["Product", "Qty", "Unit Price", "Total", "Status"]
    ]

    for item in order.items.all():
        product_name = item.product_name

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

        item_rows.append(
            [
                product_name,
                str(item.quantity),
                f"₹{item.unit_price:.2f}",
                f"₹{item.total_price:.2f}",
                item.item_status,
            ]
        )

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
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0E8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elements.append(items_table)
    elements.append(Spacer(1, 15))

    # Payment summary
    elements.append(Paragraph("Payment Summary", styles["Heading3"]))

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
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elements.append(summary_table)

    document.build(elements)

    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"{order.order_number}.pdf",
        content_type="application/pdf",
    )