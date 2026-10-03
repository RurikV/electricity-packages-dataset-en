#!/usr/bin/env python3
"""
Cleaner: raw scraped records -> tidy dataset (data/packages_clean.csv).

Pipeline stage 2 of 3. Demonstrates the regex-cleaning stage of the
homework:
  * number/unit normalization ("13.4 c/kWh" -> 13.4, "0 €" -> 0.0);
  * removal of UI chrome / navigation junk from free text;
  * keyword-based derivation of package_type, green flag and tariff;
  * parsing of contract terms ("9/12/36 months", "open-ended").

One row = one purchasable offer variant. Terminal Energy fixed packages
expand into one row per contract term; Solarix's exchange package expands
into one row per consumption tier (S/M/L/XL).

Target variable for later ML homeworks:
  cost_per_kwh_cnt -- fixed energy price (c/kWh) for fixed packages,
  seller margin over the exchange price for exchange/hybrid packages.
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone

NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

# phrases that are page chrome, not package information
JUNK_PATTERNS = [
    r"Continue in self-service", r"Detailed package", r"Sign contract",
    r"Request a quote", r"Request quote", r"Read more", r"See details",
    r"Compare", r"Join", r"View terms", r"Sign agreement", r"See the package",
    r"Get a quote", r"Switch in 3 minutes", r"Explore", r"App Store",
    r"Google Play", r"Self-service", r"Private customer", r"Business customer",
]
JUNK_RE = re.compile("|".join(rf"\b{p}\b" for p in JUNK_PATTERNS), re.I)

FIELDS = [
    "seller", "package_name", "package_type", "green", "tariff",
    "contract_period", "period_months", "included_kwh_month",
    "price_c_kwh", "night_price_c_kwh", "margin_c_kwh",
    "monthly_fee_eur", "buyback_margin_c_kwh", "reference_spot_c_kwh",
    "cost_per_kwh_c", "description", "url", "scraped_at",
]


def to_float(value):
    """'13.4 c/kWh' / '1.91 €' / '0 €' -> float or None."""
    if not value:
        return None
    m = NUM_RE.search(str(value).replace(" ", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def clean_free_text(text):
    """Strip UI junk, separators and duplicate punctuation; collapse spaces."""
    text = JUNK_RE.sub(" ", text or "")
    text = text.replace("|", " ").replace("→", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;])", r"\1", text)          # space before punctuation
    text = re.sub(r"([.,;])(?=[^\s\d])", r"\1 ", text)  # space after punctuation
    text = re.sub(r"\.{2,}", ".", text)
    return text.strip(" -–")


def as_sentences(parts):
    """Join text fragments into a single clean description string."""
    sents = []
    for p in parts:
        p = clean_free_text(p).strip()
        if len(p) < 3:
            continue
        p = p[0].upper() + p[1:] if p else p
        sents.append(p.rstrip(".") + ".")
    # de-duplicate while preserving order
    seen, out = set(), []
    for s in sents:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return " ".join(out)


def pick(fields, *labels, **kw):
    """First numeric value among field labels matching any regex."""
    allow_reference = kw.get("reference", False)
    for pat in labels:
        for k, v in fields.items():
            if re.search(pat, k, re.I):
                if not allow_reference and re.search(
                        r"last month|average|volume covered", k, re.I):
                    continue  # reference info / included volume, not a price
                val = to_float(v)
                if val is not None:
                    return k, val
    return None, None


def pick_from_text(text, *patterns):
    """First numeric value captured from free text (e.g. feature bullets)."""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m and m.group(1):
            if m.group(1).lower() == "zero":
                return 0.0
            return float(m.group(1).replace(",", "."))
    return None


def derive_flags(record):
    """Derive green / tariff / contract term from name+features text."""
    fields = record.get("price_fields", {})
    blob = " ".join([record.get("package_name", ""), record.get("subtitle", ""),
                     record.get("badge", ""),
                     " ".join(record.get("features", [])),
                     " ".join(f"{k} {v}" for k, v in fields.items()),
                     record.get("description_raw", "")]).lower()
    green = bool(re.search(r"green|renewable|certified", blob))
    if record.get("badge", "").lower() == "green service":
        green = True
    has_single = bool(re.search(r"single-tariff|single- and dual-tariff", blob))
    has_double = bool(re.search(r"dual-tariff|night price", blob))
    if has_single and has_double:
        tariff = "single_or_double"
    elif has_double:
        tariff = "double"
    else:
        tariff = "single"
    period_str, period_months = "", None
    multi = re.search(r"term:?\s*(\d{1,2}(?:\s*[,/]\s*\d{1,2})+)\s*months", blob)
    ongoing = re.search(r"open-ended", blob)
    single = re.search(r"term[:\s]*(\d{1,2})\s*months", blob) \
        or re.search(r"\bfor\s+(\d{1,2})\s*months\b", blob)
    hyphen = re.search(r"(\d{1,2})-month", blob)
    if multi:
        nums = re.findall(r"\d{1,2}", multi.group(1))
        period_str = "/".join(nums)
        period_months = int(nums[0])
    elif ongoing:
        period_str = "ongoing"
        period_months = 0
    elif single:
        period_str = single.group(1)
        period_months = int(single.group(1))
    elif hyphen:
        period_str = hyphen.group(1)
        period_months = int(hyphen.group(1))
    return green, tariff, period_str, period_months


def pretty_field_label(k):
    """Humanize mangled labels produced by nested card markup."""
    if re.search(r"sellback.*margin", k, re.I):
        return "Buyback margin (grid sellback)"
    return k


def build_rows(record):
    """Expand one raw record into one or more clean dataset rows."""
    fields = record.get("price_fields", {})
    features = record.get("features", [])
    feature_text = " ".join(features)
    green, tariff, period_str, period_months = derive_flags(record)

    desc_pairs = []
    for k, v in fields.items():
        if v and v.strip():
            desc_pairs.append(f"{pretty_field_label(k)}: {v}")
        elif re.search(r"VAT", k, re.I):
            desc_pairs.append("Price includes 24% VAT")
    base_desc = as_sentences(
        [record.get("package_name", "")]
        + ([record["subtitle"]] if record.get("subtitle") else [])
        + features
        + desc_pairs
        + ([record["description_raw"]] if record.get("description_raw") else [])
    )

    def row(**kw):
        r = {f: None for f in FIELDS}
        r.update({
            "seller": record["seller"],
            "package_name": record["package_name"],
            "green": green,
            "tariff": tariff,
            "contract_period": period_str or None,
            "period_months": period_months,
            "url": record["url"],
            "scraped_at": record.get("scraped_at"),
            "description": base_desc,
        })
        r.update(kw)
        return r

    # Terminal Energy fixed packages: one row per contract-term variant
    if record.get("period_variants"):
        out = []
        for months, variant in sorted(record["period_variants"].items(),
                                      key=lambda kv: int(kv[0])):
            price = to_float(variant["price"])
            _, fee = pick(fields, r"^monthly fee$")
            _, buyback = pick(fields, r"sellback.*margin", r"buyback")
            # variant text repeats the price; keep only the prose part
            prose = re.sub(r"^\s*[\d.,]+\s*c/kWh\s*", "", variant["text"])
            desc = as_sentences([base_desc, clean_free_text(prose)])
            out.append(row(
                package_type="fixed",
                period_months=int(months),
                contract_period=f"{months}",
                price_c_kwh=price,
                monthly_fee_eur=fee,
                buyback_margin_c_kwh=buyback,
                cost_per_kwh_c=price,
                description=desc,
            ))
        return out

    # single-offer records; prices stated only in feature bullets
    # (Elm Energy) or in prose ("exchange price + zero margin") are
    # picked from text
    _, price = pick(fields, r"^day price", r"^base price", r"above the volume")
    _, night = pick(fields, r"^night price")
    _, margin = pick(fields, r"^margin")
    _, fee = pick(fields, r"^monthly fee$")
    _, buyback = pick(fields, r"buyback", r"sellback.*margin")
    _, ref_spot = pick(fields, r"last month'?s average", reference=True)
    _, included = pick(fields, r"^volume covered", reference=True)
    included = included if included and included > 10 else None  # "200 kWh"

    if price is None:
        price = pick_from_text(feature_text,
                               r"from\s*(\d+[.,]?\d*)\s*c\s*/\s*kWh")
    if margin is None:
        margin = pick_from_text(feature_text,
                                r"exchange price\s*\+\s*(\d+[.,]\d+)\s*c\s*/\s*kWh",
                                r"exchange price\s*\+\s*(zero|\d+)\s*margin")

    if price is not None and margin is not None:
        ptype = "hybrid"
    elif price is not None:
        ptype = "fixed"
    elif margin is not None:
        ptype = "exchange"
    else:
        ptype = "unknown"

    # bundle package: fixed monthly fee covers N kWh, overage priced per kWh
    if record["seller"] == "Altra Energy" and "Fixed Volume" in record["package_name"]:
        ptype = "bundle"

    target = price if price is not None else margin
    return [row(
        package_type=ptype,
        included_kwh_month=included,
        price_c_kwh=price,
        night_price_c_kwh=night,
        margin_c_kwh=margin,
        monthly_fee_eur=fee,
        buyback_margin_c_kwh=buyback,
        reference_spot_c_kwh=ref_spot,
        cost_per_kwh_c=target,
    )]


def main():
    with open("data/raw/packages_raw.json", encoding="utf-8") as fh:
        raw = json.load(fh)

    scraped_at = raw.get("scraped_at") or \
        datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = [dict(r, scraped_at=scraped_at) for r in raw["records"]]

    rows = []
    for record in records:
        rows.extend(build_rows(record))

    with open("data/packages_clean.csv", "w", encoding="utf-8-sig",
              newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Clean dataset: {len(rows)} rows x {len(FIELDS)} cols "
          f"-> data/packages_clean.csv")
    by_seller = {}
    for r in rows:
        by_seller[r["seller"]] = by_seller.get(r["seller"], 0) + 1
    for s, n in sorted(by_seller.items()):
        print(f"  {s:16s} {n}")
    bad = [r for r in rows if r["cost_per_kwh_c"] is None]
    if bad:
        print(f"  ! {len(bad)} rows without target value: "
              f"{[r['package_name'] for r in bad]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
