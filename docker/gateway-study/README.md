# Gateway Study Container

Build:

```bash
docker build -t gateway-study -f docker/gateway-study/Dockerfile .
```

Run interactively from the `ns-3-dev` root:

```bash
docker run --rm -it \
  -v "$(pwd)":/workspace/ns-3-dev \
  -w /workspace/ns-3-dev \
  gateway-study
```

Inside the container:

```bash
./ns3 configure
./ns3 build
python3 scripts/run-gateway-scenario-matrix.py \
  --ns3-path . \
  --scenario-set enhanced \
  --runs 1,2,3,4,5 \
  --bar \
  --plot \
  --output-root scenario-matrix
```

Prepare the release bundle:

```bash
python3 scripts/prepare-gateway-study-release.py \
  --ns3-path . \
  --scenario-root scenario-matrix/enhanced \
  --release-dir release/gateway-sleep-study \
  --scenarios s2_mid_baseline,s3_mid_dense,s4_mid_long_period,s5_far_moderate,s7_operating_limit
```
