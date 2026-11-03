// Google Trends API for JavaScript/Node 18+ (no dependencies). Calls the hosted scraper
// seodatalab/google-trends-scraper on Apify, which handles Google's rate limits, retries and proxies.
const API = 'https://api.apify.com/v2';
export const SECTIONS = ['interestOverTime', 'interestByRegion', 'relatedQueries', 'relatedTopics'];

export class TrendsError extends Error {}

export class GoogleTrends {
    constructor({ token = globalThis.process?.env?.APIFY_TOKEN, actor = 'seodatalab~google-trends-scraper', timeoutMs = 900_000 } = {}) {
        if (!token) throw new TrendsError('No Apify token. Create a free account at https://apify.com and pass { token } or set APIFY_TOKEN.');
        Object.assign(this, { token, actor, timeoutMs });
    }

    async #call(method, path, body, params = {}) {
        const qs = new URLSearchParams(params).toString();
        const r = await fetch(`${API}${path}${qs ? `?${qs}` : ''}`, {
            method, body: body === undefined ? undefined : JSON.stringify(body),
            headers: { authorization: `Bearer ${this.token}`, 'content-type': 'application/json' },
        });
        if (!r.ok) throw new TrendsError(`Apify API ${r.status}: ${(await r.text()).slice(0, 300)}`);
        return r.json();
    }

    /** Run one batch; returns one item per search term. Put up to 5 comma-separated terms in one string to compare them. */
    async fetch(searchTerms, { geo = '', timeframe = 'today 12-m', sections = ['interestOverTime'], property = 'web', category = 0, raiseOnError = true, ...extra } = {}) {
        const terms = Array.isArray(searchTerms) ? searchTerms : [searchTerms];
        const bad = sections.filter((s) => !SECTIONS.includes(s));
        if (bad.length) throw new TypeError(`Unknown sections ${bad}. Use any of ${SECTIONS}.`);
        let run = (await this.#call('POST', `/acts/${this.actor}/runs`, { searchTerms: terms, geo, timeRange: timeframe, sections, property, category, ...extra })).data;
        const deadline = Date.now() + this.timeoutMs;
        while (run.status === 'READY' || run.status === 'RUNNING') {
            if (Date.now() > deadline) throw new TrendsError(`Run ${run.id} still running after ${this.timeoutMs / 1000}s.`);
            run = (await this.#call('GET', `/actor-runs/${run.id}`, undefined, { waitForFinish: 60 })).data;
        }
        if (run.status !== 'SUCCEEDED') throw new TrendsError(`Run ${run.id} ended with status ${run.status}. Log: https://console.apify.com/view/runs/${run.id}`);
        const items = await this.#call('GET', `/datasets/${run.defaultDatasetId}/items`, undefined, { clean: 'true', format: 'json' });
        const errors = items.filter((i) => i.error);
        if (errors.length && raiseOnError) throw new TrendsError(errors.map((i) => `${i.searchTerm}: ${i.error}`).join('; '));
        return items;
    }

    async interestOverTime(keywords, opts = {}) {
        const [item] = await this.fetch([join(keywords)], opts);
        return item.interestOverTime.map((p) => ({ date: p.date, isPartial: !!p.isPartial, ...p.values }));
    }

    async interestByRegion(keywords, opts = {}) {
        const [item] = await this.fetch([join(keywords)], { ...opts, sections: ['interestOverTime', 'interestByRegion'] });
        return (item.interestByRegion ?? []).map((r) => ({ geoCode: r.geoCode, geoName: r.geoName, ...r.values }));
    }

    async relatedQueries(keywords, opts = {}) {
        const [item] = await this.fetch([join(keywords)], { ...opts, sections: ['interestOverTime', 'relatedQueries'] });
        return item.relatedQueries ?? {};
    }
}

function join(keywords) {
    const kws = Array.isArray(keywords) ? keywords : [keywords];
    if (kws.length < 1 || kws.length > 5) throw new TypeError('Google Trends compares 1 to 5 keywords at a time.');
    return kws.join(', ');
}
