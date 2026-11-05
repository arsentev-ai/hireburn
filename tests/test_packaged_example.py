"""The synthetic example shipped inside the package must match examples/ in the repo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_example_matches_repo_copy():
    src = ROOT / "examples" / "example-company"
    pkg = ROOT / "hireburn" / "_example" / "example-company"
    files = sorted(p.relative_to(src) for p in src.rglob("*") if p.is_file())
    assert files, "examples/example-company is empty"
    for rel in files:
        assert (pkg / rel).read_bytes() == (src / rel).read_bytes(), rel
