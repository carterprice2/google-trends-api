"""Compare up to 5 keywords and print which one is growing fastest over the last 3 months."""
from google_trends_api import GoogleTrends

gt = GoogleTrends()
rows = gt.interest_over_time(["chatgpt", "gemini", "claude"], geo="US", timeframe="today 3-m")
first, last = rows[0], rows[-2]  # the last point is usually partial
for kw in ("chatgpt", "gemini", "claude"):
    print(f"{kw:10} {first[kw]:>3} -> {last[kw]:>3}")
