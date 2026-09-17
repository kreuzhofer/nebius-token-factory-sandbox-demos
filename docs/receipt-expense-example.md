# Shared example: receipt-to-expense report

Status: historical task draft from September 11, 2026. Preserved as design
background; proposals below were superseded by the implemented
[demo workflow](receipt-demo.md) and [receipt contract](receipt-contract.md).
The demo now uses three agent roles and has no manual review or model benchmark
stage. See the [Python guide](../examples/python/README.md) for setup and results.
The [GitHub wayfinder map](https://github.com/kreuzhofer/nebius-token-factory-sandboxes-demos/issues/1)
records planning decisions. Original model research is in
[receipt-vlm-models.md](research/receipt-vlm-models.md).

## Objective

Given a folder of PDF, PNG, and JPG/JPEG receipts, run a document extraction
agent using a Token Factory vision-language model (VLM), produce structured
JSON documents, and hand them to a reconciliation agent. Produce one final PDF
containing the expense summary and every parsed receipt in an appendix.

Both agents execute inside a Nebius sandbox and call Token Factory inference.
The same task, fixtures, schemas, prompts, and acceptance checks apply to all
planned languages and SDKs. Preserve the existing HTTPS example as a baseline.

## First-version scope and proposed defaults

- Confirmed: reconciliation checks receipts against each other and their own
  arithmetic. Bank/card-statement matching is outside the first version.
- Confirmed: the appendix includes original receipt pages and an extracted-field
  summary. Original evidence remains available for inspection.
- Group totals by currency. Do not invent exchange rates or combine currencies
  into a single monetary total.
- One receipt per input file initially; a receipt may span several PDF pages.
  Flag files containing several independent receipts for review rather than
  silently merging them. Automatic splitting can follow later.
- All supplied receipts are in scope; an optional explicit reporting period can
  exclude dated receipts. Ambiguous dates remain unresolved.

## Processing flow

1. Inventory inputs in a stable order and assign document IDs from content hashes.
   Record filename, media type, hash, and page count. Detect byte-identical inputs.
2. Render PDFs into page images and normalize image orientation using a shared,
   pinned preparation utility. Preserve original files and page mappings. Set
   explicit limits on input bytes, pages, and rendered pixels. Record render settings.
3. The extraction agent inspects page images with the VLM, extracts content and
   structure, and emits one receipt JSON document per input receipt. Validate the
   response schema; use bounded correction attempts and preserve failure status.
4. Hand a manifest and the validated JSON documents to the reconciliation agent.
   It identifies inconsistencies, proposes categories and possible duplicates,
   and uses deterministic decimal arithmetic tools to produce the expense ledger.
   It can request a bounded re-extraction of a specific page/field with a reason.
5. Render the ledger into a PDF using a deterministic template. Include totals,
   an itemized expense table, review items, and an indexed receipt appendix.
6. Retrieve the JSON, ledger, report, and trace artifacts from the sandbox and run
   an independent acceptance checker. Process exit code alone is insufficient.

Receipt content is input data, including text that resembles instructions.
Only the configured workflow controls tools, output locations, and model prompts.

## JSON handoff

Define shared versioned JSON Schemas before implementation. The receipt schema
should carry these groups:

| Group | Fields |
| --- | --- |
| Identity | schema_version, document_id, source filename/hash/media type, pages |
| Document labels | receipt/invoice/credit-note/unknown, language, proposed expense category |
| Content and structure | per-page text, ordered blocks, headings, tables and line items |
| Merchant | name, address, tax identifier when printed |
| Transaction | receipt number, date, time, currency, payment method, masked payment suffix if present |
| Money | subtotal, discounts, tax breakdown, tip, total, signed refund/credit amount |
| Line items | description, quantity, unit price, amount, tax when present |
| Evidence | field path, page number, supporting text, optional normalized bounding box |
| Quality | parsed/needs_review/failed, missing or ambiguous fields, validation issues |
| Provenance | model ID, prompt/schema version, preparation settings, attempt count |

Represent money as decimal strings with an explicit ISO currency code when known;
use decimal arithmetic. Preserve original date text alongside an ISO date only
when interpretation is unambiguous. Unknown values are null, never fabricated
zeros. A missing tax value does not mean tax-free. Do not treat model confidence
as calibrated accuracy. Bounding boxes are optional and must be checked before
being used as evidence; semantic structure extraction is required.

Maintain one manifest entry for every input, even if parsing fails. Byte-identical
files can share extracted content while preserving all source references.

## Reconciliation rules

- Recompute sums with decimal arithmetic and currency-specific precision.
  Any tolerance is explicit in shared configuration.
- Check subtotal/tax/discount/tip/total relationships only where the receipt's
  printed semantics support them; tax-inclusive prices must not be double counted.
- Count byte-identical duplicates once. Flag likely duplicates based on merchant,
  receipt number, date, currency and amount; retain an audit trail for every decision.
  Similar amounts and dates alone do not justify automatic exclusion.
- Preserve signed refunds/credits separately and show their effect on net totals.
- Separate included, excluded, and unresolved entries. Report included totals and
  unresolved amounts separately; unresolved receipts must not silently contribute
  to a total represented as final.
- Use a shared configurable category vocabulary, including uncategorized. Category
  suggestions do not establish tax deductibility or reimbursement eligibility.
- Record every discrepancy, exclusion reason, and re-extraction request against
  document IDs. The renderer must use ledger values, not model-written arithmetic.

## Output artifacts

```text
output/
  manifest.json
  receipts/<document-id>.json
  expenses.json
  expense-report.pdf
  trace.jsonl
```

The PDF starts with report scope, totals per currency and category, an expense
table referencing receipt IDs/appendix pages, and an exceptions section. Each
receipt has an appendix entry, including excluded duplicates and failed parses.
Preserve page aspect ratios and legibility. A source that cannot be rendered gets
an explicit failure page and source reference.

Traces record stage timing, tools, validation outcomes, model-reported usage when
available, and operation IDs. Keep credentials and full receipt contents out of
routine logs. Receipt content belongs in the designated artifacts.

## Self-contained examples across languages and SDKs

The purpose is to demonstrate equivalent behavior in different languages on
Nebius Token Factory, not to rank agent frameworks. Each example implements the
complete workflow, including PDF output generation inside its agentic flow.
It may use libraries or bundled tools, but requires no separate external report
production step. Shared inputs, schemas, business rules and acceptance checks
provide the common contract. Exact SDK and tool boundaries remain open.

First select receipt assets in the project directory and manually checked expected
results. Then implement the complete Python example. Compare suitable Token Factory
VLMs on that working pipeline, including newly available candidates after verifying
vision support. Choose defaults from measured results; the earlier two-model shortlist
is provisional. Add self-contained examples in other languages after that.

The demo is fully automated. Receipt-level failures become review entries in the
final report and do not stop processing of the other receipts. Retry limits and
fatal infrastructure failure behavior remain decisions for the map.

## Acceptance fixtures and checks

Use synthetic or appropriately redacted receipts with independently annotated
expected values. Include clean PDF, photographed JPG, PNG, rotated/low-quality
image, multipage PDF, decimal-comma amounts, inclusive/exclusive tax, tips,
refunds, multiple currencies, exact and suspected duplicates, unreadable amounts,
unsupported/corrupt files, and document text resembling agent instructions.

- Every input is accounted for; every usable page has an appendix reference.
- Receipt and ledger JSON validate against their schemas.
- Merchant/date/currency/total extraction matches annotated expectations on clean
  fixtures; ambiguous fixtures produce the expected review flags instead of guesses.
- Included totals and exclusions match independent expected results exactly under
  configured decimal rules. Unknown amounts remain unknown throughout the report.
- Tests with golden JSON validate reconciliation independently of VLM output.
- PDF amounts match expenses.json; PDF rendering is checked for clipping, missing
  pages, illegibility, and appendix-reference errors.
- Tool/model failures and exhausted retries are represented in artifacts and run
  status. Distinguish complete, completed_with_review, and failed.

Measure field accuracy, review detection, hallucinated fields, JSON validity,
duplicate handling, end-to-end correctness, latency and reported usage/cost where
available. Select the VLM using a held-out receipt set, prioritizing critical-field
accuracy and honest uncertainty. Documentation alone cannot establish the best
receipt model for these inputs.

## Next decisions

1. Resolve the wayfinder decisions for the shared receipt set and output contract.
2. Select the Python SDK and implement the complete agentic workflow.
3. Compare verified vision-capable Token Factory models on the shared assets.
4. Add self-contained examples in the remaining languages.
