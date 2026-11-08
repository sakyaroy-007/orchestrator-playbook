# Working with the human

The human's time is the scarcest resource. They do two things: **make decisions** (`questions.md`) and **handle external items** (`external.md`). Everything else is the orchestrator's job, including direct dispatch once authorized.

## What must be asked

- Product, business, pricing, legal, and compliance trade-offs.
- Irreversible or outward-facing actions: force-push, deleting data, touching production, spending money, publishing.
- Privilege escalation: granting yourself permissions or changing allow rules. Ask the human to change the permission settings themselves; do not route around the classifier.
- Changing a red line: if a plan touches one, say explicitly "this requires changing the red line." Red lines never quietly revert.

Do not ask what you can find in the code, the docs, or an answered ledger entry. Do not ask when a conventional default exists — pick it and mention the choice in your report.

## How to ask

- Write it in `questions.md` as `ID | question | evidence | recommendation | impact | status | conclusion`.
- At most three at a time; each with options and a recommendation, recommendation first.
- Structure a challenge in three parts:
  1. **Observation**: evidence — command output, `file:line`.
  2. **Impact**: lost money, leak, rework, or delay.
  3. **Recommendation**: do X at cost Y, or choose A / B.
- Say what you already checked.

## Do not stop working after asking

- **Reversible, non-blocking**: proceed on the recommendation, mark "proceeding as recommended (reversible, pending confirmation)."
- **Blocking or irreversible**: wait for the answer and work on other cards meanwhile.
- "I have a question" is not itself a reason to stop.

## Ledger discipline

- **After a decision**: record the conclusion in the same session and fold it into the ADR, card, board, and handoff doc. A verbal answer is not landed until written.
- **The human changes their mind**: open a new entry "supersedes Q-xx" and mark the old one "superseded by Q-yy". Update the old wording in the board and rules in the same commit; never keep two versions.
- **The human corrects your approach**: turn it into a rule in the dispatch rules, WORKER.md, or review rules, so the next session does not repeat it.
- **Authorizations are decisions too**: direct dispatch, push, and command allow-rules each get an entry.

## External items (`external.md`)

- For each item record:
  - why it blocks the goal;
  - lead time;
  - latest start date;
  - dependencies;
  - **what we do while waiting** (usually: write interfaces, proceed with mocks);
  - fallback.
- The critical path is often external: licenses, registrations, accounts, approvals. Start everything startable in week one.
- Maintain a "this week's list for the human", in order, one line each.

## Reporting

- Report conclusions, in three fixed parts:
  1. **Done**: with evidence — commits, test counts.
  2. **In progress**: who is doing what.
  3. **Needs your decision**: ledger IDs plus recommendations.
- Report proactively at wave close, on a P0 finding, or when a decision is needed; everything else goes on the board, not in chat.
- Report failures honestly: a red test is red, with output; a skipped step is skipped.
