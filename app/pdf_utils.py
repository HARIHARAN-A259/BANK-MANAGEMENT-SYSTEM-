"""
pdf_utils.py — PDF generation for Cashio Security
  • ATM Card PDF  (85.6 mm × 54 mm — ISO/IEC 7810 ID-1 card size)
  • Transaction Receipt PDF
  • Account Statement PDF

Uses reportlab. Output goes to relative paths:
  output/cards/        → ATM card PDFs
  output/receipts/     → receipt PDFs
  output/statements/   → statement PDFs
"""

import os
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Base output directories (relative to project root)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DIR = os.path.join(BASE_DIR, "output", "cards")
RECEIPTS_DIR = os.path.join(BASE_DIR, "output", "receipts")
STATEMENTS_DIR = os.path.join(BASE_DIR, "output", "statements")

for d in (CARDS_DIR, RECEIPTS_DIR, STATEMENTS_DIR):
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
NAVY = HexColor("#0A1931")          # card background
GOLD = HexColor("#D4AF37")          # heading colour
WHITE = HexColor("#FFFFFF")
LIGHT_GREY = HexColor("#F0F0F0")
DARK_GREY = HexColor("#555555")
STRIPE_BLACK = HexColor("#1A1A1A")  # magnetic stripe


# ===========================================================================
# ATM Card PDF
# ===========================================================================

CARD_W = 85.6 * mm
CARD_H = 54.0 * mm

