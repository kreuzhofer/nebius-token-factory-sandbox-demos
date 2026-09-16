# Nebius sandbox constraints for the coding-agent demo

Checked official documentation and its OpenAPI schema on 2026-09-16. No sandbox job was run and no credentials were read.

## Network and permissions

- The official `InstanceNetworking.enabled` schema defaults to **true**. Setting it false starts the VM without a guest network interface. The only documented networking field is this boolean; the schema contains no host allowlist, egress proxy policy, or separate inference-only route. This is evidence of the public API surface, not proof that Nebius has no private capability. [Official OpenAPI, InstanceNetworking](https://eu-north.nebius.computer/static/api.yaml)
- Therefore, an agent inside the sandbox calling remote Token Factory inference directly needs networking enabled. An inference-only mode would require another enforcement design; turning the interface off cannot retain direct HTTPS inference. This is an inference from the documented interface behavior, not a tested deployment result.
- Sandbox process user/group default to root (UID/GID 0). Agent-level permission approval is a separate OpenCode configuration concern. [Spawn instance](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance)

## Time and resource limits

- Instance `timeout` is a server-side maximum execution time in seconds. Neither its omitted default nor a universal maximum is specified in the spawn schema. `result.state.timed_out` means the process was killed because the operation timeout was reached. [Spawn instance](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance), [Official OpenAPI, ExecutionResult](https://eu-north.nebius.computer/static/api.yaml)
- **Read the actual limit instead of guessing:** `GET /whoami` returns a limits map whose example contains `instance_max_timeout: 3600`. That 3600 is an example, not a guaranteed account limit. This read-only endpoint can resolve the current token limit before selecting long-run experiments. [Current token information](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/auth/get-current-token-information)
- `truncate_output_at` defaults to 1 MiB per recorded stream; maximum 10 MiB. Full stdin is still delivered. `disposable=false` preserves a resulting image; `preserve_env=false` avoids intentionally saving supplied environment into image metadata. [Spawn instance](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance)
- Writable layer default is 12 GiB in the current API schema. The existing repository wrapper may deliberately request smaller limits; coding tools and dependencies need an explicit budget. [Official OpenAPI, InstanceResourcesLimits](https://eu-north.nebius.computer/static/api.yaml)
- The service represents executions as asynchronous operations; the documented normal flow waits until terminal status, then reads the resulting checkpoint. It is not described as an indefinitely idle VM service. [Sandbox overview](https://docs.tokenfactory.nebius.com/sandboxes/overview)

## Completion notification

- `GET /operations/{operationId}/events?follow=1` streams SSE including stdout, stderr, spawn and exit events. It can resume using `Last-Event-Id` or `since`. A subscription needs LIST plus SPAWN or SPAWN_DISPOSABLE permissions.
- A process exit or stream close is insufficient evidence that final artifacts are ready: the endpoint explicitly documents 410 while terminal artifacts are pending. Confirm the operation's final status before downloading outputs.
- No webhook/callback registration surface was found in the official API. SSE is a client-held subscription, not a server-initiated webhook.

Source for the three preceding points: [Operation event stream](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/operations/stream-the-operation-event-log-via-server-sent-events). The documentation browser could not render that page; its official Markdown and the corresponding OpenAPI endpoint were inspected locally.

## Proposed decision questions

1. Does v1 allow general network access so OpenCode can use Token Factory and install dependencies? Recommend yes for this demo; map inference-only egress as a later research decision.
2. Is the first helper a blocking task-to-result call with polling, or must callers detach, observe progress and retrieve later? Recommend keep a simple blocking convenience interface while returning/persisting the operation identifier early; event streaming is a separate capability decision.
3. What concrete artifacts constitute the result: final answer plus a workspace archive, selected output paths, or a patch? This determines retrieval and output limits more directly than copying an entire hosted Agents API.
4. What long-run ladder proves the process? Recommend small edit/test, multi-file change/test, then a bounded larger task. Read the token limit first, explicitly cap execution, and leave time after process completion for checkpoint/retrieval. Exact deadlines remain to be selected, not assumed.

## Unverified items

Actual token limits; real network reachability and endpoint restrictions; omitted timeout behavior; artifact availability after timeout or cancellation; timeout accounting during setup/checkpoint; behavior under long-run model retries and large output. These require targeted API reads or later bounded experiments, not claims based on the docs.
