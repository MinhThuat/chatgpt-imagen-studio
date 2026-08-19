#!/usr/bin/env bash
# Setup Imagegen Studio (ban standalone). Chay 1 lan. Tu cai thu con thieu.
set -e
cd "$(dirname "$0")"
HERE="$(pwd)"

SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

pm_install() {  # pm_install <pkg...> qua package manager he thong
  if   command -v apt-get >/dev/null 2>&1; then $SUDO apt-get update -y && $SUDO apt-get install -y "$@"
  elif command -v dnf     >/dev/null 2>&1; then $SUDO dnf install -y "$@"
  elif command -v pacman  >/dev/null 2>&1; then $SUDO pacman -S --noconfirm "$@"
  elif command -v zypper  >/dev/null 2>&1; then $SUDO zypper install -y "$@"
  else echo "!! Khong ro package manager — cai tay: $*"; return 1; fi
}

npm_g() {  # cai npm global, thu sudo neu bi tu choi quyen
  npm install -g "$@" 2>/dev/null || $SUDO npm install -g "$@"
}

echo "== 1. python3 =="
command -v python3 >/dev/null 2>&1 || pm_install python3
python3 --version

echo "== 2. node + npm (can cho claude & codex) =="
command -v npm >/dev/null 2>&1 || pm_install nodejs npm
npm --version

echo "== 3. claude (Claude Code CLI) =="
command -v claude >/dev/null 2>&1 && echo "  da co: $(command -v claude)" \
  || npm_g @anthropic-ai/claude-code

echo "== 4. codex (ChatGPT backend) =="
command -v codex >/dev/null 2>&1 && echo "  da co: $(command -v codex)" \
  || npm_g @openai/codex

echo "== 5. aiohttp (server Studio) =="
python3 -c "import aiohttp" 2>/dev/null && echo "  aiohttp: da co" \
  || python3 -m pip install --user --break-system-packages "aiohttp>=3.9"

echo "== 6. Thu muc output/refs (o HOME, tranh o NTFS hay xoa) =="
mkdir -p "$HOME/imagegen_studio/out" "$HOME/imagegen_studio/refs"
echo "  out : $HOME/imagegen_studio/out"
echo "  refs: $HOME/imagegen_studio/refs"

echo "== 7. chmod +x =="
chmod +x Studio.sh start.sh login.sh autoupdate.sh imagegen_studio.py chatgpt-imagegen 2>/dev/null || true

echo "== 8. Dang nhap ChatGPT (codex) =="
if [ -f "$HOME/.codex/auth.json" ]; then
  echo "  OK: da co $HOME/.codex/auth.json"
else
  echo "  Chua dang nhap — chay: codex login   (hoac ./login.sh)"
fi

echo
echo "XONG. Chay:  ./start.sh   (mo http://127.0.0.1:8760)"
