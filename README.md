# Grok Trading Desk

Multi-agent paper desk. **No live orders.** Nothing here is financial advice.

The original desk (`python main.py`) still asks the language-model agents, and it needs `XAI_API_KEY`. The scanner below does not: Scout, Skeptic, the risk agent and the coordinator used by the scanner are deterministic, so a backtest can be repeated.

## Scanner multi-mercato

Lo scanner gira solo in finestra di sessione e manda i candidati al team, che li può bocciare. Il conto di carta è **500 EUR**. Non esiste un percorso per ordini reali: `order_send` e `login` sull'adattatore MT5 vengono sostituiti con funzioni che alzano `LiveOrderRefused`, e un conto che non è demo (oppure un server il cui nome non contiene `demo`) chiude la connessione.

### Mercati

- **Conto demo MT5:** l'universo è l'intera lista del terminale (`symbols_get`), non una lista da 10–30 simboli. Sul MetaQuotes-Demo del proprietario sono circa 12.213 strumenti: forex, metalli, indici, energie, crypto CFD, azioni. La scoperta è dinamica; i metadati finiscono in una cache JSON (24 ore).
- **Imbuto, per non saturare un Mac M2 da 8 GB:** (1) tradabile e sessione aperta adesso, (2) un lotto a rotazione (default 400 richieste di storico per ciclo) con spread, tick e liquidità, (3) volume e volatilità allineati alla loro norma recente, (4) solo quelli arrivano a Scout, al rischio, allo scettico e al coordinatore. I simboli scartati vengono deselezionati dal Market Watch (`symbol_select` false).
- **Simulazione offline:** il sottoinsieme che si riesce a scaricare gratis. In questo ambiente il datafeed Dukascopy rispondeva 503, quindi la storia usata è Yahoo Finance, candele orarie, circa due anni, per l'S&P 500, futures su indici/metalli/energie, i principali indici cash, crypto e un paniere di azioni EUR, più il forex spot. Il forex spot Yahoo non ha volume: il quality gate lo scarta invece di inventare un volume. L'elenco esatto di cosa è stato simulato e di cosa è stato escluso sta in `reports/simulation_report.md`.

### Finestre temporali

Le finestre sono in `config/scanner.yaml`, in ora locale della borsa, con l'ora legale di Londra/Europa, New York, Tokyo, Hong Kong e Sydney. Fuori finestra lo scanner non chiede storico.

Regole spedite con il repo (si possono sostituire per simbolo):

