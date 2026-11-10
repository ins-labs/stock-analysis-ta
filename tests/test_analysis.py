import csv
from datetime import date, timedelta
import json
import math
from pathlib import Path
import tempfile
import unittest

import analyze
from command_runner import parse_command


def reference_rsi(values, window):
    """Plain scalar recurrence, not pandas or ta. Matches pinned release seed."""
    gain = loss = 0.0
    result = []
    for i, value in enumerate(values):
        diff = 0 if i == 0 else value-values[i-1]
        gain = (1-1/window)*gain + max(diff, 0)/window
        loss = (1-1/window)*loss + max(-diff, 0)/window
        result.append(None if i < window-1 else 100 if loss == 0 else 100-100/(1+gain/loss))
    return result


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.values = [100+i+(2 if i%3==0 else -2) for i in range(40)]
        self.dates = [(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(40)]

    def test_rsi_against_scalar_recurrence(self):
        frame = analyze.calculate(self.dates, self.values, 14, 20, 2)
        for got, expected in zip(frame.RSI, reference_rsi(self.values, 14)):
            if expected is None: self.assertTrue(math.isnan(got))
            else: self.assertAlmostEqual(got, expected, places=11)

    def test_bollinger_against_population_formula(self):
        frame = analyze.calculate(self.dates, self.values, 14, 20, 2)
        for i in range(19,40):
            window = self.values[i-19:i+1]
            mean = sum(window)/20
            sigma = math.sqrt(sum((v-mean)**2 for v in window)/20)
            self.assertAlmostEqual(frame.BB_Middle.iloc[i], mean, places=10)
            self.assertAlmostEqual(frame.BB_Upper.iloc[i], mean+2*sigma, places=10)
            self.assertAlmostEqual(frame.BB_Lower.iloc[i], mean-2*sigma, places=10)

    def test_warmup_and_exact_minimum(self):
        frame = analyze.calculate(self.dates[:20], self.values[:20],14,20,2)
        self.assertEqual(frame.RSI.isna().sum(),13)
        self.assertEqual(frame.BB_Upper.isna().sum(),19)
        self.assertEqual(frame.RSI.notna().sum(),7)

    def test_flat_source_specific_behavior(self):
        frame = analyze.calculate(self.dates,[100]*40,14,20,2)
        self.assertTrue((frame.RSI.dropna()==100).all())
        self.assertTrue((frame.BB_Upper.dropna()==100).all())
        self.assertTrue((frame.BB_Lower.dropna()==100).all())

    def test_monotonic_up_down(self):
        up=analyze.calculate(self.dates,list(range(1,41)),14,20,2)
        down=analyze.calculate(self.dates,list(range(40,0,-1)),14,20,2)
        self.assertTrue((up.RSI.dropna()==100).all())
        self.assertTrue((down.RSI.dropna()==0).all())

    def test_nondefault_windows(self):
        frame=analyze.calculate(self.dates,self.values,3,5,3)
        self.assertEqual(frame.RSI.isna().sum(),2)
        self.assertEqual(frame.BB_Upper.isna().sum(),4)
        for got, expected in zip(frame.RSI.iloc[2:],reference_rsi(self.values,3)[2:]): self.assertAlmostEqual(got,expected)

    def test_bad_parameters_and_insufficient_history(self):
        for r,b,d in [(1,20,2),(14,1,2),(14,20,0),(14,20,11),(10001,20,2),(14,10001,2),(41,20,2)]:
            with self.subTest((r,b,d)),self.assertRaises(ValueError): analyze.calculate(self.dates,self.values,r,b,d)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=analyze.ROOT/'data')
        self.addCleanup(self.temp.cleanup)
        self.csv=Path(self.temp.name)/'input.csv'
        self.meta=Path(self.temp.name)/'input.json'
        self.metadata=json.loads((analyze.ROOT/'data/synthetic.json').read_text())
        self.meta.write_text(json.dumps(self.metadata))
        self.csv.write_text('Date,Close\n2026-01-01,100\n2026-01-02,101\n')

    def test_valid_and_hashes(self):
        dates, closes, meta, digest, mdigest=analyze.load_input(self.csv,self.meta)
        self.assertEqual(dates,['2026-01-01','2026-01-02'])
        self.assertEqual(closes,[100,101])
        self.assertEqual(len(digest),64);self.assertEqual(len(mdigest),64)

    def test_invalid_closes(self):
        for close in ['', 'NaN','inf','-inf','0','-1','abc']:
            self.csv.write_text('Date,Close\n2026-01-01,'+close+'\n')
            with self.subTest(close=close),self.assertRaises(ValueError): analyze.load_input(self.csv,self.meta)

    def test_malformed_headers_rows(self):
        for content in ['Date,Close\n','Date,AdjustedClose\n2026-01-01,2\n','Date,Close,Volume\n2026-01-01,2,3\n','Date,Close\n2026-01-01\n','Date,Close\n2026-01-01,2,3\n']:
            self.csv.write_text(content)
            with self.subTest(content=content),self.assertRaises(ValueError): analyze.load_input(self.csv,self.meta)

    def test_dates_duplicate_unsorted_invalid_future(self):
        for dates in [('2026-01-02','2026-01-01'),('2026-01-01','2026-01-01'),('2026-02-30','2026-03-01'),('20260101','2026-01-02'),('2027-01-01','2027-01-02')]:
            self.csv.write_text('Date,Close\n'+dates[0]+',100\n'+dates[1]+',101\n')
            with self.subTest(dates=dates),self.assertRaises(ValueError): analyze.load_input(self.csv,self.meta)

    def test_gaps_preserved(self):
        self.csv.write_text('Date,Close\n2026-01-01,100\n2026-01-09,101\n')
        self.assertEqual(analyze.load_input(self.csv,self.meta)[0],['2026-01-01','2026-01-09'])

    def test_metadata_rejected(self):
        for k,v in [('source',''),('price_basis',None),('dataset_kind','fiction'),('as_of','2026-10-10T00:00:00'),('timezone','BAD/TIMEZONE')]:
            meta=dict(self.metadata);meta[k]=v;self.meta.write_text(json.dumps(meta))
            with self.subTest(k=k),self.assertRaises((ValueError,KeyError)): analyze.load_input(self.csv,self.meta)

    def test_path_confinement(self):
        for path in ['../README.md','analyze.py','/etc/passwd','data/../analyze.py']:
            with self.subTest(path=path),self.assertRaises(ValueError): analyze.data_path(path,'.csv')


class CommandTests(unittest.TestCase):
    def test_allowed(self):
        argv=parse_command('python analyze.py --input data/synthetic.csv --metadata data/synthetic.json --output results')
        self.assertEqual(argv[1],str(analyze.ROOT/'analyze.py'))

    def test_arbitrary_shell_and_scripts_rejected(self):
        for cmd in ['', 'python -c "print(1)"', 'bash analyze.py','python other.py','python analyze.py --input data/synthetic.csv --metadata data/synthetic.json; echo hi','python analyze.py --input data/synthetic.csv --metadata data/synthetic.json $(id)','python analyze.py --input data/synthetic.csv --metadata data/synthetic.json --output /tmp/x']:
            with self.subTest(cmd=cmd),self.assertRaises((ValueError,SystemExit)): parse_command(cmd)


if __name__=='__main__': unittest.main()
