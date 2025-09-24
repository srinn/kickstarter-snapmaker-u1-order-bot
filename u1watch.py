"""
ks_monitor_uc.py
- undetected-chromedriver 버전
- 수동 로그인 + 쿠키 재사용 권장
"""

import time
import json
import random
import webbrowser
from datetime import datetime, timezone
import os
import sys
import requests

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# === 설정 ===
KICKSTARTER_URL = "https://www.kickstarter.com/projects/snapmaker/snapmaker-u1-color-3d-printer-5x-more-speed-5x-less-waste/pledge/edit"
KICKSTARTER_PLEDGE_EDIT_URL = "https://www.kickstarter.com/projects/snapmaker/snapmaker-u1-color-3d-printer-5x-more-speed-5x-less-waste/pledge/edit"
COOKIES_FILE = "ks_cookies.json"      # 수동 로그인 후 저장한 쿠키 파일
POLL_INTERVAL_SECONDS = 2            # 기본 폴링 시간
MAX_POLL_INTERVAL = 15 * 60           # 백오프 최대값(예: 15분)
#TARGET_YEAR = 2025
#TARGET_MONTH = 10                      # 10 = October
TARGET_REWARD_TIME_TEXT = "Oct 2025" # 예약 변경 시 배송일자가 Oct 2025 인 상품을 찾기 위한 것
#TARGET_ID = 10710483                  # 테스트용 Nov 2025 배송 25% 얼리버드 U1 x 2
#TARGET_ID = 10756605                  # 테스트용 Dec 2025 배송 20% 스페셜
TARGET_ID = 10702768                # Oct 2025 배송 25% 얼리버드
OPEN_URL_ON_DETECT = KICKSTARTER_PLEDGE_EDIT_URL
HEADLESS = False                       # headless는 탐지 확률↑ -> False 권장

# === Telegram 설정 ===
USE_TELEGRAM = False
TELEGRAM_TOKEN = "텔레그램 봇 API 토큰"   # 예: "1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
TELEGRAM_CHAT_ID = "텔레그램 채팅방 ID"     # 예: 123456789

# === Telegram 알림 ===
def send_telegram_message(text):
    if USE_TELEGRAM:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("[!] Telegram 설정이 비어 있음 — 메시지 전송 안 함")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
            if r.status_code != 200:
                print(f"[!] Telegram 전송 실패: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[!] Telegram 예외 발생: {e}")

# === 유틸 ===
#def epoch_is_target_month(epoch_seconds, year=TARGET_YEAR, month=TARGET_MONTH):
#    try:
#        dt = datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc)
#        return (dt.year == year) and (dt.month == month)
#    except Exception:
#        return False

def save_cookies(driver, filename=COOKIES_FILE):
    cookies = driver.get_cookies()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now().isoformat()}] 쿠키 저장: {filename}")

