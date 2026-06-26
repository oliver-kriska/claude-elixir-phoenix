# Special Scan Modes

## Gate Mode (`--gate`)

Quality gate for CI integration. NO agents needed -- Python script only.

```
/xray:scan --gate measure   # Scan project, create baseline.json
/xray:scan --gate check     # Compare against baseline, exit 0 (pass) or 1 (fail)
```

Run:

```bash
python3 "{SCRIPTS}/quality-gate.py" {SUBCOMMAND} "{PROJECT_ROOT}" --baseline .claude/xray/baseline.json
```

Present results to user. For `check`: show pass/fail per category + any regressions.

## PR Mode (`--pr NUMBER`)

Targeted scan of files changed in a specific PR. Much faster than full scan (~2 min).

1. Get changed files: `gh pr diff NUMBER --name-only` (in the ONE Bash call)
2. Run only relevant scripts:
   - git history: `--since` set to PR base branch merge-base
   - code analysis: pass changed file list (focus on those files)
   - architecture: check if changed files introduce NEW violations
3. Skip: config layer, session layer (not relevant for single PR)
4. Spawn 3 agents (L1, L3, L6) -- not 6
5. Report format: "This PR introduces:" + cross-reference with existing findings

```bash
# PR mode Bash call (ONE command)
PR_FILES=$(gh pr diff {NUMBER} --name-only 2>/dev/null) && mkdir -p .claude/xray/layers/sessions && S="{SCRIPTS}" && P="{PROJECT_ROOT}" && echo "$PR_FILES" > .claude/xray/layers/pr-files.txt && python3 "$S/analyze-git-history.py" "$P" --since "$(git merge-base HEAD main)" > .claude/xray/layers/git-history.json 2>.claude/xray/layers/git-history.err & python3 "$S/analyze-code.py" "$P" --since "$(git merge-base HEAD main)" > .claude/xray/layers/code-docs.json 2>.claude/xray/layers/code-docs.err & bash "$S/analyze-architecture.sh" "$P" > .claude/xray/layers/architecture.json 2>.claude/xray/layers/architecture.err & wait && echo "Done" && wc -c .claude/xray/layers/*.json
```
