# Failure scenarios (MP1)

Machine data: 12 machines (M01-M12, zones A/B/C, types motor/pump/compressor/conveyor), 1 sample/s,
contract fields `temperature, vibration, speed, current, pressure, power, frequency, state`.
Everything is generated from `configs/scenarios.yaml` with a fixed seed (reproducible).

## Normal operation
Load cycle (sinusoid around 75 %, period 1 h, random phase per machine, noise) drives current,
vibration and speed (slip). Temperature follows the load with a first-order thermal lag (tau = 300 s).
Power = sqrt(3)·U·I·cos(phi). Frequency ~ 50 Hz.

## Fault model
Each fault has a severity curve s(t) in [0, 1]: 0 before `start_s`, reaching 1 after `duration_s`.
BEARING_WEAR is exponential (slow start, fast end), the others linear. The effect on the signals is
proportional to s(t), so early faults are small compared with normal load swings.
Samples are labelled faulty once s >= 0.2 (`label_threshold`); before that the label stays `NONE`
(grey zone, excluded from per-sample metrics). `state` = FAULT when s >= 0.9.

| Fault (`predicted_fault`) | Physical cause | Signature at s = 1 | Curve |
|---|---|---|---|
| BEARING_WEAR | worn bearing | vibration x3.5, temperature +6 °C | exponential (k=3) |
| OVERHEATING | cooling loss | temperature +30 °C, vibration +10 %, current unchanged | linear |
| IMBALANCE | rotor imbalance | vibration up to x3, proportional to speed² | linear |
| ELECTRICAL_OVERLOAD | overload / winding | current +45 %, temperature +15 °C, speed -8 % | linear |

## Datasets
| Set | Seed | Duration | Faulty machines |
|---|---|---|---|
| train | 42 | 4 h | 8 (2 per fault type) |
| test | 7 (+ seeds 11, 23, 31, 47 in evaluation) | 4 h | 6, on different machines and timings |

Ground truth (`severity`, `fault_type`, `label`) is stored in the CSVs and the `*_events.csv` files
(fault start, label start) but is never published in MQTT messages.

## Known simplifications
See "Limitations" in `EVALUATION.md`.