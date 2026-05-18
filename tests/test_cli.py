from __future__ import annotations

import pytest

from devbits.cli import main


def test_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_clearcache_dry_run(tmp_path) -> None:
    cache = tmp_path / "pkg" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "a.pyc").write_bytes(b"test")
    assert main(["clearcache", str(tmp_path), "--dry-run"]) == 0


def test_standalone_wrapper_help() -> None:
    import pytest

    from devbits.scripts import _run

    with pytest.raises(SystemExit) as exc_info:
        _run("clearcache", ["--help"])
    assert exc_info.value.code == 0
