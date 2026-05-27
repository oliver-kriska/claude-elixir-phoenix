#!/bin/bash
# Structural checks that the scorer doesn't cover.
# Run AFTER eval passes. If checks fail, revert regardless of score.
# Usage: checks.sh <skill-name>
#
# Inspired by pi-autoresearch's autoresearch.checks.sh pattern:
# catches things the metric can't measure.

set -euo pipefail

SKILL_NAME="$1"
SKILL_DIR="plugins/elixir-phoenix/skills/${SKILL_NAME}"
SKILL_FILE="${SKILL_DIR}/SKILL.md"
PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

cd "$PROJECT_ROOT"

if [ ! -f "$SKILL_FILE" ]; then
    echo "FAIL: Skill file not found: $SKILL_FILE"
    exit 1
fi

ERRORS=0

# 1. Markdown lint (if available)
if command -v npx &>/dev/null && [ -f "node_modules/.bin/markdownlint" ]; then
    if ! npx markdownlint "$SKILL_FILE" --quiet 2>/dev/null; then
        echo "FAIL: markdownlint errors in $SKILL_FILE"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 2. YAML frontmatter must parse
python3 -c "
import yaml
with open('$SKILL_FILE') as f:
    content = f.read()
if not content.startswith('---'):
    raise ValueError('No frontmatter')
end = content.find('---', 3)
fm = yaml.safe_load(content[3:end])
assert fm.get('name'), 'Missing name'
assert fm.get('description'), 'Missing description'
" 2>/dev/null || {
    echo "FAIL: YAML frontmatter broken in $SKILL_FILE"
    ERRORS=$((ERRORS + 1))
}

# 3. File size under hard limit (command skills: 185, reference: 150, orchestrators: 535)
LINES=$(wc -l < "$SKILL_FILE")
if [ "$LINES" -gt 535 ]; then
    echo "FAIL: $SKILL_FILE is $LINES lines (hard limit: 535)"
    ERRORS=$((ERRORS + 1))
fi

# 4. All reference files mentioned in SKILL.md exist
python3 -c "
import re, os
with open('$SKILL_FILE') as f:
    content = f.read()
refs = re.findall(r'CLAUDE_SKILL_DIR\}?/references/([\w-]+\.md)', content)
missing = [r for r in refs if not os.path.isfile('$SKILL_DIR/references/' + r)]
if missing:
    print(f'FAIL: Missing reference files: {missing}')
    exit(1)
" 2>/dev/null || {
    ERRORS=$((ERRORS + 1))
}

# 5. No conflict markers
if grep -qE '<<<<<<|======|>>>>>>' "$SKILL_FILE" 2>/dev/null; then
    echo "FAIL: Conflict markers in $SKILL_FILE"
    ERRORS=$((ERRORS + 1))
fi

# 6. No empty sections (heading followed immediately by another heading)
python3 -c "
import re
with open('$SKILL_FILE') as f:
    lines = f.readlines()
prev_was_heading = False
for i, line in enumerate(lines):
    is_heading = line.startswith('## ') or line.startswith('### ')
    if is_heading and prev_was_heading:
        print(f'FAIL: Empty section at line {i}: {lines[i-1].strip()}')
        exit(1)
    prev_was_heading = is_heading and not lines[i+1].strip() if i+1 < len(lines) else is_heading
" 2>/dev/null || {
    ERRORS=$((ERRORS + 1))
}

# 7. Protected-section invariant: Iron Laws are append-only (SkillOpt fast/slow split).
#    A mutation may ADD an Iron Law but never delete or reword an existing one.
#    Compares the working tree against git HEAD (last kept state). New skills not
#    yet in HEAD are skipped — there is nothing to protect.
PROTECT_OUT=$(python3 "$(dirname "$0")/protected_sections.py" "$SKILL_FILE" 2>/dev/null) || {
    echo "${PROTECT_OUT:-FAIL: protected Iron Law eroded}"
    ERRORS=$((ERRORS + 1))
}

if [ "$ERRORS" -gt 0 ]; then
    echo "CHECKS FAILED: $ERRORS errors"
    exit 1
fi

echo "CHECKS PASSED"
exit 0
