from pathlib import Path

from nara_common.paths import find_project_root


def test_marker_at_start_wins(tmp_path: Path) -> None:
    start = tmp_path / "project"
    start.mkdir()
    (start / ".nara-root").write_text("", encoding="utf-8")

    assert find_project_root(start) == start


def test_nearest_marker_wins(tmp_path: Path) -> None:
    (tmp_path / ".nara-root").write_text("outer", encoding="utf-8")
    nearer = tmp_path / "services" / "search"
    nearer.mkdir(parents=True)
    (nearer / ".nara-root").write_text("nearer", encoding="utf-8")
    start = nearer / "backend" / "core"
    start.mkdir(parents=True)

    assert find_project_root(start) == nearer


def test_marker_directory_is_ignored(tmp_path: Path) -> None:
    (tmp_path / ".nara-root").mkdir()
    start = tmp_path / "service" / "module"
    start.mkdir(parents=True)

    assert find_project_root(start) == start.parent


def test_no_marker_uses_lexical_parent_fallback(tmp_path: Path) -> None:
    start = tmp_path / "missing" / ".." / "service"

    result = find_project_root(start)

    assert result == start.parent
    assert result != tmp_path


def test_marker_match_does_not_resolve_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    (project / ".nara-root").write_text("", encoding="utf-8")
    start = child / ".."

    result = find_project_root(start)

    assert result == start
    assert result != start.resolve()
