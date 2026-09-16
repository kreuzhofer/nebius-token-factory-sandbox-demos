# Python agent and sandbox SDK facts

Status: historical research preceding implementation. The single-sandbox proposal
below was superseded by [multi-agent orchestration](../receipt-demo.md).
See the [Python guide](../../examples/python/README.md) for the implemented design
and live verification results. Findings below reflect the research date.

Checked 2026-09-15 for **Choose the Python agent and sandbox execution design**.
This is a small documentation check for an automation demo. No packages were
installed, credentials accessed, inference requested, or sandbox operations run.

## Pydantic AI and Token Factory

Pydantic AI documents both a native `NebiusProvider` and the generic
`OpenAIChatModel` with `OpenAIProvider(base_url=..., api_key=...)`. The latter
makes the Token Factory endpoint explicit in the example. Use the Chat
Completions model class explicitly; the current docs say the bare `openai:`
shorthand selects the Responses API. The minimal dependency option is
`pydantic-ai-slim[openai]`. These are documented integration surfaces, not a
successful test against the chosen receipt model.
[Pydantic AI provider guide](https://pydantic.dev/docs/ai/models/openai/)

Nebius's vision example uses
`https://api.tokenfactory.nebius.com/v1/` and sends image content through Chat
Completions. This supports proposing rendered receipt pages as image inputs;
it does not establish that every model supports images, tool calls, and the
chosen structured-output mode together.
[Token Factory vision documentation](https://docs.tokenfactory.nebius.com/api-reference/examples/vision-capabilities)

The framework can register ordinary synchronous or asynchronous Python
functions through `tools`, `@agent.tool`, or `@agent.tool_plain`. Its agent API
also exposes an output type and separate tool/output retry budgets. An
extraction tool, reconciliation tool, and report-writing tool therefore fit
the documented framework surface without a multi-agent framework or external
tool server. That fit is an inference from the API, not an implemented workflow.
[Pydantic AI agent API](https://pydantic.dev/docs/ai/api/pydantic-ai/agent/)

## Nebius Sandboxes execution and files

The official ConTree SDK README demonstrates choosing an image, executing a
command with `run()`, supplying input files through
`files=[UploadFileSpec(source=..., path=...)]`, and retrieving generated files
with `session.download(remote_path, local_path)` or reading bytes with
`session.read(remote_path)`. Synchronous executions use `.wait()`. Sessions
track filesystem image versions after commands; they should not be described
as proof that several `run()` calls share one continuously running process.
[Official ConTree SDK README](https://github.com/nebius/contree-sdk)

The docs and default release still differ materially. The current GitHub README
constructs `Contree`/`ContreeSync` with an existing `contree_client` transport;
PyPI's stable release remains **0.3.6**, whose published example constructs
`Contree(token=...)`. PyPI also lists **0.4.0.dev5** as a prerelease. Do not copy
current-main setup examples into a stable-version install without checking the
matching version. This corroborates the repository's earlier mismatch finding;
it is not a fresh runtime inspection of the installed SDK.
[Official SDK README](https://github.com/nebius/contree-sdk),
[Published SDK and release history](https://pypi.org/project/contree-sdk/)

## Smallest proposed design

Recommendation, subject to the live design discussion: a local launcher sends
the receipts and starts one Python agent process in one Nebius sandbox. The
agent calls Token Factory and uses ordinary Python tools to extract receipts,
reconcile expenses, and generate PDF plus JSON. Retrieval happens before the
result is discarded. Use deterministic arithmetic and PDF generation; the
model supplies interpretation and tool decisions. Flagged items are final
automated outcomes, as defined in `CONTEXT.md`.

Keep the existing HTTPS launcher unless teaching the high-level sandbox SDK
is itself a requirement. Its existing live execution evidence is recorded in
[the Python guide](../../examples/python/README.md); artifact upload/download still needs
implementation verification. SDK download examples alone do not prove that
artifacts survive the current launcher's disposable execution settings.
