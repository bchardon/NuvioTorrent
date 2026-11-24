#!/usr/bin/env python3
"""Prepare a pinned upstream checkout without resetting or removing existing files."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare(platform, destination):
    upstream = json.loads((ROOT / "upstreams.json").read_text())[platform]
    if not destination.exists():
        subprocess.run(["git", "clone", "--no-checkout", "--filter=blob:none",
                        f"https://github.com/{upstream['repository']}.git", str(destination)], check=True)
        subprocess.run(["git", "-C", str(destination), "checkout", "--detach", upstream["commit"]], check=True)
    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
    if actual != upstream["commit"]:
        raise SystemExit(f"Unexpected upstream commit in {destination}; no files were changed")
    patch = ROOT / "patches" / f"{platform}.patch"
    subprocess.run(["git", "-C", str(destination), "apply", "--check", str(patch)], check=True)
    subprocess.run(["git", "-C", str(destination), "apply", str(patch)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["tv", "mobile"])
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    prepare(args.platform, args.destination or ROOT / "work" / args.platform)
