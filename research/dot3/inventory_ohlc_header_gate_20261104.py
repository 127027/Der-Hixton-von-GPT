#!/usr/bin/env python3
"""Read-only, bounded ZIP OHLC schema inventory. No trading or synthetic candles."""
import argparse, csv, hashlib, io, json, re, sys, zipfile
from pathlib import Path
COINS = ("BTC","ETH","BNB","SOL","XRP","ADA","DOGE","DOT","AVAX","LINK","SUI","NEAR","UNI","AAVE","BCH")
REQUIRED = {"open","high","low","close"}
TIME = {"timestamp","time","open_time","close_time","datetime","date","timestamp_utc"}
def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def audit(path, expected):
    actual=sha256(path)
    if actual != expected: raise ValueError("ARCHIVE_SHA256_MISMATCH")
    out={"status":"SCHEMA_ONLY_NOT_OHLC_VALIDATED","archive_sha256":actual,
         "coins":{c:[] for c in COINS},"candidates":[],"errors":[]}
    with zipfile.ZipFile(path) as z:
        members=z.infolist()
        if len(members)>20000: raise ValueError("TOO_MANY_ZIP_MEMBERS")
        for m in members:
            if m.is_dir(): continue
            name=m.filename
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                out["errors"].append({"path":name,"reason":"UNSAFE_PATH"});continue
            if not name.lower().endswith((".csv",".csv.gz")):continue
            if m.file_size>250*1024*1024: 
                out["errors"].append({"path":name,"reason":"OVERSIZED_CSV"});continue
            # Header-only read: no extraction; cap decompressed bytes.
            try:
                with z.open(m) as f:
                    if name.lower().endswith(".gz"):
                        import gzip
                        stream=gzip.GzipFile(fileobj=f)
                    else:stream=f
                    header=stream.readline(8193)
                if len(header)>8192: raise ValueError("HEADER_TOO_LONG")
                fields=next(csv.reader([header.decode("utf-8-sig")]))
                cols={x.strip().lower() for x in fields}
                schema=REQUIRED.issubset(cols) and bool(TIME & cols)
                coin_hits=[c for c in COINS if re.search(r"(?<![A-Z])"+c+r"(?:USDC|USDT)?(?![A-Z])",name.upper())]
                row={"path":name,"bytes":m.file_size,"crc32":f"{m.CRC:08x}",
                     "columns":fields,"ohlc_schema":schema,"coins_by_filename":coin_hits,
                     "pair_quote_evidence":"USDC" if "USDC" in name.upper() else ("USDT_PROXY_NOT_USDC_LIQUIDITY" if "USDT" in name.upper() else "UNKNOWN")}
                out["candidates"].append(row)
                if schema:
                    for c in coin_hits:out["coins"][c].append(name)
            except Exception as e:out["errors"].append({"path":name,"reason":type(e).__name__+":"+str(e)[:120]})
    out["missing_coin_schema"]=[c for c,v in out["coins"].items() if not v]
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("archive");p.add_argument("--sha256",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        result=audit(a.archive,a.sha256.lower())
        Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"status":result["status"],"missing":result["missing_coin_schema"],"candidates":len(result["candidates"])}))
        return 0
    except Exception as e:
        print(json.dumps({"status":"BLOCKED","reason":str(e)}),file=sys.stderr);return 2
if __name__=="__main__":sys.exit(main())
