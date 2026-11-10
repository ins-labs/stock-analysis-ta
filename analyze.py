"""Close-only ta indicators. See PROVENANCE.md for exact upstream semantics."""
import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

ROOT = Path(__file__).resolve().parent


def data_path(value, suffix):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT / 'data') or path.suffix != suffix or not path.is_file():
        raise ValueError('Input must be an existing data/ file with suffix ' + suffix)
    return path


def parser():
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    p.add_argument('--input', required=True)
    p.add_argument('--metadata', required=True)
    p.add_argument('--rsi-window', type=int, default=14)
    p.add_argument('--bb-window', type=int, default=20)
    p.add_argument('--bb-dev', type=int, default=2)
    p.add_argument('--output', choices=['results'], default='results')
    return p


def load_input(csv_path, metadata_path):
    if csv_path.stat().st_size > 10_000_000 or metadata_path.stat().st_size > 100_000:
        raise ValueError('Input exceeds 10 MB CSV or 100 KB metadata limit')
    raw = csv_path.read_bytes()
    metadata_raw = metadata_path.read_bytes()
    meta = json.loads(metadata_raw)
    fields = ['dataset_kind', 'instrument', 'source', 'as_of', 'timezone', 'price_basis', 'currency', 'publication_rights']
    if not isinstance(meta, dict) or any(not isinstance(meta.get(k), str) or not meta[k].strip() for k in fields):
        raise ValueError('Metadata requires non-empty string fields: ' + ', '.join(fields))
    if meta['dataset_kind'] not in ['synthetic', 'market']:
        raise ValueError('dataset_kind must be synthetic or market')
    ZoneInfo(meta['timezone'])
    asof = datetime.fromisoformat(meta['as_of'])
    if asof.tzinfo is None or asof.utcoffset() is None:
        raise ValueError('as_of must contain a UTC offset')
    reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader, None) != ['Date', 'Close']:
        raise ValueError('CSV header must be exactly Date,Close')
    dates, closes = [], []
    for row in reader:
        if len(row) != 2 or any(not cell.strip() for cell in row):
            raise ValueError('Malformed or blank CSV row')
        label = row[0]
        day = date.fromisoformat(label)
        if day.isoformat() != label or (dates and label <= dates[-1]):
            raise ValueError('Dates must be unique and strictly chronological ISO dates')
        if day > asof.astimezone(ZoneInfo(meta['timezone'])).date():
            raise ValueError('Input date is later than declared as_of in dataset timezone')
        close = float(row[1])
        if not math.isfinite(close) or close <= 0:
            raise ValueError('Every close must be positive and finite; no fill or drop')
        dates.append(label)
        closes.append(close)
    if not dates:
        raise ValueError('CSV contains no observations')
    return dates, closes, meta, hashlib.sha256(raw).hexdigest(), hashlib.sha256(metadata_raw).hexdigest()


def calculate(dates, closes, rsi_window, bb_window, bb_dev):
    if not 2 <= rsi_window <= 10000 or not 2 <= bb_window <= 10000 or not 1 <= bb_dev <= 10:
        raise ValueError('Windows must be 2..10000 and bb-dev 1..10')
    if len(closes) < max(rsi_window, bb_window):
        raise ValueError('Insufficient observations for both requested windows')
    series = pd.Series(closes, dtype='float64')
    rsi = RSIIndicator(close=series, window=rsi_window, fillna=False).rsi()
    bb = BollingerBands(close=series, window=bb_window, window_dev=bb_dev, fillna=False)
    frame = pd.DataFrame({'Date': dates, 'Close': closes, 'RSI': rsi, 'BB_Middle': bb.bollinger_mavg(), 'BB_Upper': bb.bollinger_hband(), 'BB_Lower': bb.bollinger_lband()})
    for col, warmup in [('RSI', rsi_window-1), ('BB_Middle', bb_window-1), ('BB_Upper', bb_window-1), ('BB_Lower', bb_window-1)]:
        values = frame[col].tolist()
        if not all(pd.isna(v) for v in values[:warmup]) or not all(math.isfinite(v) for v in values[warmup:]):
            raise ValueError('Unexpected indicator missing/non-finite pattern: ' + col)
    if not frame['RSI'].dropna().between(0, 100).all():
        raise ValueError('RSI outside 0..100')
    return frame


def run(args):
    input_path = data_path(args.input, '.csv')
    metadata_path = data_path(args.metadata, '.json')
    dates, closes, meta, digest, meta_digest = load_input(input_path, metadata_path)
    frame = calculate(dates, closes, args.rsi_window, args.bb_window, args.bb_dev)
    output = ROOT / 'results'
    if output.is_symlink():
        raise ValueError('results cannot be a symlink')
    output.mkdir(exist_ok=True)
    frame.to_csv(output / 'indicators.csv', index=False, na_rep='')
    last = frame.iloc[-1]
    summary = {'status': 'success', 'dataset': meta, 'input': args.input, 'input_sha256': digest, 'metadata_sha256': meta_digest,
        'observations': len(dates), 'start_date': dates[0], 'end_date': dates[-1],
        'parameters': {'rsi_window': args.rsi_window, 'bb_window': args.bb_window, 'bb_dev': args.bb_dev, 'fillna': False, 'bollinger_std_ddof': 0},
        'usable_rows': {c: int(frame[c].notna().sum()) for c in ['RSI', 'BB_Middle', 'BB_Upper', 'BB_Lower']},
        'warmup_rows': {'RSI': args.rsi_window-1, 'Bollinger': args.bb_window-1},
        'latest': {k: str(last[k]) if k == 'Date' else float(last[k]) for k in frame.columns},
        'versions': {n: version(n) for n in ['ta', 'numpy', 'pandas', 'python-dateutil', 'pytz', 'tzdata', 'six']},
        'python': sys.version, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'interpretation': 'Descriptive indicators only, not a trade recommendation. Dates are supplied observation labels, not verified exchange sessions; calendar gaps are retained without interpolation.',
        'rsi_semantics': 'ta 0.11.0 zero-seeded EWM alpha=1/window, adjust=False; first diff counted as zero; flat series RSI=100. Not an SMA-seeded Wilder implementation.'}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    text = (f"{meta['dataset_kind'].upper()} DATA: {meta['instrument']}\n"
        f"Source: {meta['source']}\nAs of: {meta['as_of']} ({meta['timezone']})\n"
        f"Basis: {meta['price_basis']}; currency: {meta['currency']}\n"
        f"{len(dates)} supplied observations: {dates[0]} through {dates[-1]}\n"
        f"Latest close {last['Close']:.6f}; RSI({args.rsi_window}) {last['RSI']:.6f}\n"
        f"Bollinger({args.bb_window}, {args.bb_dev} population standard deviations): "
        f"lower {last['BB_Lower']:.6f}, middle {last['BB_Middle']:.6f}, upper {last['BB_Upper']:.6f}\n"
        f"Warmup nulls retained: RSI {args.rsi_window-1}, Bollinger {args.bb_window-1}.\n"
        f"Input SHA256: {digest}\n{summary['rsi_semantics']}\n{summary['interpretation']}\n")
    (output / 'summary.txt').write_text(text)
    print(text)
    return summary


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        run(args)
    except (ValueError, OSError, KeyError, TypeError, OverflowError, csv.Error) as exc:
        print('Analysis rejected: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
