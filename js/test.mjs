import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GoogleTrends, TrendsError } from './index.mjs';

const FX = JSON.parse(readFileSync(new URL('../tests/fixtures/compare.json', import.meta.url)));
const fakeFetch = (items = FX, status = 'SUCCEEDED', calls = []) => async (url, init) => {
    calls.push({ url, body: init.body && JSON.parse(init.body) });
    const json = url.includes('/runs?') || url.endsWith('/runs') ? { data: { id: 'r1', status: 'RUNNING', defaultDatasetId: 'd1' } }
        : url.includes('/actor-runs/') ? { data: { id: 'r1', status, defaultDatasetId: 'd1' } } : items;
    return { ok: true, status: 200, json: async () => json, text: async () => '' };
};

test('helpers shape rows and send the actor input', async () => {
    const calls = [];
    globalThis.fetch = fakeFetch(FX, 'SUCCEEDED', calls);
    const gt = new GoogleTrends({ token: 't' });
    const rows = await gt.interestOverTime(['iphone', 'samsung galaxy'], { geo: 'US', timeframe: 'today 3-m' });
    assert.deepEqual(Object.keys(rows[0]).sort(), ['date', 'iphone', 'isPartial', 'samsung galaxy']);
    assert.equal(calls[0].body.searchTerms[0], 'iphone, samsung galaxy');
    assert.equal(calls[0].body.timeRange, 'today 3-m');
    assert.ok((await gt.interestByRegion(['iphone']))[0].geoName);
    assert.ok((await gt.relatedQueries(['iphone'])).iphone.top.length);
});

test('failures raise', async () => {
    globalThis.fetch = fakeFetch(FX, 'FAILED');
    await assert.rejects(new GoogleTrends({ token: 't' }).fetch(['x']), TrendsError);
    globalThis.fetch = fakeFetch([{ searchTerm: 'x', error: 'no data' }]);
    await assert.rejects(new GoogleTrends({ token: 't' }).fetch(['x']), /no data/);
    assert.throws(() => new GoogleTrends({ token: '' }), TrendsError);
});
