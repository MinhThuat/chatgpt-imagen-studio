#!/usr/bin/env bash
# Bam 1 cai la day code len GitHub. Lan dau hoi URL repo, sau do nho luon.
#   ./publish.sh                 # commit moi thay doi + push
#   ./publish.sh <git-url>       # set remote lan dau roi push
set -e
cd "$(dirname "$0")"
git config --global --add safe.directory "$PWD" 2>/dev/null || true

[ -d .git ] || git init -q
git branch -M main 2>/dev/null || true

# Chua co remote -> lay tu tham so hoac hoi
if ! git remote get-url origin >/dev/null 2>&1; then
  URL="${1:-}"
  [ -z "$URL" ] && read -rp "URL repo GitHub (vd git@github.com:ban/imagegen-studio.git): " URL
  [ -z "$URL" ] && { echo "!! Chua co URL, dung."; exit 1; }
  git remote add origin "$URL"
fi

# Commit neu co thay doi
if ! git diff --quiet || ! git diff --cached --quiet || \
   [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git add -A
  git commit -q -m "update $(git rev-list --count HEAD 2>/dev/null || echo 1)"
  echo "[publish] da commit thay doi moi."
else
  echo "[publish] khong co thay doi moi."
fi

git push -u origin main
echo "[publish] xong -> $(git remote get-url origin)"
