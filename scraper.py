#!/usr/bin/env python3
"""
Scraper: household electricity retail packages (sanitized English edition).

Pipeline stage 1 of 3: crawl the retailer pages and extract semi-structured
package records -> data/raw/packages_raw.json.

This edition parses sanitized English snapshots of the retailers' package
pages (mock_sites/*.html) so that the whole pipeline runs offline and the
material is vendor-neutral: seller names and all textual content are
rendered in English. The snapshots preserve the exact DOM structure of the
original pages, so the parsing logic below (CSS selectors + regexes) is the
same that collected the live data. In the online collection variant each
fetch is preceded by a robots.txt check and a time.sleep(0.3) rate limit;
the delay is kept here as well so the crawler stays polite by construction.

Sellers covered (5 of ~10 retailers in the market; the rest render their
prices client-side and offer no static HTML to parse, and no public API
exists for retail offers):
  Altra Energy    9 package cards
  Terminal Energy fixed prices per contract term in data-* attributes
  Elm Energy      2 packages with long explanatory prose
  Solarix         one zero-margin package with 4 monthly-fee tiers
  VoltEdge        one exchange package
"""

import html
import json
import re
import sys
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup

REQUEST_DELAY = 0.3  # seconds between "requests" (kept from the online run)

SITES = {
    "Altra Energy": ("mock_sites/altra.html",
                     "https://example.test/altra-energy/electricity"),
    "Terminal Energy": ("mock_sites/terminal.html",
                        "https://example.test/terminal-energy/electricity"),
    "Elm Energy": ("mock_sites/elm.html",
                   "https://example.test/elm-energy/electricity"),
    "Solarix": ("mock_sites/solarix.html",
                "https://example.test/solarix/electricity"),
    "VoltEdge": ("mock_sites/voltedge.html",
                 "https://example.test/voltedge"),
}

# UI chrome that leaks into page text and must not reach the dataset
JUNK_SENTENCES = [
    "Sign contract", "Request a quote", "Request quote", "Read more",
    "See details", "Compare", "Join", "View terms", "Continue in self-service",
    "Detailed package", "Sign agreement", "See the package", "Get a quote",
    "Switch in 3 minutes", "Explore", "App Store", "Google Play",
    "Self-service", "Private customer", "Business customer",
]


def sleep_politely():
    """Rate limiting between page fetches (course requirement)."""
    time.sleep(REQUEST_DELAY)


def fetch(snapshot_path):
    """Load a sanitized page snapshot (offline replay of the crawl)."""
    with open(snapshot_path, encoding="utf-8") as fh:
        return fh.read()


def clean_text(s):
    """Collapse whitespace, strip UI junk phrases. Keeps sentence periods."""
    s = re.sub(r"\s+", " ", s or "").strip()
    for junk in JUNK_SENTENCES:
        s = re.sub(rf"(?i)\b{re.escape(junk)}\b", " ", s)
    return re.sub(r"\s+", " ", s).strip(" -–")


# ----------------------------------------------------------- Altra Energy --

def parse_altra(html_text, url):
    """Package cards: .package-cards__card with title, features and
    label/value price rows in .package-cards__info."""
    soup = BeautifulSoup(html_text, "html.parser")
    records = []
    for card in soup.select(".package-cards__card"):
        title = card.select_one(".package-cards__title")
        if not title:
            continue
        record = {
            "seller": "Altra Energy",
            "url": url,
            "package_name": clean_text(title.get_text(" ", strip=True)),
            "subtitle": clean_text(card.select_one(".package-cards__subtitle").get_text(" ", strip=True))
            if card.select_one(".package-cards__subtitle") else "",
            "badge": clean_text(card.select_one(".package-cards__badge").get_text(" ", strip=True))
            if card.select_one(".package-cards__badge") else "",
            "features": [clean_text(li.get_text(" ", strip=True))
                         for li in card.select("ul.ul--custom li")],
            "price_fields": {},
            "description_raw": "",
        }
        for info in card.select(".package-cards__info"):
            spans = info.find_all("span", recursive=False)
            if len(spans) >= 2:
                label = clean_text(spans[0].get_text(" ", strip=True))
                value = clean_text(spans[-1].get_text(" ", strip=True))
                if label and value:
                    record["price_fields"][label] = value
        records.append(record)
        print(f"  + {record['package_name']} ({len(record['price_fields'])} price fields)")
    return records


# ------------------------------------------------------- Terminal Energy --

