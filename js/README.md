# gtrends-client

Google Trends for Node 18+ (no dependencies): interest over time, by region, related queries and topics. It calls the hosted [Google Trends Scraper on Apify](https://apify.com/seodatalab/google-trends-scraper?fpr=fi898m), which handles Google's rate limits and proxies.

```js
import { GoogleTrends } from 'gtrends-client';
const trends = new GoogleTrends({ token: process.env.APIFY_TOKEN });
```

Full docs and the Python client (`pip install pytrends-alt`): https://github.com/carterprice2/google-trends-api

*Disclosure: the maintainer also publishes the scraper. Links to apify.com include a referral code; it doesn't change your price.*
