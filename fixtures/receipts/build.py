"""Rebuild synthetic receipts/variants and manifest; never modify public originals."""

import hashlib
import io
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
WIDTH, HEIGHT = 300, 430


def receipt_pdf(spec, hide_merchant=False):
    """Render only visible evidence, never hidden source values or expectations."""
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(WIDTH, HEIGHT), invariant=1, pageCompression=1)
    pdf.setTitle("Synthetic demo receipt " + spec["id"])
    pdf.setAuthor("Nebius sandbox demo project")
    for number, lines in enumerate(spec["pages"], start=1):
        pdf.setFont("Courier-Bold", 10)
        pdf.drawCentredString(WIDTH / 2, HEIGHT - 25, "SYNTHETIC DEMO - NOT A REAL PURCHASE")
        pdf.setFont("Courier-Bold", 13)
        if hide_merchant:
            pdf.setFillGray(0.8)
            pdf.rect(40, HEIGHT - 65, WIDTH - 80, 18, fill=1, stroke=0)
            pdf.setFillGray(0)
        else:
            pdf.drawCentredString(WIDTH / 2, HEIGHT - 60, spec["merchant"])
        pdf.setFont("Courier", 10)
        pdf.drawString(20, HEIGHT - 86, "Receipt: " + spec["id"].upper())
        pdf.drawString(20, HEIGHT - 103, "Date: " + spec["date"])
        pdf.drawString(20, HEIGHT - 120, "Currency: " + spec["currency"])
        pdf.line(20, HEIGHT - 135, WIDTH - 20, HEIGHT - 135)
        y = HEIGHT - 160
        for label, value in lines:
            pdf.setFont(
                "Courier-Bold" if label.startswith(("TOTAL", "SUMME", "REFUND")) else "Courier", 10
            )
            assert stringWidth(label, "Courier-Bold", 10) <= WIDTH - 40
            if value:
                assert stringWidth(label, "Courier-Bold", 10) + 12 <= WIDTH - 40 - 78
            pdf.drawString(20, y, label)
            if value == "[unreadable]":
                # Solid damage replaces the value; there is no concealed PDF text.
                pdf.rect(WIDTH - 95, y - 3, 75, 13, fill=1, stroke=0)
            else:
                pdf.drawRightString(WIDTH - 20, y, value)
            y -= 25
        assert y >= 55, "Receipt content overlaps footer"
        pdf.setFont("Courier", 9)
        pdf.drawCentredString(
            WIDTH / 2, 35, f"Page {number} of {len(spec['pages'])} - {spec['id'].upper()}"
        )
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def raster(pdf_bytes):
    with pdfium.PdfDocument(pdf_bytes) as document:
        page = document[0]
        bitmap = page.render(scale=3)
        result = bitmap.to_pil().convert("RGB").copy()
        bitmap.close()
        page.close()
        return result


def file_record(input_id, receipt_id, path, kind, language, coverage, **extra):
    raw = path.read_bytes()
    if extra.get("deliberately_corrupt"):
        dimensions = {"page_count": None}
    elif path.suffix == ".pdf":
        with pdfium.PdfDocument(path) as doc:
            dimensions = {"page_count": len(doc), "pdf_kind": "native_text"}
    else:
        with Image.open(path) as image:
            dimensions = {"page_count": 1, "width": image.width, "height": image.height}
    return {
        "input_id": input_id,
        "source_receipt_id": receipt_id,
        "path": path.relative_to(ROOT).as_posix(),
        "kind": kind,
        "language": language,
        "coverage": coverage,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        **dimensions,
        **extra,
    }


