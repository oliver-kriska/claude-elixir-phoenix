#!/bin/bash
# Check if current branch is behind origin/main and warn if so.
# Runs on SessionStart. Silent when fresh.
# No `git fetch`: a hook must not reach the network with the user’s git
# credentials, so this compares against the remote refs of the last fetch.

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0
git rev-parse --is-inside-work-tree &>/dev/null || exit 0

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
[ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ] && exit 0

# Count commits behind main (try main, then master)
BASE="origin/main"
git rev-parse --verify "$BASE" &>/dev/null || BASE="origin/master"
git rev-parse --verify "$BASE" &>/dev/null || exit 0

BEHIND=$(git rev-list --count HEAD.."$BASE" 2>/dev/null)
[ -z "$BEHIND" ] || [ "$BEHIND" -eq 0 ] && exit 0

echo "⚠ Branch ‘$BRANCH’ is $BEHIND commits behind $BASE (as of your last fetch). Consider rebasing."
