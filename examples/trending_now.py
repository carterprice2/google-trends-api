"""Google's trending searches right now (pip install apify-client; export APIFY_TOKEN=...)."""
import os
from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_TOKEN"])
run = client.actor("seodatalab/google-trending-now").call(
    run_input={"geos": ["US"], "timeWindow": "24h", "sortBy": "searchVolume",
               "maxItemsPerLocation": 6})
for t in client.dataset(run.default_dataset_id).iterate_items():
    print(f'{t["rank"]}. {t["title"][:28]:<28} {t["searchVolume"]:>10,}+  +{t["increasePercent"]}%')
