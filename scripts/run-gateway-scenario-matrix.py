#!/usr/bin/env python3
"""
Run curated scenario sets for the gateway sleep study.
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from typing import Dict, List


SCENARIO_SETS: Dict[str, List[dict]] = {
    "quick-enhanced": [
        {
            "id": "q1_near_sparse",
            "label": "Near sparse baseline",
            "nodes": 20,
            "radius": 2000,
            "period": 30,
            "sim_hours": 2,
        },
        {
            "id": "q2_mid_dense",
            "label": "Mid-range dense",
            "nodes": 60,
            "radius": 5000,
            "period": 30,
            "sim_hours": 2,
        },
        {
            "id": "q3_far_edge",
            "label": "Far edge case",
            "nodes": 120,
            "radius": 10000,
            "period": 10,
            "sim_hours": 2,
        },
    ],
    "enhanced": [
        {
            "id": "s1_near_baseline",
            "label": "Near baseline",
            "nodes": 20,
            "radius": 2000,
            "period": 30,
            "sim_hours": 6,
        },
        {
            "id": "s2_mid_baseline",
            "label": "Mid baseline",
            "nodes": 30,
            "radius": 5000,
            "period": 30,
            "sim_hours": 6,
        },
        {
            "id": "s3_mid_dense",
            "label": "Mid dense",
            "nodes": 60,
            "radius": 5000,
            "period": 30,
            "sim_hours": 6,
        },
        {
            "id": "s4_mid_long_period",
            "label": "Mid dense long period",
            "nodes": 60,
            "radius": 5000,
            "period": 60,
            "sim_hours": 6,
        },
        {
            "id": "s5_far_moderate",
            "label": "Far moderate load",
            "nodes": 80,
            "radius": 7500,
            "period": 20,
            "sim_hours": 6,
        },
        {
            "id": "s6_far_dense",
            "label": "Far dense load",
            "nodes": 120,
            "radius": 10000,
            "period": 10,
            "sim_hours": 6,
        },
        {
            "id": "s7_operating_limit",
            "label": "Operating limit",
            "nodes": 160,
            "radius": 10000,
            "period": 10,
            "sim_hours": 6,
        },
        {
            "id": "s8_extreme_limit",
            "label": "Extreme operating limit",
            "nodes": 320,
            "radius": 10000,
            "period": 5,
            "sim_hours": 6,
        },
    ],
}


def run_command(cmd: List[str], cwd: str) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def write_manifest(path: str, rows: List[dict]) -> None:
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "label", "nodes", "radius", "period", "sim_hours", "runs", "plot_dir"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns3-path", default=".", help="Path to ns-3-dev root")
    parser.add_argument(
        "--scenario-set",
        default="enhanced",
        choices=sorted(SCENARIO_SETS.keys()),
        help="Curated scenario set to run",
    )
    parser.add_argument("--runs", default="1,2,3", help="RNG run numbers")
    parser.add_argument("--seed", default="1", help="RNG seed")
    parser.add_argument("--slot-spacing", default="0", help="Slot spacing seconds")
    parser.add_argument("--idle-a", default="0.542", help="Gateway idle current (A)")
    parser.add_argument("--sleep-a", default="0.1", help="Gateway sleep current (A)")
    parser.add_argument("--rx-a", default="0.65", help="Gateway RX current (A)")
    parser.add_argument("--supply-v", default="5.0", help="Gateway supply voltage (V)")
    parser.add_argument("--wakeup-seconds", default="4", help="Gateway wakeup time (s)")
    parser.add_argument("--output-root", default="scenario-matrix", help="Output directory root")
    parser.add_argument("--plot", action="store_true", help="Generate line plots")
    parser.add_argument("--bar", action="store_true", help="Generate bar charts")
    parser.add_argument("--map", action="store_true", help="Generate layout maps")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit")
    args = parser.parse_args()

    ns3_path = os.path.abspath(args.ns3_path)
    scenarios = SCENARIO_SETS[args.scenario_set]

    if args.list:
        for scenario in scenarios:
            print(
                f"{scenario['id']}: nodes={scenario['nodes']}, radius={scenario['radius']} m, "
                f"period={scenario['period']} min, sim_hours={scenario['sim_hours']} "
                f"({scenario['label']})"
            )
        return 0

    output_root = os.path.join(ns3_path, args.output_root, args.scenario_set)
    os.makedirs(output_root, exist_ok=True)

    manifest_rows = []
    sweep_script = os.path.join(ns3_path, "scripts", "run-gateway-sleep-sweep.py")

    for scenario in scenarios:
        scenario_id = scenario["id"]
        plot_dir = os.path.join(output_root, f"plots-{scenario_id}")
        out_csv = os.path.join(output_root, f"sweep-{scenario_id}.csv")
        summary_csv = os.path.join(output_root, f"summary-{scenario_id}.csv")
        delta_csv = os.path.join(output_root, f"delta-{scenario_id}.csv")

        cmd = [
            sys.executable,
            sweep_script,
            "--ns3-path",
            ns3_path,
            "--nodes",
            str(scenario["nodes"]),
            "--radius",
            str(scenario["radius"]),
            "--period",
            str(scenario["period"]),
            "--runs",
            args.runs,
            "--seed",
            args.seed,
            "--sim-hours",
            str(scenario["sim_hours"]),
            "--slot-spacing",
            args.slot_spacing,
            "--idle-a",
            args.idle_a,
            "--sleep-a",
            args.sleep_a,
            "--rx-a",
            args.rx_a,
            "--supply-v",
            args.supply_v,
            "--wakeup-seconds",
            args.wakeup_seconds,
            "--out",
            out_csv,
            "--summary-out",
            summary_csv,
            "--delta-out",
            delta_csv,
            "--plot-dir",
            plot_dir,
        ]

        if args.plot:
            cmd.append("--plot")
        if args.bar:
            cmd.append("--bar")
        if args.map:
            cmd.append("--map")
            cmd.extend(
                [
                    "--map-nodes",
                    str(scenario["nodes"]),
                    "--map-radius",
                    str(scenario["radius"]),
                    "--map-period",
                    str(scenario["period"]),
                    "--map-run",
                    args.runs.split(",")[0].strip(),
                ]
            )

        print(
            f"[{scenario_id}] nodes={scenario['nodes']} radius={scenario['radius']} "
            f"period={scenario['period']} runs={args.runs}"
        )
        run_command(cmd, ns3_path)

        manifest_rows.append(
            {
                "id": scenario_id,
                "label": scenario["label"],
                "nodes": scenario["nodes"],
                "radius": scenario["radius"],
                "period": scenario["period"],
                "sim_hours": scenario["sim_hours"],
                "runs": args.runs,
                "plot_dir": plot_dir,
            }
        )

    manifest_path = os.path.join(output_root, "scenario-manifest.csv")
    write_manifest(manifest_path, manifest_rows)
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