def parse_terminal(html_text, url):
    """Package columns .p-epackages_switcher__col. Fixed-price columns carry
    per-term price HTML in data-3/6/12/36months attributes; exchange columns
    carry Margin/Monthly fee as .__col-contract-item pairs."""
    soup = BeautifulSoup(html_text, "html.parser")
    records = []
    for col in soup.select(".p-epackages_switcher__col"):
        title = col.select_one(".p-epackages_switcher__col-title")
        if not title:
            continue
        green_badge = col.select_one(".p-epackages_switcher__col-title .green")
        record = {
            "seller": "Terminal Energy",
            "url": url,
            "package_name": clean_text(title.get_text(" ", strip=True)),
            "subtitle": "",
            "badge": clean_text(green_badge.get_text(" ", strip=True)) if green_badge else "",
            "features": [clean_text(t.get_text(" ", strip=True))
                         for t in col.select(".p-epackages_switcher__col-tariff")
                         + col.select(".p-epackages_switcher__col-period")],
            "price_fields": {},
            "period_variants": {},
            "description_raw": "",
        }

        # exchange packages: label/price contract items (Margin, fee...)
        for item in col.select(".p-epackages_switcher__col-contract-item"):
            lab = item.select_one(".p-epackages_switcher__col-contract-label")
            pri = item.select_one(".p-epackages_switcher__col-contract-price")
            if lab and pri:
                record["price_fields"][clean_text(lab.get_text(" ", strip=True))] = \
                    clean_text(pri.get_text(" ", strip=True))

        # producer (solar sellback) items -> kept as text evidence
        for item in col.select(".p-epackages_switcher__col-producer-item"):
            lab = item.select_one(".p-epackages_switcher__col-producer-label")
            pri = item.select_one(".p-epackages_switcher__col-producer-price")
            if lab and pri:
                record["price_fields"][clean_text(lab.get_text(" ", strip=True))] = \
                    clean_text(pri.get_text(" ", strip=True))

        # fixed packages: price per contract term in data-attributes
        content = col.select_one(".p-epackages_switcher__col-content.period-content")
        if content:
            for attr, label in [("data-3months", "3"), ("data-6months", "6"),
                                ("data-12months", "12"), ("data-36months", "36")]:
                raw = content.get(attr)
                if not raw:
                    continue
                inner = BeautifulSoup(html.unescape(raw), "html.parser")
                price_el = inner.select_one(".content-title")
                record["period_variants"][label] = {
                    "price": clean_text(price_el.get_text()) if price_el else "",
                    "text": clean_text(inner.get_text(" ", strip=True)),
                }

        # descriptive text: any non-period content block
        desc_parts = []
        extra = col.select_one(".p-epackages_switcher__col-additional-info")
        if extra:
            desc_parts.append(extra.get_text(" ", strip=True))
        for block in col.select(".p-epackages_switcher__col-content"):
            if "period-content" not in (block.get("class") or []):
                desc_parts.append(block.get_text(" ", strip=True))
        record["description_raw"] = clean_text(" ".join(desc_parts))

        records.append(record)
        print(f"  + {record['package_name']} "
              f"(variants: {list(record['period_variants']) or '-'}, "
              f"fields: {list(record['price_fields']) or '-'})")
    return records


# ------------------------------------------------------------- Elm Energy --

def parse_elm(html_text, url):
    """Content blocks .c-columns__item, one per package. First <ul> holds the
    price terms, the rest of the block is descriptive prose."""
    soup = BeautifulSoup(html_text, "html.parser")
    records = []
    for item in soup.select(".c-columns__item"):
        heading = None
        for h in item.find_all("h3"):
            if "package" in h.get_text(strip=True).lower():
                heading = h
                break
        if heading is None:
            continue
        record = {
            "seller": "Elm Energy",
            "url": url,
            "package_name": clean_text(heading.get_text(" ", strip=True)),
            "subtitle": "",
            "badge": "",
            "features": [],
            "price_fields": {},
            "description_raw": "",
        }
        first_ul = item.find("ul")
        if first_ul:
            for li in first_ul.find_all("li"):
                record["features"].append(clean_text(li.get_text(" ", strip=True)))

        # descriptive prose: paragraphs and later lists, skipping buttons
        desc_parts = []
        for p in item.find_all("p"):
            if p.find("a") and not clean_text(p.get_text(" ", strip=True)).replace(
                    clean_text(p.a.get_text(" ", strip=True)), "").strip():
                continue  # button paragraph
            txt = clean_text(p.get_text(" ", strip=True))
            if len(txt) > 40:
                desc_parts.append(txt)
        for ul in item.find_all("ul"):
            if ul is first_ul:
                continue
            for li in ul.find_all("li"):
                txt = clean_text(li.get_text(" ", strip=True))
                if len(txt) > 25:
                    desc_parts.append(txt)
        record["description_raw"] = clean_text(" ".join(desc_parts))
        records.append(record)
        print(f"  + {record['package_name']} ({len(record['features'])} terms)")
    return records


# --------------------------------------------------------------- Solarix --

