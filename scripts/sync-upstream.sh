#!/usr/bin/env bash
# sync-upstream.sh
# upstream(lfnovo/open-notebook)의 최신 변경사항을 main에 merge하고,
# custom/main에도 merge하는 스크립트

set -e

echo "🔄 Fetching upstream..."
git fetch upstream

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📍 Current branch: $CURRENT_BRANCH"

# ── Step 1: main ← upstream/main ──────────────────────────
echo ""
echo "📥 Merging upstream/main → main..."
git checkout main
git merge upstream/main --no-edit -m "chore: sync upstream lfnovo/open-notebook"
git push origin main
echo "✅ main is now up to date with upstream"

# ── Step 2: custom/main ← main ────────────────────────────
echo ""
echo "📥 Merging main → custom/main..."
git checkout custom/main
git merge main --no-edit -m "chore: merge upstream sync into custom/main"
git push origin custom/main
echo "✅ custom/main is now up to date"

# ── Return to original branch ─────────────────────────────
git checkout "$CURRENT_BRANCH"
echo ""
echo "🎉 Sync complete! Returned to: $CURRENT_BRANCH"
