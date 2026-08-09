"""Build an interactive argv from the options declared by ``argparse``."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

# dest -> 이 질문을 할지 정하는 조건. 문자열이면 다른 답의 참/거짓, 함수면 답 전체를 본다.
Condition = str | Callable[[dict[str, Any]], bool]

TRIGGER_FLAGS = ("-i", "--interactive")
_AUTO_ACTIONS = (argparse._HelpAction, argparse._VersionAction)
_YES = {"y", "yes", "예", "네", "응"}
_NO = {"n", "no", "아니오", "아니요", "아니"}


class Cancelled(Exception):
    pass


def is_console() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def wants_interactive(argv: Sequence[str]) -> bool:
    args = list(argv)
    return (len(args) == 1 and args[0] in TRIGGER_FLAGS) or (not args and is_console())


def interactive_argv(
    parser: argparse.ArgumentParser,
    ask_if: dict[str, Condition] | None = None,
    prog: str | None = None,
    choices_for: dict[str, Sequence[str]] | None = None,
) -> list[str] | None:
    """Ask for the parser's options and return the argv they imply.

    ``choices_for`` narrows what a menu *offers* without narrowing what the CLI
    *accepts*: the parser still takes every declared choice, so hiding an option
    here cannot break a command someone already scripted.
    """
    print("대화형 모드입니다. Enter는 기본값, Ctrl+C는 취소입니다.")
    if parser.description:
        print(parser.description)
    try:
        argv = _fill(parser, ask_if or {}, {}, choices_for or {})
        command = f"{prog or os.path.basename(sys.argv[0])} {_render(argv)}".rstrip()
        print(f"\n실행할 명령:\n  {command}")
        if not _confirm("이대로 실행할까요?", True):
            raise Cancelled
    except Cancelled:
        print("\n취소했습니다.")
        return None
    print()
    return argv


def _fill(
    parser: argparse.ArgumentParser,
    ask_if: dict[str, Condition],
    answers: dict[str, Any],
    choices_for: dict[str, Sequence[str]],
) -> list[str]:
    actions = [
        action for action in parser._actions
        if not isinstance(action, _AUTO_ACTIONS) and action.help != argparse.SUPPRESS
    ]
    sub = next((a for a in actions if isinstance(a, argparse._SubParsersAction)), None)
    command = ""
    if sub is not None:
        command = _ask_command(sub)
        answers[sub.dest if sub.dest != argparse.SUPPRESS else "command"] = command

    positionals: list[str] = []
    options: list[str] = []
    for action in (item for item in actions if item is not sub):
        condition = ask_if.get(action.dest)
        if condition and not _condition_holds(condition, answers):
            continue
        fragment, value = _ask_action(action, choices_for.get(action.dest))
        answers[action.dest] = value
        (options if action.option_strings else positionals).extend(fragment)

    argv = positionals + options
    if sub is not None:
        argv += [command] + _fill(sub.choices[command], ask_if, answers, choices_for)
    return argv


def _ask_command(action: argparse._SubParsersAction) -> str:
    names = list(action.choices)
    helps = {choice.dest: choice.help or "" for choice in action._choices_actions}
    print("\n실행할 커맨드")
    for number, name in enumerate(names, 1):
        print(f"  {number}) {name}  {helps.get(name, '')}".rstrip())
    while True:
        answer = _prompt("번호 또는 커맨드")
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        if answer in names:
            return answer
        print("  목록에 있는 값을 입력하세요.")


def _ask_action(
    action: argparse.Action, offered: Sequence[str] | None = None
) -> tuple[list[str], Any]:
    label = "/".join(action.option_strings) or action.dest
    print(f"\n{label}")
    if action.help:
        print(f"  {action.help}")
    required = bool(action.required) or (
        not action.option_strings and action.nargs not in ("?", "*")
    )
    if action.default not in (None, False) and not required:
        print(f"  기본값: {action.default}")

    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        enabled = _confirm("이 옵션을 사용할까요?", False)
        return ([action.option_strings[-1]] if enabled else [], enabled)

    if action.choices:
        accepted = [str(choice) for choice in action.choices]
        # 메뉴에는 offered만 보이지만, 파서가 받는 값은 직접 입력해도 통과시킨다 —
        # 프롬프트가 명령줄보다 좁게 거절하면 그게 더 헷갈린다.
        values = [str(value) for value in offered] if offered is not None else accepted
        for number, value in enumerate(values, 1):
            print(f"  {number}) {value}")
        while True:
            answer = _prompt("번호 또는 값" + ("" if required else " (Enter=생략)"))
            if not answer and not required:
                return [], None
            if answer.isdigit() and 1 <= int(answer) <= len(values):
                value = values[int(answer) - 1]
                return _emit(action, value), value
            if answer in accepted:
                return _emit(action, answer), answer
            print("  목록에 있는 값을 입력하세요.")

    while True:
        answer = _prompt("값" + ("" if required else " (Enter=기본값)"))
        if not answer:
            if required:
                print("  필수 항목입니다.")
                continue
            return [], action.default
        if _valid(action, answer):
            return _emit(action, answer), answer


def _emit(action: argparse.Action, value: str) -> list[str]:
    return [action.option_strings[-1], value] if action.option_strings else [value]


def _valid(action: argparse.Action, text: str) -> bool:
    if not callable(action.type):
        return True
    try:
        action.type(text)
    except (TypeError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"  값이 올바르지 않습니다: {exc}")
        return False
    return True


def _condition_holds(condition: Condition, answers: dict[str, Any]) -> bool:
    """`"deep"`은 deep가 참일 때, `"!no_hermes"`는 거짓일 때.

    답들 사이의 관계가 그보다 복잡하면 호출부가 함수를 준다 — 도메인 규칙은
    문자열 문법을 키우는 것보다 호출부에 두는 편이 읽기 쉽다.
    """
    if callable(condition):
        return bool(condition(answers))
    negated = condition.startswith("!")
    dest = condition[1:] if negated else condition
    return bool(answers.get(dest)) != negated


def _prompt(question: str) -> str:
    try:
        return input(f"  {question} > ").strip()
    except (EOFError, KeyboardInterrupt):
        raise Cancelled from None


def _confirm(question: str, default: bool) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        answer = _prompt(f"{question} {hint}").lower()
        if not answer:
            return default
        if answer in _YES:
            return True
        if answer in _NO:
            return False
        print("  y 또는 n으로 답하세요.")


def _render(argv: Sequence[str]) -> str:
    return " ".join(f'"{token}"' if not token or " " in token else token for token in argv)

