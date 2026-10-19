from interviewforge.context.tokens import estimate_messages_tokens, estimate_tokens
from interviewforge.types import Message, Role


def test_empty_is_zero():
    assert estimate_tokens("") == 0


def test_cjk_one_char_one_token():
    assert estimate_tokens("分布式锁") == 4


def test_ascii_four_chars_one_token():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2  # ceil(5/4)


def test_mixed_cjk_and_ascii():
    # 2 CJK + ceil(4/4)=1 -> 3
    assert estimate_tokens("你好abcd") == 3


def test_estimate_messages_sums_content():
    msgs = [
        Message(role=Role.USER, content="abcd"),      # 1
        Message(role=Role.ASSISTANT, content="分布式"),  # 3
    ]
    assert estimate_messages_tokens(msgs) == 4
