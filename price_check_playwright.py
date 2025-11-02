# price_check_playwright.py
import os
import asyncio
import json
from datetime import datetime
import requests
import random
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

    

# 자동화 노출 최소화용 초기화 스크립트
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.navigator.chrome = { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""

async def fetch_price_with_checks(page, item_id, max_retries=3):
    url = f"https://item.gmarket.co.kr/Item?goodscode={item_id}"
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] Attempt {attempt} for {item_id}")
            # 사람같은 약간의 행동: 스크롤/짧은 랜덤 대기
            await page.evaluate("window.scrollTo(0, 200)")
            await asyncio.sleep(random.uniform(0.5, 1.2))

            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            status = resp.status if resp else None
            print(f"[DEBUG] goto {url} -> status: {status}")

            content = await page.content()
            print(f"[DEBUG] content length: {len(content)} | contains Access Denied: {'Access Denied' in content or 'access denied' in content.lower()}")

            # 디버그: 현재 쿠키와 UA (개인정보 유출 주의, 로그에 민감 정보는 남기지 마)
            try:
                cookies = await page.context.cookies()
                print(f"[DEBUG] cookies count: {len(cookies)}")
            except Exception as e:
                print(f"[DEBUG] cookie read error: {e}")

            ua = await page.evaluate("navigator.userAgent")
            print(f"[DEBUG] userAgent (sample): {ua[:120]}")

            # Access Denied 단서 검사: HTTP 상태나 주요 문구
            if status and status >= 400:
                print(f"[WARN] HTTP status {status} for {item_id} (attempt {attempt})")
            if "Access Denied" in content or "access denied" in content.lower() or (status and str(status).startswith("4")):
                print(f"[WARN] Access Denied detected for {item_id} (attempt {attempt})")
                # 재시도 전 짧은 백오프와 약간 더 사람같은 행동
                await asyncio.sleep(2 + attempt * 2)
                try:
                    await page.context.clear_cookies()
                except Exception as e:
                    print(f"[DEBUG] clear_cookies error: {e}")
                # 옵션: 새 페이지로 바꿔서 재시도 (간단한 컨텍스트 리셋)
                try:
                    await page.close()
                    page = await page.context.new_page()
                except Exception:
                    pass
                continue

            # 정상 페이지로 보이면 기존 fetch_price 로직으로 파싱
            return await fetch_price(page, item_id)

        except Exception as e:
            print(f"[ERROR] fetch attempt {attempt} for {item_id}: {repr(e)}")
            await asyncio.sleep(2 + attempt * 2)
            # 재시도 전에 가능하면 페이지 재생성
            try:
                await page.close()
                page = await page.context.new_page()
            except Exception:
                pass
            continue

    # 최대 재시도 실패 시 Access Denied 형태 결과 반환
    return {"상품ID": item_id, "상품명": "Access Denied", "가격": "N/A", "링크": url, "수집시각": now_str()}

async def main():
    results = []
    async with async_playwright() as p:
        # launch 인자: 자동화 표시 억제, 안정성 옵션 추가
        browser = await p.chromium.launch(
            headless=True,  # GitHub Actions 환경에서는 headless True 유지
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114 Safari/537.36",
            accept_downloads=False,
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

        # 초기화 스크립트 삽입 (navigator.webdriver 등 덮어쓰기)
        await context.add_init_script(STEALTH_SCRIPT)

        page = await context.new_page()

        for item in ITEM_IDS:
            info = await fetch_price_with_checks(page, item, max_retries=3)
            print(info)
            results.append(info)
            await asyncio.sleep(random.uniform(2.0, 4.0))

        await browser.close()

    # 텔레그램 전송 기존 로직
    messages = []
    for r in results:
        messages.append(f"상품ID: {r['상품ID']}\n상품명: {r['상품명']}\n가격: {r['가격']}\n링크: {r['링크']}\n수집: {r['수집시각']}")
    summary = "\n\n".join(messages)
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, f"📦 G마켓 가격 알림\n\n{summary}")


if __name__ == "__main__":
    print(f"🔍 TELEGRAM_TOKEN: {repr(TELEGRAM_TOKEN)}")
    print(f"🔍 TELEGRAM_CHAT_ID: {repr(TELEGRAM_CHAT_ID)}")

    asyncio.run(main())