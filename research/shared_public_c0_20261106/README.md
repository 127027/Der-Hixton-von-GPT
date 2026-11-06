# Executed shared public C0 core ledger — 2026-11-06
ONE offline normal-cost continuous5year baseline to unblock D1/D2; no candidate sweep.
Window2021-11-05T10:00:00Z–2026-11-05T10:00:00Z; synthetic research seed1000USDC,zero initial coins,full compounding,15public market histories.
Infrastructure8964151000c6ef4c48cfc871de9951e879b9a81a; Python-source fingerprint07ee592e2f50eff1b414551e55b78a1d9cee43047b59184904e04b17d5b73f26. Strategy payload equals frozenf56contract; original reference market rules and current costs.
Result:549fills,274closed trades,43824hourly records; end10190.898943604694USDC,maxDD54.927230308277545%. This is a C0 REFERENCE, not an improved strategy.
EXPLORATORY_DATA_GAPS / comparison UNVERIFIED: later SUI history/warmup,USDTproxies and shared2023-03-24T13UTCoutage retained. No invented candles/orders or capital resets. No account inputs,private results,keys,product database,product changes or exchange access.

## Retrieve once — no repeated financial replay
ledger.zip.b64.part00 through part04 encode a standard ZIP as UTF-8 base64. Archive.json binds every text part and final ZIP.
Reconstruct in a normal checkout/regular offline runtime:
```python
from pathlib import Path
import base64,hashlib,json,io,zipfile
root=Path("research/shared_public_c0_20261106")
m=json.loads((root/"Archive.json").read_text())
parts=[]
for p in m["parts"]:
    b=(root/p["name"]).read_bytes()
    assert hashlib.sha256(b).hexdigest()==p["sha256_text_with_newline"]
    parts.append(b.strip())
raw=base64.b64decode(b"".join(parts),validate=True)
assert len(raw)==m["bytes"] and hashlib.sha256(raw).hexdigest()==m["sha256"]
out=Path("public-c0-core").resolve()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert all((out/n).resolve().is_relative_to(out) for n in z.namelist())
    seal=json.loads(z.read("Complete.json"))
    for n,h in seal["files_sha256"].items():
        assert hashlib.sha256(z.read(n)).hexdigest()==h
    z.extractall(out)
```
ZIP:953865bytes,SHA256 c0522791a31150493ac1f1669ab4138c45831c6ad1eddb18a0615175aaeabb4a.
Part hashes refer to exact LF text as committed; a Windows checkout must not transform these base64part files to CRLF (normalize CRLF to LF before checking if needed). File bytes within ZIP are individually sealed.
Complete archive roundtrip and member hashes verified locally.

## Outputs / scope
Fills.json:all549native fills including fees;Trades.json:all274closed trades;Equity.csv.gz:43824hourly cash,combined marked position value,equity. Cash+positions=equity and cash>=0 checked for every hour. Metrics,Input-Contract,Manifest,DustAtEnd,PendingSignals and exact generating script included.
Signals/blocked-signals remain in the local full run but are excluded from this public CORE distribution;Complete.json says so. Hourly per-position costbasis/units/DD10flags/entrybudgets are not directly exported by this engine. D1/D2 should derive supported facts from fills and market data and explicitly list remaining fields; do not fabricate or make perfect traces a prerequisite for all loss attribution.
Start with actual2021–2023trade-loss attribution and synchronous cash/equity. No account-derived capital has been published.

Independent financial/ledger QA:PENDING. This is not HELD004 integration,METHOD_PASS,a qualified improvement,or a replacement of the original16contexts/gates.
