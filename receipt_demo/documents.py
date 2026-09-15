"""Render source evidence in the receipt job, without fixture annotations."""
import hashlib
import io
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps


def prepare(path, directory):
    path, directory = Path(path), Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    raw = path.read_bytes()
    content_hash = hashlib.sha256(raw).hexdigest()
    pages = []
    pixels = hashlib.sha256()

    def save(image):
        image = ImageOps.exif_transpose(image).convert('RGB')
        if image.width * image.height > 25_000_000:
            raise ValueError('Page exceeds the demo pixel limit')
        pixels.update(f'{image.width},{image.height}:'.encode())
        pixels.update(image.tobytes())
        target = directory / f'{len(pages) + 1}.png'
        image.save(target)
        pages.append(str(target))

    if path.suffix.lower() == '.pdf':
        with pdfium.PdfDocument(raw) as document:
            if not 1 <= len(document) <= 8:
                raise ValueError('PDF must contain 1 to 8 pages')
            for page in document:
                try:
                    width, height = page.get_size()
                    if width * height * 4 > 25_000_000:
                        raise ValueError('PDF page exceeds the demo pixel limit')
                    bitmap = page.render(scale=2)
                    try:
                        save(bitmap.to_pil())
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    else:
        with Image.open(io.BytesIO(raw)) as image:
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Supply multipage documents as PDF')
            save(image)
    return pages, content_hash, pixels.hexdigest()


def inference_image(path):
    with Image.open(path) as image:
        image.thumbnail((1800, 2400))
        output = io.BytesIO()
        image.convert('RGB').save(output, format='JPEG', quality=90)
        return output.getvalue()
