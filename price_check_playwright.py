# price_check_playwright.py
import os
import asyncio
import json
from datetime import datetime
import requests
from playwright.async_api import async_playwright

ITEM_IDS = ["1920684660", "2701336763"]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(token, chat_id, message):
    if not token or not chat_id:
        print("Telegram token/chat_id not set, skipping message.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram send failed:", e)

    

async def fetch_price(page, item_no):
    url = f"https://item.gmarket.co.kr/Item?goodscode={item_no}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # 짧은 대기 후 동적 렌더된 가격 탐색
    try:
        await page.wait_for_selector(".price_real, .price", timeout=10000)
        # 여러 요소가 있을 수 있으니 첫번째 텍스트 추출
        price_text = await page.locator(".price_real, .price").first.text_content()
        price_text = price_text.strip() if price_text else "N/A"
    except Exception:
        price_text = "N/A"
    title = await page.title()
    return {"상품ID": item_no, "상품명": title, "가격": price_text, "링크": url, "수집시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="ko-KR", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114 Safari/537.36")
        page = await context.new_page()
        for item in ITEM_IDS:
            info = await fetch_price(page, item)
            print(info)
            results.append(info)
            # 랜덤 지연 비슷하게 동작 (간단하게 고정 지연 사용)
            await asyncio.sleep(3)
        await browser.close()

    # 텔레그램으로 요약 전송 (가격 정상값만 모아서 보낼지 전체 전송 선택)
    messages = []
    for r in results:
        messages.append(f"상품ID: {r['상품ID']}\n상품명: {r['상품명']}\n가격: {r['가격']}\n링크: {r['링크']}\n수집: {r['수집시각']}")
    summary = "\n\n".join(messages)
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, f"📦 G마켓 가격 알림\n\n{summary}")

if __name__ == "__main__":
    print(f"🔍 TELEGRAM_TOKEN: {repr(TELEGRAM_TOKEN)}")
    print(f"🔍 TELEGRAM_CHAT_ID: {repr(TELEGRAM_CHAT_ID)}")

    asyncio.run(main())