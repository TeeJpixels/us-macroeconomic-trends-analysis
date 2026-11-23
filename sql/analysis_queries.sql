-- Load data by running analyze.py; it creates outputs/us_macrodata.sqlite.

-- 1. Annual averages for key indicators.
SELECT year,
       ROUND(AVG(realgdp), 2) AS avg_real_gdp,
       ROUND(AVG(unemp), 2) AS avg_unemployment_pct,
       ROUND(AVG(infl), 2) AS avg_inflation_pct
FROM quarterly_macro
GROUP BY year
ORDER BY year;

-- 2. Quarters with the highest unemployment rate.
SELECT period, unemp, realgdp, infl
FROM quarterly_macro
ORDER BY unemp DESC
LIMIT 10;

-- 3. Quarterly GDP and year-over-year GDP growth.
SELECT period, realgdp, gdp_yoy_pct
FROM quarterly_macro
ORDER BY date;

-- 4. Latest observation in this historical dataset.
SELECT period, realgdp, unemp, infl
FROM quarterly_macro
ORDER BY date DESC
LIMIT 1;
