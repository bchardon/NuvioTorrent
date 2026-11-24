#!/usr/bin/env python3
"""Export modified source checkouts as reviewable, text-only patches."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def export():
    upstreams = json.loads((ROOT / "upstreams.json").read_text())
    for platform, upstream in upstreams.items():
        checkout = ROOT.parent / upstream["directory"]
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        if actual != upstream["commit"]:
            raise SystemExit(f"Unexpected base commit in {checkout}")
        patch = subprocess.check_output(["git", "-C", str(checkout), "diff", "--binary", "HEAD"])
        untracked = subprocess.check_output(["git", "-C", str(checkout), "ls-files", "--others", "--exclude-standard", "-z"]).split(b"\0")
        for raw_name in filter(None, untracked):
            name = raw_name.decode()
            if not name.endswith(".kt"):
                raise SystemExit(f"Review this untracked file before exporting: {name}")
            added = subprocess.run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", name],
                                   cwd=checkout, capture_output=True)
            if added.returncode != 1:
                raise SystemExit(added.stderr.decode())
            patch += added.stdout
        (ROOT / "patches" / f"{platform}.patch").write_bytes(patch)
        print(f"{platform}: {len(patch)} bytes exported")


if __name__ == "__main__":
    export()
