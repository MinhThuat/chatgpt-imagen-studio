# Chat History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm danh sách chat kiểu ChatGPT vào Studio: hover mép trái → sidebar; bấm 1 chat → resume phiên Claude đó + gallery lọc về ảnh của chat đó.

**Architecture:** Một `uuid` do **client sinh** (`crypto.randomUUID()`) dùng cho cả `IMAGEGEN_OUT=out/<uuid>/` lẫn `claude --session-id <uuid>`. Client luôn gửi id qua `?chat=<uuid>`; server tự quyết resume (nếu transcript đã có) hay tạo mới. Danh sách chat = các folder `out/<uuid>/` có ảnh, tiêu đề đọc từ `~/.claude/projects/<enc>/<uuid>.jsonl`.

**Tech Stack:** Python (stdlib + aiohttp) backend, vanilla JS + xterm frontend. Không thêm dependency.

## Global Constraints

- Nền tảng Linux, chỉ bash. `python3` (không `python`).
- Không thêm dependency (chỉ stdlib + aiohttp đã có).
- Ảnh gen phải nằm trong `$IMAGEGEN_OUT` để hiện gallery.
- `ROOT` = thư mục project (`/mnt/6C96C1A096C16AE2/vsc/imagegen-studio`).
- Claude transcript: `~/.claude/projects/<ROOT với '/' và '.' → '-'>/<session-uuid>.jsonl`.
- CLI đã verify hỗ trợ: `--session-id <uuid>`, `-r/--resume [value]`, `--permission-mode`.

---

### Task 1: Pure helpers (`_valid_uuid`, `_chat_title`, `_claude_project_dir`)

**Files:**
- Modify: `imagegen_studio.py` (thêm `import uuid` tại khối import; thêm 3 helper ngay trước `async def pty_ws`, ~line 358)
- Test: `test_chat_history.py` (create)

**Interfaces:**
- Produces:
  - `_valid_uuid(s) -> bool` — True nếu `s` là uuid canonical (lowercase, có dấu `-`).
  - `_chat_title(path, maxlen=60) -> str | None` — câu user text đầu tiên trong file jsonl, cắt `maxlen` (thêm `…`); None nếu không đọc được / không có.
  - `_claude_project_dir() -> str` — đường dẫn thư mục transcript của ROOT.

- [ ] **Step 1: Viết test thất bại** — tạo `test_chat_history.py`:

```python
import os, json, tempfile
import imagegen_studio as S

def test_valid_uuid():
    assert S._valid_uuid("bf92dd61-7a69-41b4-8289-bdd4f3f02b89")
    assert not S._valid_uuid("ornament_set1")
    assert not S._valid_uuid("")
    assert not S._valid_uuid("../etc")
    assert not S._valid_uuid("BF92DD61-7A69-46F3-8289-BDD4F3F02B89".replace("-", ""))

def _write(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for o in lines:
        f.write(json.dumps(o) + "\n")
    f.close()
    return f.name

def test_chat_title_skips_tool_result():
    p = _write([
        {"type": "user", "message": {"role": "user",
            "content": [{"type": "tool_result", "content": "x"}]}},
        {"type": "user", "message": {"role": "user", "content": "gen 8 mockup coc su"}},
    ])
    assert S._chat_title(p) == "gen 8 mockup coc su"
    os.unlink(p)

def test_chat_title_list_text_block():
    p = _write([{"type": "user", "message": {"role": "user",
        "content": [{"type": "text", "text": "xin chao"}]}}])
    assert S._chat_title(p) == "xin chao"
    os.unlink(p)

def test_chat_title_truncates():
    long = "a" * 100
    p = _write([{"type": "user", "message": {"role": "user", "content": long}}])
    r = S._chat_title(p, maxlen=60)
    assert r == "a" * 60 + "…"
    os.unlink(p)

def test_chat_title_missing_file():
    assert S._chat_title("/nonexistent/x.jsonl") is None

def test_claude_project_dir():
    d = S._claude_project_dir()
    assert d.endswith("imagegen-studio")
    assert ".claude/projects" in d

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `python3 test_chat_history.py`
Expected: FAIL — `AttributeError: module 'imagegen_studio' has no attribute '_valid_uuid'`

- [ ] **Step 3: Thêm `import uuid`** — trong `imagegen_studio.py` sau dòng `import urllib.parse` (line 29):

```python
import urllib.parse
import uuid
```

- [ ] **Step 4: Thêm 3 helper** — ngay trước `async def pty_ws(request):` (~line 358):

```python
def _valid_uuid(s):
    """True neu s la uuid canonical (dung phan biet folder chat vs set thuong)."""
    try:
        return str(uuid.UUID(str(s))) == str(s).lower()
    except (ValueError, AttributeError, TypeError):
        return False


