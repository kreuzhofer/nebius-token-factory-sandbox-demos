"""Generate the compact expense summary and an appendix retaining every original."""

from collections import Counter
from io import BytesIO
from math import ceil
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class AppendixHeading(Paragraph):
    def __init__(self, text, style, receipt_id):
        super().__init__(text, style)
        self.receipt_id = receipt_id


class ReportDocument(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, AppendixHeading):
            self.appendix_pages[flowable.receipt_id] = self.page


def write_pdf(report, path):
    font_dir = Path(reportlab.__file__).parent / "fonts"
    if "ReceiptSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("ReceiptSans", str(font_dir / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("ReceiptBold", str(font_dir / "VeraBd.ttf")))
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle("Receipt", fontName="ReceiptSans", fontSize=9, leading=13, spaceAfter=5)
    )
    styles.add(ParagraphStyle("SmallReceipt", parent=styles["Receipt"], fontSize=7, leading=10))
    styles.add(
        ParagraphStyle(
            "ReceiptTitle", fontName="ReceiptBold", fontSize=20, leading=25, spaceAfter=12
        )
    )
    styles.add(
        ParagraphStyle(
            "ReceiptHeading", fontName="ReceiptBold", fontSize=12, leading=17, spaceAfter=10
        )
    )

    def p(value, small=False):
        return Paragraph(
            escape(str(value if value is not None else "Unknown")).replace("\n", "<br/>"),
            styles["SmallReceipt" if small else "Receipt"],
        )

    def footer(canvas, doc):
        canvas.setFont("ReceiptSans", 8)
        canvas.setFillColor(colors.HexColor("#526174"))
        canvas.drawString(36, 22, "Expense report")
        canvas.drawRightString(A4[0] - 36, 22, str(doc.page))

    appendix_pages = {}
    # Two passes give the summary real appendix page references without fixed pagination.
    for _ in range(2):
        doc = ReportDocument(
            str(path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title="Receipt expense report",
        )
        doc.appendix_pages = {}
        story = [
            Paragraph("Expense report", styles["ReceiptTitle"]),
            p("Run finished: " + report.status.replace("_", " ")),
        ]
        counts = Counter(entry.outcome for entry in report.entries)
        story.append(
            p(
                f"{len(report.entries)} inputs | "
                + " | ".join(
                    f"{counts[key]} {key}" for key in ("included", "flagged", "duplicate", "error")
                )
            )
        )
        if report.totals:
            for currency, amount in report.totals.items():
                story.append(Paragraph(escape(f"{currency} {amount}"), styles["ReceiptHeading"]))
        else:
            story.append(
                p(
                    "No confirmed expenses. Excluded amounts may be unknown; this is not a verified zero total."
                )
            )
        story.append(
            p(
                "Totals include signed refunds and exclude flagged, duplicate, and failed inputs. "
                "Currencies are kept separate.",
                True,
            )
        )
        rows = [
            [
                p(value, True)
                for value in ("Input / merchant", "Signed amount", "Outcome / reason", "Appendix")
            ]
        ]
        for entry, receipt in zip(report.entries, report.receipts, strict=True):
            amount = f"{entry.currency or '?'} {entry.signed_amount or 'Unknown'}"
            rows.append(
                [
                    p(f"{entry.source}\n{receipt.merchant or 'Unknown merchant'}", True),
                    p(amount, True),
                    p(
                        entry.outcome + ("\n" + "; ".join(entry.reasons) if entry.reasons else ""),
                        True,
                    ),
                    p("p. " + str(appendix_pages.get(entry.receipt_id, "?")), True),
                ]
            )
        table = Table(rows, colWidths=[162, 76, 229, 56], repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd3dd")),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([Spacer(1, 8), table])
        for entry, receipt in zip(report.entries, report.receipts, strict=True):
            story.append(PageBreak())
            story.append(
                AppendixHeading(
                    escape(receipt.source), styles["ReceiptHeading"], receipt.receipt_id
                )
            )
            story.append(
                p(entry.outcome + (" - " + "; ".join(entry.reasons) if entry.reasons else ""))
            )
            story.append(
                p(
                    f"Merchant: {receipt.merchant or 'Unknown'} | Date: {receipt.transaction_date or receipt.date_text or 'Unknown'}"
                )
            )
            story.append(
                p(
                    f"Currency: {receipt.currency or 'Unknown'} | Type: {receipt.transaction_type or 'Unknown'} | "
                    f"Printed total: {receipt.printed_total or 'Unknown'} | Signed total: {entry.signed_amount or 'Unknown'}"
                )
            )
            for label, details in (
                ("Items", receipt.line_items),
                ("Tax", receipt.taxes),
                ("Discounts", receipt.discounts),
            ):
                if details:
                    story.append(
                        p(
                            label
                            + ": "
                            + "; ".join(
                                f"{item.description}: {item.amount or 'Unknown'}"
                                for item in details
                            ),
                            True,
                        )
                    )
            if receipt.issues:
                story.append(p("Issues: " + "; ".join(receipt.issues), True))
            if receipt.credit:
                story.append(p("Source credit: " + receipt.credit, True))
            if not receipt.rendered_pages:
                story.append(
                    p(
                        "Original could not be rendered. "
                        + (receipt.error or "No readable pages available.")
                    )
                )
            for page_number, rendered in enumerate(receipt.rendered_pages, 1):
                with PILImage.open(rendered) as original:
                    # Preserve full-width readability on long till receipts by splitting vertically.
                    width = min(500, original.width * 0.55)
                    if original.height / original.width <= 2.5:
                        width = min(width, 560 * original.width / original.height)
                    scale = width / original.width
                    strips = max(1, ceil(original.height * scale / 560))
                    strip_height = ceil(original.height / strips)
                    for top in range(0, original.height, strip_height):
                        crop = original.crop(
                            (0, top, original.width, min(top + strip_height, original.height))
                        )
                        buffer = BytesIO()
                        crop.save(buffer, format="PNG")
                        buffer.seek(0)
                        story.append(
                            KeepTogether(
                                [
                                    p(
                                        f"Original page {page_number}"
                                        + (" (continued)" if top else ""),
                                        True,
                                    ),
                                    Image(
                                        buffer,
                                        width=width,
                                        height=crop.height * scale,
                                        hAlign="LEFT",
                                    ),
                                ]
                            )
                        )
                        story.append(Spacer(1, 10))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        appendix_pages = doc.appendix_pages


def write_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_pdf(report, directory / "report.pdf")
    (directory / "report.json").write_text(report.model_dump_json(indent=2))
    return {name: directory / name for name in ("report.json", "report.pdf")}
