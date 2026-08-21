from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from nara_common import cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def test_form_groups_required_and_optional_details(console, capsys):
    parser = argparse.ArgumentParser(description="sample")
    parser.add_argument("type", choices=["openapi", "fileData"], help="수집 유형")
    parser.add_argument("--workers", type=int, default=16, help="작업자 수")
    parser.add_argument("--deep", action="store_true", help="심화 분석")
    parser.add_argument("--full-download", action="store_true", help="전체 파일")

    console("type=openapi", "")
    assert cli.interactive_argv(parser, ask_if={"full_download": "deep"}) == ["openapi"]

    output = capsys.readouterr().out
    assert "[필수 항목]" in output
    assert "[선택 항목]" in output
    assert "기본값: 16" in output
    assert "선택지: openapi, fileData" in output
    assert "현재 사용 불가: --deep 를 켜야 사용" in output


def test_missing_required_reasks_only_missing_and_preserves_values(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)

    console("--workers=30", "type=openapi", "")
    argv = cli.interactive_argv(parser)

    assert argv == ["openapi", "--workers", "30"]
    assert parser.parse_args(argv).workers == 30
    output = capsys.readouterr().out
    assert "필수 항목이 빠졌습니다: type" in output
    assert "다시 입력 (type)" not in output  # input 프롬프트 자체는 fake_input이 출력하지 않는다


def test_optional_blank_uses_parser_default(console):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=16)
    console("", "")
    argv = cli.interactive_argv(parser)
    assert argv == []
    assert parser.parse_args(argv).workers == 16


def test_quoted_windows_path_and_comma_inside_value_are_preserved(console):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir")
    parser.add_argument("--only")
    console(r'--output-dir "C:\Program Files\Nara" --only="alpha,beta"', "")
    assert cli.interactive_argv(parser) == [
        "--output-dir",
        r"C:\Program Files\Nara",
        "--only",
        "alpha,beta",
    ]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "--workers=30 --port 8020 --deep 4",
            ["--workers", "30", "--port", "8020", "--deep", "--harvest"],
        ),
        (
            "1=30, 2=8020, 3, --harvest",
            ["--workers", "30", "--port", "8020", "--deep", "--harvest"],
        ),
    ],
)
def test_one_line_input_syntaxes(console, line, expected):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--port", type=int)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--harvest", action="store_true")
    console(line, "")
    assert cli.interactive_argv(parser) == expected


def test_bad_type_reasks_only_that_item_and_preserves_other_answers(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)
    parser.add_argument("--deep", action="store_true")

    console("type=openapi --workers=bad --deep", "8", "")
    argv = cli.interactive_argv(parser)

    assert argv == ["openapi", "--workers", "8", "--deep"]
    output = capsys.readouterr().out
    assert "--workers: 값이 올바르지 않습니다" in output


