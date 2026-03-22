#!/usr/bin/env python3
"""
Prepare a reproducibility bundle for the gateway sleep study.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path


DEFAULT_SCENARIOS = [
    "s2_mid_baseline",
    "s3_mid_dense",
    "s4_mid_long_period",
    "s5_far_moderate",
    "s7_operating_limit",
]

SOURCE_SNAPSHOTS = [
    "README_gateway_sleep_study.md",
    "scripts/run-gateway-sleep-sweep.py",
    "scripts/run-gateway-scenario-matrix.py",
    "scripts/prepare-gateway-study-release.py",
    "src/lorawan/examples/CMakeLists.txt",
    "src/lorawan/examples/lorawan-gateway-sleep-energy-example.cc",
    "src/lorawan/model/gateway-lora-phy.h",
    "src/lorawan/model/gateway-lora-phy.cc",
    "src/lorawan/model/simple-gateway-lora-phy.cc",
]

PLOT_PREFIXES = [
    "bar_",
    "state_breakdown_",
    "loss_breakdown_",
]


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def scenario_plot_paths(plot_dir: Path) -> list[Path]:
    files = []
    for prefix in PLOT_PREFIXES:
        files.extend(sorted(plot_dir.glob(f"{prefix}*.png")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns3-path", default=".", help="Path to ns-3-dev root")
    parser.add_argument(
        "--scenario-root",
        default="scenario-matrix/enhanced",
        help="Path to generated scenario matrix outputs relative to ns3 path",
    )
    parser.add_argument(
        "--release-dir",
        default="release/gateway-sleep-study",
        help="Release output directory relative to ns3 path",
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(DEFAULT_SCENARIOS),
        help="Comma-separated scenario ids to include",
    )
    args = parser.parse_args()

    ns3_root = Path(args.ns3_path).resolve()
    scenario_root = (ns3_root / args.scenario_root).resolve()
    release_root = (ns3_root / args.release_dir).resolve()
    artifact_root = release_root / "artifacts"
    source_root = release_root / "source-snapshots"

    scenario_ids = [item.strip() for item in args.scenarios.split(",") if item.strip()]

    if release_root.exists():
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True, exist_ok=True)

    manifest_rows = []

    for scenario_id in scenario_ids:
        summary = scenario_root / f"summary-{scenario_id}.csv"
        delta = scenario_root / f"delta-{scenario_id}.csv"
        sweep = scenario_root / f"sweep-{scenario_id}.csv"
        plot_dir = scenario_root / f"plots-{scenario_id}"

        for src in [summary, delta, sweep]:
            if src.exists():
                dst = artifact_root / scenario_id / src.name
                copy_file(src, dst)
                manifest_rows.append({"scenario": scenario_id, "type": "csv", "path": str(dst.relative_to(release_root))})

        for plot in scenario_plot_paths(plot_dir):
            dst = artifact_root / scenario_id / plot.name
            copy_file(plot, dst)
            manifest_rows.append({"scenario": scenario_id, "type": "plot", "path": str(dst.relative_to(release_root))})

    manifest_path = release_root / "artifact-manifest.csv"
    with manifest_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scenario", "type", "path"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    for rel_path in SOURCE_SNAPSHOTS:
        src = ns3_root / rel_path
        if src.exists():
            copy_file(src, source_root / rel_path)

    write_markdown(
        release_root / "PAPER_FIGURES.md",
        """# Paper Figures

Recommended scenarios for the article:

- `s2_mid_baseline`
- `s3_mid_dense`
- `s4_mid_long_period`
- `s5_far_moderate`
- `s7_operating_limit`

Recommended figure usage per scenario:

- `bar_*.png`: main energy/PDR comparison
- `state_breakdown_*.png`: gateway time share and energy share by state
- `loss_breakdown_*.png`: packet loss cause breakdown

Suggested narrative:

- `s2`, `s3`, `s4`: core evidence that sleep scheduling preserves reliability while reducing energy.
- `s5`: transition regime where higher SFs and collision pressure start increasing.
- `s7`: operating-limit regime showing that degradation is dominated by coverage/collision effects, not missed sleep windows.
""",
    )

    write_markdown(
        release_root / "REPRODUCIBILITY.md",
        """# Reproducibility Bundle

This directory contains:

- `artifacts/`: selected CSV summaries and PNG plots from the enhanced scenario run
- `source-snapshots/`: the exact modified source files used to produce those outputs
- `artifact-manifest.csv`: inventory of included artifacts

To regenerate the enhanced scenario matrix from the source tree:

```bash
python3 scripts/run-gateway-scenario-matrix.py \\
  --ns3-path . \\
  --scenario-set enhanced \\
  --runs 1,2,3,4,5 \\
  --bar \\
  --plot \\
  --output-root scenario-matrix
```

To regenerate this bundle:

```bash
python3 scripts/prepare-gateway-study-release.py \\
  --ns3-path . \\
  --scenario-root scenario-matrix/enhanced \\
  --release-dir release/gateway-sleep-study \\
  --scenarios s2_mid_baseline,s3_mid_dense,s4_mid_long_period,s5_far_moderate,s7_operating_limit
```
""",
    )

    print(f"Wrote release bundle to {release_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
