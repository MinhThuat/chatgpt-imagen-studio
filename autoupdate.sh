#!/usr/bin/env bash
# Tu cap nhat code moi tu git remote moi 60s (Studio.sh chay nen file nay).
# Recipient chi la user, khong sua code -> hard reset ve dung remote, khong ket conflict.
# Anh output nam ngoai repo (~/imagegen_studio/) nen reset an toan.
#   ./autoupdate.sh          # vong lap moi 60s
#   ./autoupdate.sh --once   # kiem tra + update 1 lan roi thoat (de test)
set -u
cd "$(dirname "$0")"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || {
  echo "[autoupdate] khong phai git repo — bo qua."; exit 0; }

# NTFS (/mnt) khong giu bit thuc thi -> git thay mode 644->755 va bao MOI file
# "modified" gia. Tat filemode -> git bo qua doi bit exec.
git config core.filemode false 2>/dev/null

# May tac gia: dat IMAGEGEN_DEV=1 hoac tao file .dev de BAO VE cong viec chua commit
# (guard duoi se chan pull khi tree ban / local di truoc). May user (khong co marker):
# LUON hard-reset ve origin -> tu lanh khi NTFS lam mat/sua/xoa file tracked (vd
# setup.bat bi xoa) ma khong kep pull mai. Anh output nam ngoai repo nen reset an toan.
DEV=0
{ [ -n "${IMAGEGEN_DEV:-}" ] || [ -f .dev ]; } && DEV=1

update_once() {
  git fetch -q origin "$BRANCH" 2>/dev/null || return 0   # mat mang -> thu lai sau
  local local_h remote_h base
  local_h="$(git rev-parse HEAD)"
  remote_h="$(git rev-parse "origin/$BRANCH" 2>/dev/null)" || return 0
  [ "$local_h" = "$remote_h" ] && return 0

  if [ "$DEV" = 1 ]; then
    # Chi may tac gia: khong nuot cong viec local. run_*.sh / rac NTFS la untracked
    # nen --untracked-files=no bo qua; chi diff noi dung file da-track moi chan.
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
      echo "[autoupdate] (dev) co thay doi file da track chua commit — bo qua."; return 0
    fi
    base="$(git merge-base HEAD "origin/$BRANCH" 2>/dev/null)"
    if [ "$base" != "$local_h" ]; then
      echo "[autoupdate] (dev) local di truoc/re nhanh origin — bo qua (day: git push)."; return 0
    fi
  fi

  git reset --hard -q "origin/$BRANCH" \
    && echo "[autoupdate] da cap nhat code moi (${remote_h:0:7}) — chay lai Studio de ap dung."
}

[ "${1:-}" = "--once" ] && { update_once; exit 0; }

while true; do
  update_once
  sleep 60
done
