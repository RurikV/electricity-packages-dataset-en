#!/usr/bin/env python3
"""
EDA for the electricity-package dataset.

Pipeline stage 3 of 3.

Numeric side:  offer counts by seller/type, cost-per-kWh distribution,
monthly fees, the fixed-price term structure (price vs contract length).
Text side:     tokenization, stopword filtering, word frequencies overall
               and per package type, description length stats,
               length-vs-cost correlation.

Outputs: eda/*.png charts and eda/summary.md with all statistics.
"""

import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TOKEN_RE = re.compile(r"[a-z]+")

# grammatical/function words only -- domain words (price, margin, exchange,
# fixed, monthly...) are the signal and stay in the corpus
STOPWORDS = set("""
the a an is are was were be been being for with and or to of on in at by from
as if it its this that these those you your yours our ours we they them their
there here when where why how what which who whom whose not no nor but so than
then too very can will just should now do does did doing have has had having
i me my myself he him his she her hers ourselves themselves itself each other
more most some any all both few own same s t don ll re ve d m o y ain aren
couldn didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn wasn
weren won wouldn also only per each one two based directly
""".split())


def tokenize(text):
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS
            and len(t) > 1]


def main():
    df = pd.read_csv("data/packages_clean.csv", encoding="utf-8-sig")
    df["desc_len_chars"] = df["description"].str.len()
    df["desc_len_words"] = df["description"].str.split().str.len()
    df["tokens"] = df["description"].map(tokenize)
    out = []

    def emit(line=""):
        print(line)
        out.append(line)

    # ------------------------------------------------------------ numbers --
    emit("# EDA — electricity retail packages")
    emit()
    emit(f"Rows: {len(df)}  |  sellers: {df['seller'].nunique()}  |  "
         f"collected: {df['scraped_at'].iloc[0]}")
    emit()

    emit("## Offers by seller and package type")
    emit("```")
    emit(pd.crosstab(df["seller"], df["package_type"]).to_string())
    emit("```")
    emit()

    fixed = df[df["package_type"] == "fixed"]
    exch = df[df["package_type"] == "exchange"]
    emit("## Fixed-package energy price, c/kWh (incl. VAT where stated)")
    emit("```")
    emit(fixed["cost_per_kwh_c"].describe().to_string())
    emit("```")
    emit()
    emit("## Exchange-package margin over spot, c/kWh")
    emit("```")
    emit(exch["cost_per_kwh_c"].describe().to_string())
    emit("```")
    emit()

    emit("## Monthly fee, EUR")
    emit("```")
    emit(df["monthly_fee_eur"].describe().to_string())
    emit("```")
    emit()

    emit("## Mean cost by seller")
    emit("```")
    g = df.groupby(["seller", "package_type"])["cost_per_kwh_c"] \
          .agg(["count", "mean", "min", "max"])
    emit(g.round(3).to_string())
    emit("```")
    emit()

    term = fixed[fixed["seller"] == "Terminal Energy"] \
        .sort_values("period_months")
    emit("## Fixed-price term structure (Terminal Energy, c/kWh by months)")
    emit("```")
    emit(term[["period_months", "cost_per_kwh_c", "green"]]
        .to_string(index=False))
    emit("```")
    emit()

    # --------------------------------------------------------------- text --
    emit("## Text statistics")
    emit("```")
    emit(df[["desc_len_chars", "desc_len_words"]].describe().to_string())
    emit("```")
    emit()

    all_tokens = [t for toks in df["tokens"] for t in toks]
    vocab = Counter(all_tokens)
    emit(f"Total tokens: {len(all_tokens)}  |  vocabulary: {len(vocab)}  |  "
         f"tokens/row: {len(all_tokens)/len(df):.0f}")
    emit()

    top = vocab.most_common(25)
    emit("## Top-25 words (stopwords removed)")
    emit("```")
    for w, c in top:
        emit(f"{w:20s} {c:3d} {'#' * c}")
    emit("```")
    emit()

    emit("## Top-12 words per package type")
    emit("```")
    for ptype, grp in df.groupby("package_type"):
        cnt = Counter(t for toks in grp["tokens"] for t in toks)
        words = ", ".join(f"{w}({c})" for w, c in cnt.most_common(12))
        emit(f"{ptype:10s} {words}")
    emit("```")
    emit()

    corr = df["desc_len_words"].corr(df["cost_per_kwh_c"])
    emit(f"Pearson r (description length vs cost): {corr:.3f}")
    emit()

    with open("eda/summary.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    # -------------------------------------------------------------- charts --
    plt.figure(figsize=(8, 4.5))
    labels = (df["seller"] + "\n" + df["package_type"])
    plt.bar(range(len(df)), df["cost_per_kwh_c"],
            color=["#4c78a8" if t == "fixed" else "#f58518" if t == "exchange"
                   else "#54a24b" if t == "hybrid" else "#b279a2"
                   for t in df["package_type"]])
    plt.xticks(range(len(df)), labels, rotation=90, fontsize=6)
    plt.ylabel("c/kWh (fixed price or margin)")
    plt.title("Cost per kWh by offer — fixed prices vs exchange margins")
    plt.tight_layout()
    plt.savefig("eda/cost_by_offer.png", dpi=150)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    axes[0].hist(fixed["cost_per_kwh_c"], bins=8, color="#4c78a8")
    axes[0].set_title("Fixed price, c/kWh")
    axes[1].hist(exch["cost_per_kwh_c"], bins=8, color="#f58518")
    axes[1].set_title("Exchange margin, c/kWh")
    for ax in axes:
        ax.set_ylabel("offers")
    plt.tight_layout()
    plt.savefig("eda/cost_histograms.png", dpi=150)
    plt.close()

    plt.figure(figsize=(6, 3.5))
    for green, grp in term.groupby("green"):
        plt.plot(grp["period_months"], grp["cost_per_kwh_c"], "o-",
                 label="green" if green else "regular")
    plt.xlabel("contract length, months")
    plt.ylabel("c/kWh")
    plt.title("Fixed price term structure (Terminal Energy)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("eda/term_structure.png", dpi=150)
    plt.close()

    words, counts = zip(*vocab.most_common(25))
    plt.figure(figsize=(6, 7))
    plt.barh(range(len(words)), counts, color="#4c78a8")
    plt.yticks(range(len(words)), words)
    plt.gca().invert_yaxis()
    plt.xlabel("frequency")
    plt.title("Top-25 words in package descriptions")
    plt.tight_layout()
    plt.savefig("eda/top_words.png", dpi=150)
    plt.close()

    print("\nSaved: eda/summary.md, eda/cost_by_offer.png, "
          "eda/cost_histograms.png, eda/term_structure.png, eda/top_words.png")


if __name__ == "__main__":
    main()
