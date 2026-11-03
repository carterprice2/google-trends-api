"""Find rising (breakout) searches for several seed keywords in one run: content and product ideas."""
from google_trends_api import GoogleTrends

gt = GoogleTrends()
for item in gt.fetch(["air fryer", "standing desk", "protein powder"], geo="US", timeframe="today 3-m",
                     sections=["relatedQueries"]):
    for kw, rq in (item.get("relatedQueries") or {}).items():
        for r in (rq.get("rising") or [])[:5]:
            print(f"{kw:15} {r['formattedValue']:>10}  {r['query']}")
