# Catalogo dei pattern dalle quattro immagini — FabioQuant x Grok (1 novembre 2026)

## Stato e origine

Questa è una trascrizione **interpretativa e normalizzata** dei quattro poster
grafici allegati dall'utente. I nomi dei pattern sono nozioni tecniche
generiche; **nessuna copia delle immagini viene pubblicata** nel repository.
Non sono osservazioni statistiche e non provano un vantaggio predittivo.

Il branch di ricerca `research/pattern-features-offline-2026-11-01`
rimane distinto da `main` e dal repository privato FabioQuant.

## Inventario, deduplicazione e priorità

| Gruppo normalizzato | Presenza nei poster | Implementazione |
| --- | --- | --- |
| Doji, hammer, shooting star, engulfing bullish/bearish, inside bar | Poster candele (terza immagine) | Fase A: riconoscimento di *forme* su OHLCV completato |
| Three rising/falling bodies | Poster candele (tre white soldiers/black crows) | Fase A: solo componente grossolana di tre corpi concordi; **NON** identificazione certificata dei pattern canonici |
| Morning/evening star, harami, piercing, tweezers, marubozu, gap patterns, 3-methods | Poster candele | Non implementati; richiedono definizioni causali e spesso contesto/gap non adatti a crypto 24/7 |
| Double top/bottom, triple top/bottom | Poster 1, 2, 3, 4 | Fase B: pivot confermati, livello di breakout, tolleranza ATR, profondità |
| Head & shoulders, inverso | Poster 1, 2, 3, 4 | Fase B: tre pivot coerenti, neckline, conferma, no barre future |
| Ascending/descending/symmetrical triangle | Poster 1, 2, 3, 4 | Fase B: almeno due massimi/minimi confermati per trendline, breakout |
| Bull/bear flag e pennant | Poster 1, 2, 3, 4 | Fase B: impulso preliminare, consolidamento e risoluzione |
| Rising/falling wedge | Poster 1, 2, 3, 4 | Fase B: linee convergenti e contesto di trend |
| Bull/bear rectangle, channel | Poster 2, 3, 4 | Fase B: multipli tocchi con tolleranza e durata minima |
| Cup & handle, rounding top/bottom | Poster 2, 3 | Fase C: geometria di lungo periodo e controllo della durata |
| Megaphone, diamond, Livermore cylinder | Poster 4 | Fase C: definizioni non uniformi da formalizzare |
| Gartley, Cypher | Poster 4 | Fase C: rapporti armonici e pivot causali, alto rischio di fitting |

Un nome ripetuto in più poster corrisponde a **una** sola definizione
algoritmica, non a più voti o evidenze statistiche indipendenti.

## Incongruenze nei poster: attenzione alle etichette

- Il triangolo ascendente è mostrato come bullish in alcuni poster e
  come neutrale/bilaterale in altri; analogamente quello discendente.
- Le wedge possono essere catalogate come inversione o continuazione a
  seconda del trend precedente: non stabilire la direzione dalla forma sola.
- I poster raffigurano ENTRY / SL / TP in modo illustrativo; tali linee non
  sono policy validate e **non devono essere trascritte in ordini**.
- Il volume e il contesto contano: stessi segmenti grafici possono apparire
  in mercati laterali, fortemente volatili o rumorosi.
- Alcune varianti delle figure possono essere descrizioni imprecise del
  disegno schematico; i criteri matematici devono prevalere sui titoli.

## Cosa è stato implementato oggi (FASE A)

`agents/pattern_features.py`:
- Legge *localmente* i due JSON grezzi orari Coinbase (BTC-EUR, ETH-EUR)
  e il report derivato verificato di FabioQuant per **una giornata**.
- Confronta SHA-256 dei JSON orari con gli hash riportati nel report derivato.
- Per ciascuna delle quattro origini (12:00 e 18:00 UTC × 2 mercati)
  richiede **25 candele orarie consecutive già terminate**.
- Filtra con `open_time < origin` e `close_time <= origin`, prima di
  leggere i prezzi. Niente etichette del futuro, niente rietichettatura.
- Rileva esclusivamente le forme semplici: doji, hammer, shooting star,
  bullish/bearish engulfing, inside/outside bar e tre corpi rialzisti o
  ribassisti consecutivi. Tutti i flag sono osservazioni descrittive.
- Integra ogni record con le quattro feature prezzo e due feature news
  già derivate da FabioQuant. Il valore futuro `label` **non compare**
  nell'output, che rimane un report locale JSON.
- Non esegue inferenza Grok, machine learning, download, scambi,
  notifiche o posizionamento.

Attenzione: `three_rising_bodies` e `three_falling_bodies` **non**
significano riconoscimento automatico dei Three White Soldiers o
Three Black Crows: mancano criteri rigorosi su aperture, ombre e contesto.

### Esecuzione offline con sorgenti locali non committate

```bash
python3 -m unittest discover -s tests -p 'test_pattern_features.py' -v
python3 -m agents.pattern_features \
  --derived /percorso/privato/research_rows_verified.json \
  --btc /percorso/privato/btc-eur.json \
  --eth /percorso/privato/eth-eur.json
```

La CLI produce quattro record JSON su stdout e **non scrive** sul
repository. Eseguire una giornata per volta. Nessuna cartella Drive
viene modificata; evitare di pubblicare gli output.

## Come valuteremo l'aggiunta dei pattern

Questo primo strato è preparazione tecnica, **non training del modello**.
Tre o quattro poster non costituiscono esempi di mercato etichettati;
le 44 osservazioni delle 11 giornate non giustificano la ricerca
estensiva di decine di pattern e iperparametri.

Mantenere intatto il protocollo preregistrato di FabioQuant. In un
esperimento separato e dichiarato esplorativo, confrontare:

1. Baseline probabilistica costante.
2. Prezzi.
3. Notizie.
4. Prezzi + notizie.
5. Prezzi + notizie + pattern **predefiniti**.

La metrica principale, sul periodo esterno realmente nuovo e
pre-registrato, può essere differenza di Brier / log loss, con
copertura, calibrazione, incertezza e costi dichiarati.
L'esperimento di 11 giorni da solo non può attestare un vantaggio.
Non cercare i pattern che casualmente fanno salire l'accuratezza
su quelle 11 giornate; prima valutazione prospettica in osservazione
soltanto, senza operazioni reali.

## Prossimo stadio — figure geometriche

Per ciascuna figura, definire:
- pivot locale confermato solo dopo un ritardo esplicito;
- numero minimo di tocchi, distanza minima in barre, tolleranza ATR;
- trend precedente, pendenza e convergenza delle trendline;
- conferma **a chiusura** già osservata, non linee disegnate usando
  il prezzo posteriore al segnale;
- doppie classificazioni da risolvere con etichette neutre prima
  della conferma;
- test sintetici per falsi positivi, replay causale, dati mancanti,
  sovrapposizioni fra figure.

Non inferire direzione, probabilità, entry, SL o TP direttamente dalle
immagini. I pattern sono candidati a feature, non segnali verificati.
