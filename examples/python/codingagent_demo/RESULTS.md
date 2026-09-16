# Live example results

Runs on 2026-09-16 use OpenCode 1.18.31, Token Factory model
`Qwen/Qwen3-235B-A22B-Instruct-2507`, and prepared runtime image
`a485428f-a38c-42a5-9e55-ac216fa5b045`. Each task starts a fresh sandbox.
Checks run separately without networking or inference credentials.

| Stage | Cap | Task elapsed | Task operation | Validation operation | Outcome |
| --- | --- | --- | --- | --- | --- |
| Create | 300 s | 17.885 s | `01a0ac59-fb8f-77e1-81a4-e4e48b7c9a8f` | `01a0ac5a-3c83-7018-9e16-fb6a92ea6b86` | Completed; generated summary and rerun passed |
| Repair | 600 s | 31.101 s | `01a0ac66-24c1-73b6-b0ea-fc8d50d8f7a4` | `01a0ac66-93e6-7686-8f92-91b4fb711ee3` | Completed; original tests and independent regression passed |

Repair attempt 1 (`01a0ac5c-8ab5-70e8-b5da-e41b5380168d`) timed out after
584.170 seconds including setup/retrieval. The agent repeatedly patched a manual
CSV parser. The helper returned `timed_out` and recovered its workspace and logs;
validation did not run. The task prompt was clarified to use `csv.DictReader` and
`decimal.Decimal` before starting a new run. No checks were relaxed.

Extend attempt 1 (`01a0ac69-0933-7191-905e-238a3c641da4`) completed in
86.971 seconds but failed independent validation
(`01a0ac6a-4d07-71aa-86fe-28986f9dc6f2`): issue lists were empty. Inspection
also found manually joined CSV rows. Before a fresh run, the prompt added the
specified expected outputs and explicit `csv.writer` guidance. Checks were unchanged.

These durations are observations, not minimum runtimes or evidence of execution
near the configured caps. Local run directories contain `example.json`, the
answer, workspace archive, and agent logs; they are not committed to the repo.
