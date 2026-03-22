# Sleep-Enabled LoRaWAN Gateway Study (ns-3)

This repository contains a custom ns-3 LoRaWAN experiment for comparing:

- `always_on` gateway behavior
- `sleep_enabled` gateway behavior with SF-clustered scheduling

The study code is implemented as:

- `src/lorawan/examples/lorawan-gateway-sleep-energy-example.cc`
- `scripts/run-gateway-sleep-sweep.py`

## 1) What is implemented

- Gateway duty-cycling (wake/sleep windows)
- SF-based clustering (parallel SF windows, stagger within same SF)
- Gateway energy tracking by state (`IDLE`, `RX`, `SLEEP`)
- Comparison metrics: `totalJ`, `pdr`, and derived `energyPerRxJ`
- Statistical summaries: mean/std/95% CI from repeated runs

## 2) Build once

```bash
./ns3 configure
./ns3 build
```

## 3) Quick single run

```bash
./ns3 run "lorawan-gateway-sleep-energy-example --nDevices=30 --radius=5000 --periodMinutes=30 --slotSpacing=0 --seed=1 --run=1 --outCsv=gateway-energy-results.csv"
```

## 4) Reproducible final scenarios (paper set)

Run these 6 scenarios (10 runs each) to reproduce the final evaluation:

```bash
(
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 30 --radius 5000 --period 30 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s1.csv --summary-out summary-final-s1.csv --delta-out delta-final-s1.csv \
  --plot-dir plots-final-s1 &&
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 60 --radius 5000 --period 30 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s2.csv --summary-out summary-final-s2.csv --delta-out delta-final-s2.csv \
  --plot-dir plots-final-s2 &&
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 30 --radius 5000 --period 60 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s3.csv --summary-out summary-final-s3.csv --delta-out delta-final-s3.csv \
  --plot-dir plots-final-s3 &&
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 60 --radius 5000 --period 60 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s4.csv --summary-out summary-final-s4.csv --delta-out delta-final-s4.csv \
  --plot-dir plots-final-s4 &&
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 160 --radius 10000 --period 10 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s5.csv --summary-out summary-final-s5.csv --delta-out delta-final-s5.csv \
  --plot-dir plots-final-s5 &&
python3 scripts/run-gateway-sleep-sweep.py \
  --ns3-path . --nodes 320 --radius 10000 --period 5 \
  --runs 1,2,3,4,5,6,7,8,9,10 --slot-spacing 0 --plot --bar \
  --out sweep-final-s6.csv --summary-out summary-final-s6.csv --delta-out delta-final-s6.csv \
  --plot-dir plots-final-s6
) 2>&1 | tee run-final-6scenarios.log
```

## 5) Which files to cite in the paper

- Summary metrics and CI:
  - `summary-final-s1.csv` ... `summary-final-s6.csv`
- Paired scenario deltas:
  - `delta-final-s1.csv` ... `delta-final-s6.csv`
- Figures:
  - `plots-final-s1` ... `plots-final-s6`

## 6) Enhanced scenario matrix

For broader validation beyond the original paper set, use:

```bash
python3 scripts/run-gateway-scenario-matrix.py \
  --ns3-path . \
  --scenario-set enhanced \
  --runs 1,2,3,4,5 \
  --bar \
  --plot \
  --output-root scenario-matrix
```

This generates per-scenario bundles under:

- `scenario-matrix/enhanced/summary-*.csv`
- `scenario-matrix/enhanced/delta-*.csv`
- `scenario-matrix/enhanced/sweep-*.csv`
- `scenario-matrix/enhanced/plots-*/`

Recommended scenarios to keep for the paper:

- `s2_mid_baseline`
- `s3_mid_dense`
- `s4_mid_long_period`
- `s5_far_moderate`
- `s7_operating_limit`

Recommended figures per selected scenario:

- `bar_*.png` for energy and PDR
- `state_breakdown_*.png` for gateway time and energy shares
- `loss_breakdown_*.png` for packet loss causes

## 7) Prepare a reproducibility bundle

To collect the selected plots, CSV summaries, and the exact modified source files into one
publishable directory, run:

```bash
python3 scripts/prepare-gateway-study-release.py \
  --ns3-path . \
  --scenario-root scenario-matrix/enhanced \
  --release-dir release/gateway-sleep-study \
  --scenarios s2_mid_baseline,s3_mid_dense,s4_mid_long_period,s5_far_moderate,s7_operating_limit
```

This creates:

- `release/gateway-sleep-study/artifacts/`
- `release/gateway-sleep-study/source-snapshots/`
- `release/gateway-sleep-study/PAPER_FIGURES.md`
- `release/gateway-sleep-study/REPRODUCIBILITY.md`

## 8) Run in a container

For a reproducible environment, use the container files in:

- `docker/gateway-study/Dockerfile`
- `docker/gateway-study/README.md`

Build and run:

```bash
docker build -t gateway-study -f docker/gateway-study/Dockerfile .
docker run --rm -it \
  -v "$(pwd)":/workspace/ns-3-dev \
  -w /workspace/ns-3-dev \
  gateway-study
```

## 9) Publish to GitHub (minimal and clean)

Create a new GitHub repository first (web UI), then run:

```bash
git checkout -b paper-final
git add src/lorawan/examples/lorawan-gateway-sleep-energy-example.cc
git add src/lorawan/examples/CMakeLists.txt
git add scripts/run-gateway-sleep-sweep.py
git add scripts/run-gateway-scenario-matrix.py
git add scripts/prepare-gateway-study-release.py
git add docker/gateway-study
git add README_gateway_sleep_study.md
git add release/gateway-sleep-study
git add .gitignore
git commit -m "Add sleep-enabled LoRaWAN gateway study and reproducibility guide"
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin paper-final
```

This keeps the repository focused on source and reproducibility instructions,
without committing generated result artifacts by default.
