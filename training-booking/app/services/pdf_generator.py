import io
import os
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False


def _reshape(text: str) -> str:
    if not text:
        return text
    if HAS_BIDI:
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text
    return text


def _register_font():
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("DejaVu", fp))
                return "DejaVu"
            except Exception:
                pass
    return "Helvetica"


FONT_NAME = _register_font()


def generate_attendance_pdf(session, bookings: List, logo_path: Optional[str] = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    story = []
    styles = getSampleStyleSheet()
    rtl_style = ParagraphStyle("rtl", parent=styles["Normal"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=11)
    title_style = ParagraphStyle("title", parent=styles["Title"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=16, spaceAfter=6)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=10, textColor=colors.grey)

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=40*mm, height=15*mm)
            story.append(img)
            story.append(Spacer(1, 4*mm))
        except Exception:
            pass

    story.append(Paragraph(_reshape(session.title), title_style))
    date_str = session.session_date.strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(_reshape(f"תאריך: {date_str}"), rtl_style))
    if session.location:
        story.append(Paragraph(_reshape(f"מיקום: {session.location}"), rtl_style))
    instructor_name = ""
    if session.instructor:
        instructor_name = f"{session.instructor.first_name} {session.instructor.last_name}"
        story.append(Paragraph(_reshape(f"מדריך: {instructor_name}"), rtl_style))
    story.append(Paragraph(_reshape("רשימת נוכחות"), sub_style))
    story.append(Spacer(1, 6*mm))

    headers = [_reshape("#"), _reshape("שם פרטי"), _reshape("שם משפחה"), _reshape("טלפון"), _reshape("חתימה")]
    data = [headers]
    for i, booking in enumerate(bookings, 1):
        u = booking.user
        data.append([
            str(i),
            _reshape(u.first_name),
            _reshape(u.last_name),
            u.phone,
            "",
        ])

    col_widths = [10*mm, 35*mm, 35*mm, 35*mm, 55*mm]
    table = Table(data, colWidths=col_widths, rowHeights=28)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
    ])
    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 6*mm))

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(_reshape(f"הופק בתאריך: {now_str} | סה\"כ משתתפים: {len(bookings)}"), sub_style))

    doc.build(story)
    return buf.getvalue()


def generate_session_card_pdf(session, logo_path: Optional[str] = None) -> bytes:
    from reportlab.lib.pagesizes import A5
    buf = io.BytesIO()
    page_size = landscape((148*mm, 210*mm))
    doc = SimpleDocTemplate(buf, pagesize=page_size, rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    story = []
    styles = getSampleStyleSheet()
    rtl = ParagraphStyle("rtl", parent=styles["Normal"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=11)
    big_title = ParagraphStyle("bigtitle", parent=styles["Title"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=22, spaceAfter=4)
    badge_style = ParagraphStyle("badge", parent=styles["Normal"], fontName=FONT_NAME, alignment=TA_RIGHT, fontSize=10, textColor=colors.HexColor("#2563eb"))
    center = ParagraphStyle("center", parent=styles["Normal"], fontName=FONT_NAME, alignment=TA_CENTER, fontSize=9, textColor=colors.grey)

    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=50*mm, height=20*mm)
            story.append(img)
            story.append(Spacer(1, 3*mm))
        except Exception:
            pass

    # Accent line
    accent = Table([[""]], colWidths=[186*mm], rowHeights=[2])
    accent.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb"))]))
    story.append(accent)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph(_reshape(session.title), big_title))
    if session.activity_type:
        story.append(Paragraph(_reshape(f"[{session.activity_type.name}]"), badge_style))
    story.append(Spacer(1, 3*mm))

    date_str = session.session_date.strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(_reshape(f"📅 {date_str}"), rtl))
    if session.location:
        story.append(Paragraph(_reshape(f"📍 {session.location}"), rtl))
    if session.requirements:
        story.append(Paragraph(_reshape(f"✏️ {session.requirements}"), rtl))
    story.append(Paragraph(_reshape(f"👥 מקסימום משתתפים: {session.max_participants}"), rtl))
    if session.instructor:
        name = f"{session.instructor.first_name} {session.instructor.last_name}"
        story.append(Paragraph(_reshape(f"🏋️ מדריך: {name}"), rtl))

    story.append(Spacer(1, 6*mm))
    qr_table = Table([["הרשמה\nRegister"]], colWidths=[40*mm], rowHeights=[40*mm])
    qr_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(qr_table)

    doc.build(story)
    return buf.getvalue()