def _claude_project_dir():
    """Thu muc transcript Claude cho ROOT: ~/.claude/projects/<ROOT '/'&'.'->'->'-'>."""
    enc = ROOT.replace("/", "-").replace(".", "-")
    return os.path.join(HOME, ".claude", "projects", enc)


def _chat_title(path, maxlen=60):
    """Cau user text dau tien trong transcript jsonl -> tieu de chat. None neu khong co."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"user"' not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("type") != "user":
                    continue
                c = (o.get("message") or {}).get("content")
                text = ""
                if isinstance(c, str):
                    text = c
                elif isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "text":
                            text = b.get("text", "")
                            break
                        if isinstance(b, str):
                            text = b
                            break
                text = text.strip()
                if text:
                    return text[:maxlen] + ("…" if len(text) > maxlen else "")
    except OSError:
        pass
    return None
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `python3 test_chat_history.py`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add imagegen_studio.py test_chat_history.py
git commit -m "feat(studio): helper uuid/title/project-dir cho lich su chat"
```

---

### Task 2: PTY per-chat session + resume

**Files:**
- Modify: `imagegen_studio.py` — `async def pty_ws` (line 358-420)

**Interfaces:**
- Consumes: `_valid_uuid`, `_claude_project_dir`, `uuid`, `request.app["OUT"]` (từ Task 1 / hiện có).
- Produces: WS `/pty?chat=<uuid>` — set `IMAGEGEN_OUT=out/<uuid>`, spawn `claude --session-id <uuid>` (mới) hoặc `claude --resume <uuid>` (nếu transcript đã có), đều kèm `--permission-mode auto`.

- [ ] **Step 1: Sửa đầu `pty_ws`** — thay đoạn từ dòng docstring tới hết block `if pid == 0` (line 358-369):

Cũ:
```python
async def pty_ws(request):
    """Cau noi terminal: spawn bash -> tu mo claude, bom byte 2 chieu qua WS."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(ROOT)
        os.environ["IMAGEGEN_OUT"] = request.app["OUT"]
        os.environ["IMAGEGEN_REFS"] = request.app["REFS"]
        os.execvp("bash", ["bash", "-l"])
        os._exit(1)
