#!/usr/bin/env bash
# new-feature.sh <feature-name>
# custom/main 기반으로 새 커스텀 기능 브랜치를 생성합니다

set -e

FEATURE_NAME="$1"

if [ -z "$FEATURE_NAME" ]; then
  echo "Usage: ./scripts/new-feature.sh <feature-name>"
  echo "Example: ./scripts/new-feature.sh add-sso-login"
  exit 1
fi

BRANCH="custom/feature/$FEATURE_NAME"

echo "🌿 Creating branch: $BRANCH from custom/main..."
git checkout custom/main
git pull origin custom/main
git checkout -b "$BRANCH"
git push -u origin "$BRANCH"

echo "✅ Branch '$BRANCH' created and pushed."
echo "👉 Start working: git checkout $BRANCH"
