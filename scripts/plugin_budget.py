"""Fail when a plugin's always-on context cost grows past its recorded baseline.

`claude plugin details` projects the tokens a plugin adds to every session
(skill and agent listings). The skill-listing budget is shared by every installed
plugin, so growth here crowds out other skills' descriptions.

Usage: python3 -m scripts.plugin_budget [--update]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = ROOT / "scripts" / "plugin_budget.json"
PLUGIN_DIRS = ("plugins/elixir-phoenix", "plugins/ecto", "plugins/lv")
ALWAYS_ON = re.compile(r"Always-on:\s+~?([\d,]+)\s+tok")


def parse_always_on(details: str) -> int:
    match = ALWAYS_ON.search(details)
    if not match:
        raise ValueError("no 'Always-on' line in `claude plugin details` output")
    return int(match.group(1).replace(",", ""))


def measure(name: str) -> int:
    cmd = ["claude"]
    for plugin_dir in PLUGIN_DIRS:
        cmd += ["--plugin-dir", str(ROOT / plugin_dir)]
    cmd += ["plugin", "details", name]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
    return parse_always_on(result.stdout)


def over_budget(measured: int, baseline: int, tolerance: float, floor: int) -> bool:
    return measured > baseline + max(round(baseline * tolerance), floor)


def main(argv: list[str]) -> int:
    config = json.loads(BASELINE_FILE.read_text())
    failed = False
    for name, baseline in config["baselines"].items():
        measured = measure(name)
        over = over_budget(measured, baseline, config["tolerance"], config["floor_tokens"])
        failed |= over
        status = "OVER" if over else "ok"
        print(f"{name:<6} always-on ~{measured:>6,} tok  (baseline {baseline:,})  {status}")
        if "--update" in argv:
            config["baselines"][name] = measured
    if "--update" in argv:
        BASELINE_FILE.write_text(json.dumps(config, indent=2) + "\n")
        print(f"baselines written to {BASELINE_FILE.relative_to(ROOT)}")
        return 0
    if failed:
        print("Always-on cost grew past the baseline. Trim descriptions, or run "
              "`make budget-update` if the growth is intended.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
