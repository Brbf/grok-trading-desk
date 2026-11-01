"""Causal, descriptive geometric pattern candidates from fully closed OHLCV candles.

Poster drawings are hypotheses, not predictive labels. No orders, direction
probabilities, SL/TP, remote calls, model fitting or future observations.
"""
from __future__ import annotations

import math
from statistics import median

NAMES = (
    'double_top', 'double_bottom', 'triple_top', 'triple_bottom',
    'head_and_shoulders', 'inverse_head_and_shoulders',
    'ascending_triangle', 'descending_triangle', 'symmetric_triangle',
    'rising_wedge', 'falling_wedge', 'rectangle', 'rising_channel',
    'falling_channel', 'bull_flag', 'bear_flag', 'bull_pennant', 'bear_pennant',
)


def _pivots(bars, side, radius=2):
    """Only extrema confirmed by radius subsequent, already-closed bars."""
    field = 'high' if side == 'high' else 'low'
    result = []
    for i in range(radius, len(bars) - radius):
        x = bars[i][field]
        neighbors = [bars[j][field] for j in range(i-radius, i+radius+1) if j != i]
        if (x > max(neighbors) if side == 'high' else x < min(neighbors)):
            result.append((i, x))
    return result


def _line(points):
    a, b = points[0], points[-1]
    if b[0] <= a[0]:
        return None
    return (b[1]-a[1])/(b[0]-a[0])


def _between(points, start, end):
    return [v for i, v in points if start < i < end]


def _same_level(points, atol):
    return max(v for _, v in points) - min(v for _, v in points) <= atol


def geometric_candidates(bars):
    """Report shape candidates with a confirmed-pivot delay, not trade signals.

    All input candles must be chronologically ordered and already closed by
    the caller. At least 15 bars are required. The very last bar may be used
    to describe a breakout, but never to confirm its own pivot.
    """
    if not isinstance(bars, list) or len(bars) < 15 or len(bars) > 300:
        raise ValueError('Require bounded chronological completed OHLCV bars')
    for b in bars:
        if (not isinstance(b, dict) or not all(k in b for k in ('open','high','low','close','volume'))
                or any(type(b[k]) not in (int,float) or not math.isfinite(b[k])
                       for k in ('open','high','low','close','volume'))
                or not 0 < b['low'] <= min(b['open'],b['close'])
                <= max(b['open'],b['close']) <= b['high'] or b['volume'] < 0):
            raise ValueError('Invalid completed candle')
    for older, newer in zip(bars, bars[1:]):
        if 't' in older and 't' in newer and not older['t'] < newer['t']:
            raise ValueError('Nonmonotonic candle times')
    spread = [max(0, b['high']-b['low']) for b in bars[-14:]]
    atr = median(spread)
    if atr <= 0:
        raise ValueError('No volatility scale in completed bars')
    tol = 0.65*atr
    hs = _pivots(bars, 'high')
    ls = _pivots(bars, 'low')
    out = {key: False for key in NAMES}

    # Rounded double/triple peaks/troughs must be confirmed pivots.
    for points, opposite, two_name, three_name, shoulder_name, sign in (
        (hs, ls, 'double_top', 'triple_top', 'head_and_shoulders', 1),
        (ls, hs, 'double_bottom', 'triple_bottom', 'inverse_head_and_shoulders', -1),
    ):
        if len(points) >= 2:
            (ia, a), (ib, b) = points[-2:]
            middle = _between(opposite, ia, ib)
            if ib-ia >= 4 and abs(a-b) <= tol and middle:
                depth = (min(a,b) - min(middle) if sign == 1
                         else max(middle) - max(a,b))
                out[two_name] = depth >= 1.0*atr
        if len(points) >= 3:
            triple = points[-3:]
            if (triple[-1][0]-triple[0][0] >= 8
                    and all(triple[i+1][0]-triple[i][0] >= 3 for i in (0,1))
                    and _same_level(triple, tol)):
                out[three_name] = (bool(_between(opposite,triple[0][0],triple[1][0]))
                    and bool(_between(opposite,triple[1][0],triple[2][0])))
            a,b,c = triple
            valleys = (_between(opposite,a[0],b[0]),
                       _between(opposite,b[0],c[0]))
            if (b[0]-a[0] >= 3 and c[0]-b[0] >= 3
                    and abs(a[1]-c[1]) <= 1.0*atr and all(valleys)):
                head_height = (b[1] - max(a[1],c[1]) if sign == 1
                               else min(a[1],c[1])-b[1])
                out[shoulder_name] = head_height >= 0.7*atr

    # Trendline families: minimum two causally confirmed extrema of each type.
    if len(hs) >= 2 and len(ls) >= 2:
        hp, lp = hs[-2:], ls[-2:]
        span = min(hp[-1][0],lp[-1][0])-max(hp[0][0],lp[0][0])
        global_span = max(hp[-1][0],lp[-1][0])-min(hp[0][0],lp[0][0])
        if global_span >= 5 and span >= -5:
            hu, lo = _line(hp), _line(lp)
            if hu is not None and lo is not None:
                dh, dl = hp[-1][1]-hp[0][1], lp[-1][1]-lp[0][1]
                flat_h, flat_l = abs(dh) <= tol, abs(dl) <= tol
                rising_l, falling_h = dl >= 0.5*atr, dh <= -0.5*atr
                out['ascending_triangle'] = flat_h and rising_l
                out['descending_triangle'] = flat_l and falling_h
                out['symmetric_triangle'] = falling_h and rising_l
                narrowing = hu < lo - 0.02*atr
                out['rising_wedge'] = (narrowing and hu > 0.03*atr
                                       and lo > 0.03*atr)
                out['falling_wedge'] = (narrowing and hu < -0.03*atr
                                        and lo < -0.03*atr)
                height = median([x[1] for x in hp])-median([x[1] for x in lp])
                out['rectangle'] = flat_h and flat_l and height >= 1.0*atr
                parallel = abs(hu-lo) <= 0.12*atr and height >= 1.0*atr
                out['rising_channel'] = parallel and hu > 0.08*atr and lo > 0.08*atr
                out['falling_channel'] = parallel and hu < -0.08*atr and lo < -0.08*atr

    # Impulse then retracement: only a flag-like candidate, not classical validation.
    if len(bars) >= 20:
        pole = bars[-16]['close'] - bars[-25]['close'] if len(bars) >= 25 else (
            bars[-11]['close'] - bars[-20]['close'])
        recent = bars[-8:]
        width = max(b['high'] for b in recent) - min(b['low'] for b in recent)
        pullback = recent[-1]['close'] - recent[0]['close']
        if abs(pole) >= 3.5*atr and width <= 4.5*atr:
            out['bull_flag'] = pole > 0 and pullback <= 0 and abs(pullback) <= 2.0*atr
            out['bear_flag'] = pole < 0 and pullback >= 0 and abs(pullback) <= 2.0*atr
            out['bull_pennant'] = out['bull_flag'] and out['symmetric_triangle']
            out['bear_pennant'] = out['bear_flag'] and out['symmetric_triangle']

    return {
        'flags': out,
        'detected': [x for x in NAMES if out[x]],
        'confirmed_pivot_right_bars': 2,
        'volatility_scale': atr,
        'number_of_confirmed_high_pivots': len(hs),
        'number_of_confirmed_low_pivots': len(ls),
        'descriptive_not_directional': True,
        'breakout_or_trade_trigger': False,
    }
