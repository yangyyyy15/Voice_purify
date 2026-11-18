from backend.pipeline.textutil import align_tokens, join_words, tokenize_with_punct


def test_tokenize_chinese_with_punct():
    assert tokenize_with_punct("你好，世界。") == ["你", "好，", "世", "界。"]


def test_tokenize_mixed_english():
    assert tokenize_with_punct("我用iPhone 15拍的") == ["我", "用", "iPhone", "15", "拍", "的"]


def test_tokenize_leading_punct():
    assert tokenize_with_punct("“好”") == ["“好”"]


def test_align_exact():
    words, exact = align_tokens("你好。", [[100, 300], [300, 500]])
    assert exact
    assert words == [{"word": "你", "start": 0.1, "end": 0.3}, {"word": "好。", "start": 0.3, "end": 0.5}]


def test_align_mismatch_falls_back():
    # 文本 3 个 token，时间戳 2 个
    words, exact = align_tokens("一二三", [[0, 1000], [1000, 2000]])
    assert not exact
    assert len(words) == 3
    assert words[0]["start"] == 0.0 and words[-1]["end"] == 2.0
    assert all(w["end"] > w["start"] for w in words)


def test_align_empty():
    assert align_tokens("", []) == ([], True)


def test_join_words():
    assert join_words(["我", "用", "iPhone", "15", "拍", "的。"]) == "我用iPhone 15拍的。"
    assert join_words(["Hello,", "world"]) == "Hello, world"
    assert join_words(["你", "好"]) == "你好"
