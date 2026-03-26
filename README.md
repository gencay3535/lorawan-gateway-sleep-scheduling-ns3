# Sleep-Enabled LoRaWAN Gateway Scheduling in ns-3

This repository packages a reproducible ns-3 LoRaWAN study of:

- sleep-enabled gateway scheduling
- SF-based clustered uplink windows
- gateway energy reduction versus packet delivery tradeoffs
- packet loss cause analysis
- gateway state time and energy breakdowns

The study is implemented primarily in:

- `src/lorawan/examples/lorawan-gateway-sleep-energy-example.cc`
- `src/lorawan/model/gateway-lora-phy.cc`
- `src/lorawan/model/gateway-lora-phy.h`
- `src/lorawan/model/simple-gateway-lora-phy.cc`
- `scripts/run-gateway-sleep-sweep.py`
- `scripts/run-gateway-scenario-matrix.py`

## What Is In This Repo

- A full ns-3 source tree used as the reproducible base
- Modified LoRaWAN gateway PHY and study example code
- Sweep and scenario-matrix runners for repeated experiments
- Docker files for environment reproducibility
- A release bundle with selected plots and CSV results for the paper

## Quick Start

Build once:

```bash
./ns3 configure --enable-examples
./ns3 build
```

Note: `lorawan-gateway-sleep-energy-example` is an ns-3 example target, so a fresh clone must be
configured with examples enabled before `./ns3 run ...` can resolve it.

Run a single study scenario:

```bash
./ns3 run "lorawan-gateway-sleep-energy-example --nDevices=30 --radius=5000 --periodMinutes=30 --slotSpacing=0 --seed=1 --run=1 --outCsv=gateway-energy-results.csv"
```

If `./ns3 configure` or `./ns3 build` reports that `CMakeCache.txt` was created from a different
source directory, clear the stale build state and reconfigure:

```bash
rm -rf cmake-cache build
./ns3 configure --enable-examples
./ns3 build
```

Run the enhanced curated scenario matrix:

```bash
python3 scripts/run-gateway-scenario-matrix.py \
  --ns3-path . \
  --scenario-set enhanced \
  --runs 1,2,3,4,5 \
  --bar \
  --plot \
  --output-root scenario-matrix
```

Plot generation requires Python plotting dependencies, including `matplotlib`. If you only need CSV
outputs, the simulations can still complete without those packages, but PNG figures will not be
generated. The Docker environment included in this repository provides the plotting dependencies.

## Recommended Paper Scenarios

The strongest scenarios for reporting are:

- `s2_mid_baseline`
- `s3_mid_dense`
- `s4_mid_long_period`
- `s5_far_moderate`
- `s7_operating_limit`

The selected release artifacts for these scenarios are bundled under:

- `release/gateway-sleep-study/`

## Reproducibility Bundle

The release bundle contains:

- selected `summary`, `delta`, and `sweep` CSV files
- selected energy/PDR, state breakdown, and loss breakdown plots
- snapshots of the modified source files
- paper-figure guidance

See:

- `release/gateway-sleep-study/REPRODUCIBILITY.md`
- `release/gateway-sleep-study/PAPER_FIGURES.md`

## Container

For a reproducible environment:

```bash
docker build -t gateway-study -f docker/gateway-study/Dockerfile .
docker run --rm -it \
  -v "$(pwd)":/workspace/ns-3-dev \
  -w /workspace/ns-3-dev \
  gateway-study
```

Container details:

- `docker/gateway-study/Dockerfile`
- `docker/gateway-study/README.md`

## Study Documentation

The detailed study README is:

- `README_gateway_sleep_study.md`

The original upstream ns-3 landing-page README has been preserved as:

- `README_ns3_upstream.md`

## License

This repository follows the ns-3 / LoRaWAN code licensing already present in the
source tree, including GPL-2.0-only licensing for the distributed code.
