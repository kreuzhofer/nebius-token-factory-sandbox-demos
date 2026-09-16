# Token Factory models for receipt extraction

Status: historical model research. The evaluation proposal below is background,
not part of the current demo scope. See the
[Python guide](../../examples/python/README.md) for the selected models and live
results, and the [demo workflow](../receipt-demo.md) for current behavior.
Availability and API claims below reflect the research date.

Research date: 2026-09-11. Primary-source desk research only; no credentials inspected, paid inference performed, or receipt benchmark run.

## Recommendation

Start the extraction evaluation with **`Qwen/Qwen3.5-397B-A17B`**, with **`Qwen/Qwen2.5-VL-72B-Instruct`** as the established document-oriented baseline. This is a provisional recommendation, not a measured winner on this project's receipts. Freeze the model only after testing the shared fixture and verifying the selected account and region support image input plus the required JSON schema.

Nebius lists Qwen3.5-397B-A17B in its current cookbook and supplies a Token Factory API example with base URL `https://api.tokenfactory.us-central1.nebius.com/v1/` (chat completion route: `POST /chat/completions`). This does not establish availability in every region. [Nebius Qwen3.5 guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/qwen-3.5.md)

Qwen's own model card documents image understanding and reports **90.8 on OmniDocBench 1.5, 93.1 on OCRBench, and 82.0 on CC-OCR**. These are vendor-reported document/OCR benchmarks, not receipt field accuracy, and do not prove performance on Nebius's serving configuration. They nevertheless provide relevant evidence for selecting it as the first candidate. [Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-397B-A17B)

## Candidate comparison

| Candidate | Evidence of Token Factory offering | Relevance and remaining uncertainty |
| --- | --- | --- |
| `Qwen/Qwen3.5-397B-A17B` | Current Nebius cookbook model guide and playground link | Best initial candidate from the document/OCR evidence reviewed; hosted image and JSON-schema combination still needs a smoke test. |
| `Qwen/Qwen2.5-VL-72B-Instruct` | Nebius's vision solution page explicitly advertises it | Strong baseline: model author explicitly describes invoice/form/table extraction, layouts, coordinates, and structured content. No project-specific accuracy or current price measured. |
| `moonshotai/Kimi-K2.6` | Nebius's vision solution page explicitly advertises it | Alternative general VLM; no same-setting receipt extraction comparison found in the reviewed primary sources. |
| `moonshotai/Kimi-K3` | Current Nebius cookbook provides API example and describes image input | Worth including if account access permits. The reviewed guide emphasizes general reasoning and agents and provides no receipt/OCR comparison that justifies declaring it the parsing winner. |
| `MiniMaxAI/MiniMax-M3` | Nebius cookbook model list identifies native multimodal input | Additional candidate if available; listing alone does not establish superior document extraction or schema support. |

Sources for this comparison: [Nebius model list](https://github.com/nebius/token-factory-cookbook/blob/main/models/README.md), [Nebius vision offering](https://nebius.com/solutions/vision), [Qwen2.5-VL model card](https://huggingface.co/Qwen/Qwen2.5-VL-72B-Instruct), [Nebius Kimi K3 guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/kimi-k3.md).

The cookbook and marketing pages demonstrate a published offering, not live access for this account. Use the documented authenticated `GET /v1/models` (optionally `verbose=true`) before implementation to confirm available model IDs. No authenticated request was made for this research. [Nebius list-models API](https://docs.tokenfactory.nebius.com/api-reference/models/list-models)

## Input and structured-output contract

Nebius documents image URLs and base64 image payloads in chat-completion content using `image_url`. The vision example contains older and inconsistent model names across language snippets, so use it for request shape, not model selection. [Nebius vision API example](https://docs.tokenfactory.nebius.com/api-reference/examples/vision-capabilities)

The general documented API base URL is `https://api.tokenfactory.nebius.com/v1/`, with image messages sent to `POST /chat/completions`. Keep the base URL configurable and verify the intended region during the initial smoke test. [Nebius chat-completion API](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion)

**Design recommendation:** render each PDF page to an image before extraction, normalize JPEG/PNG orientation, and retain source-file/page provenance. Direct PDF parsing was not established by the reviewed vision documentation; do not assume that general file-upload support means arbitrary PDFs can be passed to every VLM. Rendering keeps the input contract identical across SDK implementations and preserves the visual evidence needed for the report appendix.

Nebius documents both `response_format.type=json_schema` and `json_object`, and says support is model-dependent (the model card's JSON-mode tag). Prefer schema-constrained output when supported, then independently validate the result. A VLM's ability to generate JSON does not establish backend-enforced schema support for that endpoint. [Nebius structured-output documentation](https://docs.tokenfactory.nebius.com/ai-models-inference/json)

**Design recommendation:** extract transcription, reading-order blocks and field labels, merchant/date/currency/amounts, line items and tax breakdowns, with source-page evidence. Treat absent or illegible values as null with a reason. Model-generated confidence values are not calibrated probabilities. Keep arithmetic validation and cross-receipt duplicate decisions separate from extraction.

## Pricing and selection experiment

The public model catalog and pricing URL returned JavaScript shells in this research session; current Qwen extraction prices could not be verified. Do not use another provider's price or infer cost from parameter count. Retrieve current Token Factory pricing for the chosen endpoint when running the benchmark. [Token Factory pricing](https://tokenfactory.nebius.com/organization/prices)

Proposed experiment (project design, not external findings):

1. Build a manually checked fixture containing PDF scans, digital PDFs, JPEG photographs and PNG receipts, including a multipage receipt, skew, faint text, different layouts and decimal conventions.
2. Send identical normalized page images and schema to each accessible candidate. Record model ID, region, prompts, image resolution, output settings, tokens, retries, elapsed time and price snapshot.
3. Measure merchant/date/currency/total exact match; line-item and tax accuracy; missing-value handling; reading-order preservation; JSON-schema validity; and page provenance. Record hallucinated fields separately.
4. Evaluate reconciliation independently on golden extracted JSON. This prevents OCR differences from being mistaken for language/SDK orchestration differences.
5. Prefer the highest extraction quality meeting the agreed limits, with cost and latency as tie-breakers. Publish results before replacing the provisional model recommendation.
