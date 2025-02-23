from pathlib import Path

from click.testing import CliRunner

import atd


def test_copy(tmp_path: Path) -> None:
    runner = CliRunner()
    destination = tmp_path / "data"
    destination.mkdir()
    runner.invoke(atd.cli, ["data", str(destination)], catch_exceptions=False)
