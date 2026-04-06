#!/usr/bin/env bash
# Stage and commit any uncommitted changes at end of session.
# Commits with a placeholder message — the Stop agent will amend it.
cd "$(git rev-parse --show-toplevel)" || exit 1

if [ -z "$(git status --porcelain)" ]; then
  exit 0
fi

git add -A
git commit -m "wip: session changes (message pending agent rewrite)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
