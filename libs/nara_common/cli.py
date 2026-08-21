"""Build an interactive argv from the options declared by ``argparse``."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

# dest -> 이 옵션을 사용할 수 있는지 정하는 조건. 문자열이면 다른 답의 참/거짓,
# 함수면 답 전체를 본다.
Condition = str | Callable[[dict[str, Any]], bool]
Requirement = bool | Condition

TRIGGER_FLAGS = ("-i", "--interactive")
_AUTO_ACTIONS = (argparse._HelpAction, argparse._VersionAction)
_YES = {"y", "yes", "예", "네", "응"}
_NO = {"n", "no", "아니오", "아니요", "아니"}


class Cancelled(Exception):
    pass


@dataclass
class _ParserLevel:
    actions: list[argparse.Action]
    command: str | None = None
    child: _ParserLevel | None = None


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
    ask_first: Sequence[str] | None = None,
    required_if: dict[str, Requirement] | None = None,
    condition_help: dict[str, str] | None = None,
) -> list[str] | None:
    """Show one option form and return the argv entered for it.

    ``choices_for`` narrows what the form *offers* without narrowing what the
    parser *accepts*. ``ask_first`` only controls display order within the
    required and optional groups; every value is still entered in one line.
    ``required_if`` adds interactive-only required fields without changing the
    parser used by non-interactive callers.
    """
    print("대화형 모드입니다. Enter는 기본값, Ctrl+C는 취소입니다.")
    if parser.description:
        print(_console_text(parser.description))
    try:
        argv = _fill(
            parser,
            ask_if or {},
            choices_for or {},
            ask_first or (),
            required_if or {},
            condition_help or {},
        )
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
    choices_for: dict[str, Sequence[str]],
    ask_first: Sequence[str],
    required_if: dict[str, Requirement],
    condition_help: dict[str, str],
) -> list[str]:
    answers: dict[str, Any] = {}
    level = _prepare_levels(parser, answers)
    actions = list(_walk_actions(level))
    for action in actions:
        if action.default != argparse.SUPPRESS:
            answers.setdefault(action.dest, action.default)

    display_actions = _display_order(actions, ask_first, required_if)
    numbers = {action: number for number, action in enumerate(display_actions, 1)}
    _print_form(display_actions, numbers, ask_if, answers, choices_for, required_if, condition_help)
    fragments = (
        _read_form(
            display_actions,
            numbers,
            ask_if,
            answers,
            required_if,
            condition_help,
        )
        if display_actions
        else {}
    )
    return _build_argv(level, fragments)


def _visible_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        action
        for action in parser._actions
        if not isinstance(action, _AUTO_ACTIONS) and action.help != argparse.SUPPRESS
    ]


def _prepare_levels(parser: argparse.ArgumentParser, answers: dict[str, Any]) -> _ParserLevel:
    actions = _visible_actions(parser)
    sub = next((action for action in actions if isinstance(action, argparse._SubParsersAction)), None)
    rest = [action for action in actions if action is not sub]
    if sub is None:
        return _ParserLevel(rest)

    command = _ask_command(sub)
    answers[sub.dest if sub.dest != argparse.SUPPRESS else "command"] = command
    return _ParserLevel(rest, command, _prepare_levels(sub.choices[command], answers))


def _walk_actions(level: _ParserLevel):
    yield from level.actions
    if level.child is not None:
        yield from _walk_actions(level.child)


def _display_order(
    actions: Sequence[argparse.Action],
    ask_first: Sequence[str],
    required_if: dict[str, Requirement],
) -> list[argparse.Action]:
    order = {dest: index for index, dest in enumerate(ask_first)}
    ranked = sorted(
        enumerate(actions),
        key=lambda pair: (order.get(pair[1].dest, len(order)), pair[0]),
    )
    ordered = [action for _, action in ranked]
    required = [action for action in ordered if _declared_required(action, required_if)]
    optional = [action for action in ordered if action not in required]
    return required + optional


def _print_form(
    actions: Sequence[argparse.Action],
    numbers: dict[argparse.Action, int],
    ask_if: dict[str, Condition],
    answers: dict[str, Any],
    choices_for: dict[str, Sequence[str]],
    required_if: dict[str, Requirement],
    condition_help: dict[str, str],
) -> None:
    print("\n옵션 입력 폼")
    if not actions:
        print("  선택할 항목이 없습니다.")
        return
    for required, heading in ((True, "필수 항목"), (False, "선택 항목")):
        grouped = [
            action
            for action in actions
            if _declared_required(action, required_if) is required
        ]
        if not grouped:
            continue
        print(f"\n[{heading}]")
        for action in grouped:
            details = [action.help or "설명 없음", "필수" if required else "선택"]
            default = _default_text(action)
            if default is not None:
                details.append(f"기본값: {default}")
            offered = choices_for.get(action.dest)
            if action.choices is not None:
                values = offered if offered is not None else action.choices
                details.append("선택지: " + ", ".join(str(value) for value in values))
            condition = ask_if.get(action.dest)
            if condition is not None:
                note = _condition_note(action, condition, actions, condition_help)
                state = "현재 사용 가능" if _condition_holds(condition, answers) else "현재 사용 불가"
                details.append(f"{state}: {note}")
            text = " | ".join(_console_text(str(detail)) for detail in details)
            print(f"  {numbers[action]}) {_label(action)} | {text}")
    print(
        "\n입력 형식: --이름=값, --이름 값, 번호=값, "
        "플래그 이름 또는 번호 (공백/쉼표로 구분)"
    )


def _read_form(
    actions: Sequence[argparse.Action],
    numbers: dict[argparse.Action, int],
    ask_if: dict[str, Condition],
    answers: dict[str, Any],
    required_if: dict[str, Requirement],
    condition_help: dict[str, str],
) -> dict[argparse.Action, list[str]]:
    fragments: dict[argparse.Action, list[str]] = {}
    entered: set[argparse.Action] = set()
    focus: list[argparse.Action] | None = None

    while True:
        if focus:
            names = ", ".join(_label(action) for action in focus)
            question = f"다시 입력 ({names})"
        else:
            question = "값을 한 줄로 입력 (Enter=선택 항목 기본값)"
        line = _prompt(question)
        # 다시 물을 때도 아직 직접 입력한 적 없는 항목은 열어둔다. 첫 줄을 Enter로
        # 넘겨 선택 항목이 기본값이 된 뒤 필수만 채우는 흐름에서, 사용자가 같은 줄에
        # 적은 선택 옵션을 거절하지 않기 위해서다. 이미 입력한 값만 재입력을 막는다.
        allowed = (set(focus) | (set(actions) - entered)) if focus else set(actions)
        invalid, understood, applied = _apply_line(
            line,
            actions,
            numbers,
            allowed,
            answers,
            fragments,
            entered,
            focus,
        )
        _discard_inactive(
            actions,
            ask_if,
            answers,
            fragments,
            entered,
            condition_help,
        )
        invalid = [action for action in invalid if _asks(action, ask_if, answers)]
        if invalid:
            focus = invalid
            continue

        missing = [
            action
            for action in actions
            if _required_now(action, ask_if, answers, required_if) and action not in entered
        ]
        if missing:
            print("  필수 항목이 빠졌습니다: " + ", ".join(_label(action) for action in missing))
            focus = missing
            continue

        if line and not understood and not applied:
            continue
        if focus and not line:
            print("  표시된 항목을 입력하세요.")
            continue
        return fragments


def _apply_line(
    line: str,
    actions: Sequence[argparse.Action],
    numbers: dict[argparse.Action, int],
    allowed: set[argparse.Action],
    answers: dict[str, Any],
    fragments: dict[argparse.Action, list[str]],
    entered: set[argparse.Action],
    focus: Sequence[argparse.Action] | None = None,
) -> tuple[list[argparse.Action], bool, bool]:
    if not line:
        return [], True, False
    try:
        tokens = _split_input(line)
    except ValueError as exc:
        print(f"  입력 형식이 올바르지 않습니다: {_console_text(str(exc))}")
        return [], False, False

    by_name: dict[str, argparse.Action] = {}
    for action in actions:
        by_name[action.dest] = action
        for option in action.option_strings:
            by_name[option] = action
    by_number = {str(number): action for action, number in numbers.items()}

    invalid: list[argparse.Action] = []
    understood = True
    applied = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        key, separator, attached = token.partition("=")
        action = by_number.get(key) or by_name.get(key)

        # 다시 물을 항목이 하나뿐이면 값만 적어도 그 항목으로 읽는다. 판단 기준은
        # allowed가 아니라 focus다 - allowed에는 아직 안 채운 선택 항목도 들어 있다.
        if action is None and focus is not None and len(focus) == 1 and not separator:
            only = focus[0]
            if not _is_flag(only):
                action = only
                attached = token
                separator = "="

        if action is None:
            print(f"  알 수 없는 항목입니다: {_console_text(token)}")
            understood = False
            index += 1
            continue
        if action not in allowed:
            print(f"  이번에는 {_label(action)} 항목을 다시 받을 차례가 아닙니다.")
            understood = False
            index += 1
            continue

        if _is_flag(action):
            if separator:
                print(f"  {_label(action)}: 플래그에는 값을 붙이지 마세요.")
                if action not in invalid:
                    invalid.append(action)
            else:
                fragments[action] = [action.option_strings[-1]]
                answers[action.dest] = action.const
                entered.add(action)
                applied = True
            index += 1
            continue

        if not separator:
            if index + 1 >= len(tokens):
                print(f"  {_label(action)}: 값이 필요합니다.")
                if action not in invalid:
                    invalid.append(action)
                index += 1
                continue
            next_token = tokens[index + 1]
            if next_token.startswith("-") and next_token in by_name:
                print(f"  {_label(action)}: 값이 필요합니다.")
                if action not in invalid:
                    invalid.append(action)
                index += 1
                continue
            attached = next_token
            index += 2
        else:
            index += 1

        converted, error = _convert_value(action, attached)
        if error is not None:
            print(f"  {_label(action)}: {_console_text(error)}")
            if action not in invalid:
                invalid.append(action)
            continue
        fragments[action] = _emit(action, attached)
        answers[action.dest] = converted
        entered.add(action)
        applied = True

    return invalid, understood, applied


def _split_input(line: str) -> list[str]:
    """Split on spaces/commas outside quotes while preserving Windows paths."""
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for character in line:
        if quote is not None:
            if character == quote:
                quote = None
            else:
                current.append(character)
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "," or character.isspace():
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(character)
    if quote is not None:
        raise ValueError("따옴표가 닫히지 않았습니다")
    if current:
        tokens.append("".join(current))
    return tokens


def _discard_inactive(
    actions: Sequence[argparse.Action],
    ask_if: dict[str, Condition],
    answers: dict[str, Any],
    fragments: dict[argparse.Action, list[str]],
    entered: set[argparse.Action],
    condition_help: dict[str, str],
) -> None:
    changed = True
    while changed:
        changed = False
        for action in list(entered):
            condition = ask_if.get(action.dest)
            if condition is None or _condition_holds(condition, answers):
                continue
            note = _condition_note(action, condition, actions, condition_help)
            print(f"  {_label(action)}: {note}. 입력을 반영하지 않았습니다.")
            entered.remove(action)
            fragments.pop(action, None)
            if action.default == argparse.SUPPRESS:
                answers.pop(action.dest, None)
            else:
                answers[action.dest] = action.default
            changed = True


def _build_argv(
    level: _ParserLevel,
    fragments: dict[argparse.Action, list[str]],
) -> list[str]:
    positionals: list[str] = []
    options: list[str] = []
    for action in level.actions:
        fragment = fragments.get(action, [])
        (options if action.option_strings else positionals).extend(fragment)
    argv = positionals + options
    if level.child is not None and level.command is not None:
        argv += [level.command] + _build_argv(level.child, fragments)
    return argv


def _ask_command(action: argparse._SubParsersAction) -> str:
    hidden = {
        choice.dest
        for choice in action._choices_actions
        if choice.help == argparse.SUPPRESS
    }
    names = [name for name in action.choices if name not in hidden]
    helps = {choice.dest: choice.help or "" for choice in action._choices_actions}
    print("\n실행할 커맨드")
    for number, name in enumerate(names, 1):
        print(f"  {number}) {name}  {_console_text(helps.get(name, ''))}".rstrip())
    while True:
        answer = _prompt("번호 또는 커맨드")
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        if answer in names:
            return answer
        print("  목록에 있는 값을 입력하세요.")


def _label(action: argparse.Action) -> str:
    return "/".join(action.option_strings) or action.dest


def _is_flag(action: argparse.Action) -> bool:
    return isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction))


def _is_required(action: argparse.Action) -> bool:
    return bool(action.required) or (
        not action.option_strings and action.nargs not in ("?", "*")
    )


def _declared_required(
    action: argparse.Action, required_if: dict[str, Requirement]
) -> bool:
    return _is_required(action) or action.dest in required_if


def _required_now(
    action: argparse.Action,
    ask_if: dict[str, Condition],
    answers: dict[str, Any],
    required_if: dict[str, Requirement],
) -> bool:
    if not _asks(action, ask_if, answers):
        return False
    if _is_required(action):
        return True
    requirement = required_if.get(action.dest, False)
    if isinstance(requirement, bool):
        return requirement
    return _condition_holds(requirement, answers)


def _default_text(action: argparse.Action) -> str | None:
    default = action.default
    if default in (None, argparse.SUPPRESS):
        return None
    if _is_flag(action):
        return "사용" if bool(default) else "사용 안 함"
    return str(default)


def _convert_value(action: argparse.Action, text: str) -> tuple[Any, str | None]:
    if not text:
        return None, "값이 비어 있습니다."
    try:
        value = action.type(text) if callable(action.type) else text
    except (TypeError, ValueError, argparse.ArgumentTypeError) as exc:
        return None, f"값이 올바르지 않습니다: {exc}"
    if action.choices is not None and value not in action.choices:
        choices = ", ".join(str(choice) for choice in action.choices)
        return None, f"선택지 밖의 값입니다 ({choices})"
    return value, None


def _emit(action: argparse.Action, value: str) -> list[str]:
    return [action.option_strings[-1], value] if action.option_strings else [value]


def _valid(action: argparse.Action, text: str) -> bool:
    if not callable(action.type):
        return True
    try:
        action.type(text)
    except (TypeError, ValueError, argparse.ArgumentTypeError) as exc:
        print(f"  값이 올바르지 않습니다: {_console_text(str(exc))}")
        return False
    return True


def _asks(action: argparse.Action, ask_if: dict[str, Condition], answers: dict[str, Any]) -> bool:
    condition = ask_if.get(action.dest)
    return condition is None or _condition_holds(condition, answers)


def _condition_note(
    action: argparse.Action,
    condition: Condition,
    actions: Sequence[argparse.Action],
    condition_help: dict[str, str],
) -> str:
    if action.dest in condition_help:
        return _console_text(condition_help[action.dest]).rstrip(".")
    if callable(condition):
        return "관련 항목의 조건이 맞아야 사용"
    negated = condition.startswith("!")
    dest = condition[1:] if negated else condition
    dependency = next((item for item in actions if item.dest == dest), None)
    label = _label(dependency) if dependency is not None else dest
    return f"{label} 를 끄거나 생략해야 사용" if negated else f"{label} 를 켜야 사용"


def _condition_holds(condition: Condition, answers: dict[str, Any]) -> bool:
    """``deep`` means true; ``!no_hermes`` means false."""
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


def _console_text(text: str) -> str:
    """Avoid dash characters that legacy cp949 consoles cannot encode."""
    return " ".join(text.replace("\u2014", "-").replace("\u2013", "-").split())
