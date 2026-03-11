#!/usr/bin/env bash
# sync-upstream.sh
# upstream(lfnovo/open-notebook)의 최신 변경사항을 main → custom/main 순으로 merge합니다

set -e

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "🔄 Fetching upstream..."
git fetch upstream

# ── Step 1: main ← upstream/main ──────────────────────────
echo "📥 Merging upstream/main → main..."
git checkout main
git merge upstream/main --no-edit -m "chore: sync upstream lfnovo/open-notebook"
git push origin main

# ── Step 2: custom/main ← main ────────────────────────────
echo "📥 Merging main → custom/main..."
git checkout custom/main
git merge main --no-edit -m "chore: merge upstream sync into custom/main"
git push origin custom/main

git checkout "$CURRENT_BRANCH"
echo "✅ Sync complete. Returned to: $CURRENT_BRANCH"
