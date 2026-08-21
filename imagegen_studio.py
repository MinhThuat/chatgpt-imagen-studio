#!/usr/bin/env python3
"""Studio UI: terminal (Claude) o duoi + gallery anh output o tren.

Ket noi terminal that vao trang web bang cau noi PTY <-> WebSocket (aiohttp
da co san, pty/fcntl/termios la stdlib -> khong them dependency).

  python3 imagegen_studio.py            # mo http://127.0.0.1:8760
  python3 imagegen_studio.py --port 9000 --out ~/anh_gen

Anh gen ra thu muc OUT se tu hien len gallery (poll moi 2s). Keo anh/folder
vao nua tren de lam reference: file duoc luu vao REFS va duong dan duoc go
thang vao o nhap cua terminal (Claude nhin thay ngay).
"""
import argparse
import asyncio
import base64
import fcntl
import json
import os
import pty
import shutil
import signal
import subprocess
import glob
import struct
import sys
import termios
import time
import urllib.parse
from datetime import datetime

from aiohttp import WSMsgType, web

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, "studio.html")
HOME = os.path.expanduser("~")

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif"}
IMG_EXT = set(MIME)

# source code cua Studio -> phat hien khi code doi de nhac restart
SRC = [os.path.join(ROOT, f) for f in ("imagegen_studio.py", "studio.html")]


def _src_mtime():
    return max((os.path.getmtime(f) for f in SRC if os.path.exists(f)), default=0)


async def index(request):
    return web.FileResponse(HTML)


async def media(request):
    """Phuc vu anh theo duong dan tuyet doi, chi trong cac ROOT cho phep."""
    p = os.path.realpath(urllib.parse.unquote(request.query.get("p", "")))
    if not any(p == r or p.startswith(r + os.sep) for r in request.app["ROOTS"]) \
            or not os.path.isfile(p):
        return web.Response(status=404, text="not found")
    ext = os.path.splitext(p)[1].lower()
    return web.FileResponse(p, headers={"Content-Type": MIME.get(ext, "application/octet-stream")})


async def reveal(request):
    """Mo thu muc chua anh bang file manager (xdg-open), chi trong ROOT cho phep."""
    p = os.path.realpath(urllib.parse.unquote(request.query.get("p", "")))
    if not any(p == r or p.startswith(r + os.sep) for r in request.app["ROOTS"]) \
            or not os.path.isfile(p):
        return web.Response(status=404, text="not found")
    subprocess.Popen(["xdg-open", os.path.dirname(p)])
    return web.Response(text="ok")


async def delete(request):
    """Chuyen anh vao thung rac (.trash) thay vi xoa han -> Ctrl+Z khoi phuc duoc.
    Ghi log LIFO (trashpath<TAB>origpath) de /undo pop nguoc lai."""
    p = os.path.realpath(urllib.parse.unquote(request.query.get("p", "")))
    if not any(p == r or p.startswith(r + os.sep) for r in request.app["ROOTS"]) \
            or not os.path.isfile(p):
        return web.Response(status=404, text="not found")
    trash = request.app["TRASH"]
    os.makedirs(trash, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(p))
    dst = os.path.join(trash, stem + ext)
    n = 1
    while os.path.exists(dst):
        dst = os.path.join(trash, "%s_%d%s" % (stem, n, ext))
        n += 1
    shutil.move(p, dst)                       # shutil.move: chiu duoc khac o dia (NTFS->HOME)
    if os.path.exists(p + ".txt"):
        shutil.move(p + ".txt", dst + ".txt")  # dem prompt sidecar theo
    with open(request.app["TRASHLOG"], "a", encoding="utf-8") as f:
        f.write(dst + "\t" + p + "\n")
    return web.Response(text="ok")