def load_cookies(driver, filename=COOKIES_FILE, domain=None):
    if not os.path.exists(filename):
        return False
    with open(filename, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    for c in cookies:
        cookie = c.copy()
        # Selenium cookie must not include 'sameSite' sometimes; remove problematic keys
        cookie.pop("sameSite", None)
        try:
            # 도메인 지정이 되어 있지 않으면 현재 도메인에 맞춰 넣음
            driver.add_cookie(cookie)
        except Exception as e:
            # 일부 쿠키엔 domain이 존재하고 일치하지 않으면 add 실패
            pass
    print(f"[{datetime.now().isoformat()}] 쿠키 로드 완료: {filename}")
    return True

def is_cloudflare_challenge(driver):
    """
    간단한 탐지: 페이지 소스에 reCAPTCHA / Checking your browser / h-captcha 등 문자열 존재 여부로 판단
    """
    try:
        src = driver.page_source.lower()
    except Exception:
        return True
    checks = [
        "please verify you are a human",
        "checking your browser before accessing",
        "cf-chl-bypass",
        "cf-captcha-container",
        "h-captcha",
        "g-recaptcha",
        "please complete the security check to access"
    ]
    for c in checks:
        if c in src:
            return True
    # 또한 페이지 타이틀이나 특정 element 로도 감지 가능
    title = ""
    try:
        title = driver.title.lower()
    except Exception:
        title = ""
    if "just a moment" in title or "checking your browser" in title:
        return True
    return False

def alert_user_and_blocking_open(url=OPEN_URL_ON_DETECT):
    # 1) 콘솔 벨
    print("\a")
    ## 2) 브라우저로 열기(새 탭)
    # webbrowser.open(url, new=2)

# === 드라이버 생성 ===
def make_uc_driver(headless=HEADLESS):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    # 일반 브라우저처럼 보이게 하는 옵션들
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,900")
    # 실제 브라우저 User-Agent (원하는 UA로 바꿔도 됨)
    user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36")
    options.add_argument(f"--user-agent={user_agent}")
    # 언어 헤더
    options.add_argument("--lang=en-US,en;q=0.9,ko;q=0.8")
    # 기타 실전 팁
    options.add_argument("--disable-blink-features=AutomationControlled")
    # undetected-chromedriver가 자동으로 많은 시도를 합니다.
    driver = uc.Chrome(options=options)
    return driver

# === reward 검사 ===
def extract_project_json(driver):
    """
    페이지에 window.current_project 또는 window.currentProject 같은 JS 객체가 있으면 추출 시도.
    없으면 None 반환.
    """
    script = """
    try {
        var cp = window.current_project.data;
        if (!cp) { return null; }
        if (typeof cp === 'string') {
            try { return JSON.stringify(JSON.parse(cp)); } catch(e) { return cp; }
        } else {
            return JSON.stringify(cp);
        }
    } catch(e) { return null; }
    """
    try:
        raw = driver.execute_script(script)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(json.loads(raw))
        except Exception:
            return None

def check_rewards_for_target(rewards):
    hits = []
    for r in rewards:
        # est = r.get("estimated_delivery_on")
        available = r.get("available")
        remaining = r.get("remaining")
        t_id = r.get("id")
        try:
            remaining_int = int(remaining) if remaining is not None else None
        except Exception:
            remaining_int = None
        # if est is None:
        #     continue
        # if epoch_is_target_month(est):
        #     if (available is True) or (remaining_int is not None and remaining_int > 0):
        #         hits.append(r)
        if t_id == TARGET_ID:
            if (available is True) or (remaining_int is not None and remaining_int > 0):
                hits.append(r)
    return hits

# === 메인 루프 ===
def main_loop():
    driver = make_uc_driver()
    try:
        # 1) 처음 로드: 로그인 쿠키가 있으면 먼저 도메인 열어서 주입
        print(f"[{datetime.now().isoformat()}] 브라우저 시작, URL로 이동: {KICKSTARTER_URL}")
        driver.get("https://www.kickstarter.com/")  # 도메인 맞춘 뒤 쿠키 주입
        if os.path.exists(COOKIES_FILE):
            try:
                load_cookies(driver, COOKIES_FILE)
            except Exception as e:
                print("쿠키 로드 중 오류:", e)

        # 사용자에게 수동 로그인을 시킬 수도 있게 한 번 열어둠
        print("만약 로그인 되어 있지 않다면, 브라우저에서 Kickstarter에 수동 로그인 후 Enter를 누르세요.")
        print("쿠키를 저장하려면 로그인 완료 후 이 스크립트에서 's' 입력 -> 쿠키 저장.")
        sys.stdout.write("계속하려면 Enter (또는 s 입력 후 Enter로 쿠키 저장): ")
        choice = sys.stdin.readline().strip().lower()
        if choice == "s":
            save_cookies(driver, COOKIES_FILE)
            print("쿠키 저장 완료. 계속 진행합니다.")

        # 폴링 변수
        poll_interval = POLL_INTERVAL_SECONDS
        consecutive_failures = 0
        last_seen = {}  # reward_id -> (available, remaining) 상태 저장

        while True:
            # 랜덤 지터 추가 (작게)
            jitter = random.uniform(0.0, min(5.0, poll_interval * 0.2))
            sleep_before = poll_interval + jitter
            print(f"[{datetime.now().isoformat()}] 다음 검사까지 대기: {sleep_before:.1f}s (지터 포함)")
            time.sleep(sleep_before)

            try:
                driver.get(KICKSTARTER_URL)
            except Exception as e:
                print(f"[{datetime.now().isoformat()}] 페이지 로드 실패: {e}")
                consecutive_failures += 1
                # 실패가 쌓이면 폴링 간격을 늘려 차단 위험 감소
                poll_interval = min(MAX_POLL_INTERVAL, poll_interval * 2)
                continue

            # Cloudflare / 챌린지 감지
            if is_cloudflare_challenge(driver):
                msg = "⚠️ Cloudflare/챌린지 감지됨. 수동으로 확인해 주세요."
                print(f"[{datetime.now().isoformat()}] {msg}")
                # alert_user_and_blocking_open(KICKSTARTER_URL)
                send_telegram_message(msg)
                # 사용자에게 직접 풀도록 안내 (동기식)
                sys.stdout.write("브라우저에서 체크박스를 풀고 완료되면 Enter를 누르세요: ")
                _ = sys.stdin.readline()
                # 수동 해결 후 쿠키 저장을 권장
                try:
                    save_cookies(driver, COOKIES_FILE)
                except Exception:
                    pass
                # 이후 다시 검사
                consecutive_failures = 0
                poll_interval = POLL_INTERVAL_SECONDS
                continue

            # time.sleep(2.0)
            project = extract_project_json(driver)
            if not project:
                # JSON이 없으면 DOM 파싱 또는 다음 시도로
                print(f"[{datetime.now().isoformat()}] 프로젝트 JSON을 찾지 못했습니다. DOM 파싱 미구현 - 다음 주기 재시도")
                consecutive_failures += 1
                poll_interval = min(MAX_POLL_INTERVAL, POLL_INTERVAL_SECONDS * (1 + consecutive_failures))
                continue

            rewards = project.get("rewards") or []
            hits = check_rewards_for_target(rewards)

            # 변화 감지: new hit이 있으면 알림
            #new_hits = []
            #for h in hits:
            #    rid = str(h.get("id"))
            #    avail = bool(h.get("available"))
            #    remaining = h.get("remaining")
            #    prev = last_seen.get(rid)
            #    # consider it new if never seen or previously unavailable/0
            #    was_unavailable = (prev is None) or (prev and (prev[0] is False or (prev[1] is not None and prev[1] == 0)))
            #    if was_unavailable:
            #        new_hits.append(h)
            #    # update last_seen
            #    try:
            #        rem_int = int(remaining) if remaining is not None else None
            #    except Exception:
            #        rem_int = None
            #    last_seen[rid] = (avail, rem_int)

            #if new_hits:
            if len(hits) > 0:
                for h in hits:
                    rid = h.get("id")
                    title = h.get("title") or h.get("reward") or "<no-title>"
                    remaining = h.get("remaining")
                    available = h.get("available")
                    est = h.get("estimated_delivery_on")
                    est_dt = datetime.fromtimestamp(int(est), tz=timezone.utc).strftime("%Y-%m-%d UTC")
                    print(f"[{datetime.now().isoformat()}] **감지** reward id={rid}, title={title}, available={available}, remaining={remaining}, est={est_dt}")
                msg = f"[✅ 자리 발생] Reward {title} (id={rid}) / Remaining={remaining}, Delivery={est_dt}"
                print(f"[{datetime.now().isoformat()}] {msg}")
                send_telegram_message(msg)
                alert_user_and_blocking_open(OPEN_URL_ON_DETECT)

                try:
                    reward_time_elements = driver.find_elements(By.XPATH, '//*[@id="pledge-app"]/div/div/div[2]/ul[1]/li/div/div[1]/div[4]/div/span[2]/time')
                    #print(reward_time_elements)
                    pledge_button_elements = driver.find_elements(By.XPATH, '//*[@id="pledge-app"]/div/div/div[2]/ul[1]/li/div/div[2]/div[2]/button')
                    #print(pledge_button_elements)
                    for idx, element in enumerate(reward_time_elements):
                        #print(idx)
                        #print(element)
                        if element.text == TARGET_REWARD_TIME_TEXT:
                            pledge_button_elements[idx].click()
                            pay_button_element = driver.find_element(By.XPATH, '//*[@id="pledge-summary"]/div[4]/div/button')
                            pay_button_element.click()
                            confirm_button_element = driver.find_element(By.XPATH, '//*[@id="pledge-app"]/div/div/div[2]/form/div[2]/div[2]/div[2]/button')
                            confirm_button_element.click()
                            msg = f"✅ 예약이 변경되었습니다! 야호!"
                            print(f"[{datetime.now().isoformat()}] {msg}")
                            send_telegram_message(msg)

                except Exception as e:
                    #print(e)
                    msg = f"⚠️ 페이지 로드 실패, 수동으로 예약을 수정하세요!"
                    print(f"[{datetime.now().isoformat()}] {msg}")
                    send_telegram_message(msg)

                # 알림 후 계속 감시하고 싶으면 아래를 주석처리하고 계속 루프 유지
                break
            else:
                print(f"[{datetime.now().isoformat()}] 대상 리워드 자리가 없음 (검사된 reward 수: {len(rewards)}).")

            # 성공적으로 검사했으므로 실패 카운트 리셋 및 폴링 간격 천천히 원상복구
            consecutive_failures = 0
            poll_interval = POLL_INTERVAL_SECONDS

    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main_loop()
