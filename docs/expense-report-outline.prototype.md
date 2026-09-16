# Expense report outline — throwaway prototype

Status: historical design prototype. The implemented report behavior is described
in [the demo workflow](receipt-demo.md); the examples below remain fictional.

Question: does a summary followed by original receipts and extracted fields make
the automated demo's output clear? This is a discussion outline, not a PDF
implementation. All names, amounts, counts, and page references below are fictional.

## Page 1: expense report

**Run finished: completed with flags**

7 inputs · 4 included · 1 flagged · 1 duplicate · 1 error

| Currency | Confirmed net expenses |
| --- | ---: |
| EUR | 37.00 |
| USD | 9.90 |

Totals include refunds and exclude flagged, duplicate, and failed inputs. Each
currency stands alone; there is no converted grand total.

| Input | Merchant | Signed amount | Outcome / reason | Appendix |
| --- | --- | ---: | --- | --- |
| cafe.jpg | Example Cafe | EUR 12.00 | Included | p. 2 |
| market.pdf | Example Market | EUR 28.00 | Included | pp. 3–4 |
| refund.png | Example Market | EUR -3.00 | Included — refund | p. 5 |
| shop.jpg | Example Shop | USD 9.90 | Included | p. 6 |
| blurred.jpg | Unknown | Unknown | Flagged — unreadable total | p. 7 |
| cafe-copy.jpg | Example Cafe | EUR 12.00 | Duplicate of cafe.jpg; excluded | p. 8 |
| corrupt.pdf | Unknown | Unknown | Error — file could not be read | p. 9 |

Keep this summary compact. For larger runs it may continue onto another page;
do not shrink it into unreadable type. No action buttons or pending-review text.

## Appendix: one section per input

Each section starts with the source filename, outcome, and any reason for
exclusion. Present the original page image alongside a compact extracted summary:

| Original evidence | Extracted summary |
| --- | --- |
| [Original receipt page, scaled legibly] | Merchant: Example Cafe; Date: 2026-09-01; Currency: EUR; Printed total: 12,00; Signed total: 12.00; Outcome: included |

Include available line items, taxes, discounts, and field issues beneath the
summary where useful. Preserve unknowns explicitly. Detailed page text and field
evidence remain available in the JSON artifact; do not print the full JSON or a
second full transcription in the PDF.

Use side-by-side image/fields when legible; move fields beneath the image when
needed. Multipage receipts retain their original page order and can span as many
report pages as needed. Every report page has a page number; the summary points
to each appendix section.

Duplicates and flagged receipts retain their original pages and extracted fields.
An unrenderable file gets a short placeholder section with its filename and error
instead of an invented image. Preserve applicable source attribution with the
receipt sections.

## Completion behavior

The agent generates this PDF automatically inside its sandbox workflow, alongside
the structured JSON. Flags and exclusions are final results. An all-excluded run
still gets a report with no included expenses and an explanation of every input;
it must not imply a verified zero when expense amounts are unknown.

Keep execution traces and setup instructions outside the expense report. The
demo's README/run output explains the agent flow, Token Factory calls, sandbox
execution, and artifact retrieval. No model-quality scoring, review workflow,
dashboard, or manual follow-up is part of this report.