def main():
    INPUTS.mkdir(exist_ok=True)
    records = []
    public = json.loads((ROOT / "public-sources.json").read_text())
    coverage = {
        "r01": ["photograph", "low_resolution"],
        "r02": ["scan", "vat_adjustment"],
        "r03": ["scan", "cashier_redacted", "merchant_visible"],
        "r04": ["photograph", "dual_currency_display"],
    }
    for source in public:
        path = ROOT / source["file"]
        assert hashlib.sha1(path.read_bytes()).hexdigest() == source["source_sha1"]
        records.append(
            file_record(
                source["receipt_id"],
                source["receipt_id"],
                path,
                "public",
                source["language"],
                coverage[source["receipt_id"]],
                provenance="public-sources.json#" + source["receipt_id"],
            )
        )
    specs = json.loads((ROOT / "synthetic-sources.json").read_text())
    for spec in specs:
        path = INPUTS / spec["file"]
        content = receipt_pdf(spec)
        if path.suffix == ".pdf":
            path.write_bytes(content)
        else:
            picture = raster(content)
            if path.suffix == ".jpg":
                picture.save(path, quality=92, subsampling=0)
            else:
                picture.save(path, compress_level=9)
        records.append(
            file_record(
                spec["id"],
                spec["id"],
                path,
                "synthetic",
                spec["language"],
                spec["coverage"],
                provenance="synthetic-sources.json#" + spec["id"],
            )
        )

    control = next(s for s in specs if s["id"] == "s08")
    source = INPUTS / control["file"]
    with Image.open(source) as original:
        picture = original.convert("RGB")
    variants = [
        ("v01", "v01-control-exact-copy.png", ["exact_duplicate"], "Byte-identical copy of s08."),
        (
            "v02",
            "v02-control-reencoded.png",
            ["reencoded_duplicate"],
            "PNG compression level 0; decoded pixels equal s08.",
        ),
        ("v03", "v03-control-rotated.png", ["rotation"], "Rotate s08 clockwise by 90 degrees."),
        ("v04", "v04-control-blurred.jpg", ["blur"], "Gaussian blur radius 2; JPEG quality 65."),
        (
            "v05",
            "v05-control-corrupt.pdf",
            ["corrupt_file"],
            "Deliberately truncated PDF with no document structure.",
        ),
        (
            "v06",
            "v06-control-missing-merchant.png",
            ["missing_merchant"],
            "Render s08 with its merchant heading masked; other visible values preserved.",
        ),
    ]
    for vid, name, tags, transformation in variants:
        path = INPUTS / name
        if vid == "v01":
            path.write_bytes(source.read_bytes())
        elif vid == "v02":
            picture.save(path, compress_level=0)
        elif vid == "v03":
            picture.transpose(Image.Transpose.ROTATE_270).save(path)
        elif vid == "v04":
            picture.filter(ImageFilter.GaussianBlur(2)).save(path, quality=65)
        elif vid == "v05":
            path.write_bytes(b"%PDF-1.7\n% Deliberately corrupt demo fixture derived from s08.\n")
        else:
            raster(receipt_pdf(control, hide_merchant=True)).save(path)
        records.append(
            file_record(
                vid,
                "s08",
                path,
                "variant",
                "en",
                tags,
                derived_from="s08",
                transformation=transformation,
                deliberately_corrupt=(vid == "v05"),
            )
        )
    manifest = {
        "fixture_version": "1",
        "purpose": "Demo inputs, not benchmark annotations; never send source definitions to extraction agents.",
        "profiles": {
            "base": [r["input_id"] for r in records if r["kind"] != "variant"],
            "demo": [r["input_id"] for r in records if r["kind"] != "variant"] + ["v01", "v05"],
            "all": [r["input_id"] for r in records],
            "minimal": ["s08", "s04", "v05"],
            "duplicates": ["s08", "v01", "v02"],
            "missing_merchant": ["v06"],
        },
        "inputs": records,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    expected = {
        "schema_version": "1",
        "scope": "Lightweight intended behaviors; no model run or accuracy claim.",
        "synthetic": {
            s["id"]: {"currency": s["currency"], "transaction_type": s["type"], **s["expected"]}
            for s in specs
        },
        "variants": {
            "v01": "Count once with s08, retaining both source entries.",
            "v02": "Decoded-pixel duplicate of s08; count this receipt once in the duplicates profile.",
            "v03": "Exercise orientation handling; no promised model result.",
            "v04": "Exercise degraded-image handling; no promised model result.",
            "v05": "Document error; continue processing and include a failure entry.",
            "v06": "In isolation merchant is null with a reason; known total may still be included.",
        },
        "public": {
            "r01": "Do not invent a date outside the cropped evidence.",
            "r02": "Distinguish the pre-adjustment subtotal from the final payable total.",
            "r03": "Merchant is visible; the cashier name is masked.",
            "r04": "CHF is payable; the displayed EUR equivalent is not a second expense.",
        },
    }
    (ROOT / "expected-behaviors.json").write_text(json.dumps(expected, indent=2) + "\n")
    print(
        f"Built {len(specs)} synthetic receipts, {len(variants)} variants; {len(records)} total inputs."
    )


if __name__ == "__main__":
    main()
