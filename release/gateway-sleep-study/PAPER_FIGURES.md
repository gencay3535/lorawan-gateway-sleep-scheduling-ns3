# Paper Figures

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
