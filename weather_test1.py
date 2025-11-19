import os
import requests
from datetime import datetime, timedelta, timezone
import time
import urllib.parse

def get_weather(retries=3):
    service_key = urllib.parse.quote_plus(os.getenv("KMA_KEY").strip())
    nx, ny = 61, 129  # 서울 신내동

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    base_date = now.strftime("%Y%m%d")
    hour = now.hour

    # 안정적인 base_time 선택 (최소 1시간 전 발표 기준)
    if hour < 2:
        base_time = "2300"
        base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
    elif hour < 5:
        base_time = "0200"
    elif hour < 8:
        base_time = "0500"
    elif hour < 11:
        base_time = "0800"
    elif hour < 14:
        base_time = "1100"
    elif hour < 17:
        base_time = "1400"
    elif hour < 20:
        base_time = "1700"
    elif hour < 23:
        base_time = "2000"
    else:
        base_time = "2300"

    url = (
        "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={service_key}&numOfRows=300&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )
    headers = {"User-Agent": "Mozilla/5.0"}

    for attempt in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code != 200:
                print(f"Attempt {attempt+1}: HTTP {res.status_code}")
                time.sleep(5)
                continue
            data = res.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if not items:
                print(f"Attempt {attempt+1}: Empty items, retrying...")
                time.sleep(5)
                continue
            break
        except Exception as e:
            print(f"Attempt {attempt+1} Exception:", e)
            time.sleep(5)
    else:
        return None, None, None, None, "API 응답 지연, 나중에 시도하세요"

    temp = None
    rain_prob = None
    for item in items:
        if item.get("category") == "TMP" and temp is None:
            temp = item.get("fcstValue")
        if item.get("category") == "POP" and rain_prob is None:
            rain_prob = item.get("fcstValue")
        if temp and rain_prob:
            break

    pm10 = None
    pm25 = None

    return temp, rain_prob, pm10, pm25, None

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

def main():
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    temp, rain_prob, pm10, pm25, error_msg = get_weather()

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    message = (
        f"📅 {today}\n"
        f"🌡️ 기온: {temp if temp is not None else '데이터 없음'}°C\n"
        f"🌧️ 강수확률: {rain_prob if rain_prob is not None else '데이터 없음'}%\n"
        f"🌫️ 미세먼지(PM10): {pm10 if pm10 is not None else '데이터 없음'}\n"
        f"😷 초미세먼지(PM2.5): {pm25 if pm25 is not None else '데이터 없음'}"
    )
    if error_msg:
        message += f"\n⚠️ {error_msg}"

    send_telegram_message(token, chat_id, message)
    print(message)

if __name__ == "__main__":
    main()







