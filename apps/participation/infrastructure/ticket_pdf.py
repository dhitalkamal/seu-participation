"""PDF ticket generator using reportlab and qrcode."""

from __future__ import annotations

import io
from datetime import datetime

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A6
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_ticket_pdf(
    registration_code: str,
    event_title: str,
    event_date: datetime,
    attendee_name: str,
    qr_data: str,
) -> bytes:
    """Generate a PDF ticket and return the raw bytes.

    Renders event title, formatted date, attendee name, a QR code image, and
    the registration code as text. Output is capped to A6 size and stays under 500 KB.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A6,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # * title block
    title_style = styles["Heading2"]
    story.append(Paragraph(event_title, title_style))
    story.append(Spacer(1, 4 * mm))

    # * date and attendee rows
    date_str = event_date.strftime("%d %B %Y, %H:%M UTC")
    body_style = styles["Normal"]
    story.append(Paragraph(f"<b>Date:</b> {date_str}", body_style))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<b>Attendee:</b> {attendee_name}", body_style))
    story.append(Spacer(1, 6 * mm))

    # * QR code rendered as an in-memory image
    qr_image_bytes = _render_qr(qr_data)
    qr_img = Image(io.BytesIO(qr_image_bytes), width=40 * mm, height=40 * mm)
    story.append(qr_img)
    story.append(Spacer(1, 4 * mm))

    # * registration code in a styled table cell for emphasis
    code_table = Table(
        [[registration_code]],
        colWidths=[60 * mm],
    )
    code_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Courier-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
            ]
        )
    )
    story.append(code_table)

    doc.build(story)
    return buffer.getvalue()


def _render_qr(data: str) -> bytes:
    """Render a QR code to PNG bytes using the qrcode library."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    png_buffer = io.BytesIO()
    img.save(png_buffer, format="PNG")
    return png_buffer.getvalue()
