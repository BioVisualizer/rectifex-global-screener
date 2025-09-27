import math

import numpy as np

from core.data.fundamentals import read_fundamentals


def test_read_fundamentals_parses_and_normalises_values():
    info = {
        "roe": "15.5%",
        "roa": "0.12",
        "grossMargin": "58%",
        "operatingMargin": None,
        "ebitdaMargin": "nan",
        "revenueGrowth": "12.5%",
        "earningsGrowth": "-0.05",
        "trailingPE": "18.3",
        "forwardPE": "15.7",
        "pb": "4.2",
        "enterpriseToEbitda": "10.5",
        "debtToEquity": "1.5",
        "totalDebt": "1.2B",
        "totalCash": "800M",
        "currentRatio": "1.8",
        "dividendYield": "2.4%",
        "payoutRatio": "45%",
        "beta": 1.1,
        "marketCap": 1_500_000_000,
        "averageVolume": "1.2M",
    }

    fundamentals = read_fundamentals(info)

    assert math.isclose(fundamentals["roe"], 0.155, rel_tol=1e-6)
    assert math.isclose(fundamentals["revenueGrowth"], 0.125, rel_tol=1e-6)
    assert math.isclose(fundamentals["totalDebt"], 1.2e9, rel_tol=1e-6)
    assert math.isclose(fundamentals["totalCash"], 8.0e8, rel_tol=1e-6)
    assert math.isclose(fundamentals["dividendYield"], 0.024, rel_tol=1e-6)
    assert math.isclose(fundamentals["payoutRatio"], 0.45, rel_tol=1e-6)
    assert math.isclose(fundamentals["averageVolume"], 1.2e6, rel_tol=1e-6)
    assert np.isnan(fundamentals["operatingMargin"])
    assert np.isnan(fundamentals["ebitdaMargin"])
 

def test_read_fundamentals_handles_missing_info():
    fundamentals = read_fundamentals(None)

    assert set(fundamentals.keys()) == {
        "roe",
        "roa",
        "grossMargin",
        "operatingMargin",
        "ebitdaMargin",
        "revenueGrowth",
        "earningsGrowth",
        "trailingPE",
        "forwardPE",
        "pb",
        "enterpriseToEbitda",
        "debtToEquity",
        "totalDebt",
        "totalCash",
        "currentRatio",
        "dividendYield",
        "payoutRatio",
        "beta",
        "marketCap",
        "averageVolume",
    }

    assert all(np.isnan(value) for value in fundamentals.values())

