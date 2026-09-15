# Receipt agents on Nebius Sandboxes

This example demonstrates hosting agents in a sandbox and using Token Factory for
inference. One command produces JSON and a PDF with totals and original receipts.
Flags, duplicates, and document errors are finished automated outcomes.

## Run it

Use Python 3.10+ for the standard-library launcher, with a Nebius key and Project ID
that have sandbox access. The receipt workflow itself runs on Python 3.12.

```sh
python3 demo.py configure
python3 receipts.py --profile minimal --output receipt-output
python3 receipts.py --profile demo --output receipt-output-demo
```

The small `minimal` profile contains a readable receipt, an unreadable total, and
a corrupt PDF. `demo` is the default 14-input batch. Other fixture profiles are
listed in the [fixture guide](../fixtures/receipts/README.md). Positional file paths
replace the profile selection:

```sh
python3 receipts.py first.jpg second.pdf --output receipt-output-custom
```

Each output directory must be fresh. Successful runs write `report.json`,
`report.pdf`, `result.json` (the coordinator response), and `job.json` (the sandbox
operation and filesystem image IDs). `completed_with_flags` exits successfully;
a failed run exits nonzero. If a completed job's download fails, retrieve its
coordinator outputs again without launching agents or spending more inference:

```sh
python3 receipts.py --retrieve COORDINATOR_FILESYSTEM_UUID --output receipt-output-retrieved
```

Use the filesystem UUID printed by the run or recorded in `job.json`. The job is
non-disposable so its files can be downloaded after the process exits. Environment
variables are not preserved in that filesystem. Inputs and generated files remain
subject to the sandbox service's beta retention policy; this example creates no
persistent tag and offers no deletion guarantee. Retrieve artifacts promptly.

## What runs where

```mermaid
sequenceDiagram
    participant L as Local launcher
    participant C as Coordinator agent (sandbox)
    participant R as Receipt agent (same sandbox)
    participant T as Token Factory
    participant P as Report agent (same sandbox)
    L->>C: Upload inputs/code and start one job
    C->>T: Choose process_receipts tool
    loop Each input, sequentially
        C->>R: Source file and input identity
        R->>R: Render PDF/image pages
        R->>T: Images and structured extraction prompt
        R-->>C: Receipt record or document error
    end
    C->>P: All receipt outcomes and original pages
    P->>T: Interpret duplicates and monetary contradictions
    P->>P: Tool performs decimal arithmetic and generates JSON/PDF
    P-->>C: Report artifacts
    C->>C: Copy and checksum actual artifacts
    C-->>L: Final result and retrievable JSON/PDF
```

There are three agent implementations. Pydantic AI output tools ensure the
coordinator and report agent cannot merely claim they finished: their ordinary
Python tools must execute and return actual files. V1 runs receipt agents
sequentially inside the same job. [V2](https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos/issues/14)
will move receipt instances and the report agent into separate jobs while keeping
the coordinator responsible for returning the result.

## Inference configuration

