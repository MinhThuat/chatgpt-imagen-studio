#!/usr/bin/env bash
# Setup Imagegen Studio (ban standalone). Chay 1 lan.
set -e
cd "$(dirname "$0")"
HERE="$(pwd)"

echo "== 1. Kiem tra python3 =="
command -v python3 >/dev/null || { echo "!! Chua co python3"; exit 1; }
python3 --version

echo "== 2. Kiem tra claude =="
command -v claude >/dev/null && echo "OK: $(command -v claude)" \
  || echo "!! Chua co 'claude' tren PATH — Studio se mo terminal nhung khong tu chay claude duoc."

echo "== 3. Cai aiohttp (cho server Studio) =="
python3 -c "import aiohttp" 2>/dev/null && echo "aiohttp: da co" \
  || python3 -m pip install --user --break-system-packages "aiohttp>=3.9"

echo "== 4. Tao thu muc output/refs (o HOME, tranh o NTFS hay xoa) =="
mkdir -p "$HOME/imagegen_studio/out" "$HOME/imagegen_studio/refs"
echo "  out : $HOME/imagegen_studio/out"
echo "  refs: $HOME/imagegen_studio/refs"

echo "== 5. chmod +x =="
chmod +x Studio.sh imagegen_studio.py chatgpt-imagegen 2>/dev/null || true

echo "== 6. Auth codex =="
if [ -f "$HOME/.codex/auth.json" ]; then
  echo "  OK: $HOME/.codex/auth.json (dung chung, khong can dang nhap lai)"
else
  echo "  !! Chua co auth — chay: codex login"
fi

echo "== 7. Cron tu refresh token (moi 20 phut) =="
MARK="# imagegen-studio-refresh"
if crontab -l 2>/dev/null | grep -q "$MARK"; then
  echo "  Da co cron refresh (bo qua)."
else
  echo "  Chua co cron refresh cho ban nay. De bat, chay lenh sau:"
  echo "    ( crontab -l 2>/dev/null; echo \"*/20 * * * * cd '$HERE' && python3 refresh_token.py >> '$HERE/refresh.log' 2>&1 $MARK\" ) | crontab -"
  echo "  (Neu ban cu van chay cron refresh thi khong bat buoc — auth dung chung.)"
fi

echo
echo "XONG. Chay Studio:  ./Studio.sh   (mo http://127.0.0.1:8760)"
