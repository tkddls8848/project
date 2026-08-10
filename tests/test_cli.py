from __future__ import annotations

import argparse

import pytest

from nara_common import cli


@pytest.fixture
def console(monkeypatch):
    def script(*responses):
        queue = list(responses)

        def fake_input(_prompt=""):
            if not queue:
                raise EOFError
            return queue.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)

    return script


def sample_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--start", type=int)
    return parser


def test_answers_are_valid_argv(console):
    console("n", "1", "7", "")
    parser = sample_parser()
    argv = cli.interactive_argv(parser, ask_if={"download": "deep"})
    assert argv == ["openapi", "--start", "7"]
    assert parser.parse_args(argv).start == 7


def test_subcommand_and_flag(console):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    extend = sub.add_parser("extend")
    extend.add_argument("--commit", action="store_true")
    console("2", "y", "")
    assert cli.interactive_argv(parser) == ["extend", "--commit"]


def test_menu_offers_a_subset_but_still_accepts_the_rest(console):
    """메뉴를 좁혀도 파서가 받는 값은 받아야 한다 — 프롬프트가 더 좁게 거절하면 헷갈린다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("type", nargs="?", choices=["openapi", "openapi_new", "fileData"])
    offered = {"type": ["openapi", "fileData"]}

    console("2", "")  # 메뉴의 2번은 좁혀진 목록 기준이다
    assert cli.interactive_argv(parser, choices_for=offered) == ["fileData"]

    console("openapi_new", "")  # 숨긴 값도 직접 치면 통과한다
    assert cli.interactive_argv(parser, choices_for=offered) == ["openapi_new"]


def test_callable_condition_sees_the_earlier_answers(console):
    """옵션이 앞선 답의 조합에 달렸을 때 — 문자열 조건으로는 표현되지 않는다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--deep", action="store_true")
    ask_if = {
        "type": "!full",
        "deep": lambda answers: answers.get("full") or answers.get("type") == "fileData",
    }

    console("n", "1", "")  # openapi -> --deep은 묻지 않는다
    assert cli.interactive_argv(parser, ask_if=ask_if) == ["openapi"]

    console("n", "2", "y", "")  # fileData -> 묻는다
    assert cli.interactive_argv(parser, ask_if=ask_if) == ["fileData", "--deep"]

    console("y", "y", "")  # --full은 타입을 묻지 않아도 fileData를 포함한다
    assert cli.interactive_argv(parser, ask_if=ask_if) == ["--full", "--deep"]


def test_optional_options_are_picked_in_one_menu(console):
    """ask_first 밖의 옵션은 하나씩이 아니라 한 번에 고른다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)
    parser.add_argument("--skip-update", action="store_true")
    parser.add_argument("--deep", action="store_true")
    ask_first = ["full", "type"]

    console("n", "2", "", "")  # 타입만 고르고 나머지는 Enter 한 번으로 끝낸다
    assert cli.interactive_argv(parser, ask_first=ask_first) == ["fileData"]

    console("n", "1", "1,3", "8", "")  # --workers 8 --deep
    argv = cli.interactive_argv(parser, ask_first=ask_first)
    assert argv == ["openapi", "--workers", "8", "--deep"]
    assert parser.parse_args(argv).workers == 8

    console("n", "1", "--skip-update", "")  # 번호 대신 옵션 이름으로도 고른다
    assert cli.interactive_argv(parser, ask_first=ask_first) == ["openapi", "--skip-update"]


def test_menu_reopens_for_options_a_pick_unlocked(console):
    """--deep을 고르면 그때 열리는 --full-download를 다음 라운드에서 묻는다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--full-download", action="store_true")
    kwargs = {"ask_if": {"full_download": "deep"}, "ask_first": ["type"]}

    console("2", "1", "1", "")  # --deep -> 추가 메뉴에서 --full-download
    assert cli.interactive_argv(parser, **kwargs) == ["fileData", "--deep", "--full-download"]

    console("2", "", "")  # --deep을 안 고르면 추가 메뉴 자체가 없다
    assert cli.interactive_argv(parser, **kwargs) == ["fileData"]


def test_cancel_and_console_detection(console, monkeypatch):
    console()
    assert cli.interactive_argv(sample_parser()) is None
    monkeypatch.setattr(cli, "is_console", lambda: True)
    assert cli.wants_interactive([])
    assert cli.wants_interactive(["--interactive"])
    assert not cli.wants_interactive(["--port", "8020"])