async def undo(request):
    """Khoi phuc anh vua chuyen vao thung rac (LIFO)."""
    log = request.app["TRASHLOG"]
    try:
        with open(log, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    except OSError:
        lines = []
    while lines:
        dst, orig = lines.pop().split("\t", 1)
        if not os.path.exists(dst):
            continue                          # da bi don tay -> bo qua, thu cai truoc do
        try:
            os.makedirs(os.path.dirname(orig), exist_ok=True)
            shutil.move(dst, orig)
            if os.path.exists(dst + ".txt"):
                shutil.move(dst + ".txt", orig + ".txt")
        except OSError as e:
            return web.json_response({"restored": None, "err": str(e)})
        with open(log, "w", encoding="utf-8") as f:
            f.write("".join(l + "\n" for l in lines))
        return web.json_response({"restored": orig})
    with open(log, "w", encoding="utf-8") as f:  # het -> don sach log
        f.write("")
    return web.json_response({"restored": None})


async def version(request):
    """Bao cho UI biet code da doi so voi luc server khoi dong -> can restart."""
    return web.json_response({"stale": _src_mtime() > request.app["SRC_MTIME"]})


async def restart(request):
    """Khoi dong lai server (re-exec) de nap code moi."""
    async def _go():
        await asyncio.sleep(0.3)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    asyncio.ensure_future(_go())
    return web.Response(text="restarting")


# ---------- Quota: doc local (khong goi mang, khong ton token) ----------
def _find_rate_limits(o):
    """Tim object 'rate_limits' o bat ky do sau nao trong 1 dong JSON."""
    if isinstance(o, dict):
        rl = o.get("rate_limits")
        if isinstance(rl, dict):
            return rl
        for v in o.values():
            r = _find_rate_limits(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_rate_limits(v)
            if r:
                return r
    return None


def _codex_quota():
    """Quota codex tu snapshot rate_limits moi nhat trong ~/.codex/sessions.
    Chi cap nhat khi dung codex CLI (gen anh POST thang -> khong ghi session)."""
    files = glob.glob(os.path.join(HOME, ".codex", "sessions", "**", "*.jsonl"), recursive=True)
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    rl = None
    try:
        with open(latest, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"rate_limits"' not in line:
                    continue
                try:
                    r = _find_rate_limits(json.loads(line))
                except ValueError:
                    continue
                if r:
                    rl = r  # giu cai cuoi cung (moi nhat)
    except OSError:
        return None
    if not rl:
        return None
    out = {"plan": rl.get("plan_type"), "at": os.path.getmtime(latest)}
    for k in ("primary", "secondary"):
        w = rl.get(k)
        if isinstance(w, dict) and w.get("used_percent") is not None:
            out[k] = {"remaining_percent": round(100 - w["used_percent"], 1),
                      "resets_at": w.get("resets_at"),
                      "window_minutes": w.get("window_minutes")}
    return out


def _iso_epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def _claude_usage(window_h=5):
    """Token Claude da tieu trong cua so window_h gio gan nhat (tong tu transcript
    ~/.claude/projects). Local chi co token DA DUNG, khong co han muc -> khong tinh
    duoc 'con lai' that; hien phan da dung."""
    cutoff = time.time() - window_h * 3600
    total = msgs = 0
    for fp in glob.glob(os.path.join(HOME, ".claude", "projects", "**", "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(fp) < cutoff:  # file khong dong trong window -> bo qua
                continue
            with open(fp, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"usage"' not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    t = _iso_epoch(o.get("timestamp") or "")
                    if t is not None and t < cutoff:
                        continue
                    m = o.get("message")
                    u = m.get("usage") if isinstance(m, dict) else o.get("usage")
                    if isinstance(u, dict):
                        # bo cache_read (token cache doc lai, re ~0.1x, phinh rat to)
                        total += ((u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
                                  + (u.get("cache_creation_input_tokens") or 0))
                        msgs += 1
        except OSError:
            continue
    return {"used_tokens": total, "messages": msgs, "window_hours": window_h}


async def quota(request):
    """Quota codex (con lai %) + token Claude da dung (5h). Chay o executor de
    khong nghen event loop khi quet file."""
    loop = asyncio.get_event_loop()
    codex = await loop.run_in_executor(None, _codex_quota)
    claude = await loop.run_in_executor(None, _claude_usage)
    return web.json_response({"codex": codex, "claude": claude})


def _gallery_roots(app):
    # ca thu muc studio (bat moi out*/ Claude tao) + out_*/output trong project
    studio_base = os.path.dirname(app["OUT"])
    return ([studio_base] + sorted(glob.glob(os.path.join(ROOT, "out*")))
            + [os.path.join(ROOT, "output")])


async def gallery(request):
    """Liet ke anh gen (de quy), moi nhat truoc. Bo qua thu muc refs (anh input)."""
    refs = os.path.realpath(request.app["REFS"])
    trash = os.path.realpath(request.app["TRASH"])
    seen, items = set(), []
    for root in _gallery_roots(request.app):
        if not os.path.isdir(root):
            continue
        for dp, dirs, files in os.walk(root):
            rp = os.path.realpath(dp)
            # anh keo vao (refs) va anh da xoa (.trash) khong hien tren gallery
            if rp == refs or rp.startswith(refs + os.sep) \
                    or rp == trash or rp.startswith(trash + os.sep):
                dirs[:] = []
                continue
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in IMG_EXT:
                    continue
                fp = os.path.join(dp, fn)
                if fp in seen:
                    continue
                seen.add(fp)
                prompt = ""
                try:
                    with open(fp + ".txt", encoding="utf-8") as pf:
                        prompt = pf.read(2000).strip()
                except OSError:
                    pass
                try:
                    items.append({"name": fn, "mtime": os.path.getmtime(fp),
                                  "prompt": prompt,
                                  "url": "/media?p=" + urllib.parse.quote(fp)})
                except OSError:
                    pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return web.json_response(items[:300])


async def upload(request):
    """Luu 1 anh keo-tha. Body JSON {name, data(dataURL), subdir?}.
    Co subdir -> luu vao refs/<subdir>/ (giu nguyen dang folder)."""
    d = await request.json()
    raw = base64.b64decode(d["data"].split(",")[-1])
    safe = os.path.basename(d.get("name", "img.png")).replace(" ", "_") or "img.png"
    sub = os.path.basename((d.get("subdir") or "").strip()).replace(" ", "_")
    base = os.path.join(request.app["REFS"], sub) if sub else request.app["REFS"]
    os.makedirs(base, exist_ok=True)
    fp = os.path.join(base, safe)
    n = 1
    while os.path.exists(fp):
        stem, ext = os.path.splitext(safe)
        fp = os.path.join(base, "%s_%d%s" % (stem, n, ext))
        n += 1
    with open(fp, "wb") as f:
        f.write(raw)
    return web.json_response({"path": fp, "dir": base})


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

    loop = asyncio.get_event_loop()
    os.set_blocking(fd, False)
    # tu chay claude, in dir output cho de thay
    os.write(fd, b'clear; echo "[studio] anh gen vao: $IMAGEGEN_OUT -> hien len gallery"; '
                 b'claude --permission-mode auto\r')

    q = asyncio.Queue()

    def on_readable():
        try:
            data = os.read(fd, 65536)
        except (OSError, BlockingIOError):
            data = b""
        q.put_nowait(data)

    loop.add_reader(fd, on_readable)

    async def pty_to_ws():
        while True:
            data = await q.get()
            if not data:  # child da thoat
                break
            await ws.send_bytes(data)

    pump = asyncio.ensure_future(pty_to_ws())
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                os.write(fd, msg.data)
            elif msg.type == WSMsgType.TEXT:
                # {"resize":[cols,rows]}
                import json
                m = json.loads(msg.data)
                if "resize" in m:
                    cols, rows = m["resize"]
                    fcntl.ioctl(fd, termios.TIOCSWINSZ,
                                struct.pack("HHHH", rows, cols, 0, 0))
    finally:
        loop.remove_reader(fd)
        pump.cancel()
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8760)
    ap.add_argument("--out", default=os.path.join(HOME, "imagegen_studio", "out"))
    ap.add_argument("--refs", default=os.path.join(HOME, "imagegen_studio", "refs"))
    a = ap.parse_args()

    out = os.path.abspath(os.path.expanduser(a.out))
    refs = os.path.abspath(os.path.expanduser(a.refs))
    os.makedirs(out, exist_ok=True)
    os.makedirs(refs, exist_ok=True)

    # anh mockup that thuong 1-8MB, base64 phinh them 33% -> noi gioi han body.
    app = web.Application(client_max_size=100 * 1024 * 1024)
    app["OUT"], app["REFS"] = out, refs
    app["TRASH"] = os.path.join(os.path.dirname(out), ".trash")
    app["TRASHLOG"] = os.path.join(app["TRASH"], "undo_log.tsv")
    app["SRC_MTIME"] = _src_mtime()
    # cac goc duoc phep phuc vu anh: ca thu muc studio (chua out*/refs) + project
    app["ROOTS"] = [os.path.realpath(p) for p in (os.path.dirname(out), ROOT)]
    app.add_routes([
        web.get("/", index),
        web.get("/pty", pty_ws),
        web.get("/gallery", gallery),
        web.post("/upload", upload),
        web.get("/media", media),
        web.get("/reveal", reveal),
        web.get("/delete", delete),
        web.post("/undo", undo),
        web.get("/version", version),
        web.get("/quota", quota),
        web.post("/restart", restart),
    ])
    print("Studio: http://127.0.0.1:%d   (out=%s)" % (a.port, out))
    web.run_app(app, host="127.0.0.1", port=a.port, print=None)


if __name__ == "__main__":
    main()
