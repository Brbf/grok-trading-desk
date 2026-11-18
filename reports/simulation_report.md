# Simulation report

Paper account: **500 EUR**. No live orders. Rules were fixed in `config/scanner.yaml` before this run (sha256 `d046b459bb3204cafd9673fee0c98cf3dceff944ab2b39eb97196cc29357d7d6`).

## Status

Run straight through, the 500 EUR account finished at 398.45 EUR (-101.55 EUR) after 540 trades. In-sample was -68.96 EUR. A fresh 500 EUR account on the out-of-sample window alone was +90.67 EUR on 270 trades. The continuous result is a loss. The out-of-sample gain does not agree with the in-sample loss, so it is not evidence of an edge. Win rates are about one trade in three; costs and gap-through-stops do the rest. This is not a case for real money. The live order path stays disabled.

## What was simulated

- Source: yahoo_chart_1h_730d.
- Dukascopy's datafeed was not reachable from the build environment (HTTP 503). Yahoo Finance hourly candles are the free substitute. Spot FX volume on this source is zero and must be rejected by the quality gate.
- Download failures recorded in the cache manifest: 5.
- Bars loaded: 605 symbols. Tradable after the volume/quality gate: 553. Excluded: 52.
- Decision-time split: 2025-12-25T07:27:00+00:00 (first 70% of the calendar span in-sample, last 30% out-of-sample).
- In-sample and out-of-sample each start from a fresh 500 EUR. Indicators at a bar use only earlier bars.
- Fills are the next bar's open, worsened by half the spread plus slippage. A stop that gaps through is filled at the open, not at the stop. Same-bar stop and time-exit: a gap through the stop wins. There is no take-profit.
- Yahoo prices are last/mid prints. The spread is a configured model, not a recorded bid/ask, because this source does not provide one. Commission is 0.35 bp per side.
- Position size is a CFD unit (1 quote currency per 1.0 price move), not an exchange future's multiplier. A 500 EUR account cannot hold a full ES or GC contract; the sim does not pretend it can.
- Spot FX from Yahoo has no volume, so those pairs are conversion-only when the gate rejects them. They are listed under excluded, not as traded markets.

## Results

| Run | Trades | Win rate | Net P&L EUR | Final equity | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| in-sample | 516 | 26.0% | -68.96 | 431.04 | 410.02 (49.3%) |
| out-of-sample | 270 | 30.0% | +90.67 | 590.67 | 134.09 (20.4%) |
| full sample | 540 | 25.4% | -101.55 | 398.45 | 433.60 (52.1%) |

Win rate is the share of trades with net P&L above zero after costs. Max drawdown is peak-to-trough on marked equity, so a run-up can produce a large drawdown before the account kill switch, which is 20% under the original 500 EUR (equity at or under 400) rather than a trailing stop.

### Out-of-sample by asset class

| Class | Trades | Wins | Net P&L EUR |
| --- | ---: | ---: | ---: |
| stock_eu | 53 | 13 | -28.97 |
| index_us | 7 | 1 | -20.90 |
| stock_us | 104 | 29 | +7.70 |
| energy | 16 | 8 | +35.54 |
| metal | 22 | 8 | +47.05 |
| crypto | 68 | 22 | +50.26 |

### Out-of-sample by market

