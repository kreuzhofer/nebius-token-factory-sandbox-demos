# Basic examples for Nebius Token Factory Sandboxes

Run these commands from `examples/python/`. See the [shared development setup](../README.md#development).


### Setup

Clone the repository and enter it:

```sh
git clone https://github.com/kreuzhofer/nebius-token-factory-sandboxes-demos.git
cd nebius-token-factory-sandboxes-demos/examples/python
```

You need an API key and a Project ID with access to Nebius Token Factory
Sandboxes. The agent example also needs access to a Token Factory model that
supports tool calling.


```sh
python3 -m basic_demo configure
python3 -m basic_demo images
python3 -m basic_demo smoke
python3 -m basic_demo models
# Set NEBIUS_MODEL in .env to an available model supporting chat tool calling.
python3 -m basic_demo agent --image IMAGE_UUID_PRINTED_BY_SMOKE
```

`configure` uses hidden prompts for tokens and creates a gitignored `.env` with mode 0600. Alternatively set the variables in `basic_demo/.env.example` in your environment. The sandbox token falls back to NEBIUS_API_KEY; the Project header comes from CONTREE_PROJECT. Sandbox and inference credentials can differ. The public sandbox API documents bearer authentication plus a Project header; sandbox access must be enabled for the selected project.

Without `--image` or CONTREE_IMAGE, a run imports `docker.io/library/python:3.12-slim` privately, then prints the resulting image UUID for reuse. An existing image must contain `/usr/local/bin/python3`. `images` displays the first 100 public images; it does not guarantee those images include Python. `models` lists available inference IDs; tool support needs live verification. `all` runs both stages, requiring inference settings up front.

## What runs where

Local basic_demo → sandbox HTTPS API → OCI Python filesystem in a microVM → basic_demo/agent.py → Token Factory chat completions → Python subprocess tool inside the microVM.

* `smoke`: networking disabled; computes and verifies a sum of squares, writes `/tmp/smoke.json`, and returns stdout. A checkpoint is retained.
* `agent`: networking enabled; asks a model to calculate primes using a Python tool, sends tool results back, and prints the final answer. Limited to five inference turns, 1,200 output tokens per turn, 15 seconds per Python tool, and 360 seconds of sandbox execution. This run is disposable and does not preserve environment variables.

Commands are submitted as operations. Each execution gets its own VM; this example does not keep a long-lived VM between stages. Filesystem checkpointing is distinct from keeping a live Python process. The import and smoke checkpoint may remain under beta retention rules. No persistent tag is created.

The inference key is passed in the agent execution environment, removed from the agent's environment before tools run, and excluded from subprocess environments. It is still sent to the sandbox service as request metadata; disposable execution is not a guarantee of metadata deletion. Use a scoped test key. This tiny agent is an execution demonstration, not a hardened adversarial agent framework.

### SDK versus HTTPS — checked September 11, 2026

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


To check the standard-library smoke example locally:

```sh
python3 -m basic_demo.agent smoke
```

The receipt workflow and the small prime-number tool demo share `../nebius_sandbox.py`. Other language implementations own their own
sandbox and agent code.
