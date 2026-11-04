"""Google Trends API client for Python: a maintained alternative to pytrends.

Google Trends has no public API, and pytrends (the popular unofficial library) was archived in 2025.
This client calls a hosted scraper on Apify (seodatalab/google-trends-scraper) that handles Google's
rate limits, retries and proxies for you. You need a free Apify account and an API token.

    from google_trends_api import GoogleTrends
    gt = GoogleTrends()                       # reads APIFY_TOKEN from the environment
    rows = gt.fetch(["iphone, samsung galaxy"], geo="US", sections=["relatedQueries"])

Or, for code written against pytrends:

    from google_trends_api import TrendReq    # instead of: from pytrends.request import TrendReq
    pytrends = TrendReq()
    pytrends.build_payload(["iphone", "samsung galaxy"], timeframe="today 3-m", geo="US")
    df = pytrends.interest_over_time()
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

__version__ = "0.1.0"
__all__ = ["GoogleTrends", "TrendReq", "TrendsError"]

ACTOR_ID = "seodatalab~google-trends-scraper"
API = "https://api.apify.com/v2"
SECTIONS = ("interestOverTime", "interestByRegion", "relatedQueries", "relatedTopics")
_GPROP = {"": "web", "web": "web", "images": "images", "news": "news", "youtube": "youtube",
          "froogle": "shopping", "shopping": "shopping"}


class TrendsError(RuntimeError):
    """The run failed, or Google returned no data for a query."""


class GoogleTrends:
    """Thin client for the hosted Google Trends scraper. No dependencies beyond the standard library."""

    def __init__(self, token: str | None = None, *, actor: str = ACTOR_ID, timeout: int = 900,
                 user_agent: str = f"google-trends-api-python/{__version__}"):
        self.token = token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
        if not self.token:
            raise TrendsError("No Apify token. Create a free account at https://apify.com?fpr=fi898m, copy the token from "
                              "Settings > API & Integrations, and set APIFY_TOKEN or pass token=...")
        self.actor = actor
        self.timeout = timeout
        self.user_agent = user_agent

    # ---------- HTTP ----------
    def _call(self, method: str, path: str, body: Any = None, **params: Any) -> Any:
        url = f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise TrendsError(f"Apify API {e.code}: {e.read().decode(errors='replace')[:300]}") from None

    # ---------- core ----------
    def fetch(self, search_terms: Iterable[str] | str, *, geo: str = "", timeframe: str = "today 12-m",
              sections: Iterable[str] = ("interestOverTime",), property: str = "web", category: int = 0,
              raise_on_error: bool = True, **extra: Any) -> list[dict]:
        """Run one batch and return the raw items (one per search term).

        search_terms: list of queries. Put up to 5 comma-separated terms in one string to compare them on one
        chart, e.g. "iphone, samsung galaxy". Many queries in one call are cheaper than many calls.
        timeframe: "now 1-H", "now 4-H", "now 1-d", "now 7-d", "today 1-m", "today 3-m", "today 12-m",
        "today 5-y", "all", or "YYYY-MM-DD YYYY-MM-DD".
        """
        terms = [search_terms] if isinstance(search_terms, str) else list(search_terms)
        bad = [s for s in sections if s not in SECTIONS]
        if bad:
            raise ValueError(f"Unknown sections {bad}. Use any of {SECTIONS}.")
        payload = {"searchTerms": terms, "geo": geo, "timeRange": timeframe, "sections": list(sections),
                   "property": _GPROP.get(property, property), "category": int(category), **extra}
        run = self._call("POST", f"/acts/{self.actor}/runs", payload)["data"]
        deadline = time.time() + self.timeout
        while run["status"] in ("READY", "RUNNING"):
            if time.time() > deadline:
                raise TrendsError(f"Run {run['id']} still running after {self.timeout}s.")
            run = self._call("GET", f"/actor-runs/{run['id']}", waitForFinish=60)["data"]
        if run["status"] != "SUCCEEDED":
            raise TrendsError(f"Run {run['id']} ended with status {run['status']}. "
                              f"Log: https://console.apify.com/view/runs/{run['id']}")
        items = self._call("GET", f"/datasets/{run['defaultDatasetId']}/items", clean="true", format="json")
        errors = [i for i in items if i.get("error")]
        if errors and raise_on_error:
            raise TrendsError("; ".join(f"{i.get('searchTerm')}: {i['error']}" for i in errors))
        return items

    # ---------- convenience (plain Python, no pandas needed) ----------
    def interest_over_time(self, keywords: list[str] | str, **kw: Any) -> list[dict]:
        """One row per date: {"date", "isPartial", <keyword>: value, ...}. Up to 5 keywords are compared."""
        item = self.fetch([_join(keywords)], **kw)[0]
        return [{"date": p["date"], "isPartial": p.get("isPartial", False), **p["values"]} for p in item["interestOverTime"]]

    def interest_by_region(self, keywords: list[str] | str, **kw: Any) -> list[dict]:
        item = self.fetch([_join(keywords)], sections=["interestOverTime", "interestByRegion"], **kw)[0]
        return [{"geoCode": r["geoCode"], "geoName": r["geoName"], **r["values"]} for r in item.get("interestByRegion") or []]

    def related_queries(self, keywords: list[str] | str, **kw: Any) -> dict:
        """{keyword: {"top": [{"query", "value"}], "rising": [...]}}"""
        item = self.fetch([_join(keywords)], sections=["interestOverTime", "relatedQueries"], **kw)[0]
        return item.get("relatedQueries") or {}


def _join(keywords: list[str] | str) -> str:
    kws = [keywords] if isinstance(keywords, str) else list(keywords)
    if not 1 <= len(kws) <= 5:
        raise ValueError("Google Trends compares 1 to 5 keywords at a time.")
    return ", ".join(kws)


class TrendReq:
    """pytrends-compatible interface. Returns pandas DataFrames shaped like pytrends' output.

    Supported: build_payload, interest_over_time, interest_by_region, related_queries.
    Constructor arguments pytrends used for its own HTTP session (hl, tz, retries, proxies, timeout...) are
    accepted and ignored: retries and proxies are handled server side.
    """

    def __init__(self, hl: str = "en-US", tz: int = 360, *args: Any, token: str | None = None, **kwargs: Any):
        self._gt = GoogleTrends(token)
        self._payload: dict | None = None
        self._item: dict | None = None
        self._have: set[str] = set()

    def build_payload(self, kw_list: list[str], cat: int = 0, timeframe: str = "today 5-y", geo: str = "",
                      gprop: str = "") -> None:
        self._payload = {"keywords": _join(kw_list), "category": cat, "timeframe": timeframe, "geo": geo,
                         "property": _GPROP.get(gprop, "web")}
        self._item, self._have = None, set()

    def _get(self, section: str) -> dict:
        if self._payload is None:
            raise TrendsError("Call build_payload(kw_list, ...) first.")
        if self._item is None or section not in self._have:
            want = {"interestOverTime", section} | self._have
            p = self._payload
            self._item = self._gt.fetch([p["keywords"]], geo=p["geo"], timeframe=p["timeframe"], sections=sorted(want),
                                        property=p["property"], category=p["category"])[0]
            self._have = want
        return self._item

    def interest_over_time(self):
        pd = _pandas()
        pts = self._get("interestOverTime").get("interestOverTime") or []
        if not pts:
            return pd.DataFrame()
        df = pd.DataFrame([{**p["values"], "isPartial": bool(p.get("isPartial"))} for p in pts],
                          index=pd.to_datetime([p["date"] for p in pts]).tz_localize(None))
        df.index.name = "date"
        return df

    def interest_by_region(self, resolution: str = "COUNTRY", inc_low_vol: bool = False, inc_geo_code: bool = False):
        pd = _pandas()
        rows = self._get("interestByRegion").get("interestByRegion") or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([{"geoName": r["geoName"], **({"geoCode": r["geoCode"]} if inc_geo_code else {}), **r["values"]}
                           for r in rows]).set_index("geoName")
        return df

    def related_queries(self) -> dict:
        pd = _pandas()
        rq = self._get("relatedQueries").get("relatedQueries") or {}
        out = {}
        for kw in self._payload["keywords"].split(", "):
            sec = rq.get(kw) or {}
            out[kw] = {k: (pd.DataFrame([{"query": r["query"], "value": r["value"]} for r in sec[k]]) if sec.get(k) else None)
                       for k in ("top", "rising")}
        return out


def _pandas():
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        raise TrendsError("TrendReq returns pandas DataFrames: pip install pandas (or use GoogleTrends for plain dicts).") from None
    return pd
