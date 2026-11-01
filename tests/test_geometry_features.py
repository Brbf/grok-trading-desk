"""Synthetic, research-only checks for causal geometric candidate descriptors."""
import unittest
from agents.geometry_features import _pivots, geometric_candidates, NAMES


def bars_from_closes(closes):
    return [{'t': f'{i:03d}', 'open': c-0.25, 'high': c+0.4,
             'low': c-0.5, 'close': c, 'volume': 1} for i,c in enumerate(closes)]


class GeometryTests(unittest.TestCase):
    def test_double_top_candidate(self):
        p=[10,10,10,11,13,16,13,10,9,11,13,16.2,13,10,8,9,8,7,7,7,7,7,7,7,7]
        self.assertTrue(geometric_candidates(bars_from_closes(p))['flags']['double_top'])

    def test_double_bottom_candidate(self):
        p=[20,20,20,19,17,14,17,20,21,19,17,14.2,17,20,22,21,22,23,23,23,23,23,23,23,23]
        self.assertTrue(geometric_candidates(bars_from_closes(p))['flags']['double_bottom'])

    def test_no_last_bar_pivot(self):
        bars=bars_from_closes([10,11,10,11,10]*5)
        bars[-1]['high']=100
        self.assertNotIn(len(bars)-1, [i for i,_ in _pivots(bars,'high')])

    def test_earlier_snapshot_unchanged_when_future_bar_arrives(self):
        bars=bars_from_closes([10,11,12,11,10]*5)
        old=geometric_candidates(bars)
        bars.append({'t':'025','open':100,'high':100,'low':99,'close':99,'volume':2})
        self.assertEqual(old,geometric_candidates(bars[:25]))

    def test_bad_candles_rejected(self):
        bars=bars_from_closes([10,11,12,11,10]*5)
        bars[2].pop('high')
        with self.assertRaises(ValueError):
            geometric_candidates(bars)

    def test_flat_market_rejected(self):
        bars=[{'open':1,'high':1,'low':1,'close':1,'volume':1} for _ in range(25)]
        with self.assertRaises(ValueError):
            geometric_candidates(bars)

    def test_no_orders_or_direction_claims(self):
        r=geometric_candidates(bars_from_closes([10,11,12,11,10]*5))
        self.assertFalse(r['breakout_or_trade_trigger'])
        self.assertTrue(r['descriptive_not_directional'])
        self.assertEqual(set(r['flags']),set(NAMES))

    def test_unsorted_candle_times_rejected(self):
        bars=bars_from_closes([10,11,12,11,10]*5)
        bars[-1]['t']='001'
        with self.assertRaises(ValueError):
            geometric_candidates(bars)


if __name__=='__main__':
    unittest.main()