| Symbol | Class | Trades | Wins | Net P&L EUR |
| --- | --- | ---: | ---: | ---: |
| AES | stock_us | 3 | 1 | -35.23 |
| ETC-USD | crypto | 6 | 0 | -24.63 |
| A | stock_us | 5 | 0 | -21.08 |
| ETH-USD | crypto | 4 | 0 | -16.25 |
| SI_F | metal | 4 | 0 | -15.18 |
| ADA-USD | crypto | 4 | 0 | -14.83 |
| SAP.DE | stock_eu | 3 | 0 | -11.90 |
| ES_F | index_us | 3 | 0 | -11.88 |
| AIR.PA | stock_eu | 4 | 1 | -11.24 |
| AVGO | stock_us | 3 | 0 | -10.95 |
| MBG.DE | stock_eu | 2 | 0 | -10.65 |
| AWK | stock_us | 2 | 0 | -9.52 |
| LTC-USD | crypto | 2 | 0 | -9.43 |
| MC.PA | stock_eu | 5 | 1 | -9.05 |
| ACN | stock_us | 3 | 0 | -8.78 |
| ERIE | stock_us | 2 | 0 | -8.48 |
| ADI | stock_us | 3 | 0 | -8.32 |
| AVAX-USD | crypto | 2 | 0 | -7.79 |
| APO | stock_us | 2 | 0 | -7.78 |
| TTE.PA | stock_eu | 2 | 0 | -7.72 |
| INGA.AS | stock_eu | 2 | 0 | -7.69 |
| BMW.DE | stock_eu | 3 | 1 | -7.69 |
| OR.PA | stock_eu | 2 | 0 | -7.65 |
| AKAM | stock_us | 2 | 0 | -6.23 |
| MA | stock_us | 1 | 0 | -5.94 |
| AXON | stock_us | 1 | 0 | -5.83 |
| RB_F | energy | 4 | 1 | -5.35 |
| RTY_F | index_us | 3 | 1 | -5.17 |
| BAS.DE | stock_eu | 4 | 1 | -5.10 |
| BBY | stock_us | 1 | 0 | -4.83 |
| RSG | stock_us | 1 | 0 | -4.74 |
| ADSK | stock_us | 1 | 0 | -4.70 |
| BA | stock_us | 1 | 0 | -4.69 |
| TPL | stock_us | 1 | 0 | -4.60 |
| CVS | stock_us | 1 | 0 | -4.60 |
| DTE.DE | stock_eu | 4 | 1 | -4.59 |
| TKO | stock_us | 1 | 0 | -4.54 |
| BF.B | stock_us | 1 | 0 | -4.51 |
| CDNS | stock_us | 1 | 0 | -4.49 |
| BIIB | stock_us | 1 | 0 | -4.48 |
| ALV.DE | stock_eu | 6 | 2 | -4.47 |
| ALGN | stock_us | 1 | 0 | -4.44 |
| SU.PA | stock_eu | 1 | 0 | -4.31 |
| FICO | stock_us | 1 | 0 | -4.18 |
| IQV | stock_us | 1 | 0 | -4.17 |
| CSCO | stock_us | 1 | 0 | -4.14 |
| ADBE | stock_us | 1 | 0 | -4.06 |
| INVH | stock_us | 1 | 0 | -4.05 |
| SAN.PA | stock_eu | 1 | 0 | -4.04 |
| ATO | stock_us | 1 | 0 | -4.01 |
| APD | stock_us | 1 | 0 | -3.96 |
| NOC | stock_us | 1 | 0 | -3.93 |
| SIE.DE | stock_eu | 1 | 0 | -3.89 |
| YM_F | index_us | 1 | 0 | -3.85 |
| XLM-USD | crypto | 1 | 0 | -3.79 |
| CMCSA | stock_us | 1 | 0 | -3.77 |
| LLY | stock_us | 1 | 0 | -3.62 |
| HUM | stock_us | 1 | 0 | -3.55 |
| BMY | stock_us | 1 | 0 | -3.54 |
| DOGE-USD | crypto | 1 | 0 | -3.43 |
| CHRW | stock_us | 1 | 0 | -3.41 |
| BKR | stock_us | 1 | 0 | -3.39 |
| CDW | stock_us | 1 | 0 | -3.39 |
| DVA | stock_us | 1 | 0 | -3.37 |
| SCHW | stock_us | 1 | 0 | -3.34 |
| AXP | stock_us | 1 | 0 | -3.34 |
| AVY | stock_us | 1 | 0 | -3.30 |
| AFL | stock_us | 1 | 0 | -3.30 |
| APA | stock_us | 1 | 0 | -3.25 |
| ULTA | stock_us | 1 | 0 | -3.13 |
| AIG | stock_us | 2 | 1 | -3.02 |
| XRP-USD | crypto | 3 | 1 | -2.73 |
| NEAR-USD | crypto | 2 | 1 | -2.59 |
| ADM | stock_us | 2 | 1 | -2.40 |
| DE | stock_us | 1 | 0 | -1.73 |
| AEP | stock_us | 2 | 1 | +0.05 |
| APP | stock_us | 1 | 1 | +0.56 |
| AIZ | stock_us | 1 | 1 | +1.34 |
| BNB-USD | crypto | 7 | 2 | +1.67 |
| AAPL | stock_us | 5 | 2 | +2.04 |
| AMGN | stock_us | 1 | 1 | +2.19 |
| AON | stock_us | 1 | 1 | +2.31 |
| ASML.AS | stock_eu | 2 | 1 | +3.03 |
| GLW | stock_us | 1 | 1 | +3.15 |
| DOT-USD | crypto | 3 | 2 | +3.71 |
| RCL | stock_us | 1 | 1 | +3.98 |
| WSM | stock_us | 1 | 1 | +4.08 |
| CASY | stock_us | 2 | 1 | +4.97 |
| TRX-USD | crypto | 2 | 1 | +5.07 |
| DG | stock_us | 1 | 1 | +5.34 |
| ABT | stock_us | 3 | 1 | +6.54 |
| HG_F | metal | 8 | 3 | +8.07 |
| ABBV | stock_us | 4 | 1 | +9.17 |
| CBOE | stock_us | 1 | 1 | +9.59 |
| BSX | stock_us | 1 | 1 | +10.36 |
| FTNT | stock_us | 1 | 1 | +11.61 |
| CHTR | stock_us | 1 | 1 | +12.22 |
| HO_F | energy | 5 | 3 | +12.43 |
| NG_F | energy | 5 | 3 | +13.44 |
| AI.PA | stock_eu | 3 | 1 | +13.74 |
| GEN | stock_us | 1 | 1 | +14.48 |
| ADP | stock_us | 1 | 1 | +14.51 |
| BZ_F | energy | 2 | 1 | +15.03 |
| AD.AS | stock_eu | 5 | 2 | +15.28 |
| AMD | stock_us | 3 | 1 | +16.45 |
| ATOM-USD | crypto | 8 | 2 | +16.49 |
| ALGO-USD | crypto | 2 | 1 | +16.74 |
| AAVE-USD | crypto | 6 | 3 | +17.59 |
| FSLR | stock_us | 2 | 1 | +19.89 |
| CTSH | stock_us | 1 | 1 | +20.45 |
| BR | stock_us | 1 | 1 | +22.38 |
| LINK-USD | crypto | 2 | 2 | +24.03 |
| BCH-USD | crypto | 10 | 5 | +24.76 |
| SOL-USD | crypto | 3 | 2 | +25.66 |
| KO | stock_us | 1 | 1 | +30.81 |
| BAYN.DE | stock_eu | 3 | 2 | +38.95 |
| F | stock_us | 1 | 1 | +45.32 |
| GC_F | metal | 10 | 5 | +54.15 |

