# Nebius Token Factory Sandbox Demos

Examples showing how to build and host agents in Nebius Sandboxes and use Token
Factory for inference. The receipt demo starts a coordinator, fans out one sandbox
job per receipt, and launches a report agent. The coordinator returns the final
JSON/PDF or errors. Flags and document failures are automated outcomes.

## Examples

| Language | Implementation | Status |
| --- | --- | --- |
| [Python](examples/python/README.md) | Pydantic AI agents, sandbox orchestration, JSON/PDF generation, and small smoke/tool examples | Implemented |

Start with the [Python setup and commands](examples/python/README.md):

```sh
cd examples/python
python3 -m basic_demo configure
python3 -m receipt_demo --profile minimal --output receipt-output
```

The launcher uses the Python standard library. Agent dependencies are installed
inside the sandboxes. Each example documents its own development environment,
inference settings, and run commands.

## Repository layout

```text
examples/
  python/                  Shared sandbox client, configuration, and development tools
    receipt_demo/          Receipt launcher, agents, dependencies, docs, and tests
    basic_demo/            Smoke/tool launcher, agent, docs, and tests
fixtures/
  receipts/                Shared inputs, provenance, expected behaviors, and asset tools
docs/
  agents/                  Repository-wide engineering instructions
  receipt-contract.md      Shared JSON fields and automated outcome meanings
  receipt-demo.md          Shared orchestration flow and report layout
.github/workflows/         Repository CI
.pre-commit-config.yaml    Hook orchestration across language examples
```

Each language owns its complete workflow, including report generation. Languages
share the [receipt fixtures](fixtures/receipts/README.md),
[contract](docs/receipt-contract.md), and [demo behavior](docs/receipt-demo.md).
Generated prose and PDF bytes need not match. Fixture-generation tools are only
needed when changing assets; ordinary runs use the checked-in receipts.

## Development

Follow the development setup in the example's README. Root hooks and CI run the
applicable formatters, linters, file checks, and tests; language-specific tool
configuration and dependencies live with the example. Install hooks once in each
checkout. For Python, after its environment is installed:

```sh
examples/python/.venv/bin/pre-commit run --all-files --show-diff-on-failure
```

Add a language under `examples/<language>/` when its implementation starts, with
its own README, dependencies, and tests. Put each example in a dedicated folder
within its language. Keep shared fixtures and contract changes at the repository
root.
