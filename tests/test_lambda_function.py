import pytest

from src.lambda_function import echo


@pytest.mark.parametrize(("param", "expected"), [("hoge", "hoge")])
def test_echo(param, expected):
    assert echo(param) == expected