### Tradable symbols

A, AAPL, AAVE-USD, ABBV, ABNB, ABT, ACGL, ACN, AD.AS, ADA-USD, ADBE, ADI, ADM, ADP, ADSK, AEE, AEP, AES, AFL, AI.PA, AIG, AIR.PA, AIZ, AJG, AKAM, ALB, ALGN, ALGO-USD, ALL, ALLE, ALV.DE, AMAT, AMCR, AMD, AME, AMGN, AMP, AMT, AMZN, ANET, AON, AOS, APA, APD, APH, APO, APP, APTV, ARE, ARES, ASML.AS, ATO, ATOM-USD, AVAX-USD, AVGO, AVY, AWK, AXON, AXP, AZO, BA, BAC, BALL, BAS.DE, BAX, BAYN.DE, BBY, BCH-USD, BDX, BE, BEN, BF.B, BG, BIIB, BKNG, BKR, BLK, BMW.DE, BMY, BNB-USD, BNY, BR, BRK.B, BRO, BSX, BTC-USD, BX, BXP, BZ_F, C, CAH, CARR, CASY, CAT, CB, CBOE, CBRE, CCI, CCL, CDNS, CDW, CEG, CF, CFG, CHD, CHRW, CHTR, CI, CIEN, CINF, CL, CLX, CL_F, CMCSA, CME, CMG, CMI, CMS, CNC, CNP, COF, COHR, COIN, COO, COP, COR, COST, CPAY, CPRT, CPT, CRH, CRL, CRM, CRWD, CSCO, CSGP, CSX, CTAS, CTSH, CVNA, CVS, CVX, D, DAL, DASH, DD, DDOG, DE, DECK, DELL, DG, DGX, DHI, DHR, DIS, DLR, DLTR, DOC, DOGE-USD, DOT-USD, DOV, DOW, DPZ, DRI, DTE, DTE.DE, DUK, DVA, DVN, DXCM, EBAY, ECHO, ECL, ED, EFX, EG, EIX, EL, ELV, EME, EMR, EOG, EQIX, EQT, ERIE, ES, ESS, ES_F, ETC-USD, ETH-USD, ETN, ETR, EVRG, EW, EXC, EXE, EXPD, EXPE, EXR, F, FANG, FAST, FCX, FDS, FDX, FDXF, FE, FERG, FFIV, FICO, FIS, FISV, FITB, FIX, FLEX, FOX, FOXA, FRT, FSLR, FTNT, FTV, GC_F, GD, GDDY, GE, GEHC, GEN, GILD, GIS, GL, GLW, GM, GNRC, GOOG, GOOGL, GPC, GPN, GRMN, GS, GWW, HAL, HAS, HBAN, HCA, HD, HG_F, HIG, HII, HLT, HON, HONA, HOOD, HO_F, HPE, HPQ, HRL, HSIC, HST, HSY, HUBB, HUM, HWM, IBKR, IBM, ICE, IDXX, IEX, IFF, ILMN, INCY, INGA.AS, INTC, INTU, INVH, IP, IQV, IR, IRM, ISRG, IT, ITW, IVZ, J, JBHT, JBL, JCI, JKHY, JNJ, JPM, KDP, KEY, KEYS, KHC, KIM, KKR, KLAC, KMB, KMI, KO, KR, L, LDOS, LEN, LH, LHX, LII, LIN, LINK-USD, LITE, LLY, LMT, LNT, LOW, LRCX, LTC-USD, LULU, LUV, LVS, LYB, LYV, MA, MAA, MAR, MAS, MBG.DE, MC.PA, MCD, MCHP, MCK, MCO, MDLZ, MDT, MET, META, MGM, MKC, MLM, MMM, MNST, MO, MOS, MPC, MPWR, MRK, MRNA, MRSH, MRVL, MS, MSCI, MSFT, MSI, MTB, MTD, MU, NAS100, NCLH, NDAQ, NDSN, NEAR-USD, NEE, NEM, NFLX, NG_F, NI, NKE, NOC, NOW, NQ_F, NRG, NSC, NTAP, NTRS, NUE, NVDA, NVR, NWS, NWSA, NXPI, O, ODFL, OKE, OKTA, OMC, ON, OR.PA, ORCL, ORLY, OTIS, OXY, P, PANW, PAYX, PCAR, PCG, PEG, PEP, PFE, PFG, PG, PGR, PH, PHIA.AS, PHM, PKG, PLD, PLTR, PM, PNC, PNR, PNW, PODD, PPG, PPL, PRU, PSA, PSX, PTC, PWR, PYPL, Q, QCOM, RB_F, RCL, REG, REGN, RF, RJF, RL, RMD, ROK, ROL, ROP, ROST, RSG, RTX, RTY_F, RVTY, SAN.PA, SAP.DE, SBAC, SBUX, SCHW, SHW, SIE.DE, SI_F, SJM, SKYD, SLB, SMCI, SNA, SNDK, SNPS, SO, SOL-USD, SPG, SPGI, SRE, STE, STLD, STT, STX, STZ, SU.PA, SW, SWK, SWKS, SYF, SYK, SYY, T, TDG, TDY, TECH, TEL, TER, TFC, TGT, TJX, TKO, TMO, TMUS, TPL, TPR, TRGP, TRMB, TROW, TRV, TRX-USD, TSCO, TSLA, TSN, TT, TTE.PA, TTWO, TWLO, TXN, TXT, TYL, UAL, UBER, UDR, UHS, ULTA, UNH, UNP, UPS, URI, US30, US500, USB, V, VEEV, VICI, VLO, VLTO, VMC, VMRK, VRSK, VRSN, VRT, VRTX, VST, VTR, VTRS, VYLR, VZ, WAB, WAT, WDAY, WDC, WEC, WELL, WFC, WM, WMB, WMT, WRB, WSM, WST, WTW, WY, WYNN, XEL, XLM-USD, XOM, XRP-USD, XYL, XYZ, YM_F, YUM, ZBH, ZBRA, ZTS

