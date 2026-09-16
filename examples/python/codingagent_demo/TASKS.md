# Coding-agent demo task plan

This is the finalized plan for
[Which task ladder demonstrates longer autonomous execution?](https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos/issues/23),
using the agreed
[coding-task helper contract](https://github.com/kreuzhofer/nebius-token-factory-sandbox-demos/issues/22).
The helper, fixtures, and checks described below are implementation work still to
come. No live coding-agent results are claimed here.

The examples demonstrate supplying files, running OpenCode unattended in a fresh
Nebius sandbox with Token Factory inference, and retrieving an answer, workspace
archive, and logs. Automatic checks report task correctness separately from the
agent's execution outcome. There is no manual review stage.

## Progression and budgets

| Stage | Work | Server execution cap |
| --- | --- | --- |
| Create | Write and execute a CSV summary script | 300 seconds |
| Repair | Diagnose and fix a small multi-file project | 600 seconds |
| Extend | Add directory input, two output formats, and invalid-row reporting | 1800 seconds |
| Deadline probe | Exercise timeout handling with a deterministic command | 15 seconds |

The configured account returned `instance_max_timeout = 3600` from `GET /whoami`
on 2026-09-16. This is an observed account limit, not a universal service limit.
Read it again before live runs and reject requested caps above the reported
limit. If the limit cannot be established, report that prerequisite failure.
See the [token information API](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/auth/get-current-token-information).

Caps include setup and execution; they are not expected or minimum durations.
Allow a bounded client polling grace period of 120 seconds beyond each execution
cap for terminal status and checkpoint availability. This is a client policy to
verify during implementation, not a provider guarantee. An expired client wait
does not by itself establish that the remote operation has stopped.

Record actual elapsed time. If the larger task completes quickly, report that
honestly; it does not demonstrate sustained execution near the configured cap.
Increase useful project work in a later bounded experiment if longer execution
is needed. Do not pad coding tasks with sleeps.

## Create: write and run a script

Supply `expenses.csv`:

```csv
date,category,amount
2026-01-01,books,12.50
2026-01-02,books,7.50
2026-01-03,food,3.20
2026-01-04,food,6.80
```

Task: create `summarize.py`, accepting an input path and `--output PATH`, and run
it to produce `summary.json`. Use exact decimal arithmetic and two-decimal
strings for money. The JSON contract is:

```json
{"categories": {"books": "20.00", "food": "10.00"}, "total": "30.00", "count": 4}
```

Checks: the archive contains the script, input, and generated JSON; the JSON has
the expected values; running the returned script again produces the same values.
Compare parsed values rather than whitespace. Save the agent's final answer and
logs, but do not use its claim of success as the correctness check.

## Repair: fix an uploaded project

Supply a small standard-library Python package with separate CLI, CSV-reading,
and aggregation modules. Its public command is
`python -m expense_summary INPUT --output PATH`, using the same JSON contract.
Include runnable tests and three deliberate bugs: binary-float money handling,
discarded negative amounts, and naive comma splitting.

Use this regression input:

```csv
date,category,amount
2026-01-01,supplies,0.10
2026-01-02,supplies,0.20
2026-01-03,supplies,-0.10
2026-01-04,"food, takeaway",2.35
```

Task: diagnose and repair the project, preserve its interface, run its tests, and
write the summary. Expected category totals are `supplies = "0.20"` and
`food, takeaway = "2.35"`; grand total is `"2.55"`, with four records.

Checks: rerun the original tests against the returned code, and independently
exercise the public CLI with quoted fields, refunds, and decimal inputs. Keep
authoritative copies of checks and expected values outside the agent's writable
workspace. Include a rounding-sensitive case of one hundred `0.01` entries
totalling `"1.00"`. Fixture preparation must verify that the initial bugs fail
their intended checks and a maintained reference solution passes them.

## Extend: make a larger bounded change

Start from a maintained, correct version of the repair project, not the output
of a previous model run. Each stage is reproducible in a fresh sandbox.

Task: add directory input and `--format json|csv`; read top-level `.csv` inputs
in filename order, sort output categories, and report invalid rows while keeping
valid records. Preserve single-file input and default JSON behavior. Run tests
and generate both output formats.

The directory contains `a.csv` (the repair input above) and `b.csv`:

```csv
date,category,amount
2026-01-05,supplies,1.05
2026-01-06,"food, takeaway",2.45
2026-01-07,misc,not-a-number
```

Expected results:

- Six valid records, with category totals `food, takeaway = "4.80"` and
  `supplies = "1.25"`, and grand total `"6.05"` in JSON.
- CSV has columns `category,total` and those two category rows in sorted order,
  using normal CSV quoting. It contains no extra grand-total row.
- Each invocation writes `issues.json` beside its selected output, containing
  one issue identifying `b.csv`, line 4, and the invalid amount. Do not require
  exact wording of the explanation.
- Exit status is zero when valid records were processed and invalid rows were
  reported. Unreadable input or no valid records produces a nonzero status and
  a diagnostic.

Checks: exercise both formats, filename/category ordering, legacy single-file
behavior, invalid-row reporting, and the stated error cases through the public
CLI. Verify ordering with a separate fixture whose per-file errors expose input
ordering. Keep generated outputs outside the input directory. Validate the
returned archive and execution record automatically.

## Deadline probe

Run a deterministic command that flushes a startup marker, writes a small
workspace file, then sleeps for 60 seconds, with a 15-second server timeout.
Use the same submission, waiting, outcome, and retrieval path as coding tasks,
but no model call. This is a lifecycle probe, not a long-running coding example.

Check that the process is reported as timed out when confirmed by the provider,
that the operation ID is preserved, and that the task is not resubmitted.
Retrieve diagnostics and files if available. An unavailable checkpoint is an
explicit artifact-recovery outcome, not a reason to invent an archive or claim
successful execution. Use local fault-injection tests for connection loss and
unconfirmed cancellation; do not depend on nondeterministic network outages.

## Implementation proof and test boundaries

First pin an available OpenCode release and a tool-capable Token Factory model.
Record their exact identifiers with the run, and use configuration matching that
release. Before attempting the ladder, prove one small edit-and-test task:
inference and tool calls work, auxiliary inference remains on Token Factory,
interactive prompts are disabled, progress and the final answer are captured,
and files can be retrieved. Implement this as a narrow integration proof; a
separate throwaway prototype is unnecessary unless compatibility fails.

The test boundaries are the helper's public task/result interface, the returned
program's CLI, and the existing shared sandbox lifecycle interface. Reuse its
operation, process-failure, and cancellation coverage. Add helper outcome tests
at the caller boundary rather than testing private OpenCode parsing functions.

Authoritative checks run returned code in a fresh validation sandbox with a
60-second execution cap per stage, not directly on the user's machine. Validation
uses neither inference credentials nor networking. Deliver checks to that
sandbox separately from the returned workspace, and use literal fixture results
as the oracle. These checks are demo evidence, not adversarial evaluation.

For each run, retain task identity, operation ID, runtime/model identifiers,
configured timeout, elapsed time, execution outcome, automatic check results,
answer, log location, and archive availability. A completed agent run with failed
checks remains a completed run with failed checks. A failed stage stops automatic
progression and reports its evidence; repeat only through an explicit new run.

## Delivery boundary

This ticket finalizes the plan. Implementation supplies the helper, runtime
configuration, fixtures, reference solutions, validators, and live-run evidence
as subsequent work. No second runtime, persistent session, detached interface,
manual review queue, or model comparison suite is required.
