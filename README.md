# Nebius Token Factory Sandbox Demos

A Python standard-library example of OCI-image execution with VM isolation through Nebius Token Factory Sandboxes. Python 3.10+ recommended; no pip dependencies or Docker daemon needed.

## Status

The basic smoke/tool examples use the Python standard library. The receipt demo
adds three Pydantic AI agents: a coordinator, a receipt agent run once per input,
and a report agent. V1 hosts them in one sandbox; V2 runs receipt agents concurrently
in separate sandboxes, followed by a report sandbox. All inference goes through Token Factory.
The coordinator returns an automated expense report as JSON and PDF.

## Receipt agents: Python V1 and V2

After `python3 demo.py configure`, run:

```sh
python3 receipts.py --profile minimal --output receipt-output
# Default 14-input batch, including duplicate and corrupt inputs:
python3 receipts.py --output receipt-output-demo
# V2: coordinator fans out receipt sandboxes, then starts the report sandbox:
python3 receipts.py --mode v2 --concurrency 3 --output receipt-output-v2
# Or supply your own files:
python3 receipts.py receipt.jpg other-receipt.pdf --output receipt-output-custom
```

No local pip install or Docker daemon is needed to launch the workflow. The job
installs pinned Python dependencies inside its Python 3.12 sandbox. Model IDs and
endpoints are configurable in `.env`; see [the receipt demo guide](docs/receipt-demo.md)
for the agent flow, configuration, JSON contract, limits, and verification.

## Getting started

Clone the repository and enter it:

```sh
git clone https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos.git
cd nebius-token-factory-sandbox-demos
```

You need a Nebius API key and a Project ID with sandbox access. The agent example
also needs access to a Token Factory model that supports tool calling.


```sh
python3 demo.py configure
python3 demo.py images
python3 demo.py smoke
python3 demo.py models
# Set NEBIUS_MODEL in .env to an available model supporting chat tool calling.
python3 demo.py agent --image IMAGE_UUID_PRINTED_BY_SMOKE
```

`configure` uses hidden prompts for tokens and creates a gitignored `.env` with mode 0600. Alternatively set the variables in `.env.example` in your environment. The sandbox token falls back to NEBIUS_API_KEY; the Project header comes from CONTREE_PROJECT. Sandbox and inference credentials can differ. The public sandbox API documents bearer authentication plus a Project header; sandbox access must be enabled for the selected project.

Without `--image` or CONTREE_IMAGE, a run imports `docker.io/library/python:3.12-slim` privately, then prints the resulting image UUID for reuse. An existing image must contain `/usr/local/bin/python3`. `images` displays the first 100 public images; it does not guarantee those images include Python. `models` lists available inference IDs; tool support needs live verification. `all` runs both stages, requiring inference settings up front.

## What runs where

Local demo.py → sandbox HTTPS API → OCI Python filesystem in a microVM → agent.py → Token Factory chat completions → Python subprocess tool inside the microVM.

* `smoke`: networking disabled; computes and verifies a sum of squares, writes `/tmp/smoke.json`, and returns stdout. A checkpoint is retained.
* `agent`: networking enabled; asks a model to calculate primes using a Python tool, sends tool results back, and prints the final answer. Limited to five inference turns, 1,200 output tokens per turn, 15 seconds per Python tool, and 360 seconds of sandbox execution. This run is disposable and does not preserve environment variables.

Commands are submitted as operations. Each execution gets its own VM; this example does not keep a long-lived VM between stages. Filesystem checkpointing is distinct from keeping a live Python process. The import and smoke checkpoint may remain under beta retention rules. No persistent tag is created.

The inference key is passed in the agent execution environment, removed from the agent's environment before tools run, and excluded from subprocess environments. It is still sent to the sandbox service as request metadata; disposable execution is not a guarantee of metadata deletion. Use a scoped test key. This tiny agent is an execution demonstration, not a hardened adversarial agent framework.

## SDK versus HTTPS — checked September 11, 2026

There is an official SDK: `contree-sdk`, alongside `contree-client` and a CLI. The service is explicitly beta. At inspection, PyPI served contree-sdk **0.3.6** and contree-client **0.4.0**. The installed SDK constructor was `ContreeSync(config=None, *, base_url=None, token=None)`, while the current guide describes injecting a `contree_client` transport. The documented example therefore does not match that published SDK version.

For this small test, direct HTTPS is the most transparent option: POST /images/import, POST /instances, GET /operations/{id}, DELETE /operations/{id}. The generated contree-client is another reasonable option, especially if you need broad API coverage. Reconsider the high-level SDK when its release and docs align.

Sources:

- [Sandbox overview and beta status](https://docs.tokenfactory.nebius.com/sandboxes/overview)
- [SDK setup](https://docs.tokenfactory.nebius.com/sandboxes/sdk/python_sdk/getting-started)
- [SDK release](https://pypi.org/project/contree-sdk/)
- [Generated client release](https://pypi.org/project/contree-client/)
- [Authentication](https://docs.tokenfactory.nebius.com/sandboxes/cli/tutorial/installation)
- [Spawn API](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance)
- [Operation status](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/operations/get-an-operation-status)
- [Inference quickstart](https://docs.tokenfactory.nebius.com/quickstart)

## Verification

```sh
python3 -m unittest -v test_demo
python3 agent.py smoke
```

Local tests cover polling, deadline cancellation, process failure, disposable execution settings and output decoding. They use mocked API responses. Live verification passed on September 11, 2026 using the same Nebius API key for sandboxes and inference, plus the sandbox Project header. The smoke run returned 385. With Qwen/Qwen3-30B-A3B-Instruct-2507, the in-sandbox agent executed Python, printed all 25 primes below 100 and their sum 1060, and returned the matching final answer. The model initially omitted print statements and corrected this on a subsequent tool call. Normal process termination returned signal=-1; the runner accepts that sentinel. Requests that create operations are not automatically retried, avoiding accidental duplicate launches after an ambiguous response. Local timeouts/interrupts attempt cancellation; server execution timeouts provide a separate bound.

Reuse the image UUID printed by your own smoke run:

```sh
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 python3 demo.py all --image YOUR_IMAGE_UUID
```

## Shared receipt inputs

[The receipt fixture set](fixtures/receipts/README.md) contains 12 distinct
public/synthetic receipts plus duplicate and damaged-file variants for the
receipt-agent example. It includes provenance, lightweight checks, and a generator
for the synthetic files.

List the 14-input demo set without installing additional dependencies:

```sh
python3 fixtures/receipts/check.py --list demo
```

## Project files

| File | Purpose |
| --- | --- |
| `demo.py` | Configuration, image import, sandbox launch, and operation polling |
| `agent.py` | Smoke task and LLM/tool loop executed inside the sandbox |
| `test_demo.py` | Local tests with mocked sandbox responses |
| `receipts.py` | One-command receipt launcher and coordinator result retrieval |
| `sandbox_jobs.py` | Shared HTTPS job, file upload, and artifact download helpers |
| `receipt_demo/` | Coordinator, receipt, and report agents plus their ordinary Python tools |
| `test_receipts.py` | Accounting, document, agent workflow, and transfer checks using fake models |
| `test_orchestration.py` | Bounded fan-out, child failures, cancellation, and report handoff checks |
| `.env.example` | Credential and model configuration template |

## License

[MIT](LICENSE), copyright 2026 Daniel Kreuzhofer.
