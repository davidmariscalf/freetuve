from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "upstream.lock.json"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def sync_repo(name: str, cfg: dict[str, str]) -> None:
    target = ROOT / cfg["checkout_dir"]
    repo = cfg["repository"]
    commit = cfg["commit"]

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--filter=blob:none", "--no-checkout", repo, str(target))

    run("git", "fetch", "origin", commit, "--depth", "1", cwd=target)
    run("git", "checkout", "--detach", commit, cwd=target)
    print(f"{name}: {commit}")


def main() -> None:
    with LOCK_FILE.open("r", encoding="utf-8") as fh:
        repos = json.load(fh)

    for name, cfg in repos.items():
        sync_repo(name, cfg)


if __name__ == "__main__":
    main()
