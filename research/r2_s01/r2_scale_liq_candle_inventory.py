"""Bounded read-only inventory of original historical candles and synthetic NPZ worlds.

No hixton trading engine import, no finance, no writes to source archives.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import gzip
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

HIST_HASH = "d1d1cde8347665d74da71f9e44bb3876dc6662bfe4bfc9e34dcab1dfecd84308"
SYN_HASH = "5262f12bef7182ae10e2c85fe5b790263404764e98e759196dbf7b0970d278"
SYMBOLS = ("BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "LINK", "AVAX", "DOT", "DOGE",
           "SUI", "NEAR", "UNI", "AAVE", "BCH")
HIST_WINDOWS = ("original_32k", "current_26oct", "latest_long")
SYN_WINDOWS = ("cycles", "winter", "whipsaw", "rotation", "tail")


def verify_archive(path: Path, expected: str) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            sha.update(chunk)
    digest = sha.hexdigest()
    if digest != expected:
        raise ValueError(f"ARCHIVE_SHA_MISMATCH: {path.name} {digest}")
    return digest


def member(z: ZipFile, suffix: str) -> str:
    matches = [n for n in z.namelist() if n.endswith(suffix) and not n.startswith("__MACOSX/")]
    if len(matches) != 1:
        raise ValueError(f"MEMBER_AMBIGUOUS_OR_MISSING: {suffix} count={len(matches)}")
    return matches[0]


def sha_member(z: ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with z.open(name) as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if t.tzinfo is None:
            return None
        return t
    except ValueError:
        return None


def series_stats(symbol: str, rows: list, kind: str) -> dict:
    counts = Counter()
    first = last = previous = None
    ts_fallback = False
    for row in rows:
        counts["rows"] += 1
        if not isinstance(row, dict):
            counts["invalid_row"] += 1
            continue
        t = timestamp(row.get("open_time_utc"))
        if t is None:
            counts["missing_invalid_open_time"] += 1
        else:
            if first is None:
                first = t
            last = t
            if previous is not None:
                delta = (t - previous).total_seconds()
                if delta != 3600:
                    if delta > 3600 and delta % 3600 == 0:
                        counts["missing_hour_rows"] += int(delta / 3600) - 1
                    else:
                        counts["noncontiguous_or_out_of_order_pairs"] += 1
            previous = t
        if row.get("symbol") is not None and row["symbol"] != symbol:
            counts["symbol_mismatch"] += 1
        for key in ("volume", "quote_volume", "trade_count"):
            if key not in row or row[key] is None:
                counts[key + "_missing"] += 1
                continue
            try:
                x = float(row[key])
                if not __import__("math").isfinite(x) or x < 0:
                    counts[key + "_invalid"] += 1
                elif x == 0:
                    counts[key + "_zero"] += 1
                else:
                    counts[key + "_positive"] += 1
            except (ValueError, TypeError, OverflowError):
                counts[key + "_invalid"] += 1
        if row.get("source") is not None:
            counts["source:" + str(row["source"])[:100]] += 1
    return dict(symbol=symbol,kind=kind,rows=counts["rows"],first_open_utc=first.isoformat() if first else None,
                last_open_utc=last.isoformat() if last else None,base_volume_unit=symbol.replace("USDC",""),
                quote_volume_unit="declared_quote_asset_USDC_if_verified_else_unknown",
                missing_hour_rows=counts["missing_hour_rows"],
                noncontiguous_or_out_of_order_pairs=counts["noncontiguous_or_out_of_order_pairs"],
                volume_zero=counts["volume_zero"],volume_missing=counts["volume_missing"],
                volume_invalid=counts["volume_invalid"],
                quote_volume_zero=counts["quote_volume_zero"],quote_volume_missing=counts["quote_volume_missing"],
                quote_volume_invalid=counts["quote_volume_invalid"],
                trade_count_zero=counts["trade_count_zero"],trade_count_missing=counts["trade_count_missing"],
                trade_count_invalid=counts["trade_count_invalid"],
                source_counts={k.removeprefix("source:"):v for k,v in counts.items() if k.startswith("source:")},
                invalid_rows=counts["invalid_row"],symbol_mismatch=counts["symbol_mismatch"],
                missing_invalid_open_time=counts["missing_invalid_open_time"],
                input_provenance="ORIGINAL_HISTORICAL_INPUT_VERIFY_PAIR_OR_PROXY_USING_CONTRACT_NOT_MARKET_DEPTH")


def decode_gz_json(z: ZipFile, n: str):
    with z.open(n) as zipped, gzip.GzipFile(fileobj=zipped) as uncompressed:
        return json.load(io.TextIOWrapper(uncompressed, encoding="utf-8"))


def inspect_history(z: ZipFile) -> dict:
    contract_name = member(z, "/Input-Contract.json")
    contract = json.loads(z.read(contract_name))
    records = []
    for window in HIST_WINDOWS:
        spec = contract["windows"][window]
        files = spec["data_files"]
        candidates = [member(z, f"/data/{window}/Candles.json.gz")] if window != "latest_long" else []
        if window == "latest_long":
            for sym in SYMBOLS:
                candidates.append(member(z, f"/data/{window}/{sym}USDC.json.gz"))
        for filename in candidates:
            data = decode_gz_json(z, filename)
            if not isinstance(data, dict):
                raise ValueError(f"EXPECTED_CANDLE_SYMBOL_MAP: {filename}")
            for symbol,rows in sorted(data.items()):
                if not isinstance(rows, list):
                    raise ValueError(f"EXPECTED_CANDLE_ROWS: {window} {symbol}")
                item = series_stats(symbol,rows,"historical")
                item.update(window=window,archive_member=filename,archive_member_sha256=sha_member(z,filename))
                records.append(item)
            del data
    return dict(contract_member=contract_name,contract_sha256=sha_member(z,contract_name),
                contract_source_commit=contract.get("source_commit"),
                contract_windows={w:dict(start=contract["windows"][w].get("start"),
                                         end=contract["windows"][w].get("end"),
                                         data_files=contract["windows"][w].get("data_files"))
                                  for w in HIST_WINDOWS},
                records=records)


def inspect_synthetic(z: ZipFile) -> dict:
    import numpy as np
    name = member(z,"/Input-Contract.json")
    contract = json.loads(z.read(name))
    records=[]
    for window in SYN_WINDOWS:
        spec=contract["windows"][window]
        filenames=spec["data_files"]
        npz_name=member(z,f"/data/{window}/Path.npz")
        manifest_name=member(z,f"/data/{window}/Manifest.json") if any(n.endswith(f"/data/{window}/Manifest.json") for n in z.namelist()) else None
        manifest=json.loads(z.read(manifest_name)) if manifest_name else None
        if manifest is None:
            expected=filenames.get("manifest",{}).get("path","")
            if expected:
                manifest_name=member(z,"/"+expected.lstrip("/"))
                manifest=json.loads(z.read(manifest_name))
        if manifest is None or manifest.get("synthetic_not_forecast") is not True:
            raise ValueError("NOT_DECLARED_SYNTHETIC: "+window)
        symbols=manifest["symbols"]
        if len(symbols)!=15:
            raise ValueError("NOT_FIFTEEN_SYMBOLS: "+window)
        with z.open(npz_name) as reader:
            content=reader.read()
        with np.load(io.BytesIO(content),allow_pickle=False) as data:
            if data.files!=["values"]:
                raise ValueError("BAD_NPZ_FIELDS")
            a=data["values"]
            if a.ndim!=3 or a.shape[1]!=len(symbols) or a.shape[2]!=7:
                raise ValueError("BAD_NPZ_SHAPE")
            first=datetime.fromisoformat(spec["start"])-timedelta(hours=spec["warmup_bars"])
            last=first+timedelta(hours=a.shape[0]-1)
            for j,sym in enumerate(symbols):
                arr=a[:,j,:]
                record=dict(window=window,symbol=sym,kind="synthetic",rows=int(a.shape[0]),
                            first_open_utc=first.isoformat(),last_open_utc=last.isoformat(),
                            archive_member=npz_name,archive_member_sha256=sha_member(z,npz_name),
                            base_volume_unit=sym.removesuffix("USDC"),
                            quote_volume_unit="SYNTHETIC_QUOTE_UNITS_NOT_REAL_SPOT_USDC",
                            volume_zero=int(np.count_nonzero(arr[:,4]==0)),
                            volume_missing=int(np.count_nonzero(~np.isfinite(arr[:,4]))),
                            quote_volume_zero=int(np.count_nonzero(arr[:,5]==0)),
                            quote_volume_missing=int(np.count_nonzero(~np.isfinite(arr[:,5]))),
                            trade_count_zero=int(np.count_nonzero(arr[:,6]==0)),
                            trade_count_missing=int(np.count_nonzero(~np.isfinite(arr[:,6]))),
                            missing_hour_rows=0,synthetic_not_forecast=True,
                            market_depth_present=False)
                records.append(record)
        del content
    return dict(contract_member=name,contract_sha256=sha_member(z,name),records=records)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--historical",type=Path,required=True)
    parser.add_argument("--synthetic",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    hashes=dict(historical=verify_archive(a.historical,HIST_HASH),
                synthetic=verify_archive(a.synthetic,SYN_HASH))
    with ZipFile(a.historical) as z:
        historical=inspect_history(z)
    with ZipFile(a.synthetic) as z:
        synthetic=inspect_synthetic(z)
    report=dict(status="READ_ONLY_CANDLE_VOLUME_INVENTORY_COMPLETED",sha256=hashes,
                historical=historical,synthetic=synthetic,
                limitations=["Candle base/quote volume cannot measure available order book depth or market impact",
                             "Source field and quote pair require original manifest/proxy mapping",
                             "Unknown historical exchangeInfo MAX filters remain UNKNOWN",
                             "Synthetic historical market liquidity is NOT real historic liquidity"],
                market_orders_or_replays=0)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():
        raise RuntimeError("INVENTORY_OUTPUT_EXISTS")
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
    print(json.dumps(dict(status=report["status"],historical_records=len(historical["records"]),
                          synthetic_records=len(synthetic["records"]),sha256=hashes),sort_keys=True))


if __name__=="__main__":
    main()
