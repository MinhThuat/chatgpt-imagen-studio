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
import os
import pty
import signal
import subprocess
import glob
import struct
import termios
import urllib.parse

from aiohttp import WSMsgType, web

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(ROOT, "studio.html")
HOME = os.path.expanduser("~")

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif"}
IMG_EXT = set(MIME)


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


def _gallery_roots(app):
    # ca thu muc studio (bat moi out*/ Claude tao) + out_*/output trong project
    studio_base = os.path.dirname(app["OUT"])
    return ([studio_base] + sorted(glob.glob(os.path.join(ROOT, "out*")))
            + [os.path.join(ROOT, "output")])


async def gallery(request):
    """Liet ke anh gen (de quy), moi nhat truoc. Bo qua thu muc refs (anh input)."""
    refs = os.path.realpath(request.app["REFS"])
    seen, items = set(), []
    for root in _gallery_roots(request.app):
        if not os.path.isdir(root):
            continue
        for dp, dirs, files in os.walk(root):
            rp = os.path.realpath(dp)
            if rp == refs or rp.startswith(refs + os.sep):  # anh keo vao != anh gen
                dirs[:] = []
                continue
            for fn in files:
                if os.path.splitext(fn)[1].lower() not in IMG_EXT:
                    continue
                fp = os.path.join(dp, fn)
                if fp in seen:
                    continue
                seen.add(fp)
                try:
                    items.append({"name": fn, "mtime": os.path.getmtime(fp),
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
    # cac goc duoc phep phuc vu anh: ca thu muc studio (chua out*/refs) + project
    app["ROOTS"] = [os.path.realpath(p) for p in (os.path.dirname(out), ROOT)]
    app.add_routes([
        web.get("/", index),
        web.get("/pty", pty_ws),
        web.get("/gallery", gallery),
        web.post("/upload", upload),
        web.get("/media", media),
        web.get("/reveal", reveal),
    ])
    print("Studio: http://127.0.0.1:%d   (out=%s)" % (a.port, out))
    web.run_app(app, host="127.0.0.1", port=a.port, print=None)


if __name__ == "__main__":
    main()
