import json, pathlib, pytest
import google_trends_api as g

FX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "compare.json").read_text())


class Fake(g.GoogleTrends):
    """Replays the Apify API: start run -> poll once -> dataset items."""
    def __init__(self, items=FX, status="SUCCEEDED"):
        super().__init__("test-token")
        self.items, self.status, self.calls = items, status, []

    def _call(self, method, path, body=None, **params):
        self.calls.append((method, path, body))
        if path.endswith("/runs"):
            return {"data": {"id": "r1", "status": "RUNNING", "defaultDatasetId": "d1"}}
        if path.startswith("/actor-runs/"):
            return {"data": {"id": "r1", "status": self.status, "defaultDatasetId": "d1"}}
        return self.items


def test_fetch_sends_actor_input():
    gt = Fake()
    gt.fetch(["iphone, samsung galaxy"], geo="US", timeframe="today 3-m", sections=["relatedQueries"], property="froogle")
    body = gt.calls[0][2]
    assert gt.calls[0][1] == "/acts/seodatalab~google-trends-scraper/runs"
    assert body == {"searchTerms": ["iphone, samsung galaxy"], "geo": "US", "timeRange": "today 3-m",
                    "sections": ["relatedQueries"], "property": "shopping", "category": 0}


def test_failed_run_and_error_items_raise():
    with pytest.raises(g.TrendsError, match="FAILED"):
        Fake(status="FAILED").fetch(["x"])
    with pytest.raises(g.TrendsError, match="no data"):
        Fake(items=[{"searchTerm": "x", "error": "no data"}]).fetch(["x"])
    assert Fake(items=[{"searchTerm": "x", "error": "no data"}]).fetch(["x"], raise_on_error=False)[0]["error"]


def test_plain_helpers():
    gt = Fake()
    rows = gt.interest_over_time(["iphone", "samsung galaxy"])
    assert set(rows[0]) == {"date", "isPartial", "iphone", "samsung galaxy"}
    assert gt.interest_by_region(["iphone", "samsung galaxy"])[0]["geoName"]
    assert gt.related_queries(["iphone", "samsung galaxy"])["iphone"]["top"][0]["query"]
    with pytest.raises(ValueError):
        gt.interest_over_time(list("abcdef"))


def test_pytrends_compat(monkeypatch):
    pd = pytest.importorskip("pandas")
    fake = Fake()
    monkeypatch.setattr(g, "GoogleTrends", lambda token=None: fake)
    t = g.TrendReq(hl="en-US", tz=360, retries=2, backoff_factor=0.1)
    with pytest.raises(g.TrendsError):
        t.interest_over_time()
    t.build_payload(["iphone", "samsung galaxy"], timeframe="today 3-m", geo="US")
    iot = t.interest_over_time()
    assert list(iot.columns) == ["iphone", "samsung galaxy", "isPartial"]
    assert isinstance(iot.index, pd.DatetimeIndex) and iot.index.name == "date"
    reg = t.interest_by_region()
    assert reg.index.name == "geoName" and "iphone" in reg.columns
    rq = t.related_queries()
    assert list(rq["iphone"]["top"].columns) == ["query", "value"]
    runs = [c for c in fake.calls if c[1].endswith("/runs")]
    assert runs[-1][2]["sections"] == ["interestByRegion", "interestOverTime", "relatedQueries"]
