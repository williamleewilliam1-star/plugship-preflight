#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "preflight.py"
FIXTURES = ROOT / "tests" / "fixtures"


def scan(name):
    target = FIXTURES / name
    proc = subprocess.run(
        ["python3", str(SCANNER), str(target), "--json"],
        text=True,
        capture_output=True,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Scanner did not return JSON for {name}: {proc.stdout}\n{proc.stderr}") from exc
    return proc.returncode, payload


def main():
    good_rc, good = scan("good-plugin")
    assert good_rc == 0, good
    assert good["summary"]["BLOCK"] == 0, good

    bad_rc, bad = scan("bad-plugin")
    assert bad_rc == 2, bad
    assert bad["summary"]["BLOCK"] >= 2, bad
    codes = {item["code"] for item in bad["findings"]}
    assert "name-shape" in codes, codes
    assert "readme-short" in codes, codes
    print("PASS: good fixture accepted; bad fixture rejected with expected blockers")


if __name__ == "__main__":
    main()
