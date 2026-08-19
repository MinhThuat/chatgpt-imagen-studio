#!/usr/bin/env bash
# Mo Imagegen Studio: terminal (Claude) o duoi + gallery anh o tren.
set -e
cd "$(dirname "$0")"
PORT="${1:-8760}"
URL="http://127.0.0.1:$PORT"

# Tien trinh nen -> tat het khi Studio thoat.
PIDS=()
trap 'kill "${PIDS[@]}" 2>/dev/null' EXIT

# Tu cap nhat code moi tu git moi 60s (neu la git repo).
[ -d .git ] && { ./autoupdate.sh & PIDS+=($!); }

# Tu refresh token codex: chay ngay + moi 15 phut (khong phu thuoc cron tren may user).
# refresh_token.py tu notify "codex login" neu refresh_token het han han.
( while :; do python3 refresh_token.py >/dev/null 2>&1 || true; sleep 900; done ) & PIDS+=($!)

( sleep 1; xdg-open "$URL" >/dev/null 2>&1 || true ) &
python3 imagegen_studio.py --port "$PORT"
