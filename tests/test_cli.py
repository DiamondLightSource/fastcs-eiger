import subprocess
import sys

from eiger_fastcs import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "eiger_fastcs", "--version"]
    stdout = subprocess.check_output(cmd).decode().strip().split("\n")
    assert __version__ in stdout
