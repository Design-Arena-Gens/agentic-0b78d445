import json
import os
import subprocess
import sys
import time
from datetime import datetime

import requests

try:
    import MetaTrader5 as mt5
except Exception as e:
    print("MetaTrader5 module not available. Install dependencies first.")
    raise

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def load_config(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_terminal_running(terminal_path):
    if not terminal_path or not os.path.exists(terminal_path):
        print(f"MT5 terminal not found at {terminal_path}")
        return
    try:
        subprocess.Popen([terminal_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Failed to start terminal: {e}")


def init_mt5(terminal_path, login, password, server):
    if not mt5.initialize(path=terminal_path, login=login, password=password, server=server):
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")


def fetch_candles(symbol, timeframe, bars):
    tf = TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None:
        raise RuntimeError(f"Failed to fetch rates: {mt5.last_error()}")
    candles = []
    for r in rates:
        candles.append({
            "time": int(r['time']),
            "open": float(r['open']),
            "high": float(r['high']),
            "low": float(r['low']),
            "close": float(r['close']),
            "tick_volume": int(r['tick_volume']),
            "volume": int(r['real_volume']) if 'real_volume' in r.dtype.names else 0,
        })
    return candles


def compute_volume(symbol, entry, stop_loss, risk_percent):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError("symbol_info returned None")
    tick_size = info.trade_tick_size or info.point
    tick_value = info.trade_tick_value or 1.0
    balance = mt5.account_info().balance
    risk_amount = balance * (risk_percent / 100.0)

    price_risk = abs(entry - stop_loss)
    if price_risk <= 0:
        return 0.0

    ticks = price_risk / (tick_size if tick_size else 0.00001)
    cost_per_lot = ticks * tick_value
    if cost_per_lot <= 0:
        return 0.0

    raw_lots = risk_amount / cost_per_lot

    vol_min = info.volume_min or 0.01
    vol_max = info.volume_max or 100.0
    vol_step = info.volume_step or 0.01

    stepped = max(vol_min, min(vol_max, (round(raw_lots / vol_step) * vol_step)))
    return round(stepped, 2)


def within_spread_limit(symbol, max_spread_points):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False
    spread = (tick.ask - tick.bid) / (mt5.symbol_info(symbol).point or 0.00001)
    return spread <= max_spread_points


def place_order(symbol, action, volume, entry, stop_loss, take_profit):
    if action not in ("buy", "sell"):
        return {"skipped": True, "reason": "No actionable signal"}

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Failed to select symbol {symbol}")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError("No market tick info")

    price = tick.ask if action == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL,
        "price": float(price),
        "sl": float(stop_loss) if stop_loss else 0.0,
        "tp": float(take_profit) if take_profit else 0.0,
        "deviation": 20,
        "magic": 880055535,
        "comment": "agentic-0b78d445",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    return {
        "request": request,
        "result": {
            "retcode": getattr(result, 'retcode', None),
            "comment": getattr(result, 'comment', None),
            "order": getattr(result, 'order', None),
            "deal": getattr(result, 'deal', None),
        }
    }


def main():
    cfg_path = os.environ.get("AGENT_CONFIG", os.path.join(os.path.dirname(__file__), "config.json"))
    cfg = load_config(cfg_path)

    api = cfg.get("apiBaseUrl", "http://localhost:3000")
    agent_id = cfg["agentId"]
    agent_secret = cfg["agentSecret"]
    login = cfg["login"]
    password = cfg["password"]
    server = cfg["server"]
    terminal_path = cfg.get("terminalPath") or os.environ.get("MT5_TERMINAL_PATH")
    symbol = cfg.get("symbol", "EURUSD")
    timeframe = cfg.get("timeframe", "M5")
    risk_percent = float(cfg.get("riskPercent", 1.0))
    max_spread_points = int(cfg.get("maxSpreadPoints", 30))
    bars = int(cfg.get("bars", 250))

    ensure_terminal_running(terminal_path)
    time.sleep(2)

    init_mt5(terminal_path, login, password, server)

    session = requests.Session()

    while True:
        try:
            # Heartbeat
            try:
                session.post(f"{api}/api/agent/heartbeat", json={"agentId": agent_id, "secret": agent_secret, "ts": int(time.time())}, timeout=5)
            except Exception:
                pass

            # Market prechecks
            if not within_spread_limit(symbol, max_spread_points):
                time.sleep(5)
                continue

            candles = fetch_candles(symbol, timeframe, bars)

            resp = session.post(f"{api}/api/analyze", json={
                "symbol": symbol,
                "timeframe": timeframe,
                "candles": candles,
            }, timeout=20)
            resp.raise_for_status()
            signal = resp.json()

            action = signal.get("action", "hold")
            entry = signal.get("entry")
            sl = signal.get("stopLoss")
            tp = signal.get("takeProfit")
            conf = float(signal.get("confidence", 0))

            # Basic sanity checks
            if action in ("buy", "sell") and sl and tp:
                vol = compute_volume(symbol, entry or (mt5.symbol_info_tick(symbol).ask if action=="buy" else mt5.symbol_info_tick(symbol).bid), sl, risk_percent)
                if vol > 0:
                    result = place_order(symbol, action, vol, entry, sl, tp)
                    # Report back
                    try:
                        session.post(f"{api}/api/trade", json={
                            "agentId": agent_id,
                            "symbol": symbol,
                            "action": action,
                            "volume": vol,
                            "entry": entry,
                            "stopLoss": sl,
                            "takeProfit": tp,
                            "confidence": conf,
                            "result": result,
                            "time": datetime.utcnow().isoformat() + "Z",
                        }, timeout=10)
                    except Exception:
                        pass
            time.sleep(10)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

    mt5.shutdown()


if __name__ == "__main__":
    main()
