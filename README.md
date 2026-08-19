# Imagegen Studio

Gen ảnh mockup sản phẩm hàng loạt bằng AI (ChatGPT image gen), UI web + terminal Claude. Nền tảng **Linux**.

## Dùng (bấm 1 cái)

```bash
git clone <URL-REPO> imagegen-studio
cd imagegen-studio
./start.sh          # lần đầu tự setup, sau đó tự mở http://127.0.0.1:8760
```

`start.sh` lần đầu chạy `setup.sh`: tự cài **node/npm, claude, codex, aiohttp** vào `~/.local`
(**không cần sudo**), cái nào có sẵn thì bỏ qua. Rồi mở Studio.

Chỉ cần máy có sẵn **`python3`** (hầu như Linux nào cũng có; không có thì nhờ admin cài — không tự cài được vì không sudo).
Sau khi cài xong, đăng nhập ChatGPT một lần: `codex login` (hoặc `./login.sh`).

## Tự cập nhật

Studio tự chạy `autoupdate.sh` ở nền: mỗi 60s `git fetch` + `git reset --hard` về đúng remote.
Có code mới sẽ in `[autoupdate] ...` — chạy lại `./Studio.sh` để áp dụng.

> Repo chỉ chứa code; ảnh gen nằm ở `~/imagegen_studio/` (ngoài repo) nên hard-reset không mất ảnh.
> **Đừng sửa file trong repo** — sẽ bị auto-update ghi đè.
