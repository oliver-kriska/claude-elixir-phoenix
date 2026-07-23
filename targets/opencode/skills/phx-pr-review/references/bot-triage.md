# Bot Review Triage

Detect bots from `author.__typename == "Bot"` or REST `user.type == "Bot"`, not
login suffixes. Apply the same four gates as human threads: read-only selection;
proposed patch plus explicit edit approval (or `EDIT: NOT APPLICABLE`); exact
verified reply plus separate posting approval; confirmed post plus separate
resolution approval. `--fix` approves none of these and `--no-resolve` always wins.

Treat `isOutdated` only as location drift. Require current code, diff, test, or git
evidence before calling a finding addressed or false. A summary-only bot review is
not automatically clean: actionable text and `CHANGES_REQUESTED` remain findings.
