import subprocess
import sys

from fastcs_eiger import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "fastcs_eiger", "--version"]
    stdout = subprocess.check_output(cmd).decode().strip().split("\n")
    assert __version__ in stdout