| Classe | Quando si cercano ingressi |
| --- | --- |
| Forex major, cross, metalli | Lun–Ven 08:00–17:00 ora di Londra. Il weekend FX è quello di New York (venerdì 17:00 → domenica 17:00). |
| Coppie JPY | Anche la sessione di Tokyo, 09:00–15:00 ora di Tokyo. |
| Esotici | Londra 08:00–16:00, spread tollerato più stretto a valle. |
| Indici e azioni USA | 09:35–15:45 ora di New York (salta l'asta di apertura e quella di chiusura). |
| Indici e azioni Europa | 09:15–17:15 ora di Europa. |
| Asia (default Tokyo) | 09:15–15:00. `HK50` / `HSI` e `AUS200` / `AU200` hanno un override. |
| Energie | 09:00–14:30 ora di New York. |
| Crypto | 07:00–21:00 UTC, weekend compreso. Il resto della giornata resta fermo. |
| Classe sconosciuta | Mai. Nessun simbolo senza classificazione viene tradato. |

Il rollover FX (16:55–17:15 ora di New York) è sempre chiuso per le classi che ce l'hanno, anche se una finestra override sarebbe aperta. Un calendario news è opzionale (`scanner/news_calendar.py`, CSV `time_utc,currency,impact,title`): se il file non c'è, il filtro news non inventa eventi e non blocca; se c'è, un high-impact a ±30 minuti sulle valute del simbolo è un veto.

In più, l'ATR deve stare fra 0.75× e 1.80× della sua mediana recente e lo spread modellato (o quello vero, se il feed lo dà) non può superare il 20% dell'ATR.

### Quality gate

Prima che il team veda un candidato, il gate scarta e registra il motivo: dati stantii, buchi dentro la sessione, timestamp duplicati o non monotoni, prezzi non finiti o negativi, barre con range oltre 10 ATR, spread nullo o enorme rispetto all'ATR, serie senza volume vero (non viene inventato), segnali la cui origine non è il prezzo, segnali doppi o in conflitto sullo stesso simbolo e sulla stessa barra. Scout vuole un volume di almeno 1,5× la mediana delle 20 barre precedenti e un range di almeno 0,6 ATR. Il timeframe superiore (4 barre chiuse, senza attraversare un buco) deve essere d'accordo con il breakout Donchian a 20 barre. Se manca anche uno tra Scout, scettico, rischio e coordinatore, l'ordine non parte.

### Rischio (conto di carta da 500 EUR)

- Rischio per trade: 0,75% (dentro la banda 0,5–1%).
- Perdita giornaliera massima: 3% del capitale a inizio giornata. Scatta il fermo fino al giorno UTC dopo, e le posizioni si chiudono.
- Kill switch: equity a 400 EUR o meno (20% sotto i 500 iniziali) chiude tutto e non riapre.
- Massimo 2 posizioni, rischio aperto complessivo 2%, leva lorda 5. Se la size minima supererebbe 1,25× il budget, il trade si salta.

I costi nel backtest: spread in basis point per classe (i prezzi Yahoo sono last/mid, lo spread non è nel file), slippage 0,25 spread per lato, commissione 0,35 bp per lato. Lo stop che buca in gap viene eseguito all'open, non al livello. La size è da CFD (1 unità di valuta del profitto per 1 punto di prezzo), non il moltiplicatore di un future di borsa: con 500 EUR un contratto ES intero non è un trade realistico.

### Come si lancia

```bash
pip install -r requirements.txt

# Storia gratuita e backtest (nessun MT5, nessun API key)
python -m scanner download --cache data/cache
python -m scanner simulate --cache data/cache --report reports/simulation_report.md

# Una scansione sulla cache, a un'ora precisa
python -m scanner scan --feed offline --at 2026-01-14T15:00:00+00:00

# Terminale demo sotto Wine sul Mac. Istruzioni complete:
# docs/MT5_WINE_MACOS.md
python -m scanner scan --feed mt5 --once
```

`python -m scanner scan --feed mt5 --loop` dorme fuori dalle finestre. Non è un processo 24/7: va avviato a mano e non manda ordini.

I test:

```bash
python -m pytest tests -q
```

Coprono le finestre (inclusa l'ora legale), il quality gate, il rifiuto degli ordini live, la rotazione sull'universo intero e l'assenza di lookahead.

Il risultato del backtest, in-sample contro out-of-sample, sta in `reports/simulation_report.md`. Va letto così com'è, anche se è negativo: le regole sono quelle fissate in `config/scanner.yaml` prima del run, non una curva adattata al campione.

## Desk originale (modello linguistico)

- Scout: anomalie
- News: notizie
- Charts: livelli
- Sentiment: umore
- Skeptic: obiezioni
- Chief: decisione finale

```bash
export XAI_API_KEY=your_key
python main.py
```

`python main.py` ora esegue lo stesso scanner sulla cache reale (`data/cache`, ultime 400 barre per simbolo). Non chiede una API key. Scout, Charts, News, Sentiment, Skeptic, il rischio e il coordinatore leggono quei prezzi:

- Scout, Skeptic, rischio e coordinatore decidono in modo deterministico.
- Charts riporta entry e stop del segnale sul prezzo chiuso. Non c'è un target: l'uscita è a tempo.
- News resta vuoto se non c'è un calendario verificato. Non inventa titoli.
- Sentiment non ha un feed social: il punteggio è `null` e non è un voto.
- Se `XAI_API_KEY` è una chiave vera, gli stessi fatti (niente stringhe finte) vanno al modello `XAI_MODEL` (default `grok-4`, `grok-beta` non si usa più). Il testo è un commento. Non modifica l'ordine di carta e non può diventare un ordine live.

## Fatto e ancora aperto

Fatto in questo repo:

- Feed storico offline con prezzi orari reali (Yahoo, circa due anni, 605 simboli scaricati). Il quality gate tiene 553 serie con volume e scarta 52 senza volume, tra cui tutto il forex spot e diversi indici cash.
- Finestre di sessione, ora legale, rollover, override per simbolo.
- Quality gate con motivo di ogni scarto.
- Rischio sul conto di carta da 500 EUR: 0,75% a trade, stop giornaliero 3%, kill switch sotto 400 EUR.
- Coordinatore solo `paper_buy` / `paper_sell` / `hold`.
- Adattatore MT5 di sola lettura, con rifiuto dei conti non demo e di `order_send` / `login`.
- Backtest con costi, senza lookahead, in-sample / out-of-sample / percorso continuo. Il percorso continuo perde. I numeri sono in `reports/simulation_report.md`.

Ancora aperto, di proposito:

- Dukascopy (bid/ask) non rispondeva (HTTP 503). Gli spread del backtest sono un modello, non il book del broker.
- Il terminale MetaQuotes-Demo non è collegato da questa macchina. Va lanciato sul Mac dentro Wine, come in `docs/MT5_WINE_MACOS.md`.
- Nessun calendario news e nessun feed social verificati. Quei due agenti non votano.
- Il commento del modello linguistico non è stato eseguito qui (niente chiave) e non è un permesso a operare.
- Il risultato continuo è negativo: non è una base per i 500 EUR veri.

Quel percorso del desk, se chiamato senza cache, si ferma con `NO_CACHE` invece di inventare un mercato.
