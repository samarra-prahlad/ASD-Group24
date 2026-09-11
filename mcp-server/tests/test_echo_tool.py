from tools.echo_tool import echo


def test_echo_returns_message():
    result = echo("hello")
    assert result == {"echo": "hello"}


def test_echo_handles_empty_string():
    result = echo("")
    assert result == {"echo": ""}
