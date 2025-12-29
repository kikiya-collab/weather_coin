# 깃허브 서버용 날씨예보 및 미세먼지 알림 코드(코인 목록 추가)

import os
import time
import urllib.parse
import requests
from datetime import datetime, timedelta, timezone

# -------------------------------
# 1) 가장 안정적인 base_time 계산
# -------------------------------
def get_stable_basetime():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    base_date = now.strftime("%Y%m%d")
    hour = now.hour

    # 기상청 발표 시간대 기준
    if hour < 2:
        return (now - timedelta(days=1)).strftime("%Y%m%d"), "2300"
    elif hour < 5:
        return base_date, "0200"
    elif hour < 8:
        return base_date, "0500"
    elif hour < 11:
        return base_date, "0800"
    elif hour < 14:
        return base_date, "1100"
    elif hour < 17:
        return base_date, "1400"
    elif hour < 20:
        return base_date, "1700"
    elif hour < 23:
        return base_date, "2000"
    else:
        return base_date, "2300"

# ---------------------------------------
# 2) 기온/강수 POP을 가장 안정적으로 추출
# ---------------------------------------
def extract_temp_pop(items):
    temp = None
    pop = None

    for it in items:
        if it["category"] == "TMP" and temp is None:
            temp = it["fcstValue"]
        if it["category"] == "POP" and pop is None:
            pop = it["fcstValue"]
        if temp and pop:
            break

    return temp, pop

# ----------------------------------------------------
# 3) 미세먼지 API (AirKorea: 항상 실시간 데이터 제공)
# ----------------------------------------------------
def get_air_quality():
    key = urllib.parse.quote_plus(os.getenv("AIRKOREA_KEY").strip())
    station = "중랑구"   # 신내동 기준 측정소

    url = (
        "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/"
        "getMsrstnAcctoRltmMesureDnsty"
        f"?serviceKey={key}&returnType=json&numOfRows=1&pageNo=1&stationName={station}&dataTerm=DAILY&ver=1.0"
    )
    try:
        r = requests.get(url, timeout=20)
        data = r.json()
        rows = data.get("response", {}).get("body", {}).get("items", [])
        if not rows:
            return None, None
        row = rows[0]
        return row.get("pm10Value"), row.get("pm25Value")
    except:
        return None, None

# ----------------------------------------------------
# 4) 통합 기상 API 호출 + fallback 지원
# ----------------------------------------------------
def get_weather(retries=3):
    service_key = urllib.parse.quote_plus(os.getenv("KMA_KEY").strip())
    nx, ny = 61, 129  # 서울 신내동

    base_date, base_time = get_stable_basetime()

    url = (
        "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        f"?serviceKey={service_key}&numOfRows=300&pageNo=1&dataType=JSON"
        f"&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}"
    )
    headers = {"User-Agent": "Mozilla/5.0"}

    items = None

    for attempt in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code != 200:
                time.sleep(5)
                continue

            data = res.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if items:
                break
        except:
            time.sleep(5)

    if not items:
        return None, None, None, None, "날씨 API 응답 없음"

    temp, rain_prob = extract_temp_pop(items)
    pm10, pm25 = get_air_quality()

    return temp, rain_prob, pm10, pm25, None

# ----------------------------------------------------
# 텔레그램 전송
# ----------------------------------------------------
def send_telegram_message(token, chat_id, message):
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message},
    )

# ----------------------------------------------------
# 메인
# ----------------------------------------------------
def main():
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    temp, rain_prob, pm10, pm25, error_msg = get_weather()

    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")

    # 날씨/미세먼지 메시지
    msg = (
        f"📅 {today}\n"
        f"🌡️ 기온: {temp if temp is not None else '데이터 없음'}°C\n"
        f"🌧️ 강수확률: {rain_prob if rain_prob is not None else '데이터 없음'}%\n"
        f"🌫️ 미세먼지(PM10): {pm10 if pm10 is not None else '데이터 없음'}\n"
        f"😷 초미세먼지(PM2.5): {pm25 if pm25 is not None else '데이터 없음'}"
    )

    if error_msg:
        msg += f"\n⚠️ {error_msg}"

    # -------------------------------
    # 코인 3개 조회 (ETH, SEI, XRP)
    # -------------------------------
    url = "https://api.upbit.com/v1/ticker?markets=KRW-ETH,KRW-SEI,KRW-XRP"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # ETH
        eth_data = next(item for item in data if item['market'] == 'KRW-ETH')
        eth_price = eth_data['trade_price']
        eth_time = eth_data['trade_time_kst']
        eth_time_fmt = f"{eth_time[:2]}:{eth_time[2:4]}"
        eth_rate = eth_data['signed_change_rate'] * 100
        eth_arrow = "🔺" if eth_rate > 0 else ("🔽" if eth_rate < 0 else "")
        eth_info = f"{eth_price} 원 ({eth_rate:.2f}% {eth_arrow})"

        # SEI
        sei_data = next(item for item in data if item['market'] == 'KRW-SEI')
        sei_price = sei_data['trade_price']
        sei_time = sei_data['trade_time_kst']
        sei_time_fmt = f"{sei_time[:2]}:{sei_time[2:4]}"
        sei_rate = sei_data['signed_change_rate'] * 100
        sei_arrow = "🔺" if sei_rate > 0 else ("🔽" if sei_rate < 0 else "")
        sei_info = f"{sei_price} 원 ({sei_rate:.2f}% {sei_arrow})"

        # XRP
        xrp_data = next(item for item in data if item['market'] == 'KRW-XRP')
        xrp_price = xrp_data['trade_price']
        xrp_time = xrp_data['trade_time_kst']
        xrp_rate = xrp_data['signed_change_rate'] * 100
        xrp_arrow = "🔺" if xrp_rate > 0 else ("🔽" if xrp_rate < 0 else "")
        xrp_info = f"{xrp_price} 원 ({xrp_rate:.2f}% {xrp_arrow})"

        # 코인 정보 메시지 추가
        msg += (
            f"\n\n💰 코인 가격 알림 (현재시간: {eth_time_fmt})\n"
            f"ETH 가격: {eth_info}\n"
            f"SEI 가격: {sei_info}\n"
            f"XRP 가격: {xrp_info}"
        )

    # 최종 텔레그램 전송
    send_telegram_message(token, chat_id, msg)
    print(msg)


if __name__ == "__main__":
    main()







