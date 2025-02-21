import requests
import jwt
import uuid
import hashlib
import os
import json
import datetime
from urllib.parse import urlencode

# 🔹 업비트 API 키
ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")

# 🔹 파일 설정
TRADE_HISTORY_FILE = "trade_history.json"
LOG_FILE = "trade_log.txt"

# 🔹 업비트 거래 수수료 (매수 0.05%, 매도 0.05%)
BUY_FEE = 0.0005
SELL_FEE = 0.0005

# 🔹 로그 기록 함수
def log_message(message):
    with open(LOG_FILE, "a") as f:
        log_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{log_time}] {message}\n")

# 🔹 업비트 API 요청 헤더 생성
def get_headers(query=None):
    payload = {
        "access_key": ACCESS_KEY,
        "nonce": str(uuid.uuid4()),
    }
    
    if query:
        query_string = urlencode(query).encode()
        m = hashlib.sha512()
        m.update(query_string)
        payload["query_hash"] = m.hexdigest()
        payload["query_hash_alg"] = "SHA512"

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

# 🔹 현재 BTC 가격 조회
def get_btc_price():
    url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
    response = requests.get(url).json()
    return response[0]["trade_price"]

# 🔹 매수 데이터 저장/불러오기
def load_trade_data():
    if os.path.exists(TRADE_HISTORY_FILE):
        with open(TRADE_HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_trade_data(data):
    with open(TRADE_HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

# 🔹 5,000원어치 BTC 시장가 매수
def buy_btc():
    current_price = get_btc_price()
    btc_amount = 5000 / current_price  # 구매 BTC 수량

    url = "https://api.upbit.com/v1/orders"
    query = {
        "market": "KRW-BTC",
        "side": "bid",
        "price": "5000",
        "ord_type": "price"
    }
    
    response = requests.post(url, headers=get_headers(query), json=query)

    if "uuid" in response.json():
        trade_data = load_trade_data()
        trade_id = str(len(trade_data) + 1)  # 순번 자동 증가
        trade_data[trade_id] = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "buy_price": current_price,
            "buy_amount": 5000,
            "btc_amount": btc_amount,  # 구매한 BTC 수량 저장
            "status": "holding"
        }
        save_trade_data(trade_data)
        log_message(f"✅ [{trade_id}] BTC 매수 완료! (가격: {current_price} KRW, 수량: {btc_amount:.8f} BTC)")
    else:
        log_message(f"❌ 매수 실패! {response.json()}")

# 🔹 목표 매도가 계산 (수수료 고려하여 수익 발생 여부 체크)
def get_target_sell_price(buy_price):
    adjusted_buy_price = buy_price * (1 + BUY_FEE)
    target_sell_price = adjusted_buy_price / (1 - SELL_FEE)
    return target_sell_price

# 🔹 특정 순번의 BTC 시장가 매도
def sell_btc(trade_id):
    trade_data = load_trade_data()
    
    if trade_id not in trade_data or trade_data[trade_id]["status"] == "sold":
        log_message(f"❌ [{trade_id}] 이미 매도되었거나 존재하지 않는 순번")
        return False

    btc_amount = trade_data[trade_id]["btc_amount"]

    url = "https://api.upbit.com/v1/orders"
    query = {
        "market": "KRW-BTC",
        "side": "ask",
        "volume": str(btc_amount),
        "ord_type": "market"
    }

    response = requests.post(url, headers=get_headers(query), json=query)

    if "uuid" in response.json():
        trade_data[trade_id]["status"] = "sold"
        save_trade_data(trade_data)
        log_message(f"✅ [{trade_id}] BTC 매도 완료! (수량: {btc_amount:.8f} BTC)")
        return True
    else:
        log_message(f"❌ [{trade_id}] 매도 실패! {response.json()}")
        return False

# 🔹 자동 매매 실행 (매수 & 수익 확인 후 매도)
def auto_trade():
    now = datetime.datetime.now()

    if now.hour == 9 and now.minute == 0:
        buy_btc()
    
    trade_data = load_trade_data()
    current_price = get_btc_price()

    for trade_id, trade in trade_data.items():
        if trade["status"] == "holding":
            buy_price = trade["buy_price"]
            target_price = get_target_sell_price(buy_price)

            log_message(f"📊 [{trade_id}] 매수가: {buy_price} KRW | 현재가: {current_price} KRW | 최소 매도가: {target_price:.0f} KRW")

            if current_price >= target_price:  # 수익 발생 시 매도
                log_message(f"🚀 [{trade_id}] 수익 발생! 매도 진행")
                sell_btc(trade_id)

# 실행
if __name__ == "__main__":
    auto_trade()
