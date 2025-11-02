# price_check_playwright.py
import os
import asyncio
import random
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- 설정: ITEM 리스트, env 처리 ---
ITEM_IDS = ["1920684660", "2701336763"]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = TELEGRAM_TOKEN.strip()

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID.strip()

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram_message(token, chat_id, message):
    import requests
    if not token or not chat_id:
        print("Telegram token/chat_id not set, skipping message", flush=True)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        print(f"[INFO] Telegram send status: {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}", flush=True)

# --- fetch / 파싱 로직 (Selenium에서 잘 되던 셀렉터 반영) ---
async def fetch_price_from_page(page, item_id):
    # 상품명: document.title fallback, 셀렉터 우선 탐색
    title = None
    price = "N/A"
    try:
        # 가능한 제목 셀렉터들 시도
        for sel in ["h1.itemtit", ".itemtit", "#itemCase .item_title", "meta[property='og:title']"]:
            try:
                if sel.startswith("meta"):
                    content = await page.locator(sel).get_attribute("content")
                    if content:
                        title = content
                        break
                else:
                    locator = page.locator(sel)
                    if await locator.count() > 0:
                        title = (await locator.first.inner_text()).strip()
                        break
            except Exception:
                continue
        if not title:
            # fallback to document.title
            title = await page.title()
    except Exception:
        title = "Unknown"

    # 가격 추출: .price_real, .price 등
    try:
        for psel in [".price_real", ".buy_price", ".sold_price", ".price", ".price_value"]:
            try:
                locator = page.locator(psel)
                if await locator.count() > 0:
                    price_text = (await locator.first.inner_text()).strip()
                    # 숫자만 추출
                    m = re.search(r"[\d,]+", price_text.replace("\xa0", " "))
                    price = m.group(0) if m else price_text
                    break
            except Exception:
                continue
    except Exception:
        price = "N/A"

    return {
        "상품ID": item_id,
        "상품명": title,
        "가격": price,
        "링크": f"https://item.gmarket.co.kr/Item?goodscode={item_id}",
        "수집시각": now_str()
    }

# --- 사람같은 행동 유틸 ---
async def human_like_actions(page):
    try:
        # 마우스 이동 (임의 좌표)
        await page.mouse.move(100, 100)
        await asyncio.sleep(random.uniform(0.1, 0.4))
        await page.mouse.move(400, 300, steps=8)
    except Exception:
        pass
    try:
        # 스크롤 여러 지점
        await page.evaluate("window.scrollTo(0, 200)")
        await asyncio.sleep(random.uniform(0.2, 0.6))
        await page.evaluate("window.scrollBy(0, Math.floor(window.innerHeight/2))")
        await asyncio.sleep(random.uniform(0.3, 0.9))
    except Exception:
        pass

# --- 안전한 재시도 패턴: context 기반 페이지 새로 생성 ---
async def fetch_price_with_checks(context, item_id, max_retries=3):
    url = f"https://item.gmarket.co.kr/Item?goodscode={item_id}"
    for attempt in range(1, max_retries + 1):
        page = await context.new_page()
        try:
            print(f"[INFO] Attempt {attempt} for {item_id}", flush=True)
            await human_like_actions(page)
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            status = resp.status if resp else None
            print(f"[DEBUG] goto {url} -> status: {status}", flush=True)

            content = await page.content()
            print(f"[DEBUG] content length: {len(content)} | contains Access Denied: {'Access Denied' in content or 'access denied' in content.lower()}", flush=True)

            if status and status >= 400:
                print(f"[WARN] HTTP status {status} for {item_id} (attempt {attempt})", flush=True)

            if "Access Denied" in content or "access denied" in content.lower() or (status and str(status).startswith("4")):
                # 차단 감지 시 스냅샷(로컬 디버깅용) 및 쿠키 클리어
                try:
                    await page.screenshot(path=f"debug_{item_id}_{attempt}.png")
                    html = await page.content()
                    with open(f"debug_{item_id}_{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"[DEBUG] saved debug artifacts for {item_id} attempt {attempt}", flush=True)
                except Exception:
                    pass
                try:
                    await page.context.clear_cookies()
                except Exception:
                    pass
                await page.close()
                await asyncio.sleep(2 + attempt * 2)
                continue

            # 정상 페이지: 파싱
            result = await fetch_price_from_page(page, item_id)
            await page.close()
            return result

        except PlaywrightTimeoutError as e:
            print(f"[ERROR] Timeout on attempt {attempt} for {item_id}: {e}", flush=True)
            try:
                await page.close()
            except Exception:
                pass
            await asyncio.sleep(2 + attempt * 2)
            continue
        except Exception as e:
            print(f"[ERROR] fetch attempt {attempt} for {item_id}: {repr(e)}", flush=True)
            try:
                await page.close()
            except Exception:
                pass
            await asyncio.sleep(2 + attempt * 2)
            continue

    return {"상품ID": item_id, "상품명": "Access Denied", "가격": "N/A", "링크": url, "수집시각": now_str()}

# --- main: context 설정 및 실행 ---
async def main():
    results = []
    async with async_playwright() as p:
        # 로컬 테스트 시 headless=True, CI에서는 True로 변경
        browser = await p.chromium.launch(
            headless=False,  # GitHub Actions에서 실행할 땐 True로 바꿔라
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="ko-KR",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114 Safari/537.36"),
            extra_http_headers={
                "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "upgrade-insecure-requests": "1"
            }
        )

        # 스텔스 초기화 스크립트 (기본적 노출 차단)
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) => params && params.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(params);
        """)

        for item in ITEM_IDS:
            info = await fetch_price_with_checks(context, item, max_retries=3)
            print(info, flush=True)
            results.append(info)
            await asyncio.sleep(random.uniform(3, 6))

        await browser.close()

    # 텔레그램으로 요약 전송 (가격 정상값만)
    messages = []
    for r in results:
        if r.get("가격") and r["가격"] != "N/A":
            messages.append(f"상품ID: {r['상품ID']}\n상품명: {r['상품명']}\n가격: {r['가격']}\n링크: {r['링크']}\n수집: {r['수집시각']}")
    if messages:
        summary = "\n\n".join(messages)
        send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, f"📦 G마켓 가격 알림\n\n{summary}")
    else:
        print("No valid prices to send", flush=True)

if __name__ == "__main__":
    asyncio.run(main())