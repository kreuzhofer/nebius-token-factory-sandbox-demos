"""Validate checked-in demo assets, or list a profile without extra dependencies."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', metavar='PROFILE', help='Print absolute input paths for a manifest profile')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    records = {r['input_id']: r for r in manifest['inputs']}
    assert len(records) == len(manifest['inputs'])
    if args.list:
        if args.list not in manifest['profiles']:
            parser.error('Choose a profile: ' + ', '.join(manifest['profiles']))
        for rid in manifest['profiles'][args.list]:
            print(ROOT / records[rid]['path'])
        return

    from PIL import Image
    from pypdf import PdfReader
    import pypdfium2 as pdfium

    assert Counter(r['kind'] for r in records.values()) == {'public': 4, 'synthetic': 8, 'variant': 6}
    assert len({r['source_receipt_id'] for r in records.values()}) == 12
    assert len(manifest['profiles']['base']) == 12
    assert len(manifest['profiles']['demo']) == 14
    assert set(manifest['profiles']['all']) == set(records)
    expected_files = {r['path'] for r in records.values()}
    assert expected_files == {p.relative_to(ROOT).as_posix() for p in (ROOT / 'inputs').iterdir() if p.is_file()}
    for profile in manifest['profiles'].values():
        assert len(profile) == len(set(profile)) and set(profile) <= set(records)
    for row in records.values():
        path = ROOT / row['path']
        raw = path.read_bytes()
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], path
        if row.get('deliberately_corrupt'):
            try:
                document = pdfium.PdfDocument(path)
            except pdfium.PdfiumError:
                pass
            else:
                document.close()
                raise AssertionError('Corrupt fixture unexpectedly opened')
        elif path.suffix == '.pdf':
            reader = PdfReader(path)
            assert len(reader.pages) == row['page_count'] == 2
            with pdfium.PdfDocument(path) as document:
                for page_number, page in enumerate(reader.pages):
                    text = page.extract_text()
                    assert 'SYNTHETIC DEMO' in text and row['input_id'].upper() in text
                    assert f'Page {page_number + 1} of 2' in text
                    rendered_page = document[page_number]
                    bitmap = rendered_page.render(scale=1)
                    assert bitmap.width > 0 and bitmap.height > 0
                    bitmap.close()
                    rendered_page.close()
        else:
            with Image.open(path) as picture:
                picture.load()
                assert picture.size == (row['width'], row['height'])
        if row['kind'] == 'variant':
            assert row['source_receipt_id'] == row['derived_from'] == 's08'

    def pixels(rid):
        with Image.open(ROOT / records[rid]['path']) as picture:
            return picture.convert('RGB').tobytes()

    assert records['s08']['sha256'] == records['v01']['sha256']
    assert records['s08']['sha256'] != records['v02']['sha256']
    assert pixels('s08') == pixels('v02')
    assert (records['v03']['width'], records['v03']['height']) == (records['s08']['height'], records['s08']['width'])

    sources = json.loads((ROOT / 'synthetic-sources.json').read_text())
    expected = json.loads((ROOT / 'expected-behaviors.json').read_text())['synthetic']
    for source in sources:
        rid = source['id']
        value = Decimal(source['source_total'])
        components = sum(map(Decimal, source['source_components']))
        if rid == 's05':
            assert components == Decimal('20.00') and value == Decimal('25.00')
            assert expected[rid]['outcome'] == 'flagged'
        else:
            assert components == value
        if rid == 's04':
            assert expected[rid]['signed_total'] is None
            assert all(value not in ('42.50', '42,50') for page in source['pages'] for _, value in page)
        else:
            sign = -1 if source['type'] == 'refund' else 1
            assert Decimal(expected[rid]['signed_total']) == sign * value
    assert Decimal(expected['s07']['included_tax_total']) == Decimal('0.70') + Decimal('1.90')
    print('OK: 12 receipts + 6 variants; hashes, image decoding, PDF text/rendering, expected corruption, duplicate identity and synthetic arithmetic checked.')


if __name__ == '__main__':
    main()