def generate_card_pdf(
    account_number: str,
    card_number: str,          # Full 16-digit number (shown ONLY in this owner PDF)
    card_expiry: str,          # MM/YY
    holder_name: str,          # Already UPPERCASE
    cvv: str,                  # Shown masked on back (***) — do NOT print plain CVV
) -> str:
    """
    Generate the ATM card PDF with FRONT and BACK on a single A4 page.
    Returns the absolute file path of the saved PDF.
    """
    filename = f"card_{account_number}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    filepath = os.path.join(CARDS_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    page_w, page_h = A4

    # ---- Helper to draw rounded rectangle ----
    def rounded_rect(x, y, w, h, r, fill_color, stroke_color=None):
        c.setFillColor(fill_color)
        if stroke_color:
            c.setStrokeColor(stroke_color)
            c.setLineWidth(1)
        else:
            c.setStrokeColor(fill_color)
        c.roundRect(x, y, w, h, r, fill=1, stroke=1 if stroke_color else 0)

    # ==== FRONT FACE ====
    front_x = (page_w - CARD_W) / 2
    front_y = page_h - 30 * mm - CARD_H

    # Card background — navy blue
    rounded_rect(front_x, front_y, CARD_W, CARD_H, 5 * mm, NAVY, WHITE)

    # Bank name — gold, top left
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(front_x + 8 * mm, front_y + CARD_H - 10 * mm, "CASHIO SECURITY")

    # "DEBIT" label — top right
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(front_x + CARD_W - 6 * mm, front_y + CARD_H - 10 * mm, "DEBIT")

    # Chip rectangle — gold, top-left area
    chip_x = front_x + 8 * mm
    chip_y = front_y + CARD_H - 24 * mm
    rounded_rect(chip_x, chip_y, 12 * mm, 9 * mm, 1.5 * mm, GOLD)
    # Chip lines
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.5)
    c.line(chip_x + 4 * mm, chip_y, chip_x + 4 * mm, chip_y + 9 * mm)
    c.line(chip_x + 8 * mm, chip_y, chip_x + 8 * mm, chip_y + 9 * mm)
    c.line(chip_x, chip_y + 3 * mm, chip_x + 12 * mm, chip_y + 3 * mm)
    c.line(chip_x, chip_y + 6 * mm, chip_x + 12 * mm, chip_y + 6 * mm)

    # Simple network logo (two overlapping circles, top-right)
    logo_cx = front_x + CARD_W - 14 * mm
    logo_cy = front_y + CARD_H - 20 * mm
    c.setFillColor(colors.orange)
    c.setStrokeColor(colors.transparent)
    c.circle(logo_cx - 4 * mm, logo_cy, 5 * mm, fill=1)
    c.setFillColor(colors.red)
    c.circle(logo_cx + 1 * mm, logo_cy, 5 * mm, fill=1)

    # Card number in groups of 4
    grouped = " ".join(card_number[i:i+4] for i in range(0, 16, 4))
    c.setFillColor(WHITE)
    c.setFont("Courier-Bold", 13)
    c.drawString(front_x + 8 * mm, front_y + 17 * mm, grouped)

    # VALID THRU
    c.setFont("Helvetica", 5)
    c.setFillColor(GOLD)
    c.drawString(front_x + 8 * mm, front_y + 11 * mm, "VALID")
    c.drawString(front_x + 8 * mm, front_y + 8.5 * mm, "THRU")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawString(front_x + 15 * mm, front_y + 9 * mm, card_expiry)

    # Holder name
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(WHITE)
    c.drawString(front_x + 8 * mm, front_y + 4 * mm, holder_name[:25])

    # ==== FRONT label ====
    c.setFillColor(DARK_GREY)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w / 2, front_y - 6 * mm, "▲  FRONT FACE  ▲")

    # ==== BACK FACE ====
    back_y = front_y - 25 * mm - CARD_H

    rounded_rect(front_x, back_y, CARD_W, CARD_H, 5 * mm, NAVY, WHITE)

    # Magnetic stripe (top black band)
    stripe_y = back_y + CARD_H - 14 * mm
    c.setFillColor(STRIPE_BLACK)
    c.rect(front_x, stripe_y, CARD_W, 10 * mm, fill=1, stroke=0)

    # Signature panel (white strip)
    sig_y = back_y + CARD_H - 27 * mm
    c.setFillColor(WHITE)
    c.rect(front_x + 8 * mm, sig_y, CARD_W - 25 * mm, 7 * mm, fill=1, stroke=0)

    # Signature lines on the panel
    c.setStrokeColor(LIGHT_GREY)
    c.setLineWidth(0.3)
    for i in range(1, 4):
        c.line(front_x + 8 * mm, sig_y + i * 1.75 * mm, front_x + CARD_W - 17 * mm, sig_y + i * 1.75 * mm)

    # CVV box — masked (never print plain CVV)
    cvv_box_x = front_x + CARD_W - 16 * mm
    c.setFillColor(WHITE)
    c.rect(cvv_box_x, sig_y, 8 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(DARK_GREY)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(cvv_box_x + 1 * mm, sig_y + 3 * mm, "CVV")
    c.setFont("Courier-Bold", 8)
    c.setFillColor(colors.black)
    c.drawString(cvv_box_x + 1 * mm, sig_y + 0.5 * mm, "***")

    # Customer care line
    c.setFillColor(GOLD)
    c.setFont("Helvetica", 6)
    c.drawString(front_x + 8 * mm, back_y + 10 * mm, "Customer Care: 1800-CASHIO-00  |  support@cashiosecurity.in")

    # Property line
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Oblique", 6)
    c.drawString(front_x + 8 * mm, back_y + 5 * mm, "This card is property of Cashio Security.")

    # ==== BACK label ====
    c.setFillColor(DARK_GREY)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w / 2, back_y - 6 * mm, "▲  BACK FACE  ▲")

    # Page title
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(page_w / 2, page_h - 18 * mm, "CASHIO SECURITY — ATM Debit Card")
    c.setFont("Helvetica", 9)
    c.setFillColor(DARK_GREY)
    c.drawCentredString(page_w / 2, page_h - 24 * mm, f"Account: {account_number}  |  Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC")

    # Confidentiality notice
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.red)
    c.drawCentredString(page_w / 2, 15 * mm,
        "⚠  CONFIDENTIAL — This document contains sensitive card information. Keep it secure.")

    c.save()
    return filepath


