# Reproducibility Bundle

This directory contains:

- `artifacts/`: selected CSV summaries and PNG plots from the enhanced scenario run
- `source-snapshots/`: the exact modified source files used to produce those outputs
- `artifact-manifest.csv`: inventory of included artifacts

To regenerate the enhanced scenario matrix from the source tree:

```bash
python3 scripts/run-gateway-scenario-matrix.py \
  --ns3-path . \
  --scenario-set enhanced \
  --runs 1,2,3,4,5 \
  --bar \
  --plot \
  --output-root scenario-matrix
```

To regenerate this bundle:

```bash
python3 scripts/prepare-gateway-study-release.py \
  --ns3-path . \
  --scenario-root scenario-matrix/enhanced \
  --release-dir release/gateway-sleep-study \
  --scenarios s2_mid_baseline,s3_mid_dense,s4_mid_long_period,s5_far_moderate,s7_operating_limit
```
