# Close CSV technical indicators with ta

One explicit close CSV produces RSI, Bollinger bands, an indicator CSV and a readable summary. The default data is invented, not a real stock analysis or a trading signal. No network data fetch, broker account, API secret, OHLC fabrication or trade execution is part of this tool.

## Command

Persistent repository variable `ANALYSIS_COMMAND`:

```text
python analyze.py --input data/synthetic.csv --metadata data/synthetic.json --rsi-window 14 --bb-window 20 --bb-dev 2 --output results
```

Set this under repository Settings > Secrets and variables > Actions > Variables. Only trusted repository maintainers should change it. Run **Close CSV indicators** manually under Actions after the reviewed workflow reaches the default branch. Each later analysis updates that variable and manually dispatches the workflow. A dispatch input is not a substitute for this persistent variable. If it is missing, execution fails rather than guessing a command.

The runner uses argument parsing and `shell=False`, not eval or a shell command. Only `python analyze.py` and its documented options are accepted. Inputs must be checked-in `.csv` and `.json` files under `data/`; the only output directory is `results/`. The command is public in the logs. Do not put secrets or private data in commands, input files, metadata or results. The workflow has read-only contents permission, no credentials persisted by checkout, no authored timeout and no automatic market-analysis schedule. PR events run tests only and never the persistent analysis command.

## Explicit input

Supply exactly two columns, `Date,Close`. Dates must be unique, strictly increasing, canonical ISO date labels (`YYYY-MM-DD`). Closes must all be finite and strictly positive. Rows are neither sorted, silently dropped, interpolated nor filled. Missing/invalid values, duplicate dates and malformed rows fail the run. Calendar gaps remain as supplied; this tool does not prove that a dataset contains every trading session. Each window counts supplied observations, not calendar days. Input dates cannot be later than metadata `as_of` in the declared dataset timezone. Enough rows for both windows are required; minimal accepted input can contain only one usable Bollinger result and is not a statistically mature signal.

Use a JSON sidecar with non-empty string fields:

```json
{
  "dataset_kind": "market",
  "instrument": "EXPLICIT-INSTRUMENT-IDENTITY",
  "source": "Actual source URL and extraction reference",
  "as_of": "2026-10-10T12:00:00+00:00",
  "timezone": "UTC",
  "price_basis": "Explicit raw or adjusted close basis and relevant adjustments",
  "currency": "Actual currency",
  "publication_rights": "Grounded permission or license allowing this input and its results to be public"
}
```

Metadata is a recorded declaration, not independent verification of data origin or rights. A maintainer must verify it before committing any real dataset. Do not paste held private EGX endpoint bodies, invent market prices or use a software license as a market-data license. No real market dataset is bundled. A first real stock-analysis outcome still requires suitable public input and its publication basis; the synthetic demonstration cannot count as that outcome.

`--rsi-window` and `--bb-window` accept 2..10000; defaults are 14 and 20. `--bb-dev` accepts integer 1..10 and defaults to 2. All must pass before output is written. The explicit `--metadata` path is required, even for synthetic data.

## Indicator semantics and artifacts

The pinned `ta==0.11.0` release computes RSI using zero-seeded EWM with alpha=1/window and `adjust=False`. The initial difference is counted as zero; its first RSI is at observation 14 with the default window. This is not the SMA-seeded Wilder variant. Pinned ta returns 100 for a flat series after warmup, not 50. Bollinger uses a full rolling window and population standard deviation (`ddof=0`). Default leading missing values are preserved as blank CSV cells: 13 RSI rows, 19 Bollinger rows. No `fillna=True` or `add_all_ta_features` is used.

Manual runs upload **close-csv-results-RUN_ID**, retained for seven days:

- `indicators.csv`: all input rows, original Date/Close and RSI/BB_Middle/BB_Upper/BB_Lower.
- `summary.txt` and `summary.json`: dataset kind, date range, latest values, usable-row counts, declared provenance/basis/as-of, original input and metadata SHA256, parameters and installed versions.
- `stdout.txt`, `stderr.txt`, `exit-code.txt`, `source-commit.txt`, `run-id.txt`, `installed-versions.txt`: execution originals and source binding.

Use the run's Actions page to download the artifact during retention. Tests/install success alone do not prove that a manual command ran. A completed synthetic manual run proves only this indicator path for invented data, not market-data completeness, price adjustment correctness or investment suitability. Failed manual runs retain available diagnostic files, not a claimed successful result.

## Review and local commands

Source changes use issue branches, independent source review, PR checks and an eligible separate GitHub approval before normal merge. No self-approval or protection bypass. The repository's required job is `analyze`; it executes independent scalar RSI recurrence and Bollinger population-formula comparisons, boundary cases and input/command validation.

The qualified runner target is Python 3.12.16 on ubuntu-24.04. Install build pins in `requirements-build.txt`, then dependencies with `python -m pip install --no-build-isolation -r requirements.txt`, and check `python -m pip check`. Tests: `python -m unittest discover -s tests -v`. These instructions are not a statement that qualification has already occurred. See the actual PR, manual run and artifacts for execution evidence.

See [PROVENANCE.md](PROVENANCE.md) and [UPSTREAM-LICENSE-ta.txt](UPSTREAM-LICENSE-ta.txt). Wrapper code is provided under MIT in LICENSE. The invented data is CC0-1.0. Dependencies keep their own licenses. The ta software license does not license any market data.
