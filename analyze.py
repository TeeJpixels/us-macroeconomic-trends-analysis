"""Reproducible exploratory analysis of the U.S. macrodata dataset."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "us_macrodata.csv"
OUT = ROOT / "outputs"
DB = OUT / "us_macrodata.sqlite"

REQUIRED = {
    "year", "quarter", "realgdp", "realcons", "realinv", "realgovt",
    "realdpi", "cpi", "m1", "tbilrate", "unemp", "pop", "infl", "realint"
}


def load_and_clean() -> pd.DataFrame:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing dataset: {RAW}")
    df = pd.read_csv(RAW)
    missing_cols = REQUIRED.difference(df.columns)
    if missing_cols:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing_cols)}")

    df = df.copy()
    for col in REQUIRED:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["year", "quarter", "realgdp", "cpi", "unemp", "infl"])
    df["year"] = df["year"].astype(int)
    df["quarter"] = df["quarter"].astype(int)
    if not df["quarter"].between(1, 4).all():
        raise ValueError("Quarter values must be between 1 and 4")

    df["period"] = (df["year"].astype(str) + "Q" + df["quarter"].astype(str))
    df["date"] = pd.PeriodIndex(df["period"], freq="Q-DEC").to_timestamp(how="end").normalize()
    df = df.sort_values("date").drop_duplicates(subset=["period"]).reset_index(drop=True)
    df["gdp_qoq_pct"] = df["realgdp"].pct_change() * 100
    df["gdp_yoy_pct"] = df["realgdp"].pct_change(4) * 100
    df["cpi_yoy_pct"] = df["cpi"].pct_change(4) * 100
    return df


def run_sql(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    try:
        df.to_sql("quarterly_macro", con, index=False, if_exists="replace")
        queries = {
            "annual_summary": """
                SELECT year,
                       ROUND(AVG(realgdp), 2) AS avg_real_gdp_bil_2005_usd,
                       ROUND(AVG(unemp), 2) AS avg_unemployment_pct,
                       ROUND(AVG(infl), 2) AS avg_inflation_pct,
                       ROUND(AVG(tbilrate), 2) AS avg_3m_tbill_rate_pct
                FROM quarterly_macro
                GROUP BY year ORDER BY year;
            """,
            "highest_unemployment_quarters": """
                SELECT period, ROUND(unemp, 2) AS unemployment_pct,
                       ROUND(realgdp, 2) AS real_gdp_bil_2005_usd,
                       ROUND(infl, 2) AS inflation_pct
                FROM quarterly_macro
                ORDER BY unemp DESC LIMIT 10;
            """,
            "latest_observation": """
                SELECT period, realgdp, unemp, infl, cpi
                FROM quarterly_macro ORDER BY date DESC LIMIT 1;
            """
        }
        outputs = {name: pd.read_sql_query(sql, con) for name, sql in queries.items()}
        return outputs
    finally:
        con.close()


def make_charts(df: pd.DataFrame, annual: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 5.5))
    plt.plot(df["date"], df["realgdp"], linewidth=1.8)
    plt.title("U.S. Real GDP, 1959 Q1-2009 Q3")
    plt.xlabel("Quarter")
    plt.ylabel("Real GDP (billions of chained 2005 USD, SAAR)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(OUT / "real_gdp_trend.png", dpi=180)
    plt.close()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.plot(df["date"], df["unemp"], linewidth=1.6)
    ax1.set_ylabel("Unemployment (%)")
    ax1.set_title("U.S. Unemployment Rate")
    ax1.grid(alpha=0.2)
    ax2.plot(df["date"], df["infl"], linewidth=1.4)
    ax2.set_ylabel("Inflation (%)")
    ax2.set_xlabel("Quarter")
    ax2.set_title("Dataset Inflation Measure (Annualized Quarterly Rate)")
    ax2.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "unemployment_inflation.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(annual["year"], annual["avg_real_gdp_bil_2005_usd"], label="Average real GDP")
    ax.set_title("Annual Average Real GDP")
    ax.set_xlabel("Year")
    ax.set_ylabel("Billions of chained 2005 USD, SAAR")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "annual_real_gdp.png", dpi=180)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_and_clean()
    sql = run_sql(df)
    annual = sql["annual_summary"]
    annual.to_csv(OUT / "annual_summary.csv", index=False)
    sql["highest_unemployment_quarters"].to_csv(OUT / "highest_unemployment_quarters.csv", index=False)
    sql["latest_observation"].to_csv(OUT / "latest_observation.csv", index=False)
    df.to_csv(OUT / "quarterly_metrics.csv", index=False)
    df[["realgdp", "realcons", "realinv", "unemp", "infl", "tbilrate"]].corr().to_csv(OUT / "correlation_matrix.csv")

    make_charts(df, annual)
    max_unemp = df.loc[df["unemp"].idxmax()]
    first, last = df.iloc[0], df.iloc[-1]
    gdp_change = (last["realgdp"] / first["realgdp"] - 1) * 100
    summary = (
        f"Rows analysed: {len(df):,}\n"
        f"Period: {first['period']} to {last['period']}\n"
        f"Real GDP change across sample: {gdp_change:.1f}%\n"
        f"Highest unemployment: {max_unemp['unemp']:.1f}% in {max_unemp['period']}\n"
        f"Mean inflation field (dataset's annualized quarterly rate): {df['infl'].mean():.2f}%\n"
        "Note: this is a historical sample ending in 2009 Q3, not a current economic snapshot.\n"
    )
    (OUT / "executive_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Outputs written to: {OUT}")


if __name__ == "__main__":
    main()
