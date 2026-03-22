#!/usr/bin/env python3
"""
Run a parameter sweep for the gateway sleep energy example and aggregate results.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import os
import subprocess
from typing import Dict, List, Tuple


def parse_list(arg: str, cast):
    return [cast(x.strip()) for x in arg.split(",") if x.strip()]


def run_example(ns3_path: str, args: List[str]) -> None:
    cmd = [os.path.join(ns3_path, "ns3"), "run", "lorawan-gateway-sleep-energy-example"]
    if args:
        cmd[-1] = f'{cmd[-1]} {" ".join(args)}'
    subprocess.run(cmd, cwd=ns3_path, check=True)


def read_result(csv_path: str) -> List[dict]:
    with open(csv_path, newline="") as handle:
        return list(csv.DictReader(handle))


def read_positions(csv_path: str) -> List[dict]:
    with open(csv_path, newline="") as handle:
        return list(csv.DictReader(handle))


def mean_std_ci95(values: List[float]) -> Tuple[float, float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0, 0.0
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(var)
    ci95 = 1.96 * std / math.sqrt(n)
    return mean, std, ci95


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns3-path", default=".", help="Path to ns-3-dev root")
    parser.add_argument("--nodes", default="10,20,30", help="Node counts")
    parser.add_argument("--radius", default="300,600,900", help="Deployment radius (m)")
    parser.add_argument("--period", default="10,30", help="Send period (minutes)")
    parser.add_argument("--runs", default="1,2,3", help="RNG run numbers")
    parser.add_argument("--seed", default="1", help="RNG seed")
    parser.add_argument("--out", default="gateway-energy-sweep.csv", help="Output CSV")
    parser.add_argument(
        "--summary-out",
        default="gateway-energy-summary.csv",
        help="Summary CSV with mean/std/95CI",
    )
    parser.add_argument(
        "--delta-out",
        default="gateway-energy-delta.csv",
        help="Paired delta CSV (sleep vs always_on)",
    )
    parser.add_argument("--plot", action="store_true", help="Generate PNG plots")
    parser.add_argument("--bar", action="store_true", help="Generate bar charts")
    parser.add_argument("--map", action="store_true", help="Generate layout maps")
    parser.add_argument("--map-nodes", default="10,30", help="Map node counts")
    parser.add_argument("--map-radius", default="10000", help="Map radius (m)")
    parser.add_argument("--map-period", default="30", help="Map period (minutes)")
    parser.add_argument("--map-run", default="1", help="Map RNG run number")
    parser.add_argument("--plot-dir", default="plots", help="Plot output directory")
    parser.add_argument("--sim-hours", default="6", help="Simulation hours")
    parser.add_argument("--slot-spacing", default="2", help="Slot spacing seconds")
    parser.add_argument("--idle-a", default="0.542", help="Gateway idle current (A)")
    parser.add_argument("--sleep-a", default="0.1", help="Gateway sleep current (A)")
    parser.add_argument("--rx-a", default="0.65", help="Gateway RX current (A)")
    parser.add_argument("--supply-v", default="5.0", help="Gateway supply voltage (V)")
    parser.add_argument("--wakeup-seconds", default="4", help="Gateway wakeup time (s)")
    args = parser.parse_args()

    ns3_path = os.path.abspath(args.ns3_path)
    nodes_list = parse_list(args.nodes, int)
    radius_list = parse_list(args.radius, float)
    period_list = parse_list(args.period, float)
    runs_list = parse_list(args.runs, int)
    seed = int(args.seed)

    out_path = os.path.join(ns3_path, args.out)
    fields = [
        "nDevices",
        "radius",
        "periodMinutes",
        "seed",
        "run",
        "scenario",
        "totalJ",
        "idleJ",
        "sleepJ",
        "rxJ",
        "idleSeconds",
        "sleepSeconds",
        "rxSeconds",
        "packetsSent",
        "packetsReceived",
        "pdr",
        "sf7",
        "sf8",
        "sf9",
        "sf10",
        "sf11",
        "sf12",
        "sf12OutOfRange",
        "overlapCollision",
        "crossSfInterference",
        "gatewaySleepingMissedWindow",
        "insufficientReceiveWindow",
        "sfChannelContention",
        "underSensitivity",
        "gatewayTxBusy",
        "timingMismatch",
        "energyPerRxJ",
    ]

    with open(out_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for n_devices, radius, period, run in itertools.product(
            nodes_list, radius_list, period_list, runs_list
        ):
            out_csv = os.path.join(ns3_path, "gateway-energy-results.csv")
            args_list = [
                f"--nDevices={n_devices}",
                f"--radius={radius}",
                f"--periodMinutes={period}",
                f"--seed={seed}",
                f"--run={run}",
                f"--simHours={args.sim_hours}",
                f"--slotSpacing={args.slot_spacing}",
                f"--idleA={args.idle_a}",
                f"--sleepA={args.sleep_a}",
                f"--rxA={args.rx_a}",
                f"--supplyV={args.supply_v}",
                f"--wakeupSeconds={args.wakeup_seconds}",
                f"--outCsv={out_csv}",
            ]
            run_example(ns3_path, args_list)
            for row in read_result(out_csv):
                packets_received = int(row["packetsReceived"])
                energy_per_rx = (
                    float(row["totalJ"]) / packets_received if packets_received > 0 else float("inf")
                )
                row_out = {
                    "nDevices": n_devices,
                    "radius": radius,
                    "periodMinutes": period,
                    "seed": seed,
                    "run": run,
                    "energyPerRxJ": energy_per_rx,
                    **row,
                }
                writer.writerow(row_out)

    print(f"Wrote sweep results to {out_path}")

    # Build grouped statistical summary for academic reporting
    summary_path = os.path.join(ns3_path, args.summary_out)
    grouped: Dict[Tuple[int, float, float, str], List[dict]] = {}
    with open(out_path, newline="") as handle:
        for row in csv.DictReader(handle):
            key = (
                int(float(row["nDevices"])),
                float(row["radius"]),
                float(row["periodMinutes"]),
                row["scenario"],
            )
            grouped.setdefault(key, []).append(row)

    summary_fields = [
        "nDevices",
        "radius",
        "periodMinutes",
        "scenario",
        "nRuns",
        "meanTotalJ",
        "stdTotalJ",
        "ci95TotalJ",
        "meanPdr",
        "stdPdr",
        "ci95Pdr",
        "meanEnergyPerRxJ",
        "stdEnergyPerRxJ",
        "ci95EnergyPerRxJ",
        "meanIdleSeconds",
        "meanSleepSeconds",
        "meanRxSeconds",
        "meanIdlePct",
        "meanSleepPct",
        "meanRxPct",
        "meanIdleEnergyPct",
        "meanSleepEnergyPct",
        "meanRxEnergyPct",
        "meanSf7",
        "meanSf8",
        "meanSf9",
        "meanSf10",
        "meanSf11",
        "meanSf12",
        "meanSf12OutOfRange",
        "meanOverlapCollision",
        "meanCrossSfInterference",
        "meanGatewaySleepingMissedWindow",
        "meanInsufficientReceiveWindow",
        "meanSfChannelContention",
        "meanUnderSensitivity",
        "meanGatewayTxBusy",
        "meanTimingMismatch",
    ]
    with open(summary_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        for key in sorted(grouped.keys()):
            rows = grouped[key]
            total_j = [float(r["totalJ"]) for r in rows]
            pdr = [float(r["pdr"]) for r in rows]
            epr = [float(r["energyPerRxJ"]) for r in rows if math.isfinite(float(r["energyPerRxJ"]))]
            idle_seconds = [float(r["idleSeconds"]) for r in rows]
            sleep_seconds = [float(r["sleepSeconds"]) for r in rows]
            rx_seconds = [float(r["rxSeconds"]) for r in rows]
            total_seconds = [i + s + rx for i, s, rx in zip(idle_seconds, sleep_seconds, rx_seconds)]
            sf_means = {
                "meanSf7": sum(float(r["sf7"]) for r in rows) / len(rows),
                "meanSf8": sum(float(r["sf8"]) for r in rows) / len(rows),
                "meanSf9": sum(float(r["sf9"]) for r in rows) / len(rows),
                "meanSf10": sum(float(r["sf10"]) for r in rows) / len(rows),
                "meanSf11": sum(float(r["sf11"]) for r in rows) / len(rows),
                "meanSf12": sum(float(r["sf12"]) for r in rows) / len(rows),
                "meanSf12OutOfRange": sum(float(r["sf12OutOfRange"]) for r in rows) / len(rows),
                "meanOverlapCollision": sum(float(r["overlapCollision"]) for r in rows) / len(rows),
                "meanCrossSfInterference": sum(float(r["crossSfInterference"]) for r in rows)
                / len(rows),
                "meanGatewaySleepingMissedWindow": sum(
                    float(r["gatewaySleepingMissedWindow"]) for r in rows
                )
                / len(rows),
                "meanInsufficientReceiveWindow": sum(
                    float(r["insufficientReceiveWindow"]) for r in rows
                )
                / len(rows),
                "meanSfChannelContention": sum(float(r["sfChannelContention"]) for r in rows)
                / len(rows),
                "meanUnderSensitivity": sum(float(r["underSensitivity"]) for r in rows) / len(rows),
                "meanGatewayTxBusy": sum(float(r["gatewayTxBusy"]) for r in rows) / len(rows),
                "meanTimingMismatch": sum(float(r["timingMismatch"]) for r in rows) / len(rows),
            }
            mean_total, std_total, ci_total = mean_std_ci95(total_j)
            mean_pdr, std_pdr, ci_pdr = mean_std_ci95(pdr)
            mean_epr, std_epr, ci_epr = mean_std_ci95(epr)
            mean_idle_seconds = sum(idle_seconds) / len(idle_seconds)
            mean_sleep_seconds = sum(sleep_seconds) / len(sleep_seconds)
            mean_rx_seconds = sum(rx_seconds) / len(rx_seconds)
            mean_total_seconds = sum(total_seconds) / len(total_seconds) if total_seconds else 0.0
            mean_idle_pct = (
                100.0 * mean_idle_seconds / mean_total_seconds if mean_total_seconds > 0 else 0.0
            )
            mean_sleep_pct = (
                100.0 * mean_sleep_seconds / mean_total_seconds if mean_total_seconds > 0 else 0.0
            )
            mean_rx_pct = (
                100.0 * mean_rx_seconds / mean_total_seconds if mean_total_seconds > 0 else 0.0
            )
            mean_idle_energy_pct = 100.0 * (
                sum(float(r["idleJ"]) for r in rows) / len(rows)
            ) / mean_total if mean_total > 0 else 0.0
            mean_sleep_energy_pct = 100.0 * (
                sum(float(r["sleepJ"]) for r in rows) / len(rows)
            ) / mean_total if mean_total > 0 else 0.0
            mean_rx_energy_pct = 100.0 * (
                sum(float(r["rxJ"]) for r in rows) / len(rows)
            ) / mean_total if mean_total > 0 else 0.0
            writer.writerow(
                {
                    "nDevices": key[0],
                    "radius": key[1],
                    "periodMinutes": key[2],
                    "scenario": key[3],
                    "nRuns": len(rows),
                    "meanTotalJ": mean_total,
                    "stdTotalJ": std_total,
                    "ci95TotalJ": ci_total,
                    "meanPdr": mean_pdr,
                    "stdPdr": std_pdr,
                    "ci95Pdr": ci_pdr,
                    "meanEnergyPerRxJ": mean_epr,
                    "stdEnergyPerRxJ": std_epr,
                    "ci95EnergyPerRxJ": ci_epr,
                    "meanIdleSeconds": mean_idle_seconds,
                    "meanSleepSeconds": mean_sleep_seconds,
                    "meanRxSeconds": mean_rx_seconds,
                    "meanIdlePct": mean_idle_pct,
                    "meanSleepPct": mean_sleep_pct,
                    "meanRxPct": mean_rx_pct,
                    "meanIdleEnergyPct": mean_idle_energy_pct,
                    "meanSleepEnergyPct": mean_sleep_energy_pct,
                    "meanRxEnergyPct": mean_rx_energy_pct,
                    **sf_means,
                }
            )
    print(f"Wrote summary stats to {summary_path}")

    # Build paired deltas by run for fair scenario comparison
    delta_path = os.path.join(ns3_path, args.delta_out)
    per_run: Dict[Tuple[int, float, float, int], Dict[str, dict]] = {}
    with open(out_path, newline="") as handle:
        for row in csv.DictReader(handle):
            key = (
                int(float(row["nDevices"])),
                float(row["radius"]),
                float(row["periodMinutes"]),
                int(float(row["run"])),
            )
            per_run.setdefault(key, {})[row["scenario"]] = row

    delta_rows: List[dict] = []
    for key in sorted(per_run.keys()):
        pair = per_run[key]
        if "always_on" not in pair or "sleep_enabled" not in pair:
            continue
        ao = pair["always_on"]
        se = pair["sleep_enabled"]
        ao_total = float(ao["totalJ"])
        se_total = float(se["totalJ"])
        ao_pdr = float(ao["pdr"])
        se_pdr = float(se["pdr"])
        savings_pct = ((ao_total - se_total) / ao_total * 100.0) if ao_total > 0 else 0.0
        delta_rows.append(
            {
                "nDevices": key[0],
                "radius": key[1],
                "periodMinutes": key[2],
                "run": key[3],
                "alwaysOnTotalJ": ao_total,
                "sleepEnabledTotalJ": se_total,
                "energySavingsPct": savings_pct,
                "alwaysOnPdr": ao_pdr,
                "sleepEnabledPdr": se_pdr,
                "pdrDeltaSleepMinusAlways": se_pdr - ao_pdr,
            }
        )

    delta_fields = [
        "nDevices",
        "radius",
        "periodMinutes",
        "run",
        "alwaysOnTotalJ",
        "sleepEnabledTotalJ",
        "energySavingsPct",
        "alwaysOnPdr",
        "sleepEnabledPdr",
        "pdrDeltaSleepMinusAlways",
    ]
    with open(delta_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=delta_fields)
        writer.writeheader()
        writer.writerows(delta_rows)
    print(f"Wrote paired deltas to {delta_path}")

    if args.plot or args.bar or args.map:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed; skip plots. Install python3-matplotlib to enable.")
            return 0

        scenario_colors = {"always_on": "#6c757d", "sleep_enabled": "#2ca02c"}
        state_colors = {"idle": "#4c78a8", "sleep": "#72b7b2", "rx": "#f58518"}
        loss_labels = [
            ("overlapCollision", "Overlap"),
            ("crossSfInterference", "Cross-SF"),
            ("gatewaySleepingMissedWindow", "Sleep miss"),
            ("insufficientReceiveWindow", "Sleep abort"),
            ("sfChannelContention", "Contention"),
            ("underSensitivity", "Low power"),
            ("gatewayTxBusy", "GW TX"),
            ("timingMismatch", "Timing"),
        ]

        plots_dir = os.path.join(ns3_path, args.plot_dir)
        os.makedirs(plots_dir, exist_ok=True)

        # Aggregate by (radius, period, nDevices, scenario) across runs
        buckets: Dict[Tuple[float, float, int, str], List[dict]] = {}
        with open(out_path, newline="") as handle:
            for row in csv.DictReader(handle):
                key = (
                    float(row["radius"]),
                    float(row["periodMinutes"]),
                    int(row["nDevices"]),
                    row["scenario"],
                )
                buckets.setdefault(key, []).append(row)

        # Build summary per (radius, period, nDevices)
        summary: Dict[Tuple[float, float, int], Dict[str, Dict[str, float]]] = {}
        for (radius, period, n_devices, scenario), rows in buckets.items():
            totalJ = sum(float(r["totalJ"]) for r in rows) / len(rows)
            pdr = sum(float(r["pdr"]) for r in rows) / len(rows)
            idle_seconds = sum(float(r["idleSeconds"]) for r in rows) / len(rows)
            sleep_seconds = sum(float(r["sleepSeconds"]) for r in rows) / len(rows)
            rx_seconds = sum(float(r["rxSeconds"]) for r in rows) / len(rows)
            total_seconds = idle_seconds + sleep_seconds + rx_seconds
            idle_pct = 100.0 * idle_seconds / total_seconds if total_seconds > 0 else 0.0
            sleep_pct = 100.0 * sleep_seconds / total_seconds if total_seconds > 0 else 0.0
            rx_pct = 100.0 * rx_seconds / total_seconds if total_seconds > 0 else 0.0
            idle_energy_pct = (
                100.0 * (sum(float(r["idleJ"]) for r in rows) / len(rows)) / totalJ if totalJ > 0 else 0.0
            )
            sleep_energy_pct = (
                100.0 * (sum(float(r["sleepJ"]) for r in rows) / len(rows)) / totalJ if totalJ > 0 else 0.0
            )
            rx_energy_pct = (
                100.0 * (sum(float(r["rxJ"]) for r in rows) / len(rows)) / totalJ if totalJ > 0 else 0.0
            )
            summary.setdefault((radius, period, n_devices), {})[scenario] = {
                "totalJ": totalJ,
                "pdr": pdr,
                "idlePct": idle_pct,
                "sleepPct": sleep_pct,
                "rxPct": rx_pct,
                "idleEnergyPct": idle_energy_pct,
                "sleepEnergyPct": sleep_energy_pct,
                "rxEnergyPct": rx_energy_pct,
                "overlapCollision": sum(float(r["overlapCollision"]) for r in rows) / len(rows),
                "crossSfInterference": sum(float(r["crossSfInterference"]) for r in rows) / len(rows),
                "gatewaySleepingMissedWindow": sum(
                    float(r["gatewaySleepingMissedWindow"]) for r in rows
                )
                / len(rows),
                "insufficientReceiveWindow": sum(
                    float(r["insufficientReceiveWindow"]) for r in rows
                )
                / len(rows),
                "sfChannelContention": sum(float(r["sfChannelContention"]) for r in rows) / len(rows),
                "underSensitivity": sum(float(r["underSensitivity"]) for r in rows) / len(rows),
                "gatewayTxBusy": sum(float(r["gatewayTxBusy"]) for r in rows) / len(rows),
                "timingMismatch": sum(float(r["timingMismatch"]) for r in rows) / len(rows),
            }

        if args.plot:
            # Line plots over nDevices
            series: Dict[Tuple[float, float], Dict[str, Dict[int, Dict[str, float]]]] = {}
            for (radius, period, n_devices), scenarios in summary.items():
                for scenario, metrics in scenarios.items():
                    series.setdefault((radius, period), {}).setdefault(scenario, {})[n_devices] = metrics

            for (radius, period), scenario_map in series.items():
                fig, (ax_energy, ax_pdr) = plt.subplots(1, 2, figsize=(10, 4))
                fig.suptitle(f"Radius {radius} m, Period {period} min")

                for scenario, n_map in scenario_map.items():
                    xs = sorted(n_map.keys())
                    ys_energy = [n_map[x]["totalJ"] for x in xs]
                    ys_pdr = [n_map[x]["pdr"] for x in xs]
                    ax_energy.plot(xs, ys_energy, marker="o", label=scenario)
                    ax_pdr.plot(xs, ys_pdr, marker="o", label=scenario)

                ax_energy.set_xlabel("nDevices")
                ax_energy.set_ylabel("Total energy (J)")
                ax_energy.grid(True, alpha=0.3)
                ax_energy.legend()

                ax_pdr.set_xlabel("nDevices")
                ax_pdr.set_ylabel("PDR")
                ax_pdr.set_ylim(0, 1)
                ax_pdr.grid(True, alpha=0.3)
                ax_pdr.legend()

                filename = f"gateway_energy_r{int(radius)}_p{int(period)}.png"
                fig.tight_layout()
                fig.savefig(os.path.join(plots_dir, filename), dpi=150)
                plt.close(fig)

        if args.bar:
            # Bar charts comparing scenarios per (radius, period, nDevices)
            for (radius, period, n_devices), scenarios in summary.items():
                if "always_on" not in scenarios or "sleep_enabled" not in scenarios:
                    continue
                fig, (ax_energy, ax_pdr) = plt.subplots(1, 2, figsize=(8, 4))
                fig.suptitle(f"Radius {radius} m, Period {period} min, n={n_devices}")

                labels = ["always_on", "sleep_enabled"]
                energy_vals = [scenarios[label]["totalJ"] for label in labels]
                pdr_vals = [scenarios[label]["pdr"] for label in labels]

                ax_energy.bar(labels, energy_vals, color=[scenario_colors[label] for label in labels])
                ax_energy.set_ylabel("Total energy (J)")
                ax_energy.grid(True, axis="y", alpha=0.3)

                ax_pdr.bar(labels, pdr_vals, color=[scenario_colors[label] for label in labels])
                ax_pdr.set_ylabel("PDR")
                ax_pdr.set_ylim(0, 1)
                ax_pdr.grid(True, axis="y", alpha=0.3)

                filename = f"bar_r{int(radius)}_p{int(period)}_n{n_devices}.png"
                fig.tight_layout()
                fig.savefig(os.path.join(plots_dir, filename), dpi=150)
                plt.close(fig)

                fig, (ax_time, ax_energy_share) = plt.subplots(1, 2, figsize=(9, 4))
                fig.suptitle(f"Gateway State Breakdown: r={radius} m, p={period} min, n={n_devices}")

                bottom = [0.0, 0.0]
                for key, title in [("idlePct", "IDLE"), ("sleepPct", "SLEEP"), ("rxPct", "RX")]:
                    values = [scenarios[label][key] for label in labels]
                    color = state_colors[title.lower()]
                    ax_time.bar(labels, values, bottom=bottom, label=title, color=color)
                    bottom = [b + v for b, v in zip(bottom, values)]
                ax_time.set_ylabel("Time share (%)")
                ax_time.set_ylim(0, 100)
                ax_time.grid(True, axis="y", alpha=0.3)
                ax_time.legend()

                bottom = [0.0, 0.0]
                for key, title in [
                    ("idleEnergyPct", "IDLE"),
                    ("sleepEnergyPct", "SLEEP"),
                    ("rxEnergyPct", "RX"),
                ]:
                    values = [scenarios[label][key] for label in labels]
                    color = state_colors[title.lower()]
                    ax_energy_share.bar(labels, values, bottom=bottom, label=title, color=color)
                    bottom = [b + v for b, v in zip(bottom, values)]
                ax_energy_share.set_ylabel("Energy share (%)")
                ax_energy_share.set_ylim(0, 100)
                ax_energy_share.grid(True, axis="y", alpha=0.3)
                ax_energy_share.legend()

                filename = f"state_breakdown_r{int(radius)}_p{int(period)}_n{n_devices}.png"
                fig.tight_layout()
                fig.savefig(os.path.join(plots_dir, filename), dpi=150)
                plt.close(fig)

                fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
                fig.suptitle(f"Loss Breakdown: r={radius} m, p={period} min, n={n_devices}")

                for ax, scenario in zip(axes, labels):
                    values = [scenarios[scenario][key] for key, _ in loss_labels]
                    labels_x = [label for _, label in loss_labels]
                    ax.bar(labels_x, values, color=scenario_colors[scenario])
                    ax.set_title(scenario)
                    ax.set_ylabel("Mean packets")
                    ax.grid(True, axis="y", alpha=0.3)
                    ax.tick_params(axis="x", rotation=35)

                filename = f"loss_breakdown_r{int(radius)}_p{int(period)}_n{n_devices}.png"
                fig.tight_layout()
                fig.savefig(os.path.join(plots_dir, filename), dpi=150)
                plt.close(fig)

        if args.map:
            map_nodes = parse_list(args.map_nodes, int)
            map_radius = float(args.map_radius)
            map_period = float(args.map_period)
            map_run = int(args.map_run)

            for n_devices in map_nodes:
                positions_csv = os.path.join(
                    ns3_path, f"positions_n{n_devices}_r{int(map_radius)}.csv"
                )
                args_list = [
                    f"--nDevices={n_devices}",
                    f"--radius={map_radius}",
                    f"--periodMinutes={map_period}",
                    f"--seed={seed}",
                    f"--run={map_run}",
                    f"--simHours={args.sim_hours}",
                    f"--slotSpacing={args.slot_spacing}",
                    f"--idleA={args.idle_a}",
                    f"--sleepA={args.sleep_a}",
                    f"--rxA={args.rx_a}",
                    f"--supplyV={args.supply_v}",
                    f"--wakeupSeconds={args.wakeup_seconds}",
                    f"--outCsv={os.path.join(ns3_path, 'gateway-energy-results.csv')}",
                    f"--positionsCsv={positions_csv}",
                ]
                run_example(ns3_path, args_list)

                rows = read_positions(positions_csv)
                xs = [float(r["x"]) for r in rows if r["type"] == "end_device"]
                ys = [float(r["y"]) for r in rows if r["type"] == "end_device"]
                gw_rows = [r for r in rows if r["type"] == "gateway"]
                gw_x = float(gw_rows[0]["x"]) if gw_rows else 0.0
                gw_y = float(gw_rows[0]["y"]) if gw_rows else 0.0

                fig, ax = plt.subplots(figsize=(5, 5))
                circle = plt.Circle((0, 0), map_radius, color="#dddddd", fill=False, lw=1.0)
                ax.add_patch(circle)
                ax.scatter(xs, ys, s=20, color="#1f77b4", label="end_device")
                ax.scatter([gw_x], [gw_y], marker="*", s=120, color="#d62728", label="gateway")
                ax.set_aspect("equal", "box")
                ax.set_xlim(-map_radius * 1.05, map_radius * 1.05)
                ax.set_ylim(-map_radius * 1.05, map_radius * 1.05)
                ax.set_xlabel("x (m)")
                ax.set_ylabel("y (m)")
                ax.set_title(f"Layout: n={n_devices}, radius={int(map_radius)} m")
                ax.grid(True, alpha=0.3)
                ax.legend(loc="upper right")
                filename = f"layout_n{n_devices}_r{int(map_radius)}.png"
                fig.tight_layout()
                fig.savefig(os.path.join(plots_dir, filename), dpi=150)
                plt.close(fig)

        print(f"Wrote plots to {plots_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
