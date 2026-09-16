# Live example results

## Final complete sequence

`example all` passed at 2026-09-16 23:02 UTC, using `moonshotai/Kimi-K2.7-Code`
for all coding tasks and the same prepared image. No retries or manual edits
were needed within this sequence. The deadline stage uses no model.

| Stage | Task elapsed | Task operation | Validation operation | Result |
| --- | --- | --- | --- | --- |
| Create | 22.740 s | `01a0ac72-147d-77c7-a580-651e2e92fef5` | `01a0ac72-780b-7571-abeb-d7928903c18b` | Passed |
| Repair | 49.371 s | `01a0ac72-9943-7717-a221-34adfb7eecfd` | `01a0ac73-6393-72b9-b225-cceac4aacd2f` | Passed |
| Extend | 95.199 s | `01a0ac73-8ba7-709a-8011-567e8f2705e9` | `01a0ac75-082c-77aa-bc70-245b4b136fd4` | Passed |
| Deadline | 18.286 s | `01a0ac75-168f-7372-b699-6e0100ef109a` | Not applicable | Confirmed timeout; startup archive recovered |

Task elapsed includes submission, execution, polling, and retrieval. Validation
has its own 60-second cap. These short runs do not demonstrate execution near
the 30-minute cap.

Reproduce using the command in [README.md](README.md). The local evidence for
this development run is `/private/tmp/coding-ladder-final/ladder.json`, with
per-stage answers, logs, and workspace archives alongside it. These local paths
are not portable; every new invocation writes its own result directory.

## Earlier development runs

Runs on 2026-09-16 use OpenCode 1.18.31 and prepared runtime image
`a485428f-a38c-42a5-9e55-ac216fa5b045`. Each task starts a fresh sandbox.
Checks run separately without networking or inference credentials. Create and
Repair below used `Qwen/Qwen3-235B-A22B-Instruct-2507`; the passing Extend run used
`moonshotai/Kimi-K2.7-Code`, now the demo default. The deadline probe uses no model.

| Stage | Cap | Task elapsed | Task operation | Validation operation | Outcome |
| --- | --- | --- | --- | --- | --- |
| Create | 300 s | 17.885 s | `01a0ac59-fb8f-77e1-81a4-e4e48b7c9a8f` | `01a0ac5a-3c83-7018-9e16-fb6a92ea6b86` | Completed; generated summary and rerun passed |
| Repair | 600 s | 31.101 s | `01a0ac66-24c1-73b6-b0ea-fc8d50d8f7a4` | `01a0ac66-93e6-7686-8f92-91b4fb711ee3` | Completed; original tests and independent regression passed |
| Extend | 1800 s | 148.279 s | `01a0ac6e-721a-73b2-8555-8dc23b416ed0` | `01a0ac70-acb7-76f0-a52c-22d865a3613f` | Completed; all six check groups passed |
| Deadline | 15 s | 19.673 s | `01a0ac70-61e3-765d-bd45-161de765baf2` | No inference/validation job | Confirmed timeout; startup archive and process log recovered |

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

Extend attempt 2 (`01a0ac6b-4d9f-702a-a3f8-9471bcd1a40a`) completed in
102.672 seconds but failed checks for issue-file placement, row numbers, and
invalid-only input (`01a0ac6c-d459-7679-933b-986c1a4bda54`). The next run changed
only the model to the available coding model; the prompt, inputs, and checks
stayed unchanged.

These durations are observations, not minimum runtimes or evidence of execution
near the configured caps. Local run directories contain `example.json`, the
answer, workspace archive, and agent logs; they are not committed to the repo.
