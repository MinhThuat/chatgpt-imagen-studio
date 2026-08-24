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
