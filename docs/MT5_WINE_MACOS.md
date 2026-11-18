# MT5 demo adapter on macOS (Wine)

The scanner's live-data adapter is read-only and demo-only. It never calls `order_send` or `login`. Real and contest accounts are refused, and a server name that does not contain `demo` is refused even if the trade-mode flag looks like a demo.

The official `MetaTrader5` Python package is a Windows extension. It talks to `terminal64.exe` over local Windows IPC, so it has to run inside the **same Wine prefix** as the terminal. macOS Python cannot attach to it.

## 1. Find the Wine prefix

MetaQuotes' Mac installer hides Wine. With the terminal running and logged into **MetaQuotes-Demo** (not a live account):

```bash
ps aux | grep -i '[t]erminal64'
# or
find "$HOME/Library/Application Support" -name 'terminal64.exe' 2>/dev/null
```

The prefix is the directory that contains `drive_c`. A common location is:

```text
~/Library/Application Support/net.metaquotes.wine.metatrader5
```

If `ps` shows a `WINEPREFIX=...` value, use that. Do not create a second prefix: the Python process and the terminal must share one.

## 2. Install Windows Python in that prefix

```bash
PREFIX="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"
curl -L -o /tmp/python-win.exe https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe
WINEPREFIX="$PREFIX" wine /tmp/python-win.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
WINEPREFIX="$PREFIX" wine python -m pip install --upgrade pip
WINEPREFIX="$PREFIX" wine python -m pip install MetaTrader5 pyyaml
```

`python` above is the Windows interpreter Wine just installed (usually under `drive_c/users/<you>/AppData/Local/Programs/Python/Python312/python.exe`). If `wine python` is not found, call that `python.exe` by its full path.

Check:

```bash
WINEPREFIX="$PREFIX" wine python -c "import MetaTrader5; print(MetaTrader5.__version__)"
```

## 3. Log the terminal into the demo, then scan once

1. Open MetaTrader 5 and log in to **MetaQuotes-Demo** only. File → Open an account, or the existing demo login. Do not log into a live server in this prefix.
2. Leave the terminal open. The adapter attaches to that session. It does not receive a login or a password, and it will not switch accounts.
3. From the repo (a path Wine can read; the Mac home directory is usually `Z:`):

```bash
cd /path/to/grok-trading-desk
WINEPREFIX="$PREFIX" wine python -m scanner scan --feed mt5 --once
```

If `initialize` cannot find the terminal, pass the Windows path:

```bash
WINEPREFIX="$PREFIX" wine python -m scanner scan --feed mt5 --once \
  --terminal-path "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
```

What the adapter does:

- `symbols_get()` discovers the whole demo list (the owner's terminal log shows about 12,213 symbols). Metadata is cached as JSON for 24 hours.
- It does **not** subscribe to all of them. Each cycle rotates a batch (`max_history_requests_per_cycle`, default 400), calls `symbol_select` only for that batch, then `symbol_select(name, False)` when it is done, so Market Watch and RAM stay small on an 8 GB Mac.
- History requests are `copy_rates_from_pos` for H1. The forming hour is dropped.
- `order_send` and `login` on the MT5 module are replaced with functions that raise `LiveOrderRefused`.

## 4. Optional idle loop

```bash
WINEPREFIX="$PREFIX" wine python -m scanner scan --feed mt5 --loop
```

Outside session windows the process sleeps. It does not poll quotes all weekend. This is still a foreground process you start yourself, not a 24/7 service.

## 5. What not to do

- Do not `pip install MetaTrader5` into macOS Python and expect it to connect.
- Do not point this adapter at a live account "just to read". The guard shuts the terminal connection down.
- Do not remove the guard to place a real order. There is no live order API in this repo. The paper broker is the only fill path, and the 500 EUR figure is paper equity.
- Offline historical runs do not need Wine:

```bash
python -m scanner download --cache data/cache
python -m scanner simulate --cache data/cache --report reports/simulation_report.md
```

Those commands are the ones that run in CI and on a machine without MT5.
