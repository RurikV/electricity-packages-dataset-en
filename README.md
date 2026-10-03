# Electricity Retail Packages — Scraped Dataset (English edition)

Web scraper + dataset + EDA for **household electricity package prices** in a
liberalized retail market, built for the OTUS NLP course homework ("write
your own parser for a site that does not provide an API").

This is the vendor-neutral English edition: all seller names, package names
and textual content are rendered in English, and the collected pages are
included as sanitized local snapshots, so the entire pipeline runs offline.
The original working copy of this project (with live-collection details)
is kept separately.

## Why this dataset

Wholesale (exchange) prices are freely available via public APIs, but **no
public API exists for retail offers** — what sellers actually charge: fixed
contract prices, margins on top of the exchange price, monthly fees. All
price-comparison portals in the market render their tables client-side, and
most large sellers load prices via undocumented XHR calls. The five
retailers below publish offers as plain server-rendered HTML, which is
exactly what a `requests` + `BeautifulSoup` crawler can collect.

| Seller | Snapshot | Notes |
|---|---|---|
| Altra Energy | `mock_sites/altra.html` | 9 package cards |
| Terminal Energy | `mock_sites/terminal.html` | fixed prices per contract term in `data-*` attributes |
| Elm Energy | `mock_sites/elm.html` | 2 packages + long explanatory prose |
| Solarix | `mock_sites/solarix.html` | one zero-margin package, 4 fee tiers |
| VoltEdge | `mock_sites/voltedge.html` | one exchange package |

## Dataset format

`data/packages_clean.csv` — **one row = one purchasable offer variant**
(26 rows; Terminal Energy fixed packages expand into one row per contract
term, Solarix into one row per consumption tier).

| Column | Meaning |
|---|---|
| `seller`, `package_name` | offer identity |
| `package_type` | `fixed` / `exchange` / `hybrid` / `bundle` |
| `green` | renewable energy flag |
| `tariff` | `single` / `double` / `single_or_double` |
| `contract_period`, `period_months` | term; `0` = open-ended |
| `included_kwh_month` | bundle: kWh covered by the monthly fee |
| `price_c_kwh` | fixed energy price, c/kWh |
| `night_price_c_kwh` | night tariff (dual-meter setups) |
| `margin_c_kwh` | seller margin over the exchange spot price |
| `monthly_fee_eur` | fixed monthly fee |
| `buyback_margin_c_kwh` | margin on solar export (prosumers) |
| `reference_spot_c_kwh` | last month's average spot price shown by seller |
| **`cost_per_kwh_c`** | **target variable** — fixed price for fixed packages, margin for exchange/hybrid |
| `description` | cleaned text description (name, terms, features, prose) |
| `url`, `scraped_at` | provenance |

`description` (text) + `cost_per_kwh_c` (target) match the homework's
"object description + target variable" format; the dataset is intended for
later homework (e.g. predicting price-related attributes from text).

## Files

```
scraper.py          crawler: parses the page snapshots (same DOM structure
                    and selector logic as the online crawl; the online
                    variant additionally checks robots.txt and applies a
                    0.3 s delay per request) -> data/raw/packages_raw.json
clean_dataset.py    regex cleaning/normalization -> data/packages_clean.csv
eda.py              statistics + text EDA -> eda/summary.md, eda/*.png
mock_sites/         sanitized page snapshots parsed by the scraper
data/               raw + clean dataset (committed)
eda/                EDA outputs (committed)
```

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scraper.py         # offline crawl over the snapshots
.venv/bin/python clean_dataset.py
.venv/bin/python eda.py
```

## Scraping ethics

* in the online collection variant: `robots.txt` checked per site,
  `time.sleep(0.3)` before every request, ~10 requests total, max 3 retries
  with backoff;
* only public marketing pages, no login, no personal data.

## Key EDA findings

* Fixed prices: 9.8–17.9 c/kWh (median 13.9); exchange margins: 0–0.74
  c/kWh (median 0.40) — sellers monetize either via margin (Elm Energy
  0.67, Terminal Energy 0.54–0.74 + 1.91 €/mo fee) or via fee (Solarix 0
  margin + 3–9 €/mo fee, VoltEdge 0.4 margin + 0 € fee).
* Terminal Energy's fixed-price term structure is U-shaped: 3-month
  cheapest (~9.9), 6-month dearest (~16.9), then falling to ~12.0 at 36
  months; green variants cost a tiny premium (+0.1–0.2 c/kWh).
* Top content words after stopword removal: *price, kwh, margin, fee,
  monthly, months, exchange* — the marketing text is dominated by pricing
  vocabulary.
* Longer descriptions correlate mildly negatively with cost
  (r = −0.39): cheap-margin exchange offers carry longer explainer text.

## Limitations

* Coverage is 5 of roughly 10 retailers in the market; the others render
  prices client-side or do not publish a static price page.
* Prices are a snapshot (offers change frequently); the `scraped_at`
  column records the collection time.
* Terminal Energy's "3-month" variants exist in page data attributes but
  are not shown in the default UI — kept because they are served in the
  HTML.
