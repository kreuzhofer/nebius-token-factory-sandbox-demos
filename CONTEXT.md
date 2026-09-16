# Agent demos

Receipts demonstrate automated agents running in Nebius Sandboxes and using
Token Factory for inference. The expense report retains original evidence and
flags problematic records; the demo has no manual review or correction stage.

Three agent roles carry the workflow from input receipts to the final result.

## Language

### Receipt reporting

**Coordinator agent**:
The agent that enumerates receipts, dispatches receipt agents, collects their
outcomes, and requests the report. It retrieves and returns the final report or
errors to the caller.

**Receipt agent**:
An agent that processes one receipt and returns structured fields or a flagged
failure. Multiple receipt-agent instances share the same implementation.

**Report agent**:
The agent that reconciles collected receipt outcomes and generates the expense
report artifacts, returning them to the coordinator.

**Receipt**:
A source document recording a purchase or refund; it may span multiple pages.

**Parsed receipt**:
The extracted content, structure and expense fields of a receipt, linked to its
source evidence and any parsing issues.

**Reconciliation**:
Checking receipts for duplicates, monetary inconsistencies and missing information,
and organizing their expenses. It does not mean bank-statement matching or
reimbursement approval in this example.

**Flagged item**:
A receipt or field that could not be processed reliably and is flagged in the
final report as a completed automated outcome. It does not enter a human queue.
_Avoid_: Review item, pending review

**Expense report**:
A summary of reconciled expenses and flagged items, followed by an appendix of
original receipt pages and their extracted fields.

**Shared receipt corpus**:
The project-provided input receipts reused by the language examples to demonstrate
the automated workflow, including representative successful and problematic inputs.

**Synthetic receipt**:
A deliberately constructed receipt with known source values, labelled as synthetic
so it remains distinguishable from a real receipt.

**Receipt variant**:
A duplicate or altered representation of a source receipt used to exercise
processing behavior; it retains that receipt's identity rather than counting as
another independent example.

**Expected results**:
Known values and outcomes used for lightweight checks of the demo's behavior.
Values unreadable in the supplied evidence remain explicitly unknown, even when
the underlying synthetic source values are known.

### Coding tasks

**Coding agent**:
An agent that changes and executes code to fulfill a task using the supplied
files, returning its answer and the resulting workspace.

**Coding task**:
One requested unit of coding work, described by instructions and explicitly
supplied files or folders. Each task begins in a fresh workspace.

**Task outcome**:
The coding agent's execution status, answer, available workspace files, and
diagnostics. Completion means the agent finished; passing correctness checks is
a separate result.
