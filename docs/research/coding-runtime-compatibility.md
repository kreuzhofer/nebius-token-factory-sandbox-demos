# Coding runtime feasibility: preliminary official-docs research

Checked 2026-09-16. Scope: one task per fresh Nebius sandbox, Python helper outside, coding harness inside, Token Factory inference. Documentation evidence only; no runtime installed or paid task executed.

## OpenCode fits the proposed first runtime

OpenCode has two separately published documentation trees. The unversioned docs install `opencode-ai`; the V2 docs install `@opencode/cli` and describe versioned Docker images such as `ghcr.io/anomalyco/opencode:2.0.0`. The V2 npm postinstall selects a native platform binary. These facts do **not** establish which release/tag is available or stable for the intended sandbox platform. Pin the tested package/image version and use its matching docs/config; do not combine V1 and V2 examples. [V1 installation](https://opencode.ai/docs/), [V2 installation](https://opencode.ai/v2/docs/)

The V2 CLI documents `opencode run --standalone --model provider/model --format json "task"`: headless execution, a private server inheriting the process environment, and newline-delimited JSON for scripts. Repeated `--file` flags attach local files; `--agent` selects an agent. Session export produces JSON separately. The page does not define the JSON event schema or complete exit-code semantics. Those require pinned-source inspection or an executable probe before defining the wrapper's result parser. [V2 commands](https://opencode.ai/v2/docs/cli/commands/)

V1 also supports noninteractive `opencode run`, `--model`, `--file`, and `--format json` (raw JSON events). Its documented server attachment flag is `--attach`; V2's `--standalone` must not be assumed available in V1. [V1 CLI](https://opencode.ai/docs/cli/)

## Avoiding interactive pauses

V2 uses ordered `permissions` rules containing `action`, `resource`, and `effect`; last match wins. Wildcard action/resource with `allow` permits tools without approval. Defaults still ask for external directories and `.env` reads. Agent rules are appended after global rules, so configure the actual selected agent as well. V1 uses the different `permission` field and action names such as `bash`/`task`; V2 uses `shell`/`subagent`. OpenCode's shell carries the hosting process's filesystem/process/network authority. [V2 permissions](https://opencode.ai/v2/docs/permissions/)

A separate interaction tool, `question`, pauses for user input. Full tool approval alone therefore does not prove an unattended run cannot pause. For this demo, an explicit headless agent with all execution permissions allowed and the question tool disabled is a reasonable candidate to test. This is a design recommendation, not a verified configuration. Shell commands have a default two-minute foreground timeout; longer commands can supply their own timeout. Background shell commands have no timeout unless supplied. These are distinct from the Nebius job deadline. [V2 tools](https://opencode.ai/v2/docs/tools/)

Web search has an additional first-use provider selection prompt. V2 supports configuring the search provider in advance or setting `websearch: false`. This is separate from ordinary internet access and shell-based downloads. [V2 websearch](https://opencode.ai/v2/docs/websearch/)

## Token Factory inference

Nebius documents OpenAI-compatible Chat Completions at `https://api.tokenfactory.nebius.com/v1/`, authenticated by an API key. [Nebius quickstart](https://docs.tokenfactory.nebius.com/quickstart)

OpenCode V2 custom providers support `package: "@opencode/ai/providers/openai-compatible"`, `settings.baseURL`, environment-supplied credentials, and explicitly listed models. Therefore Token Factory integration is supported at the protocol/configuration level; actual streaming, reasoning, and tool-call compatibility of the chosen model remain untested. [V2 providers](https://opencode.ai/v2/docs/providers/)

Custom model configuration can declare the upstream `modelID`, tool support, input/output modalities, and context/output limits. These values must reflect the actual selected Token Factory model; OpenCode cannot discover their correctness automatically. [V2 models](https://opencode.ai/v2/docs/models/)

V1 uses `provider`, `npm: "@ai-sdk/openai-compatible"`, and `options.baseURL` instead. It also documents auxiliary inference for small tasks, so the proof should confirm all auxiliary/title/compaction calls stay on Token Factory rather than silently choosing another configured provider. [V1 providers](https://opencode.ai/docs/providers/)

Inference itself requires outbound connectivity. Disabling webfetch/websearch tools does not remove shell network authority. A future "no internet except inference" mode requires an enforced network boundary or proxy, not merely an agent instruction. OpenCode documents standard proxy variables and a required loopback exclusion for its local CLI/server link; that configuration alone is not an egress firewall. [V2 network](https://opencode.ai/v2/docs/network/)

## OpenClaw is a credible later adapter

Current OpenClaw docs explicitly recommend `openclaw agent exec` for headless coding/CI. It runs embedded without a Gateway, accepts a prompt or `--message-file`, `--cwd`, `--config`, and `--model`; `--json` emits a result envelope with `ok`, `status`, `final`, payloads, and optional usage. It documents timeout default 600 seconds, `--timeout` override, and exit codes 0 success, 1 error, 2 timeout. This is a stronger documented one-shot result contract than the OpenCode CLI page currently provides. [OpenClaw agent CLI](https://docs.openclaw.ai/cli/agent)

OpenClaw supports custom model providers/base URLs through `models.providers`; the exact Token Factory configuration and chosen release still need verification. [Provider configuration index](https://docs.openclaw.ai/concepts/model-providers)

Its exec policy supports full/off operation without ordinary permission prompts, but strict inline evaluation and effective host/session policy can introduce additional approval behavior. Do not claim a verified unattended setup from a single flag. [Exec tool policy](https://docs.openclaw.ai/tools/exec)

Current installation docs require Node 24.16+ or 26.1+ and document npm/container installation. That is a separate runtime image/toolchain choice from OpenCode. [OpenClaw installation](https://docs.openclaw.ai/install)

## Recommended next questions and proof

1. Which pinned OpenCode release/image will be used, and does it run in the available Nebius sandbox image/platform?
2. What exact event/result/exit behavior distinguishes success, tool failure recovered by the agent, model failure, permission/question attempts, timeout, and cancellation?
3. Can one Token Factory model complete file read/edit/test and produce retrievable changed files, with all inference staying on Token Factory?
4. Can the selected agent configuration run unattended, including external paths, shell commands, question tools, and any first-use setup?
5. Where do final text, changed workspace files, and diagnostic transcript live so they can be retrieved even when stdout is truncated or a run fails?

Recommendation: OpenCode first, a small runtime adapter boundary, OpenClaw as a later alternative rather than two mandatory initial integrations. Prove one edit-and-test task, then a bounded multi-file task, then a longer task. Measure actual duration, result retrieval, and timeout behavior; this should demonstrate the process rather than become a benchmark suite.
