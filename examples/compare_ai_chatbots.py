from google_trends_api import TrendReq
pytrends = TrendReq()
pytrends.build_payload(["chatgpt", "gemini", "claude"], timeframe="today 3-m", geo="US")
print(pytrends.interest_over_time().tail(5))
