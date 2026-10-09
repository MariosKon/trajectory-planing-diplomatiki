# ServoP parameter selection — 2026-10-09

**Decision:** Use **`aheadtime = 20`**, **`gain = 300`** as the default SDK
ServoP parameters for trajectory experiments. Priority: a relatively smooth
Rigol power waveform, with tracking accuracy as a secondary objective.

## Evidence (five repetitions per setting)

| Fixed trajectory | Parameters (aheadtime / gain) | Rigol fluctuation proxy, RMS (W) ↓ | TCP tracking RMSE (mm) ↓ | Motion duration (s) |
| --- | --- | ---: | ---: | ---: |
| Cubic | **20 / 300** | **6.13** | 11.797 | 2.874 |
| Cubic | 50 / 300 | 8.67 | **10.693** | 3.488 |
| Quintic | **20 / 300** | **6.50** | 13.074 | 2.786 |
| Quintic | 50 / 300 | 10.44 | **11.847** | 3.383 |

Source: `Final Results/servop_behavior/20261009_112859_212406/`
and `Final Results/servoP_confirmation/20261009_131342_651699/`.
Tracking and duration are means of the per-trial `metrics.json` values.
The Rigol fluctuation proxy was calculated from `rigol_scope.csv` as
the RMS of power minus a 21-point (105 ms) moving average, using the
same scope-relative interval [-2.25, 0.55] s for each valid trial.
Lower means less recorded short-timescale fluctuation, not necessarily
less physical vibration. Case `servop_behavior/case_008` (80 / 300)
had invalid scope power data and is excluded from the power ranking.

**Trade-off:** 50 / 300 reduced tracking RMSE but produced larger
recorded power fluctuations and longer motion. 20 / 300 also had the
lowest fluctuation proxy among the valid cubic sweep settings
(20/50/80 aheadtime × 300/500/700 gain).

## Implementation and scope

- `config/common.json` sets `servop_aheadtime=20` and `servop_gain=300`.
- `core/config.py` provides the same defaults when no JSON config is used.
- ServoP CSV experiments and online Ruckig use these defaults **unless
  the case supplies explicit `aheadtime`/`gain`**.
- The existing `aheadtime=20` and `gain=500` remain the ServoJ defaults.
- The `servop_behavior` and `servoP_confirmation` study matrices
  explicitly set their own parameters and are left unchanged, preserving
  historical case numbering and reproducibility.

**Limitations:** Rigol values are based on the 1,200-point NORM display
waveform, not independently validated high-rate RAW data. Scope and
robot clocks are not synchronized, and the common scope-relative window
does not guarantee the same motion-relative interval in each trial.
Differences in actual motion duration make the tracking RMSE comparison
speed-dependent. A supervised, matched-duration confirmation would
strengthen the conclusion. Do not interpret this as a safety validation.
