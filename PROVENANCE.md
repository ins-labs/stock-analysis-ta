# Source and semantic provenance

Checked 2026-11-10. This is source preparation, not runtime proof.

- Owning project: https://github.com/bukosabino/ta
- Published release: https://pypi.org/project/ta/0.11.0/
- Release metadata inspected: https://pypi.org/pypi/ta/0.11.0/json
- Exact ta source archive used for API review: https://files.pythonhosted.org/packages/e0/9a/37d92a6b470dc9088612c2399a68f1a9ac22872d4e1eff416818e22ab11b/ta-0.11.0.tar.gz
- Archive SHA256: `de86af43418420bd6b088a2ea9b95483071bf453c522a8441bc2f12bcf8493fd`.
- Source inspected in release: `ta/momentum.py` RSIIndicator and `ta/volatility.py` BollingerBands. Current upstream references: https://github.com/bukosabino/ta/blob/master/ta/momentum.py and https://github.com/bukosabino/ta/blob/master/ta/volatility.py . Release archive, not moving master, governs the wrapper's semantics.
- Upstream license: MIT, https://github.com/bukosabino/ta/blob/master/LICENSE . Upstream author copyright retained in UPSTREAM-LICENSE-ta.txt.
- Package dependency declarations: https://github.com/bukosabino/ta/blob/master/setup.py . Only numpy and pandas are mandatory. No price provider, credentials, technical-analysis binary extension or exchange connection is needed by this recipe.

RSI source: first diff becomes zero gain/loss; EWM alpha=1/window, min_periods=window, adjust=False. Downward EWM zero yields RSI=100. Preserve the first window-1 missing rows; do not reinterpret flat output as 50 or call this an SMA-seeded Wilder result.

Bollinger source: close.rolling(window,min_periods=window).mean and .std(ddof=0); upper/lower are mean +/- window_dev times population standard deviation. Preserve missing warmup. The wrapper only emits the three price bands, not percentage-band values that can divide by zero on a flat series.

All chosen dependency release metadata was inspected from PyPI under `/pypi/NAME/VERSION/json`: numpy2.1.3, pandas2.2.3, python-dateutil2.9.0.post0, pytz2024.2, tzdata2024.2, six1.16.0, setuptools75.6.0 and wheel0.45.1. Pins specify a reproducible candidate dependency set, not latest-version claims or an already qualified environment. Pip24.3.1 is pinned for install consistency. `--no-build-isolation` prevents ta's source build from silently installing another unpinned build environment. CI checks the resolved dependency set.

The exact source and metadata hash are emitted with every result. Synthetic prices are explicitly invented and dedicated under CC0-1.0: https://creativecommons.org/publicdomain/zero/1.0/ . They represent no issuer, venue or real currency. Source bytes are committed with the wrapper. Calendar-day labels in that example are not claimed as trading sessions. No private endpoint body or user metadata is included.
