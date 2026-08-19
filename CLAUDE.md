# Imagegen Studio — bản standalone

## Đây là gì
Bộ công cụ tạo ảnh mockup sản phẩm hàng loạt bằng AI (ChatGPT image generation), có **giao diện web Studio** thay cho terminal trần. Người dùng mô tả bằng tiếng Việt → bạn (Claude) hỏi lại cho rõ → viết prompt tiếng Anh → chạy CLI `chatgpt-imagegen` để gen.

> **Nền tảng: Linux.** Chỉ viết script **bash (`.sh`)**, KHÔNG viết PowerShell/`.bat`.
> **`python3`** chứ không phải `python` (máy này không có alias `python`).

## Giao diện Studio hoạt động ra sao
Chạy `./Studio.sh` → mở `http://127.0.0.1:8760`. Trang chia 2 phần:
- **Trên = gallery**: ảnh gen ra tự hiện lên (poll mỗi 2s), mới nhất trước. Nút **＋ New** ẩn ảnh cũ (chỉ ẩn khỏi giao diện, KHÔNG xoá file; mốc lưu trong trình duyệt).
- **Dưới = terminal**: chính là bạn (Claude Code), tự mở sẵn với `--permission-mode auto` (không hỏi duyệt từng bước).
- **Kéo-thả**: kéo 1 folder ảnh vào bất kỳ đâu trên trang → Studio copy folder vào `~/imagegen_studio/refs/<tên>/` rồi **tự gõ MỘT đường dẫn folder vào ô nhập của bạn**. Kéo ảnh lẻ → gõ từng đường dẫn ảnh. Đây là ảnh **reference** (input) người dùng muốn bạn dựa theo.

## ⚡ QUAN TRỌNG NHẤT: xuất ảnh gen vào đâu
Khi chạy trong Studio, biến môi trường **`$IMAGEGEN_OUT`** được set sẵn (mặc định `~/imagegen_studio/out`).

**LUÔN xuất ảnh gen vào `$IMAGEGEN_OUT` hoặc thư mục con của nó** — ví dụ `$IMAGEGEN_OUT/ten_set/` — để ảnh **tự hiện lên gallery**. Gallery theo dõi cả thư mục `~/imagegen_studio/` (mọi folder `out*` trong đó, TRỪ `refs/`). Nếu xuất ra chỗ khác (vd thư mục project), ảnh sẽ KHÔNG hiện.

```bash
OUT="${IMAGEGEN_OUT:-$HOME/imagegen_studio/out}/ornament_set1"
mkdir -p "$OUT"
```

Không xuất ảnh ra thư mục chứa code này (ổ `/mnt/...` NTFS hay tự xoá file). Dùng `$IMAGEGEN_OUT` (nằm ở HOME, an toàn).

## Mẫu chuẩn script gen ảnh (bash)
Chạy song song **tối đa 4** request (`xargs -P 4` — giới hạn của codex backend). Mỗi ảnh mất ~60-150 giây.

```bash
#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

CLI="./chatgpt-imagegen"
SRC="$HOME/imagegen_studio/refs/ten_folder_ref"      # folder ref user kéo vào
OUT="${IMAGEGEN_OUT:-$HOME/imagegen_studio/out}/ten_set"
mkdir -p "$OUT"

PROMPT="Mo ta anh can gen bang tieng Anh, chi tiet..."

gen_one() {
  local in="$1"
  local dst="$OUT/$(basename "$in")"
  echo "start: $(basename "$in")"
  python3 "$CLI" "$PROMPT" -i "$in" -o "$dst" \
    --size 1024x1024 --backend codex --quiet
}
export -f gen_one
export PROMPT OUT CLI

find "$SRC" -maxdepth 1 -name '*.png' -print0 \
  | xargs -0 -P 4 -I {} bash -c 'gen_one "$@"' _ {}

echo "done -> $OUT"
```

Sau khi tạo: `chmod +x run_xxx.sh` rồi chạy `bash run_xxx.sh` (auto mode nên không cần bấm duyệt).

## Tham số CLI hay dùng
```
python3 ./chatgpt-imagegen "prompt" -i ref.png -o out.png --size 1024x1024 --backend codex --quiet
```
- `-i` : ảnh tham chiếu (lặp lại nhiều lần được)
- `-o` : file output
- `--size` : `1024x1024` (khuyến nghị)
- `--backend codex` : dùng session ChatGPT đã đăng nhập
- `--quiet` : ít log

CLI chỉ dùng thư viện chuẩn Python — không cần cài gì.

## Backend & auth
- Dùng **codex backend** (session ChatGPT đã login). File auth: `~/.codex/auth.json` (dùng chung toàn máy).
- Token tự refresh mỗi 20 phút qua cron (xem `crontab -l`). `refresh_token.py` lo việc này.
- Nếu gặp `HTTP 401` / "token refresh failed" hoàn toàn → bảo người dùng chạy: `codex login`.
- Ảnh có thể ra 1254×1254 thay vì 2048 → giới hạn subscription, không đổi được.

## Quy trình làm việc với người dùng
1. Người dùng tả tiếng Việt (vd "gen 8 mockup cốc sứ in hình thú cưng").
2. **Hỏi lại** vài câu cho rõ (số lượng, tên/chữ, màu, style, có ref không...).
3. Viết prompt tiếng Anh + script bash theo mẫu trên.
4. Chạy, xuất vào `$IMAGEGEN_OUT/<set>/`. Ảnh tự hiện lên gallery.
5. Chỉ gen + lưu, KHÔNG tự mở xem lại ảnh (tiết kiệm token) trừ khi người dùng bảo.

## File trong folder này
- `imagegen_studio.py` — server Studio (terminal↔web + gallery + upload). Không sửa trừ khi cần.
- `studio.html` — giao diện.
- `Studio.sh` — chạy Studio.
- `chatgpt-imagegen` — CLI gen ảnh (Python, không sửa).
- `refresh_token.py` — tự refresh token codex.
- `setup.sh` — cài đặt 1 lần (aiohttp + thư mục + chmod).
- `requirements.txt` — chỉ `aiohttp` cần cho Studio (phần Trello không dùng ở đây).

## Cài lần đầu
```
./setup.sh      # cài aiohttp, tạo ~/imagegen_studio/{out,refs}
./Studio.sh     # mở http://127.0.0.1:8760
```