| Variable | Default / purpose |
| --- | --- |
| `NEBIUS_API_KEY` | Required Token Factory inference key |
| `CONTREE_TOKEN` | Sandbox credential; falls back to inference key |
| `CONTREE_PROJECT` | Sandbox Project header |
| `CONTREE_BASE_URL` | Sandbox API; existing demo default |
| `CONTREE_IMAGE` | Optional existing image with `/usr/local/bin/python3` and pip |
| `NEBIUS_AGENT_MODEL` | `Qwen/Qwen3-30B-A3B-Instruct-2507` for coordinator/report tool calls |
| `NEBIUS_VISION_MODEL` | `openbmb/MiniCPM-V-4_5` for image extraction |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1` |
| `NEBIUS_VISION_BASE_URL` | Falls back to `NEBIUS_BASE_URL`; can select a regional endpoint |

The tiny prime/tool example's `NEBIUS_MODEL` remains separate. Both receipt models
use explicit `OpenAIChatModel` and `OpenAIProvider` instances pointing to Token
Factory Chat Completions. The extraction model uses JSON-object mode with a
schema prompt and local Pydantic validation; it does not need tool calling.
Coordinator/report models need tool calling. Changing models requires compatible
capabilities and access on the selected endpoint.

The inference key goes only into the sandbox execution environment, is removed
from the agent process environment when constructing clients, and is excluded
from the dependency-install subprocess. Sandbox API credentials are not sent into
the V1 job. Logs record agent stages, selected models, and job IDs, excluding raw
model errors and credentials.

## Data and automatic outcomes

Version `1` JSON retains every source identity, merchant/date/currency, purchase or
refund direction, printed/normalized total, original page references, page text
and reading-order blocks, optional items/tax/discount, field evidence, and issues.
The JSON includes parsed receipts as well as reconciled entries and currency totals.
Money is represented as decimal strings; unknown fields are null. Original page
paths describe files within the job; the downloaded PDF embeds the rendered
originals so the report remains usable after remote storage expires.

- `included`: a resolved signed expense contributes once to its currency total.
- `flagged`: critical monetary uncertainty, an obvious contradiction, or suspected
  duplication excludes the expense. A missing secondary field alone need not.
- `duplicate`: confirmed duplicate, with `duplicate_of`; retain its source appendix.
- `error`: the source cannot be rendered or extraction attempts are exhausted.

Python applies decimal arithmetic, negative refunds, and checks only explicitly
comparable printed components. It never adds already-included tax or performs FX
conversion. Byte/pixel hashes detect exact and re-encoded duplicates from actual
inputs; semantic duplicate candidates come from the report agent. Fixture recipes,
expected values, and source-group labels never become agent evidence. Attribution
is passed only to report rendering.

The PDF starts with totals, counts, a row per input, and appendix page references.
Each appendix contains extracted summaries and original pages in order; long
receipts may span multiple strips/pages. Unrenderable files get an explanatory
placeholder. Full transcription/evidence stays in JSON. No included receipts means
no confirmed totals, rather than an invented zero expense amount.

## Bounds and failures

The launcher accepts up to 30 inputs / 50 MiB; each PDF has at most eight pages and
each rendered page at most 25 million pixels. The default job timeout is 1,800
seconds, configurable from 300 to 3,600. Dependency setup has a 240-second limit.
Inference HTTP attempts have a 90-second timeout and one transport retry. The
coordinator is limited to one model request; each receipt and the report agent
have at most two model requests, including one output-validation retry. Sandbox
job submissions are never automatically retried after ambiguous responses.

Document failures are contained and the batch continues. Shared authentication or
model-access errors, report failures, and artifact-copy failures produce a failed
coordinator response with known outcomes where possible. If the process itself
fails before it can respond, the launcher reports the job failure. Local wait
timeouts/interrupts attempt operation cancellation; the server timeout is an
independent bound. Downloaded artifacts are checked against the coordinator's
byte counts and SHA-256 before a successful local result is published.

## Live verification: September 15, 2026

The three-input run completed through Token Factory and returned checksummed JSON
and PDF after its sandbox process ended. The default 14-input run also completed
with every input represented and a 21-page PDF, using the two default models.
Its coordinator operation was `01a0a55d-4d97-70ae-a359-c05f4a67c089` and its retained
filesystem was `38bb904b-bdc8-4b56-b62d-a665b14c1dfd`. These are verification records,
not reusable image IDs for another account.

The full run finished `completed_with_flags`: one included refund, ten flagged
inputs, one duplicate, and two errors. The extractor sometimes grouped totals,
tender, included tax, or carry-forward amounts as summable components, causing
conservative exclusion. One extraction exhausted validation retries; the corrupt
PDF remained a document error. This is a working orchestration demonstration with
imperfect extraction, not a claim that the resulting expense totals are complete.
No correction step was required to finish the run.

The report step was separately checked against saved outcomes while fixing its
output-token budget, then verified in the fresh full run above. The final duplicate
safeguard (conflicting extracted fields cannot confirm a semantic match) and
simplified document-error wording are covered by local tests. The local suite has
22 passing tests. Rendered PDFs were visually inspected for summary/appendix
references, original-page order, readable long-receipt sections, and error placeholders.

## Local verification

Use Python 3.12 and install the same pinned dependencies as the sandbox:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r receipt_demo/requirements.txt
.venv/bin/python -m unittest -v
```

Tests use fake models and temporary files. They cover refunds, per-currency sums,
unknown amounts, contradictions, duplicate handling, PDF rendering, all three
agent roles, shared/document failures, and checksummed artifact retrieval. Live
verification is a bounded execution check, not an extraction benchmark.

Implementation references: [sandbox file upload](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/files/upload-a-file-to-the-server-the-body-must-be-a-file-content),
[file download](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/inspect/download-a-file-from-image),
[instance lifecycle](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance),
and [Pydantic AI provider configuration](https://pydantic.dev/docs/ai/models/openai/).
