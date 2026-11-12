import pandas as pd
from src.nepal_firewatch.normalize import normalize

def test_low_confidence_filtered():
    df=pd.DataFrame([{"latitude":27.7,"longitude":85.3,"acq_date":"2026-09-27","acq_time":123,"confidence":"l","frp":2,"source":"VIIRS_NOAA20_NRT"}])
    assert normalize(df,"nominal")==[]

def test_time_padding_and_npt():
    df=pd.DataFrame([{"latitude":27.7,"longitude":85.3,"acq_date":"2026-09-27","acq_time":5,"confidence":"n","frp":4,"source":"VIIRS_NOAA20_NRT"}])
    r=normalize(df)[0]
    assert "00:05:00+00:00" in r["observed_utc"]
    assert "+05:45" in r["observed_npt"]
