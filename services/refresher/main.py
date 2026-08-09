"""data.go.kr 활용신청 연장 자동화 CLI.

`services/crawler`와 같은 argparse 배치 도구다. 상주 프로세스도 포트도 없다.

    python main.py                           # 인자 없이 = 대화형으로 커맨드·옵션 선택
    python main.py login                     # 브라우저에서 수동 로그인 1회
    python main.py list                      # 읽기 전용: 보유 API 목록
    python main.py extend                    # dry-run (기본값)
    python main.py extend --commit           # 실제 연장
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
PROJECT_ROOT = BASE_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.accounts import fetch_account_rows  # noqa: E402
from app.browser import BrowserSession  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.extender import run_extension  # noqa: E402
from nara_common.cli import interactive_argv, wants_interactive  # noqa: E402
from app.session import NotAuthenticatedError, interactive_login  # noqa: E402


def _configure_stdio() -> None:
    """Korean output stays UTF-8 even when the console is redirected (cp949)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def cmd_login(args: argparse.Namespace) -> int:
    settings = get_settings()
    interactive_login(settings, manual=args.manual, timeout_seconds=args.timeout)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    settings = get_settings()
    with BrowserSession(settings, headless=True) as browser:
        rows = fetch_account_rows(settings, browser)
    if not rows:
        print("활용신청 목록에서 행을 찾지 못했습니다.")
        return 1
    print(f"\n총 {len(rows)}건\n")
    for index, row in enumerate(rows, 1):
        params = ", ".join(f"{k}={v}" for k, v in row.detail_params.items()) or "(식별자 미확인)"
        print(f"{index:>3}. {row.name or '(이름 미확인)'}")
        print(f"     상태={row.status_text or '-'}  {params}")
    return 0


def cmd_extend(args: argparse.Namespace) -> int:
    settings = get_settings()
    with BrowserSession(settings, headless=True) as browser:
        rows = fetch_account_rows(settings, browser)
    if args.only:
        needle = args.only.lower()
        rows = [r for r in rows if needle in r.name.lower() or needle in r.key.lower()]
    if not rows:
        print("대상이 없습니다.")
        return 1

    if not args.commit:
        print(f"[dry-run] {len(rows)}건이 대상입니다. 실제 연장은 --commit이 필요합니다.\n")

    summary = run_extension(settings, rows, commit=args.commit, limit=args.limit)
    for outcome in summary.outcomes:
        label = {"extended": "연장됨", "skipped": "건너뜀",
                 "failed": "실패", "would-extend": "연장 예정"}[outcome.action]
        note = outcome.portal_message or outcome.message
        print(f"  [{label}] {outcome.name or outcome.key}" + (f" — {note}" if note else ""))
    print(
        f"\n총 {summary.total} · 연장 {summary.extended} · 건너뜀 {summary.skipped} "
        f"· 실패 {summary.failed} · 예정 {summary.would_extend}"
    )
    return 1 if summary.failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="data.go.kr 활용신청 연장 자동화")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="브라우저에서 수동 로그인하고 세션을 저장한다")
    login.add_argument("--manual", action="store_true",
                       help="자동 감지 대신 Enter를 누를 때 저장한다 (감지가 안 될 때)")
    login.add_argument("--timeout", type=float, default=600.0,
                       help="로그인 대기 최대 초 (기본 600)")
    login.set_defaults(func=cmd_login)
    sub.add_parser("list", help="보유 API 목록을 읽는다 (읽기 전용)").set_defaults(func=cmd_list)
    extend = sub.add_parser("extend", help="연장을 수행한다 (기본 dry-run)")
    extend.add_argument("--commit", action="store_true", help="실제로 연장을 제출한다")
    extend.add_argument("--limit", type=int, help="이번 실행에서 처리할 최대 건수")
    extend.add_argument("--only", help="이름 또는 식별자에 이 문자열이 들어간 항목만")
    extend.set_defaults(func=cmd_extend)

    return parser


def main() -> int:
    _configure_stdio()
    parser = build_parser()
    argv = sys.argv[1:]
    if wants_interactive(argv):
        # 커맨드가 필수라 인자 없이 부르면 원래 usage 에러였다. 콘솔이면 그 자리에서
        # 물어보고, 비대화형(파이프·CI)이면 예전처럼 에러를 낸다.
        argv = interactive_argv(parser)
        if argv is None:
            return 0
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except NotAuthenticatedError as exc:
        print(f"[인증 필요] {exc}")
        return 2
    except RuntimeError as exc:
        print(f"[오류] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