# ===========================================================================
# Receipt PDF
# ===========================================================================

def generate_receipt_pdf(
    txn_id: str,
    account_number: str,
    holder_name: str,
    txn_type: str,
    amount_paise: int,
    balance_after_paise: int,
    timestamp: str,
    status: str,
    remark: Optional[str] = None,
    to_account: Optional[str] = None,
) -> str:
    """Generate a receipt PDF and return its file path."""
    filename = f"receipt_{txn_id}_{account_number}.pdf"
    filepath = os.path.join(RECEIPTS_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=(105 * mm, 148 * mm))  # A6 size
    pw, ph = 105 * mm, 148 * mm

    def rupees(paise: int) -> str:
        return f"Rs. {paise / 100:,.2f}"

    # Header band
    c.setFillColor(NAVY)
    c.rect(0, ph - 30 * mm, pw, 30 * mm, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(pw / 2, ph - 13 * mm, "CASHIO SECURITY")

    c.setFillColor(WHITE)
    c.setFont("Helvetica", 7)
    c.drawCentredString(pw / 2, ph - 19 * mm, "Advanced Bank Management System")
    c.drawCentredString(pw / 2, ph - 24 * mm, "support@cashiosecurity.in  |  1800-CASHIO-00")

    # Title
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(pw / 2, ph - 38 * mm, "TRANSACTION RECEIPT")

    # Divider
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(10 * mm, ph - 41 * mm, pw - 10 * mm, ph - 41 * mm)

    # Fields
    fields = [
        ("Transaction ID", txn_id),
        ("Account Number", account_number),
        ("Account Holder", holder_name.upper()),
        ("Transaction Type", txn_type.replace("_", " ")),
        ("Amount", rupees(amount_paise)),
        ("Balance After", rupees(balance_after_paise)),
        ("Date & Time", timestamp),
        ("Status", status),
    ]
    if to_account:
        fields.insert(5, ("To Account", to_account))
    if remark:
        fields.append(("Remark", remark))

    y = ph - 48 * mm
    for label, value in fields:
        c.setFillColor(DARK_GREY)
        c.setFont("Helvetica", 8)
        c.drawString(10 * mm, y, label + ":")
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(50 * mm, y, str(value))
        y -= 8 * mm

    # Status colour box
    status_color = HexColor("#27AE60") if status == "SUCCESS" else HexColor("#E74C3C")
    c.setFillColor(status_color)
    c.roundRect(10 * mm, y - 4 * mm, pw - 20 * mm, 10 * mm, 2 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(pw / 2, y + 0.5 * mm, f"Transaction {status}")

    # Footer
    c.setFillColor(DARK_GREY)
    c.setFont("Helvetica-Oblique", 6)
    c.drawCentredString(pw / 2, 10 * mm, "Thank you for banking with Cashio Security.")
    c.drawCentredString(pw / 2, 6 * mm, f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC")

    c.save()
    return filepath


# ===========================================================================
# Statement PDF
# ===========================================================================

def generate_statement_pdf(
    account_number: str,
    holder_name: str,
    email: Optional[str],
    transactions: list,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_balance_paise: int = 0,
) -> str:
    """Generate an account statement PDF and return its file path."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"statement_{account_number}_{ts}.pdf"
    filepath = os.path.join(STATEMENTS_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    pw, ph = A4

    def rupees(paise: int) -> str:
        return f"Rs. {paise / 100:,.2f}"

    def new_page():
        c.showPage()
        _draw_header()
        return ph - 55 * mm

    def _draw_header():
        # Header band
        c.setFillColor(NAVY)
        c.rect(0, ph - 40 * mm, pw, 40 * mm, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(15 * mm, ph - 18 * mm, "CASHIO SECURITY")
        c.setFillColor(WHITE)
        c.setFont("Helvetica", 9)
        c.drawString(15 * mm, ph - 25 * mm, "Advanced Bank Management System")
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(pw - 15 * mm, ph - 18 * mm, "ACCOUNT STATEMENT")
        c.setFont("Helvetica", 8)
        c.drawRightString(pw - 15 * mm, ph - 25 * mm, f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC")

        # Account info band
        c.setFillColor(LIGHT_GREY)
        c.rect(0, ph - 55 * mm, pw, 15 * mm, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(15 * mm, ph - 46 * mm, f"Account: {account_number}")
        c.drawString(15 * mm, ph - 51 * mm, f"Holder:  {holder_name.upper()}")
        c.setFont("Helvetica", 9)
        period = f"{from_date or 'Beginning'} to {to_date or 'Today'}"
        c.drawRightString(pw - 15 * mm, ph - 46 * mm, f"Period: {period}")
        c.drawRightString(pw - 15 * mm, ph - 51 * mm, f"Balance: {rupees(current_balance_paise)}")

    _draw_header()

    # Column positions
    col_date  = 15 * mm
    col_txnid = 48 * mm
    col_type  = 80 * mm
    col_dr    = 120 * mm
    col_cr    = 145 * mm
    col_bal   = 170 * mm

    y = ph - 62 * mm

    # Table header
    c.setFillColor(NAVY)
    c.rect(10 * mm, y - 1 * mm, pw - 20 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(col_date, y + 1 * mm, "DATE & TIME")
    c.drawString(col_txnid, y + 1 * mm, "TXN ID")
    c.drawString(col_type, y + 1 * mm, "TYPE")
    c.drawString(col_dr, y + 1 * mm, "DEBIT (Rs.)")
    c.drawString(col_cr, y + 1 * mm, "CREDIT (Rs.)")
    c.drawString(col_bal, y + 1 * mm, "BALANCE (Rs.)")

    y -= 8 * mm

    if not transactions:
        c.setFillColor(DARK_GREY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(pw / 2, y, "No transactions found for the selected period.")
    else:
        for i, txn in enumerate(transactions):
            if y < 25 * mm:
                y = new_page()
                y -= 5 * mm

            row_color = LIGHT_GREY if i % 2 == 0 else WHITE
            c.setFillColor(row_color)
            c.rect(10 * mm, y - 1 * mm, pw - 20 * mm, 6.5 * mm, fill=1, stroke=0)

            # Determine debit / credit columns
            credit_types = {"DEPOSIT", "TRANSFER_IN", "INTEREST"}
            debit_types  = {"WITHDRAW", "TRANSFER_OUT"}

            amt_str = f"{txn.amount / 100:,.2f}"

            c.setFillColor(colors.black)
            c.setFont("Helvetica", 7)
            ts_short = txn.timestamp[:16].replace("T", " ")
            c.drawString(col_date, y + 1 * mm, ts_short)
            c.drawString(col_txnid, y + 1 * mm, txn.txn_id)
            c.drawString(col_type, y + 1 * mm, txn.type.replace("_", " "))

            if txn.type in debit_types:
                c.setFillColor(HexColor("#C0392B"))
                c.drawString(col_dr, y + 1 * mm, amt_str)
            elif txn.type in credit_types:
                c.setFillColor(HexColor("#27AE60"))
                c.drawString(col_cr, y + 1 * mm, amt_str)
            else:
                c.setFillColor(DARK_GREY)
                c.drawString(col_dr, y + 1 * mm, "-")

            c.setFillColor(colors.black)
            c.drawString(col_bal, y + 1 * mm, f"{txn.balance_after / 100:,.2f}")

            y -= 7 * mm

    # Footer
    c.setFillColor(NAVY)
    c.rect(0, 0, pw, 15 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(pw / 2, 7 * mm, "This is a computer-generated statement. Cashio Security — Advanced Bank Management System")
    c.drawCentredString(pw / 2, 3 * mm, "support@cashiosecurity.in  |  1800-CASHIO-00  |  www.cashiosecurity.in")

    c.save()
    return filepath

