import streamlit as st
import pandas as pd
import json
import websocket
import ta
import threading

st.set_page_config(page_title="SMC Price Action Signal Generator", layout="centered")
st.title("📈 SMC Price Action Signal Generator")

symbol = st.text_input("Enter Deriv Symbol", value="volatility_75_index")
timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h"])
gran_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
gran = gran_map[timeframe]
count = st.slider("Number of Candles", 50, 499, 100)

candles = []

def fetch_data():
    global candles
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.binaryws.com/websockets/v3?app_id=1089")
        payload = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": gran,
            "count": count,
            "end": "latest"
        }
        ws.send(json.dumps(payload))
        while True:
            msg = json.loads(ws.recv())
            if "candles" in msg:
                candles = msg["candles"]
                break
            elif "error" in msg:
                st.error(f"❌ Deriv API Error: {msg['error']['message']}")
                break
        ws.close()
    except Exception as e:
        st.error(f"WebSocket error: {e}")

# Run the WebSocket in a separate thread
thread = threading.Thread(target=fetch_data)
thread.start()
thread.join()

# Signal generation logic
if not candles:
    st.error("❌ Could not fetch candle data.")
else:
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["epoch"], unit="s")
    df.set_index("time", inplace=True)
    df = df[["open", "high", "low", "close"]].astype(float)

    # Price action logic
    df["HH"] = df["high"] > df["high"].shift(1)
    df["LL"] = df["low"] < df["low"].shift(1)
    df["CHoCH"] = (df["close"] > df["high"].shift(2)) | (df["close"] < df["low"].shift(2))
    df["Imbalance"] = abs(df["open"] - df["close"].shift(1)) > (df["high"] - df["low"]).mean()
    df["Engulfing"] = ((df["close"] > df["open"]) & (df["open"] < df["close"].shift(1))) | \
                      ((df["close"] < df["open"]) & (df["open"] > df["close"].shift(1)))

    latest = df.iloc[-1]
    confluences = []

    if latest["CHoCH"]:
        confluences.append("🔁 CHoCH Detected")
    if latest["Imbalance"]:
        confluences.append("📉 Imbalance Zone")
    if latest["Engulfing"]:
        confluences.append("📍 Engulfing Candle")
    if latest["HH"]:
        confluences.append("📈 Higher High (Bullish Structure)")
    if latest["LL"]:
        confluences.append("📉 Lower Low (Bearish Structure)")

    # Signal logic
    if len(confluences) >= 3:
        signal = "🟢 Buy" if latest["HH"] and latest["Engulfing"] else "🔴 Sell"
    else:
        signal = "⚪ Neutral"

    # Display
    st.metric("Signal", signal)
    st.markdown("### 🔍 Price Action Confluences:")
    for item in confluences:
        st.write("-", item)

    st.line_chart(df[["close"]])
    with st.expander("📊 Candle Data"):
        st.dataframe(df.tail(15))
