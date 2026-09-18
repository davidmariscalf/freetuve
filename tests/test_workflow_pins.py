import re
from pathlib import Path


SHA40 = re.compile(r"^[0-9a-f]{40}$")


def test_external_github_actions_are_pinned_to_immutable_shas():
    workflow_dir = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    checked = 0

    for path in (*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped.startswith("- uses:"):
                continue
            uses = stripped.split("uses:", 1)[1].strip().split()[0]
            if uses.startswith("./") or uses.startswith("docker://"):
                continue
            checked += 1
            assert "@" in uses, f"{path.name}: missing action ref: {uses}"
            _, ref = uses.rsplit("@", 1)
            assert SHA40.fullmatch(ref), f"{path.name}: mutable action ref: {uses}"

    assert checked > 0
