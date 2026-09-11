# Issue tracker: GitHub

Issues and specs live in GitHub Issues for
kreuzhofer/nebius-token-factory-sandbox-demos. Use the gh CLI.

## Conventions

Infer the repository from the Git remote when running inside this clone.

- Create: gh issue create --title "..." --body-file <file>
- Read: gh issue view <number> --comments
- List: gh issue list --state open --json number,title,body,labels,comments
- Comment: gh issue comment <number> --body-file <file>
- Add labels: gh issue edit <number> --add-label "..."
- Remove labels: gh issue edit <number> --remove-label "..."
- Close: gh issue close <number> --comment "..."

For multiline bodies, write the exact text to a temporary file and pass
--body-file. Apply label and state filters as needed.

“Publish to the issue tracker” means create a GitHub issue.
“Fetch the relevant ticket” means read the issue, including comments.

## Pull requests as a triage surface

PRs as a request surface: no.

GitHub shares issue and PR numbers. If a reference is ambiguous, resolve
it with gh pr view <number>, falling back to gh issue view <number>.

## Wayfinding operations

- Map: one issue labelled wayfinder:map, containing Notes,
  Decisions-so-far, and Fog.
- Child tickets: link as GitHub sub-issues. If unavailable, use a task
  list in the map and “Part of #<map>” in each child.
- Ticket types: wayfinder:research, wayfinder:prototype,
  wayfinder:grilling, or wayfinder:task.
- Blocking: use native GitHub issue dependencies through gh api.
  If unavailable, record “Blocked by: #<number>” in the child body.
  A ticket is unblocked when all blockers are closed.
- Frontier: select the first open child in map order with no open
  blockers and no assignee.
- Claim: gh issue edit <number> --add-assignee @me.
- Resolve: comment with the result, close the ticket, and append a
  summary and link to the map’s Decisions-so-far.
