from cradrive.analysis.summarize import trace_integrity


def test_trace_integrity_accepts_monotone_single_run():
    rows=[{"run_id":"r","pid":1,"timestamp":0.0,"step":0},
          {"run_id":"r","pid":1,"timestamp":0.05,"step":1}]
    assert trace_integrity(rows)==(True,"")


def test_trace_integrity_rejects_mixed_run():
    rows=[{"run_id":"a","pid":1,"timestamp":0.0,"step":0},
          {"run_id":"b","pid":1,"timestamp":0.05,"step":1}]
    ok,reason=trace_integrity(rows)
    assert not ok and reason=="multiple_run_ids"


def test_trace_integrity_rejects_time_reset():
    rows=[{"run_id":"r","pid":1,"timestamp":1.0,"step":10},
          {"run_id":"r","pid":1,"timestamp":0.1,"step":0}]
    ok,reason=trace_integrity(rows)
    assert not ok and reason.startswith("timestamp_or_step_resets")
