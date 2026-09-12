# Token Factory receipt model capability inventory

Research date: 2026-09-12. Resolution asset for [Identify Token Factory vision models and document-input capabilities](https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos/issues/2).

## Finding

Keep a broad, configurable candidate inventory. Public documentation does not establish a winning receipt model or prove that every hosted endpoint exposes the upstream model's vision support. Build the shared receipt corpus and Python end-to-end flow first, then test eligible models on those same inputs as requested. No inference was run and no credentials were accessed in this research.

## Candidate inventory

“Documented” below means a first-party publication, not a live check with this project's account.

| Candidate / exact documented ID | Evidence and eligibility status |
| --- | --- |
| `Qwen/Qwen2.5-VL-72B-Instruct` | Nebius's [physical-AI workflow](https://github.com/nebius/nebius-physical-ai/blob/main/npa/workflows/workbench/npa-workflows/physical-ai-data-factory.yaml) explicitly labels it available and uses it for image captioning. Strong practical baseline; current account availability and receipt-schema support still need checking. |
| `Qwen/Qwen3.5-397B-A17B` | Exact hosting ID appears in the [Nebius cookbook](https://github.com/nebius/token-factory-cookbook/blob/main/models/qwen-3.5.md). Its [upstream model card](https://huggingface.co/Qwen/Qwen3.5-397B-A17B) demonstrates image input. Hosted image/schema combination remains untested. Candidate, not a selected winner. |
| `MiniMaxAI/MiniMax-M3` | Exact ID in the [Nebius guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/minimax-m3.md); Nebius's [model index](https://github.com/nebius/token-factory-cookbook/tree/main/models) describes text/image/video multimodality. Check hosted image support before inclusion. |
| `moonshotai/Kimi-K2.7-Code` | Nebius's [guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/kimi-k2.7-code.md) and [index](https://github.com/nebius/token-factory-cookbook/tree/main/models) describe native multimodality. That is insufficient to infer the serving endpoint accepts image requests; eligibility pending. |
| `nvidia/nemotron-3-nano-omni` | Nebius's [guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-nano-omni.md) supplies this exact ID and describes vision/video/text support. Include in capability discovery; receipt suitability unmeasured. |
| `nvidia/Cosmos3-Super-Reasoner` | Nebius's [vision walkthrough](https://github.com/nebius/nebius-physical-ai/blob/main/docs/hackathon-cosmos3-reasoner.md) names this ID. A broader vision candidate, though its physical-world focus does not establish receipt quality. |
| GLM 5.3, user-mentioned | Nebius's [OpenHands cookbook](https://dev.nebius.com/cookbook/openhands-agent-canvas) mentions GLM-5.3-Flash. This research did not establish the exact hosted ID for the user's GLM 5.3 variant or image capability. Retain for catalog discovery; do not silently substitute GLM-5.2 or assume vision. |
| DeepSeek 4 Pro 0813, user-mentioned | Nebius documents `deepseek-ai/DeepSeek-V4-Pro` in its [guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/deepseek-v4.md). The exact 0813 variant and hosted image support were not established. Retain the requested variant as pending, separate from the documented unsuffixed ID. |

This is a public-source candidate inventory, not an exhaustive authenticated catalog snapshot. An unauthenticated GET of `https://api.tokenfactory.nebius.com/v1/models` returned HTTP 401 during this research. The public catalog page did not expose machine-readable entries through the browsing tool. These limitations do not establish that pending models are unavailable or text-only.

## Document input and structured output

Nebius's [vision API example](https://docs.tokenfactory.nebius.com/api-reference/examples/vision-capabilities) documents Chat Completions content parts with `image_url`, supporting remote image URLs and base64 image data. Use that as the initial transport contract. The page's model examples are inconsistent across languages, so do not copy its model names as a current inventory.

The reviewed vision guide does not establish direct PDF input support, per-request page/image limits, pixel limits, or model-specific image-plus-schema compatibility. Planning recommendation: render PDF pages into images inside each self-contained example's agent tool flow, retain original pages for the report, and make batching/resolution configurable. This is a proposed portable design, not a claim that Token Factory cannot accept PDFs through any endpoint.

Nebius's [structured-output guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json) documents `response_format` types `json_schema` and `json_object`, directs readers to each model card's JSON-mode tag, and recommends comparing models. Therefore schema support is a per-model eligibility check; do not equate syntactically valid JSON with correct extraction. Validate locally and preserve failed/uncertain records for the final report.

## Evidence still needed during implementation

1. Snapshot the authenticated current catalog for the chosen endpoint and exact IDs, including GLM 5.3 and DeepSeek 4 Pro 0813. Record modality metadata and model-card JSON support, then validate with small image requests during the authorized implementation/evaluation phase.
2. For each candidate, record image acceptance, image-plus-schema behavior, multi-page handling limits, tool-call support where needed, and recoverable failures. Do not reject an extraction-only VLM merely because a separate orchestration model is needed; settle agent/model roles explicitly.
3. Measure receipt field accuracy, line-item/structure fidelity, missing-field handling, duplicate outcomes, end-to-end completion, latency, and actual usage/cost on the shared inputs. Keep failed receipts visible in the final PDF.

No winner is chosen here. Model selection follows the user's requested corpus-first, Python-first evaluation sequence; each language example must remain self-contained and generate its PDF within the agentic flow.