```

Mới:
```python
async def pty_ws(request):
    """Cau noi terminal: spawn bash -> tu mo claude, bom byte 2 chieu qua WS.
    ?chat=<uuid>: resume phien do neu da co transcript, khong thi tao moi voi id do."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    chat = request.query.get("chat", "")
    if not _valid_uuid(chat):
        chat = str(uuid.uuid4())
    chat_out = os.path.join(request.app["OUT"], chat)
    os.makedirs(chat_out, exist_ok=True)
    resume = os.path.exists(os.path.join(_claude_project_dir(), chat + ".jsonl"))

    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(ROOT)
        os.environ["IMAGEGEN_OUT"] = chat_out
        os.environ["IMAGEGEN_REFS"] = request.app["REFS"]
        os.execvp("bash", ["bash", "-l"])
        os._exit(1)
```

- [ ] **Step 2: Sửa lệnh spawn claude** — thay block `os.write(...claude --permission-mode auto\r')` (line 374-375):

Cũ:
```python
    os.write(fd, b'clear; echo "[studio] anh gen vao: $IMAGEGEN_OUT -> hien len gallery"; '
                 b'claude --permission-mode auto\r')
```

Mới:
```python
    flag = "--resume" if resume else "--session-id"
    cmd = "claude %s %s --permission-mode auto" % (flag, chat)  # chat la uuid -> an toan
    os.write(fd, b'clear; echo "[studio] anh gen vao: $IMAGEGEN_OUT -> hien len gallery"; '
                 + cmd.encode() + b'\r')
```

- [ ] **Step 3: Kiểm tra thủ công** — khởi động Studio, mở 2 phiên để chứng minh resume:

```bash
python3 imagegen_studio.py --port 8799 &
SRV=$!
sleep 1
# tao chat moi voi id co dinh, xac nhan folder out/<id> duoc tao
CID=$(python3 -c "import uuid;print(uuid.uuid4())")
# gia lap client: mo WS bang python (kiem tra env + folder)
python3 - "$CID" <<'PY'
import sys, asyncio, aiohttp
cid = sys.argv[1]
async def main():
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(f"http://127.0.0.1:8799/pty?chat={cid}") as ws:
            await asyncio.sleep(2)   # de bash chay lenh
asyncio.run(main())
PY
ls -d ~/imagegen_studio/out/$CID && echo "FOLDER OK"
kill $SRV
```
Expected: in ra `.../out/<CID>` + `FOLDER OK` (folder chat được tạo). *(Không cần Claude thực chạy xong — chỉ xác nhận folder + không lỗi.)*

- [ ] **Step 4: Commit**

```bash
git add imagegen_studio.py
git commit -m "feat(studio): pty per-chat IMAGEGEN_OUT + resume theo ?chat=uuid"
```

---

### Task 3: `/chats` endpoint + `/gallery?chat=` filter

**Files:**
- Modify: `imagegen_studio.py` — `async def gallery` (line 300-335), thêm `async def chats`, đăng ký route (line 443-455)

**Interfaces:**
- Consumes: `_valid_uuid`, `_chat_title`, `_claude_project_dir`, `IMG_EXT`, `request.app["OUT"]`.
- Produces:
  - `GET /gallery?chat=<uuid>` → chỉ ảnh trong `out/<uuid>/` (đệ quy). Không có/không hợp lệ → như cũ.
  - `GET /chats` → `[{id, title, thumb_url, count, mtime}]` sắp mtime giảm; chỉ folder uuid có ≥1 ảnh.

- [ ] **Step 1: Thêm filter vào `gallery`** — thay 3 dòng đầu thân hàm (line 304-305, `seen, items = ...` và `for root in _gallery_roots...`):

Cũ:
```python
    refs = os.path.realpath(request.app["REFS"])
    trash = os.path.realpath(request.app["TRASH"])
    seen, items = set(), []
    for root in _gallery_roots(request.app):
```

Mới:
```python
    refs = os.path.realpath(request.app["REFS"])
    trash = os.path.realpath(request.app["TRASH"])
    chat = request.query.get("chat", "")
    if _valid_uuid(chat):
        roots = [os.path.join(request.app["OUT"], chat)]   # chi anh cua chat nay
    else:
        roots = _gallery_roots(request.app)
    seen, items = set(), []
    for root in roots:
```

- [ ] **Step 2: Thêm handler `chats`** — ngay sau `async def gallery` (sau line 335):

```python
async def chats(request):
    """Danh sach chat: moi folder out/<uuid> co it nhat 1 anh = 1 chat.
    Tieu de doc tu transcript Claude (cung uuid)."""
    out = request.app["OUT"]
    proj = _claude_project_dir()
    try:
        names = os.listdir(out)
    except OSError:
        names = []
    items = []
    for name in names:
        if not _valid_uuid(name):
            continue
        folder = os.path.join(out, name)
        if not os.path.isdir(folder):
            continue
        newest, count = None, 0
        for dp, dirs, files in os.walk(folder):
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in IMG_EXT:
                    continue
                fp = os.path.join(dp, fn)
                try:
                    mt = os.path.getmtime(fp)
                except OSError:
                    continue
                count += 1
                if newest is None or mt > newest[0]:
                    newest = (mt, fp)
        if not count:
            continue
        title = _chat_title(os.path.join(proj, name + ".jsonl")) \
            or datetime.fromtimestamp(newest[0]).strftime("%Y-%m-%d %H:%M")
        items.append({"id": name, "title": title, "count": count,
                      "mtime": newest[0],
                      "thumb_url": "/media?p=" + urllib.parse.quote(newest[1])})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return web.json_response(items)
```

- [ ] **Step 3: Đăng ký route** — trong `app.add_routes([...])` (sau `web.get("/gallery", gallery),`, line 446):

```python
        web.get("/gallery", gallery),
        web.get("/chats", chats),
```

- [ ] **Step 4: Kiểm tra thủ công** — dựng 1 folder chat giả có ảnh rồi gọi API:

```bash
python3 imagegen_studio.py --port 8799 &
SRV=$!
sleep 1
CID=$(python3 -c "import uuid;print(uuid.uuid4())")
mkdir -p ~/imagegen_studio/out/$CID
# tao 1 png 1x1 hop le
python3 -c "import base64,sys;open('$HOME/imagegen_studio/out/$CID/a.png','wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='))"
echo "--- /chats ---"; curl -s http://127.0.0.1:8799/chats
echo; echo "--- /gallery?chat ---"; curl -s "http://127.0.0.1:8799/gallery?chat=$CID"
rm -rf ~/imagegen_studio/out/$CID
kill $SRV
```
Expected: `/chats` trả 1 item có `"id":"<CID>"`, `"count":1`, `title` = giờ (chưa có transcript). `/gallery?chat=<CID>` trả 1 ảnh `a.png`.

- [ ] **Step 5: Commit**

```bash
git add imagegen_studio.py
git commit -m "feat(studio): endpoint /chats + gallery loc theo ?chat=uuid"
```

---

### Task 4: Frontend — sidebar hover + resume + New = Chat mới

**Files:**
- Modify: `studio.html` — CSS (trong `<style>`), markup (thêm sidebar), JS (refactor WS + logic chat)

**Interfaces:**
- Consumes: `GET /chats`, `GET /gallery?chat=`, `GET /pty?chat=`, `crypto.randomUUID()`.
- Produces: sidebar hover trái; bấm chat → resume + lọc gallery; nút bar "＋ Chat mới"; nút "Tất cả" xem mọi ảnh.

- [ ] **Step 1: Thêm CSS sidebar** — trước dòng `#divider { ... }` (line 64) trong `<style>`:

```css
  #sidebar-wrap { position:fixed; left:0; top:0; bottom:0; width:14px; z-index:16; }
  #sidebar-wrap::before { content:""; position:absolute; left:0; top:0; bottom:0;
    width:4px; background:var(--line); }
  #sidebar-wrap:hover { width:280px; }
  #sidebar { position:absolute; left:0; top:0; bottom:0; width:280px; background:var(--panel);
    border-right:1px solid var(--line); box-shadow:4px 0 20px rgba(0,0,0,.4);
    transform:translateX(-100%); transition:transform .18s; overflow-y:auto; padding:8px; }
  #sidebar-wrap:hover #sidebar { transform:none; }
  #sb-head { display:flex; gap:6px; margin-bottom:8px; }
  #chatlist .item { display:flex; gap:8px; align-items:center; padding:6px; border-radius:8px;
    cursor:pointer; border:1px solid transparent; }
  #chatlist .item:hover { background:#20262f; }
  #chatlist .item.active { border-color:var(--accent); }
  #chatlist .item img { width:40px; height:40px; object-fit:cover; border-radius:5px;
    border:1px solid var(--line); flex:none; background:#0d0f13; }
  #chatlist .item .t { font-size:12px; color:var(--fg); overflow:hidden;
    text-overflow:ellipsis; white-space:nowrap; }
  #chatlist .item .c { font-size:11px; color:var(--mut); }
```

- [ ] **Step 2: Thêm markup sidebar** — ngay sau `<body>` (line 68):

```html
<div id="sidebar-wrap"><div id="sidebar">
  <div id="sb-head"><button id="showall" title="Xem tat ca anh (moi chat)">Tất cả</button></div>
  <div id="chatlist"></div>
</div></div>
```

- [ ] **Step 3: Đổi nhãn nút New** — line 78:

Cũ:
```html
      <button id="new">＋ New (xoa gallery)</button>
```
Mới:
```html
      <button id="new">＋ Chat mới</button>
```

- [ ] **Step 4: Refactor kết nối terminal** — thay line 98-109 (từ `const ws = new WebSocket...` tới hết dòng `new ResizeObserver(...).observe(...)`):

Cũ:
```javascript
const ws = new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/pty');
ws.binaryType = 'arraybuffer';
const enc = new TextEncoder();
let lastPasteLen = 0;   // do dai chuoi duong dan vua chen -> Ctrl+Z xoa dung bay nhieu ky tu
let deletedCount = 0;   // so anh da chuyen vao thung rac trong phien -> Ctrl+Z khoi phuc
function sendResize(){ try { ws.send(JSON.stringify({resize:[term.cols, term.rows]})); } catch(e){} }
ws.onopen = () => { fit.fit(); sendResize(); term.focus(); };
ws.onmessage = e => term.write(new Uint8Array(e.data));
ws.onclose = () => term.write('\r\n[studio] terminal da dong.\r\n');
term.onData(d => { lastPasteLen = 0;   // go phim khac -> huy bo dem undo-paste
  if (ws.readyState===1) ws.send(enc.encode(d)); });
new ResizeObserver(() => { fit.fit(); sendResize(); }).observe(document.getElementById('term'));
```

Mới:
```javascript
const enc = new TextEncoder();
let lastPasteLen = 0;   // do dai chuoi duong dan vua chen -> Ctrl+Z xoa dung bay nhieu ky tu
let deletedCount = 0;   // so anh da chuyen vao thung rac trong phien -> Ctrl+Z khoi phuc
let currentChat = crypto.randomUUID();   // moi lan mo trang = 1 chat moi
let ws;
const wsBase = (location.protocol==='https:'?'wss':'ws')+'://'+location.host;
function sendResize(){ try { ws.send(JSON.stringify({resize:[term.cols, term.rows]})); } catch(e){} }
function connect(chatId){
  if (ws) { try { ws.onclose = null; ws.close(); } catch(e){} }
  ws = new WebSocket(wsBase + '/pty?chat=' + chatId);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => { fit.fit(); sendResize(); term.focus(); };
  ws.onmessage = e => term.write(new Uint8Array(e.data));
  ws.onclose = () => term.write('\r\n[studio] terminal da dong.\r\n');
}
term.onData(d => { lastPasteLen = 0;   // go phim khac -> huy bo dem undo-paste
  if (ws && ws.readyState===1) ws.send(enc.encode(d)); });
new ResizeObserver(() => { fit.fit(); sendResize(); }).observe(document.getElementById('term'));
connect(currentChat);
```

- [ ] **Step 5: Bỏ `clearedAt`, gallery lọc theo chat** — line 124 xoá dòng `clearedAt`:

Cũ (line 124):
```javascript
let clearedAt = parseFloat(localStorage.getItem('clearedAt') || '0');
```
Xoá hẳn dòng này.

Trong `poll()` sửa fetch (line 129) và điều kiện skip (line 131-132):

Cũ:
```javascript
    const list = await (await fetch('/gallery')).json();
    // moi nhat truoc -> render nguoc de prepend giu thu tu
    for (const it of list.slice().reverse()) {
      if (it.mtime <= clearedAt || shown.has(it.url)) continue;
```
Mới:
```javascript
    const url = currentChat ? '/gallery?chat=' + currentChat : '/gallery';
    const list = await (await fetch(url)).json();
    // moi nhat truoc -> render nguoc de prepend giu thu tu
    for (const it of list.slice().reverse()) {
      if (shown.has(it.url)) continue;
```

- [ ] **Step 6: Thêm logic chat + sidebar** — thay khối nút `#new` (line 214-220):

Cũ:
```javascript
document.getElementById('new').onclick = () => {
  clearedAt = Date.now()/1000;
  localStorage.setItem('clearedAt', clearedAt);
  shown.clear();
  [...gallery.querySelectorAll('a')].forEach(a => a.remove());
  empty.style.display = ''; cnt.textContent = '';
};
```

Mới:
```javascript
// ---------- Chat history: sidebar + resume + doi chat ----------
function resetGallery(){
  shown.clear();
  [...gallery.querySelectorAll('a')].forEach(a => a.remove());
  empty.style.display = ''; cnt.textContent = '';
}
function openChat(id){          // bam 1 chat cu -> resume + loc gallery
  if (id === currentChat) return;
  currentChat = id;
  term.reset(); connect(id);
  resetGallery(); poll(); renderActive();
}
function newChat(){ openChat(crypto.randomUUID()); }   // nut "Chat moi"
function showAll(){ currentChat = null; resetGallery(); poll(); renderActive(); }

const chatlist = document.getElementById('chatlist');
let chatsCache = [];
function renderActive(){
  [...chatlist.querySelectorAll('.item')].forEach((el, i) =>
    el.classList.toggle('active', chatsCache[i] && chatsCache[i].id === currentChat));
}
async function loadChats(){
  try { chatsCache = await (await fetch('/chats')).json(); } catch(e){ return; }
  chatlist.innerHTML = '';
  for (const ch of chatsCache) {
    const d = document.createElement('div');
    d.className = 'item' + (ch.id === currentChat ? ' active' : '');
    d.onclick = () => openChat(ch.id);
    const img = document.createElement('img'); img.src = ch.thumb_url; img.loading = 'lazy';
    const box = document.createElement('div'); box.style.minWidth = '0';
    const t = document.createElement('div'); t.className = 't'; t.textContent = ch.title; t.title = ch.title;
    const c = document.createElement('div'); c.className = 'c'; c.textContent = ch.count + ' anh';
    box.appendChild(t); box.appendChild(c);
    d.appendChild(img); d.appendChild(box);
    chatlist.appendChild(d);
  }
}
document.getElementById('new').onclick = newChat;
document.getElementById('showall').onclick = showAll;
loadChats(); setInterval(loadChats, 5000);
```

- [ ] **Step 7: Kiểm tra thủ công trong trình duyệt**

Run: `python3 imagegen_studio.py --port 8760` rồi mở `http://127.0.0.1:8760`.
Expected:
- Hover mép trái → sidebar bung ra. Nếu đã có folder `out/<uuid>/` có ảnh (từ chat cũ) → hiện trong danh sách kèm thumbnail + tiêu đề.
- Gen 1 ảnh trong chat hiện tại → ảnh hiện gallery; sau ≤5s chat hiện tại xuất hiện/ cập nhật trong sidebar.
- Bấm 1 chat cũ → terminal reset và chạy `claude --resume <id>` (thấy Claude nạp lại hội thoại); gallery đổi sang ảnh của chat đó.
- Bấm "＋ Chat mới" → terminal mở phiên mới, gallery trống.
- Bấm "Tất cả" → gallery hiện mọi ảnh.

- [ ] **Step 8: Commit**

```bash
git add studio.html
git commit -m "feat(studio): sidebar lich su chat (hover) + resume + New=Chat moi"
```

---

## Self-Review

- **Spec coverage:** uuid dùng chung (Task 2), sidebar hover (Task 4 CSS), chỉ chat có ảnh (Task 3 `if not count: continue`), resume ngay + lọc gallery (Task 4 `openChat`), nút New → Chat mới (Task 4), bucket "Tất cả" (Task 4 `showAll`), title từ transcript (Task 1/3). ✔ Hết mục spec.
- **Placeholder scan:** không có TBD/TODO; mọi step có code/command đầy đủ. ✔
- **Type consistency:** `_valid_uuid`/`_chat_title`/`_claude_project_dir` dùng nhất quán Task 1→3; JSON keys `{id,title,thumb_url,count,mtime}` khớp giữa `/chats` (Task 3) và `loadChats` (Task 4); `?chat=` param nhất quán `/pty`,`/gallery`. ✔
- **Ambiguity:** client luôn sinh & gửi uuid → server không cần trả id ngược; gallery luôn lọc theo `currentChat` (null = tất cả). ✔
