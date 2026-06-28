import subprocess
import sys


def test_cli_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "symphony", "--help"],
        capture_output=True,
        text=True,
        cwd="c:/Users/John Doe/Desktop/SpecGuard/symphony-daemon-test",
    )
    assert result.returncode == 0
    assert "workflow" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_cli_missing_workflow_exits_nonzero(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "symphony", str(tmp_path / "missing.md")],
        capture_output=True,
        text=True,
        cwd="c:/Users/John Doe/Desktop/SpecGuard/symphony-daemon-test",
    )
    assert result.returncode != 0
