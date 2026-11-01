# Grok Trading Desk × FabioQuant — figure geometriche e confronto esplorativo

**Data:** 1 novembre 2026. **Branch isolato:** `research/pattern-features-offline-2026-11-01`.

## Intervento completato

- `agents/geometry_features.py`: 18 etichette di **candidati geometrici descrittivi** (non riconoscimento certificato di figure perfette): double/triple top e bottom, head-and-shoulders/inverso, triangoli ascendente/discendente/simmetrico, wedge crescente/decrescente, rettangolo, canali, flag e pennant.
- I pivot richiedono **due candele già chiuse** a destra del massimo/minimo; nessun pivot viene confermato dalla candela più recente.
- `agents/pattern_features.py`: integra in ognuna delle quattro osservazioni giornaliere i dati prezzo, notizie, candele e candidati geometrici, su **25 candele orarie precedenti l'istante di origine**; non espone esiti futuri.
- `tests/test_geometry_features.py`: verifica con dati sintetici pivot, doppi massimi e minimi, monotonicità, integrità dei prezzi e assenza di azioni operative.
- `scripts/pattern_ablation_11day.py`: **confronto retrospettivo offline**, senza dipendenze da exchange, senza nuove acquisizioni né API AI e senza modifica a FabioQuant.

### Limiti delle figure geometriche

I disegni di riferimento sono schemi didattici. Gli algoritmi attuali cercano **somiglianze geometriche** con tolleranze fisse, non rilevano un vantaggio di mercato e non producono ordini, livelli TP/SL o suggerimenti operativi.

Per figure complesse come la testa-spalle e i pennant il rilevatore può non individuare candidati in un campione breve: lo stato `false` è corretto. Le figure non sono state confermate manualmente, una per una, contro grafici reali etichettati da esperti.

La categorizzazione crescente/decrescente non corrisponde automaticamente alla direzione del movimento futuro. I trendline pattern possono sovrapporsi. **Due conteggi** descrittivi (numero di forme di candele e numero di candidati geometrici) sono usati nel confronto per evitare di addestrare 27 pesi su appena 44 righe.

## Verifica retrospettiva 11 giorni già disponibili

**Fonte:** i report derivati *privati* FabioQuant del 10–20 luglio 2024, con JSON Coinbase BTC-EUR/ETH-EUR. Le 44 origini sono due orari fissi al giorno (12:00 e 18:00 UTC) × due mercati.

Il loader rilegge le pagine Coinbase, confronta gli SHA256 indicati nei report, estrae 25 candele orarie che risultano già chiuse e calcola i pattern. Gli esiti futuri vengono letti **solo per la fase successiva di valutazione**.

| Indicatore | Osservato |
| --- | ---: |
| Osservazioni storiche disponibili | 44 |
| Con almeno un flag di candela | 23 |
| Con almeno un candidato geometrico | 31 |
| Confronto walk-forward, 15–20 luglio | 24 osservazioni |
| Modello baseline | 4 caratteristiche prezzo + 2 notizie |
| Modello esteso | stesse 6 caratteristiche + 2 conteggi pattern |

**Modellazione fissa:** regressione logistica regolarizzata, penalty=1, 1000 passi, learning rate=0.05; scaling mediana/MAD appreso soltanto sulle righe passate; parametri invariati tra baseline ed esteso; no tuning.

### Walk-forward espansivo: 24 osservazioni retrospettive

| Indicatore | Baseline prezzo+notizie | + Pattern |
| --- | ---: | ---: |
| Brier (minore è meglio) | **0.385229** | 0.404381 |
| Log loss | **1.141000** | 1.198010 |
| Direzioni corrette | 11/24 | 11/24 |

**Differenza Brier (baseline meno pattern): −0.019152**: nel campione il modello esteso ha errore maggiore.

### Ultimi due giorni (già osservati in precedenti ricerche): 8 osservazioni

| Indicatore | Baseline | + Pattern |
| --- | ---: | ---: |
| Brier | **0.188414** | 0.192392 |
| Log loss | **0.555696** | 0.561378 |
| Direzioni corrette | 6/8 | 6/8 |

Questa seconda verifica NON costituisce un holdout veramente incontaminato: le date sono state analizzate in precedenza.

## Riproduzione senza pubblicare i dati

I file locali restano fuori dal repository pubblico. In una cartella privata non tracciata, ciascun giorno ha tre file:

- `2024-07-DD-derived.json`
- `2024-07-DD-btc-eur.json`
- `2024-07-DD-eth-eur.json`

Per verificare, dalla radice del branch:

```bash
python3 -m unittest discover -s tests -p 'test_fabioquant_offline.py' -v
python3 -m unittest discover -s tests -p 'test_pattern_features.py' -v
python3 -m unittest discover -s tests -p 'test_geometry_features.py' -v
python3 -m scripts.pattern_ablation_11day --data-dir /percorso/privato/11day
```

Il comando di confronto stampa un JSON e **non salva** output sul repository. Il branch `main`, i repository FabioQuant, i manifesti e gli archivi GDELT rimangono invariati.

### Interpretazione e prossimo test

- Le 44 osservazioni non dimostrano un vantaggio predittivo e non sono test economicamente realistici. News disponibili solo con proxy temporale di 30 minuti, non primo timestamp pubblico certificato.
- L'ablation usa un solo set fisso di definizioni e non seleziona a posteriori quelle che sembrano favorevoli. Nessuna significatività statistica o profitto netto dimostrato.
- L'unica verifica indipendente futura sarebbe **prospettica**: raccogliere letture di prezzi e notizie timestampate, congelare le previsioni prima di vedere il risultato e confrontarle senza trading.
- Per passare da candidati a rilevatori affidabili servono test di precisione/richiamo su grafici annotati, controlli su timeframe differenti, sensibilità a tolleranza e falsi positivi. Evitare di utilizzare il campione di 11 giorni per scegliere retroattivamente una strategia.
