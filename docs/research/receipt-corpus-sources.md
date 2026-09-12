# Reusable receipt corpus sources

Investigated 2026-09-12 for [Find reusable receipt sources for the shared input corpus](https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos/issues/3).

## Recommendation

Select a small, manually checked mixture of individually licensed public receipt images and user-provided redacted scans. Public candidates exist for English JPG and German PNG/JPG; this research did not establish a suitable natively multipage receipt PDF with clear redistribution terms. User scans or an explicitly documented image-to-PDF derivative can fill PDF coverage, but a converted image does not test native digital PDF text/layout. Exact selection and expected values remain a human corpus-design decision, not a decision made by this research.

## Candidate sources

| Source | Reuse evidence | Coverage and limitations |
| --- | --- | --- |
| [Family Dollar store receipt](https://commons.wikimedia.org/wiki/File:Family_Dollar_store_receipt.jpg) | Uploader Corn cheese identifies own work and CC BY-SA 3.0. | English retail JPG, 740 × 553. Low resolution warrants inspection before selecting; no structured ground truth supplied on the page. Preserve credit/license and record modifications. |
| [Fressnapf December 2020 receipt](https://commons.wikimedia.org/wiki/File:Kassenzettel_Fressnapf_mit_ausgewiesener_MwSt-Senkung_und_TSE_Transaktionsnummer_12_2020.png) | File page marks the receipt public domain as information without original authorship; scan credited to Raimond Spekking. | German PNG, 1804 × 5016, VAT reduction and TSE transaction information. Useful long-page candidate; no structured annotations supplied. This reports the publisher's rights statement, not independent legal clearance. |
| [Kassenbon.jpg](https://commons.wikimedia.org/wiki/File:Kassenbon.jpg) | File page uses a public-domain text/logo rationale; self-scanned by Lkawer. | German JPG, 952 × 2097. Current revision explicitly blanks vendor name: useful missing-merchant case, unsuitable for positive merchant scoring. Inspect before inclusion. |
| [Swiss restaurant receipt](https://commons.wikimedia.org/wiki/File:ReceiptSwiss.jpg) | Audrius Meskauskas identifies own work; offers CC BY-SA 3.0 or GFDL. | JPG, 2448 × 3264; restaurant items, two displayed currencies, and tax. Good candidate for distinguishing payable currency from a conversion display; merchant/cashier details need inspection. No full ground truth. Prefer the CC license option and retain attribution. |

File description pages are the primary provenance evidence; the Commons category page and general site footer are not licenses for individual images. Share-alike assets must retain their applicable license when adapted. Carry credits/license links and modification notes alongside assets and into distributed report appendices. Do not blanket-relicense third-party receipts under the repository's code license.

## Dataset alternatives

[CORD's official repository](https://github.com/clovaai/cord) explicitly licenses the work CC BY 4.0 and releases 1,000 Indonesian receipts. It provides boxes, text, semantic categories, and grouping, but published target classes remove store/payment information. It is a well-evidenced structure-parsing reference, not the default English/German corpus. Keep it optional rather than silently broadening language scope.

SROIE is widely mirrored, but the [organizer site](https://rrc.cvc.uab.es/?ch=13) could not be read in this investigation. Mirror license labels were not accepted as proof of upstream redistribution permission. Do not vendor it until that is verified. No claim is made that it is prohibited.

## Gaps for the corpus decision

- Choose representative English/German scans and photos across receipt layouts, not a large indiscriminate download. Inspect the actual pixels before accepting any candidate above.
- Add a genuine multipage receipt PDF and, if relevant, a native digital receipt PDF through a permitted source or user contribution. Keep one receipt per file under the agreed initial scope.
- Obtain manually verified merchant, date, currency, line items, tax, total, and expected review flags. Public Commons descriptions are not evaluation labels.
- Define deliberate duplicates, unreadable totals, rotation/blur and truncated-page cases. Track derivatives against one source receipt identity so duplicate variants are not treated as independent accuracy samples.
- For user scans, preserve useful amounts and structure while redacting identifying details before inclusion; agree whether the redacted asset can be publicly redistributed. Keep unredacted originals outside the committed assets.
- Save a per-file manifest with source permalink/revision, author, license, transformations, checksum, language, source identity, and ground-truth status. Freeze it before the Python end-to-end/model comparison.

No receipt files were downloaded or published, and no model inference was run. This note identifies acquisition options and remaining selection work; it does not deliver or approve the final corpus.
