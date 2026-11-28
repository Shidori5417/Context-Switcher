"""Hızlı yerel test çalıştırıcı.

tray ve hotkeys testlerini koşar, çıktıyı test_results.log'a yazar.
"""

import subprocess
import sys


def run() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_tray.py",
            "tests/test_hotkeys.py",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    with open("test_results.log", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write("\nSTDERR:\n")
        f.write(result.stderr)


if __name__ == "__main__":
    run()
