"""bench_report / bench_construct: the parts that need no gateway."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import bench_construct  # noqa: E402
import bench_report  # noqa: E402

_FIXTURE = Path(__file__).parent / "corpus" / "runs" / "mhd-v4pro-5round.json"


def _bench_dir(tmp_path: Path, n: int = 1) -> Path:
    d = tmp_path / "2026-09-30-fixture"
    d.mkdir()
    for i in range(1, n + 1):
        shutil.copy(_FIXTURE, d / f"run-{i}.json")
    (d / "meta.json").write_text(json.dumps({"tag": "fixture", "spec": "mhd"}), encoding="utf-8")
    return d


def test_report_is_rebuilt_from_saved_raw_runs_and_is_deterministic(tmp_path):
    d = _bench_dir(tmp_path, n=2)
    first = bench_report.build_report(d)
    assert first == bench_report.build_report(d)
    assert "| PARTIAL | 2 / 2 |" in first and "provisional" in first and "WARNING: N = 2 < 10" in first


def test_runs_are_ordered_numerically_not_lexically(tmp_path):
    d = _bench_dir(tmp_path, n=1)
    for i in (2, 10):
        shutil.copy(_FIXTURE, d / f"run-{i}.json")
    meta, runs = bench_report.load_runs(d)
    assert len(runs) == 3 and meta["tag"] == "fixture"
    assert [bench_report._run_index(p) for p in sorted(d.glob("run-*.json"), key=bench_report._run_index)] == [1, 2, 10]


def test_main_writes_summary_md_and_handles_an_empty_dir(tmp_path, capsys):
    d = _bench_dir(tmp_path)
    assert bench_report.main(["bench_report.py", str(d)]) == 0
    assert (d / "summary.md").read_text(encoding="utf-8").startswith("# Construct bench: fixture")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert bench_report.main(["bench_report.py", str(empty)]) == 1
    assert bench_report.main(["bench_report.py"]) == 2


def test_parse_args():
    p = bench_construct.parse_args(["b.py", "s.yaml", "--tag", "t", "--n", "3", "--max-rounds", "4", "--models", "m.json"])
    assert p == {"spec": "s.yaml", "n": 3, "tag": "t", "max_rounds": 4, "models": "m.json", "note": None}
    assert bench_construct.parse_args(["b.py", "s.yaml"]) is None                      # --tag is required
    assert bench_construct.parse_args(["b.py", "s.yaml", "--tag", "t", "--n", "0"]) is None
    assert bench_construct.parse_args(["b.py", "s.yaml", "--tag", "t", "--bogus", "1"]) is None
    assert bench_construct.parse_args(["b.py", "s.yaml", "--tag", "t", "--n", "x"]) is None


def test_bench_requires_a_token(monkeypatch, capsys):
    monkeypatch.delenv("MOONSTAR_AUTH_TOKEN", raising=False)
    assert bench_construct.main(["b.py", "constructs/x.yaml", "--tag", "t"]) == 1
    assert "MOONSTAR_AUTH_TOKEN" in capsys.readouterr().err
