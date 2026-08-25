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

def _write_compact(lines):  # claude ghi jsonl compact (khong khoang trang) -> khop _resumable
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for o in lines:
        f.write(json.dumps(o, separators=(",", ":")) + "\n")
    f.close()
    return f.name

def test_resumable_real_vs_stub():
    real = _write_compact([
        {"type": "bridge-session", "sessionId": "x", "lastSequenceNum": 0},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
    ])
    stub = _write_compact([{"type": "bridge-session", "sessionId": "x", "lastSequenceNum": 0}])
    assert S._resumable(real) is True
    assert S._resumable(stub) is False           # stub -> KHONG resume (chong claude thoat)
    assert S._resumable("/nonexistent/x.jsonl") is False
    os.unlink(real); os.unlink(stub)

def test_claude_cmd_picks_flag(monkeypatch=None):
    # chuyen _claude_project_dir sang thu muc tam de kiem soat transcript
    import tempfile as _tf
    d = _tf.mkdtemp()
    orig = S._claude_project_dir
    S._claude_project_dir = lambda: d
    try:
        absent = "11111111-1111-4111-8111-111111111111"
        stubbed = "22222222-2222-4222-8222-222222222222"
        realid = "33333333-3333-4333-8333-333333333333"
        with open(os.path.join(d, stubbed + ".jsonl"), "w") as f:
            f.write(json.dumps({"type": "bridge-session"}, separators=(",", ":")) + "\n")
        with open(os.path.join(d, realid + ".jsonl"), "w") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}},
                               separators=(",", ":")) + "\n")
        # chua tung dung -> --session-id chinh chat (dat nen resume sau)
        assert S._claude_cmd(absent) == "claude --session-id %s --permission-mode auto" % absent
        # co hoi thoai that -> --resume chinh chat
        assert S._claude_cmd(realid) == "claude --resume %s --permission-mode auto" % realid
        # stub -> --session-id NHUNG id KHAC (khong phai chat) -> tranh 'already in use'
        c = S._claude_cmd(stubbed)
        assert c.startswith("claude --session-id ") and c.endswith("--permission-mode auto")
        assert stubbed not in c and S._valid_uuid(c.split()[2])
    finally:
        S._claude_project_dir = orig

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
