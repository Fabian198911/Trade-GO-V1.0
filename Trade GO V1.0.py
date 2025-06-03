import streamlit as st
import ccxt
import pandas as pd
import ta
import requests

st.title("📊 Smart Trading Signal mit Exit-Strategie + Telegram")

symbol = st.text_input("Trading-Paar", value="BTC/USDT")
exchange = ccxt.bitget()

# 📬 Telegram-Funktion (sicherer Zugriff über secrets.toml)
def send_telegram_message(message):
    token = st.secrets["telegram"]["token"]
    chat_id = st.secrets["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Fehler:", e)

# 📊 Marktdaten abrufen
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='30m', limit=200)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

try:
    df = get_data(symbol)

    # 📈 Technische Indikatoren
    df['ema9'] = ta.trend.EMAIndicator(df['close'], 9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(df['close'], 21).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(df['close'], 200).ema_indicator()
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd_line'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['volume_avg'] = df['volume'].rolling(20).mean()

    stoch = ta.momentum.StochRSIIndicator(df['close'])
    df['stoch_k'] = stoch.stochrsi_k()
    df['stoch_d'] = stoch.stochrsi_d()

    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()

    adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'])
    df['adx'] = adx.adx()

    cci = ta.trend.CCIIndicator(df['high'], df['low'], df['close'])
    df['cci'] = cci.cci()

    atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
    df['atr'] = atr

    latest = df.iloc[-1]

    # ✅ Bedingungen
    bullish = latest['ema9'] > latest['ema21'] and latest['close'] > latest['ema200']
    bearish = latest['ema9'] < latest['ema21'] and latest['close'] < latest['ema200']
    rsi_ok = 40 < latest['rsi'] < 70
    macd_ok = latest['macd_line'] > latest['macd_signal']
    vol_ok = latest['volume'] > latest['volume_avg']
    stoch_ok = latest['stoch_k'] > latest['stoch_d']
    bb_ok = latest['close'] > latest['bb_lower']
    adx_ok = latest['adx'] > 20
    cci_ok = -100 < latest['cci'] < 100

    # 🧮 Score
    score = sum([
        bullish,
        macd_ok,
        rsi_ok,
        vol_ok,
        stoch_ok,
        bb_ok,
        adx_ok,
        cci_ok
    ])

    st.write("📊 Gesamt-Score:", f"{score}/8")

    # 📌 TP/SL basierend auf ATR
    entry_price = latest['close']
    latest_atr = latest['atr']
    tp = entry_price + 2 * latest_atr
    sl = entry_price - 1.5 * latest_atr
    rr_ratio = (tp - entry_price) / (entry_price - sl)

    st.markdown("### 🎯 Exit-Strategie-Vorschläge")
    st.write(f"📈 Einstiegspreis: {entry_price:.2f}")
    st.write(f"🎯 Take Profit (2x ATR): {tp:.2f}")
    st.write(f"🛡 Stop Loss (1.5x ATR): {sl:.2f}")
    st.write(f"🔁 Risk/Reward-Ratio: {rr_ratio:.2f}")

    # 🟢 TRADE ENTSCHEIDUNG
    if score >= 6 and bullish:
        st.success("✅ STARKES GO LONG!")
        send_telegram_message(f"🚀 GO LONG für {symbol} – Score: {score}/8\n📈 Entry: {entry_price:.2f}\n🎯 TP: {tp:.2f} | 🛡 SL: {sl:.2f} | 📊 RRR: {rr_ratio:.2f}")
    elif score <= 2 and bearish:
        st.error("🔻 STARKES GO SHORT!")
        send_telegram_message(f"🔻 GO SHORT für {symbol} – Score: {score}/8")
    else:
        st.warning("⏸ NO-GO! (abwarten)")

except Exception as e:
    st.error("❌ Fehler beim Laden der Marktdaten:")
    st.text(str(e))