### Excluded symbols

- **volume_missing** (52): AUDCAD, AUDCHF, AUDJPY, AUDNZD, AUDUSD, AUS200, CADCHF, CADJPY, CHFJPY, EU50, EURAUD, EURCAD, EURCHF, EURGBP, EURJPY, EURNOK, EURNZD, EURPLN, EURSEK, EURTRY, EURUSD, FRA40, GBPAUD, GBPCAD, GBPCHF, GBPJPY, GBPNZD, GBPUSD, GBPZAR, GER40, HK50, JP225, NZDCAD, NZDCHF, NZDJPY, NZDUSD, UK100, US2000, USDCAD, USDCHF, USDCNH, USDDKK, USDHKD, USDHUF, USDJPY, USDMXN, USDNOK, USDPLN, USDSEK, USDSGD, USDTRY, USDZAR

### Download failures

- UNI-USD (UNI-USD): not found
- APT-USD (APT-USD): not found
- GEV (GEV): HTTP 422
- RDDT (RDDT): HTTP 422
- SOLV (SOLV): HTTP 422

### Rejection counts (out-of-sample walk)

- `coordinator:risk:below_min_size`: 1
- `coordinator:risk:max_positions`: 16502
- `coordinator:risk:min_lot_exceeds_risk`: 2
- `coordinator:scout:range_below_threshold`: 284
- `coordinator:scout:volume_below_threshold`: 21394
- `coordinator:skeptic:spread_vs_atr`: 93
- `quality:gap`: 1417
- `quality:outlier_bar`: 117
- `risk:below_min_size`: 2
- `risk:halted`: 367
- `risk:max_positions`: 37755
- `risk:min_lot_exceeds_risk`: 2
- `scout:range_below_threshold`: 284
- `scout:volume_below_threshold`: 21394
- `signal:volatility_not_aligned`: 5864
- `signal:volume_missing`: 4145
- `skeptic:spread_vs_atr`: 146

### Kill switch

- In-sample events: 24
- Out-of-sample events: 8
- Full-sample events: 27

Generated 2026-11-18T16:57:26.847985+00:00

## Completed and still open

Completed in this pass:

- Offline hourly prices with real volume where the vendor has it. The quality gate drops series that do not.
- Session windows, the quality gate, the 500 EUR paper risk rules, and the coordinator.
- Deterministic Scout, charts, news, sentiment, Skeptic, risk and chief on that pipeline. No API key.
- Optional language-model comments via `XAI_API_KEY` and `XAI_MODEL` (default `grok-4`). They are not orders.
- Read-only MT5 demo adapter that refuses non-demo servers and `order_send`.

Still open:

- Dukascopy bid/ask history (the datafeed returned 503 here). Spreads in this run are a model.
- Spot FX and several cash indices, excluded because this source has no volume.
- The owner's MetaQuotes-Demo terminal. It has to be attached on his Mac under Wine.
- A verified news calendar and a social feed. Until those exist, news and sentiment do not vote.
- The continuous paper account lost money. That is not clearance to use the 500 EUR for real.
