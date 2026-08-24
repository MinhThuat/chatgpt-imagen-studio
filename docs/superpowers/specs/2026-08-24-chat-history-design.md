# Lịch sử chat (kiểu ChatGPT) cho Imagegen Studio

Ngày: 2026-08-24

## Mục tiêu
Thêm danh sách các đoạn chat cũ vào Studio. Hover mép trái → sidebar bung ra danh
sách chat. Bấm 1 chat → **resume ngay** phiên Claude đó trong terminal + gallery
lọc về đúng ảnh của chat đó.

## Ý tưởng cốt lõi: một uuid cho cả folder lẫn resume
Hiện mỗi lần mở WS terminal, server spawn `claude --permission-mode auto` (session
id do Claude tự sinh, ta không nắm được → không resume được, và ảnh không gắn với
chat nào).

Thay bằng: **server tự sinh 1 `uuid4`** khi mở chat mới, dùng cho cả hai việc:
- `IMAGEGEN_OUT = <studio>/out/<uuid>/` — ảnh gen tự vào đúng folder của chat.
- spawn `claude --session-id <uuid> --permission-mode auto` — ép Claude dùng chính
  uuid đó làm session id.

Claude lưu transcript ở `~/.claude/projects/<enc>/<uuid>.jsonl`, với
`<enc>` = ROOT thay mọi `/` bằng `-` (vd `-mnt-6C96C1A096C16AE2-vsc-imagegen-studio`).
Nên **một uuid** trỏ được tới cả transcript lẫn folder ảnh — không cần bảng map.

Resume: spawn `claude --resume <uuid> --permission-mode auto`, `IMAGEGEN_OUT` cùng
folder cũ.

## Luồng dữ liệu

### Nguồn danh sách chat (chỉ chat có ảnh)
Quét `<studio>/out/<uuid>/` — folder nào **tên là uuid hợp lệ và có ít nhất 1 ảnh**
mới tính là 1 chat. Với mỗi folder:
- **tiêu đề**: câu user đầu tiên trong `~/.claude/projects/<enc>/<uuid>.jsonl`
  (đọc dòng đầu có `type:"user"`, cắt ~60 ký tự). Fallback: giờ tạo folder.
- **thumbnail**: ảnh mtime mới nhất trong folder.
- **mtime**: mtime mới nhất trong folder (để sắp mới nhất trước).
- **count**: số ảnh.

Folder tên KHÔNG phải uuid (các set cũ như `ornament_set1`) → không phải chat, gộp
vào bucket "Tất cả".

### Endpoint mới
- `GET /chats` → JSON list `[{id, title, thumb_url, mtime, count}]` sắp mtime giảm.
- `GET /pty?resume=<uuid>` → nếu có `resume`, spawn `claude --resume <uuid>` +
  `IMAGEGEN_OUT=out/<uuid>`; nếu không, sinh uuid mới + `--session-id`.
- `GET /gallery?chat=<uuid>` → chỉ liệt ảnh trong `out/<uuid>/`. Không có `chat` →
  như cũ (tất cả). `chat=<uuid>` không tồn tại → rỗng.

### Frontend
- **Sidebar**: div ẩn ở mép trái, `:hover` (hoặc mouseenter vùng mép) → trượt ra,
  đè lên gallery. Mỗi item: thumbnail + tiêu đề. Có nút **"＋ Chat mới"** ở đầu và
  mục **"Tất cả"** ở dưới.
- **Bấm 1 chat**: set `currentChat=<uuid>` → (a) đóng WS terminal, mở lại
  `/pty?resume=<uuid>`; (b) gallery poll đổi sang `/gallery?chat=<uuid>`.
- **Bấm "Tất cả"**: `currentChat=null` → gallery `/gallery`, terminal giữ nguyên.
- **Nút "＋ New" cũ** đổi thành **"Chat mới"**: `currentChat=null`, đóng+mở lại WS
  `/pty` (không resume → uuid mới), gallery về folder mới. Bỏ hành vi "ẩn ảnh cũ
  client" cũ (mốc localStorage) — không còn cần.

## Thay đổi so với hiện tại
- `pty_ws`: đọc `request.query["resume"]`; sinh/nhận uuid; set `IMAGEGEN_OUT` theo
  uuid; lệnh spawn thêm `--session-id`/`--resume`.
- `gallery`: nhận `?chat=`, khi có thì chỉ quét `out/<uuid>/`.
- Thêm handler `chats` + route `/chats`.
- `studio.html`: thêm sidebar hover + logic đổi chat (đóng/mở WS, đổi URL poll),
  đổi nút New.

## Edge cases
- Resume ngắt claude đang chạy: transcript Claude tự lưu liên tục nên không mất
  lịch sử; chỉ gián đoạn nếu đang gen ảnh dở. Chấp nhận (user đã chọn "resume ngay").
- Ảnh cũ trong `out/<set_name>/` (trước tính năng): không thuộc chat nào, chỉ thấy
  ở "Tất cả". Không migrate.
- Folder `out/<uuid>/` có ảnh nhưng `.jsonl` đã bị xoá: vẫn hiện chat, tiêu đề dùng
  fallback giờ; resume có thể báo lỗi "no conversation found" → hiếm, để Claude tự
  báo trong terminal.
- uuid validate bằng regex `^[0-9a-f]{8}-...$` để phân biệt folder chat vs set thường.

## Test
Một self-check nhỏ (python) cho phần logic thuần: parse title từ 1 dòng jsonl mẫu,
và regex nhận diện uuid. Không cần framework.

## Cố ý bỏ (YAGNI)
- Không đổi tên chat thủ công (title auto từ câu đầu là đủ).
- Không xoá chat từ UI (xoá folder out/<uuid> là đủ, dùng file manager).
- Không phân trang sidebar (≤ vài chục chat).
