import os
import requests
import datetime
import urllib.parse

def get_weather():
    service_key = urllib.parse.quote_plus(os.getenv("KMA_KEY").strip())
    nx, ny = 61, 129  # 서울 신내동

    # 현재 UTC 시간 → KST로 변환
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    base_date = now.strftime("%Y%m%d")
    hour = now.hour

    # 안정적인 base_time 선택
    if hour < 2:
        base_time = "2300"
        base_date = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
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
        f"?serviceKey={service_key}&numOfRows=200&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )

    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)

    if res.status_code != 200 or not res.text.strip():
        return None, None, None, None

    try:
        data = res.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    except:
        return None, None, None, None

    temp = None
    rain_prob = None
    for item in items:
        if item.get("category") == "TMP" and temp is None:
            temp = item.get("fcstValue")
        if item.get("category") == "POP" and rain_prob is None:
            rain_prob = item.get("fcstValue")
        if temp and rain_prob:
            break

    # PM10/PM2.5는 아직 통합 API 사용 안 하면 None
    pm10 = None
    pm25 = None

    return temp, rain_prob, pm10, pm25

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

def main():
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    temp, rain_prob, pm10, pm25 = get_weather()

    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    message = (
        f"📅 {today}\n"
        f"🌡️ 기온: {temp}°C\n"
        f"🌧️ 강수확률: {rain_prob}%\n"
        f"🌫️ 미세먼지(PM10): {pm10}\n"
        f"😷 초미세먼지(PM2.5): {pm25}"
    )

    send_telegram_message(token, chat_id, message)
    print(message)

if __name__ == "__main__":
    main()




