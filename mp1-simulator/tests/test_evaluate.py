import pandas as pd

from src.evaluate import detection_latencies, sample_metrics

TS = pd.date_range("2026-11-01", periods=6, freq="s", tz="UTC")


def frame(anomaly):
    label = ["NONE", "NONE"] + ["BEARING_WEAR"] * 4
    return pd.DataFrame({"machine_id": "M01", "timestamp": TS,
                         "severity": [0, 0, 0.5, 0.6, 0.7, 0.8], "label": label,
                         "anomaly": anomaly,
                         "predicted_fault": ["BEARING_WEAR" if a else "NONE" for a in anomaly]})


def test_perfect_detector():
    m = sample_metrics(frame([False, False, True, True, True, True]))
    assert (m["precision"], m["recall"], m["f1"]) == (1, 1, 1)
    assert m["false_alarm_rate"] == 0 and m["false_alarms_per_machine_day"] == 0


def test_false_alarm_is_counted():
    m = sample_metrics(frame([True, False, True, True, True, True]))
    assert m["false_alarm_rate"] == 0.5
    assert m["false_alarms_per_machine_day"] > 0


def test_latency_and_type():
    ev = pd.DataFrame([{"machine_id": "M01", "fault_type": "BEARING_WEAR",
                        "fault_start": TS[1], "label_start": TS[2]}])
    lat = detection_latencies(frame([False, False, True, True, True, True]), ev).iloc[0]
    assert lat["detected"] and lat["type_ok"] == 1.0
    assert lat["from_onset_min"] == 1 / 60 and lat["from_label_min"] == 0