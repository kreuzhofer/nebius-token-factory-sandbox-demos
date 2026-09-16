# Live example results

Runs on 2026-09-16 use OpenCode 1.18.31, Token Factory model
`Qwen/Qwen3-235B-A22B-Instruct-2507`, and prepared runtime image
`a485428f-a38c-42a5-9e55-ac216fa5b045`. Each task starts a fresh sandbox.
Checks run separately without networking or inference credentials.

| Stage | Cap | Task elapsed | Task operation | Validation operation | Outcome |
| --- | --- | --- | --- | --- | --- |
| Create | 300 s | 17.885 s | `01a0ac59-fb8f-77e1-81a4-e4e48b7c9a8f` | `01a0ac5a-3c83-7018-9e16-fb6a92ea6b86` | Completed; generated summary and rerun passed |

These durations are observations, not minimum runtimes or evidence of execution
near the configured caps. Local run directories contain `example.json`, the
answer, workspace archive, and agent logs; they are not committed to the repo.