def parse_solarix(html_text, url):
    """One exchange package with consumption-based monthly-fee tiers
    (S/M/L/XL) -- one record per tier."""
    soup = BeautifulSoup(html_text, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    title = soup.title.get_text() if soup.title else ""
    name = clean_text(title.split("|", 1)[-1]) if "|" in title else "Solarix exchange package"

    tiers = re.findall(r"\b(XL|[SML])\s*/\s*([^\s][^.]*?kWh)\s*(\d+)\s*€", text)
    margin = re.search(r"Margin\s*(\d+)\s*€", text)
    buyback = re.search(r"Buyback margin\s*([\d.]+)\s*c/kWh", text)
    period = re.search(r"Contract term\s+(\S+)", text)

    # sentences describing the package (for the text side of the dataset)
    desc_parts = []
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        desc_parts.append(clean_text(meta["content"]))
    for pat in [r"The monthly fee depends[^.]*\.",
                r"Selling back happens[^.]*\.",
                r"How is the package[^?]*\?"]:
        m = re.search(pat, text)
        if m:
            desc_parts.append(clean_text(m.group(0)))

    records = []
    seen = set()
    for tier, volume, fee in tiers:
        if tier in seen:
            continue
        seen.add(tier)
        record = {
            "seller": "Solarix",
            "url": url,
            "package_name": f"{name} — tier {tier}",
            "subtitle": f"Annual consumption {clean_text(volume)}",
            "badge": "",
            "features": [
                f"Margin {margin.group(1)}€" if margin else "Zero margin",
                f"Buyback margin {buyback.group(1)} c/kWh" if buyback else "",
                f"Contract term {period.group(1)}" if period else "",
                f"Monthly fee tier {tier}: {volume} -> {fee} €/month",
            ],
            "price_fields": {
                "Monthly fee": f"{fee} €",
                **({"Margin": f"{margin.group(1)} c/kWh"} if margin else {}),
                **({"Buyback margin": f"{buyback.group(1)} c/kWh"} if buyback else {}),
            },
            "description_raw": clean_text(" ".join(desc_parts)),
        }
        records.append(record)
        print(f"  + {record['package_name']} ({fee} €/month)")
    return records


# --------------------------------------------------------------- VoltEdge --

def parse_voltedge(html_text, url):
    """A single 'Golden Electricity Package' offer with import/export
    margins and a 0 EUR monthly fee."""
    soup = BeautifulSoup(html_text, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    import_m = re.search(r"Import margin\s*([\d.]+)\s*c/kWh(?:\s*([\d.]+)\s*c/kWh\s*\+ VAT)?", text)
    export_m = re.search(r"Export margin\s*([\d.]+)\s*c/kWh", text)
    fee_m = re.search(r"Monthly fee\s*([\d.]+)\s*€", text)

    desc_parts = []
    for pat in [r"[^.]*Golden Electricity Package[^.]*\.",
                r"[^.]*spot-priced power[^.]*\.",
                r"[^.]*cheapest package on the market[^.]*\."]:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        s = clean_text(m.group(0))
        # skip navigation/CTA fragments and the B2B variant sentence
        if ("→" in s or s.startswith("Explore") or "Businesses can" in s
                or "App Store" in s or "Google Play" in s):
            continue
        desc_parts.append(s)

    record = {
        "seller": "VoltEdge",
        "url": url,
        "package_name": "Golden Electricity Package",
        "subtitle": "Power exchange spot price + one transparent margin",
        "badge": "",
        "features": [
            f"Import margin {import_m.group(1)} c/kWh"
            + (f" ({import_m.group(2)} c/kWh + VAT)" if import_m.group(2) else ""),
            f"Export margin {export_m.group(1)} c/kWh" if export_m else "",
            f"Monthly fee {fee_m.group(1)} €" if fee_m else "",
        ],
        "price_fields": {
            **({"Margin": f"{import_m.group(1)} c/kWh"} if import_m else {}),
            **({"Buyback margin": f"{export_m.group(1)} c/kWh"} if export_m else {}),
            **({"Monthly fee": f"{fee_m.group(1)} €"} if fee_m else {}),
        },
        "description_raw": clean_text(" ".join(desc_parts)),
    }
    print(f"  + {record['package_name']}")
    return [record]


PARSERS = {
    "Altra Energy": parse_altra,
    "Terminal Energy": parse_terminal,
    "Elm Energy": parse_elm,
    "Solarix": parse_solarix,
    "VoltEdge": parse_voltedge,
}


def main():
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    all_records = []
    for seller, (snapshot, url) in SITES.items():
        print(f"\n=== {seller}: {url}")
        sleep_politely()
        records = PARSERS[seller](fetch(snapshot), url)
        if not records:
            print("  ! parser found no packages -- page layout changed?")
        all_records.extend(records)

    out = {
        "dataset": "electricity-retail-packages",
        "description": "Household electricity package offers collected from "
                       "retailer websites (no public API exists).",
        "scraped_at": scraped_at,
        "sources": {s: url for s, (_, url) in SITES.items()},
        "records": all_records,
    }
    path = "data/raw/packages_raw.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_records)} raw package records -> {path}")
    return 0 if all_records else 1


if __name__ == "__main__":
    sys.exit(main())
