# Imagegen Studio

Gen ảnh mockup sản phẩm hàng loạt bằng AI (ChatGPT image gen), UI web + terminal Claude. Nền tảng **Linux**.

## Cài (chạy 1 lần)

```bash
git clone <URL-REPO> imagegen-studio
cd imagegen-studio
./setup.sh          # cài aiohttp, tạo ~/imagegen_studio/{out,refs}
codex login         # nếu chưa có ~/.codex/auth.json
```

Cần sẵn: `python3`, `claude` (Claude Code CLI), và session ChatGPT đã login qua `codex`.

## Chạy

```bash
./Studio.sh         # mở http://127.0.0.1:8760
```

## Tự cập nhật

Studio tự chạy `autoupdate.sh` ở nền: mỗi 60s `git fetch` + `git reset --hard` về đúng remote.
Có code mới sẽ in `[autoupdate] ...` — chạy lại `./Studio.sh` để áp dụng.

> Repo chỉ chứa code; ảnh gen nằm ở `~/imagegen_studio/` (ngoài repo) nên hard-reset không mất ảnh.
> **Đừng sửa file trong repo** — sẽ bị auto-update ghi đè.