def test_missing_option_value_does_not_consume_the_next_flag(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--deep", action="store_true")

    console("--workers --deep", "8", "")
    assert cli.interactive_argv(parser) == ["--workers", "8", "--deep"]
    assert "--workers: 값이 필요합니다" in capsys.readouterr().out


def test_choice_outside_parser_choices_reasks_only_that_item(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)

    console("type=standard --workers=8", "fileData", "")
    argv = cli.interactive_argv(parser)

    assert argv == ["fileData", "--workers", "8"]
    assert "type: 선택지 밖의 값입니다" in capsys.readouterr().out


def test_choices_for_only_narrows_displayed_values(console):
    parser = argparse.ArgumentParser()
    parser.add_argument("type", nargs="?", choices=["openapi", "openapi_new", "fileData"])
    console("type=openapi_new", "")
    assert cli.interactive_argv(
        parser,
        choices_for={"type": ["openapi", "fileData"]},
    ) == ["openapi_new"]


def test_condition_can_be_opened_in_the_same_line(console):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--full-download", action="store_true")
    console("--deep --full-download", "")
    assert cli.interactive_argv(
        parser,
        ask_if={"full_download": "deep"},
    ) == ["--deep", "--full-download"]


def test_inactive_condition_is_reported_instead_of_silently_dropped(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--full-download", action="store_true")
    console("--full-download", "")
    assert cli.interactive_argv(parser, ask_if={"full_download": "deep"}) == []
    output = capsys.readouterr().out
    assert "--full-download: --deep 를 켜야 사용" in output
    assert "입력을 반영하지 않았습니다" in output


def test_subcommand_is_selected_before_its_single_form(console, capsys):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    extend = sub.add_parser("extend")
    extend.add_argument("--commit", action="store_true")
    extend.add_argument("--limit", type=int)

    console("2", "--commit --limit=3", "")
    assert cli.interactive_argv(parser) == ["extend", "--commit", "--limit", "3"]
    output = capsys.readouterr().out
    assert output.index("실행할 커맨드") < output.index("옵션 입력 폼")
    assert "extend --commit --limit 3" in output


def test_subcommand_without_options_goes_directly_to_confirmation(console, capsys):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")

    console("1", "")
    assert cli.interactive_argv(parser) == ["list"]
    assert "선택할 항목이 없습니다" in capsys.readouterr().out


def test_final_confirmation_rejection_and_cancel_return_none(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true")

    console("--deep", "n")
    assert cli.interactive_argv(parser) is None
    assert "실행할 명령" in capsys.readouterr().out

    console()
    assert cli.interactive_argv(parser) is None


def test_optional_left_at_default_can_still_be_set_when_refilling_required(console):
    """첫 줄을 Enter로 넘겨도 필수를 채우는 줄에서 선택 옵션을 함께 줄 수 있다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)
    parser.add_argument("--deep", action="store_true")
    kwargs = {"required_if": {"type": True}}

    # 1행 Enter로 선택 항목이 기본값이 된 뒤, 2행에서 필수와 선택을 같이 준다.
    console("", "type=fileData --workers=30 --deep", "")
    assert cli.interactive_argv(parser, **kwargs) == [
        "fileData",
        "--workers",
        "30",
        "--deep",
    ]


def test_value_already_entered_is_not_overwritten_by_a_later_line(console):
    """직접 입력한 값만 재입력을 막는다. 먼저 준 값이 이긴다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--workers", type=int)
    kwargs = {"required_if": {"type": True}}

    console("--workers=30", "type=fileData --workers=99", "")
    assert cli.interactive_argv(parser, **kwargs) == ["fileData", "--workers", "30"]


def test_same_selection_keeps_legacy_argv_order(console):
    """기존 흐름의 같은 선택이 만들던 positional + action-order argv를 고정한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("type", nargs="?", choices=["openapi", "fileData"])
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--full-download", action="store_true")
    kwargs = {
        "ask_if": {
            "type": "!full",
            "start": "!full",
            "end": "!full",
            "full_download": "deep",
        },
        "required_if": {"type": "!full", "start": "!full", "end": "!full"},
        "ask_first": ["full", "type", "start", "end"],
    }

    console(
        "type=fileData --start 10 --end=20 --workers=30 --deep --full-download",
        "",
    )
    assert cli.interactive_argv(parser, **kwargs) == [
        "fileData",
        "--start",
        "10",
        "--end",
        "20",
        "--workers",
        "30",
        "--deep",
        "--full-download",
    ]

    console("--full --deep", "")
    assert cli.interactive_argv(parser, **kwargs) == ["--full", "--deep"]


def test_wants_interactive_is_unchanged(monkeypatch):
    monkeypatch.setattr(cli, "is_console", lambda: True)
    assert cli.wants_interactive([])
    assert cli.wants_interactive(["--interactive"])
    assert not cli.wants_interactive(["--port", "8020"])


def test_help_version_and_suppressed_actions_stay_out_of_form(console, capsys):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="1.0")
    parser.add_argument("--secret", help=argparse.SUPPRESS)
    console("")
    assert cli.interactive_argv(parser) == []
    output = capsys.readouterr().out
    assert "--version" not in output
    assert "--secret" not in output


@pytest.mark.parametrize(
    ("cwd", "script"),
    [
        (
            PROJECT_ROOT / "apps" / "prologue",
            """
            import builtins
            import run
            from nara_common.cli import interactive_argv

            answers = iter(["--port=8123 --no-upstreams --no-hermes", ""])
            builtins.input = lambda _prompt="": next(answers)
            argv = interactive_argv(
                run.build_parser(),
                ask_if={
                    "upstream_timeout": "!no_upstreams",
                    "hermes_profile": "!no_hermes",
                    "proxy_port": "!no_hermes",
                },
            )
            assert argv == ["--port", "8123", "--no-upstreams", "--no-hermes"]
            """,
        ),
        (
            PROJECT_ROOT / "modules" / "crawler",
            """
            import builtins
            import main
            from nara_common.cli import interactive_argv

            answers = iter([
                "type=fileData --start 1 --end=2 --workers=3 --deep --full-download",
                "",
            ])
            builtins.input = lambda _prompt="": next(answers)
            argv = interactive_argv(
                main.build_parser(),
                ask_if={
                    "type": "!full",
                    "start": "!full",
                    "end": "!full",
                    "deep": main._may_produce_file_data,
                    "full_download": "deep",
                    "harvest": main._may_produce_link_docs,
                    "harvest_max_hosts": "harvest",
                },
                choices_for={"type": ["fileData", "openapi", "standard"]},
                ask_first=["full", "type", "start", "end"],
                required_if={"type": "!full", "start": "!full", "end": "!full"},
            )
            assert argv == [
                "fileData", "--start", "1", "--end", "2", "--workers", "3",
                "--deep", "--full-download",
            ]
            """,
        ),
        (
            PROJECT_ROOT / "modules" / "refresher",
            """
            import builtins
            import contextlib
            import io
            import main
            from nara_common.cli import interactive_argv

            answers = iter(["3", "--commit", ""])
            builtins.input = lambda _prompt="": next(answers)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                argv = interactive_argv(main.build_parser())
            assert argv == ["extend", "--commit"]
            assert "extend --commit" in output.getvalue()
            """,
        ),
    ],
    ids=["prologue", "crawler", "refresher"],
)
def test_real_launcher_parser_builds_expected_argv(cwd, script):
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
