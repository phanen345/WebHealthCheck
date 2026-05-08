import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# ── Selenium Driver Setup ──────────────────────────────────────────────────────

def create_driver(headless=True):
    """
    Create and return a configured Selenium Chrome WebDriver.
    """
    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


# ── Page Load Time via Selenium ────────────────────────────────────────────────

def get_page_load_time(url, driver=None):
    """
    Measure real browser page load time using Selenium + Navigation Timing API.

    Returns:
        dict: { url, load_time_ms, load_time_s, status, error }
    """
    own_driver = driver is None
    if own_driver:
        driver = create_driver(headless=True)

    try:
        start = time.time()
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Browser Navigation Timing API — most accurate
        load_time_ms = driver.execute_script(
            "return window.performance.timing.loadEventEnd "
            "- window.performance.timing.navigationStart;"
        )

        # Fallback to wall clock if API returns 0
        if not load_time_ms or load_time_ms <= 0:
            load_time_ms = int((time.time() - start) * 1000)

        load_time_s = round(load_time_ms / 1000, 2)
        status = (
            "FAST"       if load_time_s < 2 else
            "ACCEPTABLE" if load_time_s < 4 else
            "SLOW"
        )

        print(f"  [LOAD TIME] {load_time_s}s ({status}) → {url[:60]}")
        return {
            "url": url,
            "load_time_ms": load_time_ms,
            "load_time_s": load_time_s,
            "status": status,
            "error": None
        }

    except Exception as e:
        return {"url": url, "load_time_ms": None, "load_time_s": None,
                "status": "ERROR", "error": str(e)}
    finally:
        if own_driver:
            driver.quit()


# ── Screenshot Helper ──────────────────────────────────────────────────────────

def take_screenshot(url, filename="screenshot.png"):
    """
    Take a full-page screenshot of a URL using Selenium.
    Used to capture broken / error page evidence.

    Returns:
        str: Path to saved screenshot, or None on failure
    """
    driver = create_driver(headless=True)
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(1)

        # Expand to full page height (up to 4000px)
        total_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1280, min(total_height, 4000))

        driver.save_screenshot(filename)
        print(f"  [SCREENSHOT] Saved → {filename}")
        return filename

    except Exception as e:
        print(f"  [SCREENSHOT ERROR] {e}")
        return None
    finally:
        driver.quit()


# ── Selenium Link Extractor (JS fallback) ─────────────────────────────────────

def get_links_with_selenium(url, base_domain, same_domain_only=True):
    """
    Use Selenium to extract links from JS-rendered pages
    (React, Next.js, Angular, Vue etc.)

    Returns:
        list: Unique links found on the page
    """
    print(f"  [SELENIUM] JS fallback activated → {url[:60]}")
    driver = create_driver(headless=True)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)  # Allow JS framework to finish rendering

        anchor_tags = driver.find_elements(By.TAG_NAME, "a")
        links = set()

        for tag in anchor_tags:
            href = tag.get_attribute("href")
            if not href or not href.startswith("http"):
                continue
            if same_domain_only:
                if urlparse(href).netloc == base_domain:
                    links.add(href)
            else:
                links.add(href)

        print(f"  [SELENIUM] Found {len(links)} links via browser")
        return list(links)

    except Exception as e:
        print(f"  [SELENIUM ERROR] {e}")
        return []
    finally:
        driver.quit()


# ── Core Link Extractor ────────────────────────────────────────────────────────

def get_all_links(url, same_domain_only=True):
    """
    Extract all hyperlinks from a page.

    Strategy:
      1. Try fast requests + BeautifulSoup
      2. Detect if page is JS-rendered
      3. If yes → automatically fall back to Selenium

    Returns:
        list: Unique URLs found on the page
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    base_domain = urlparse(url).netloc
    links = set()
    use_selenium = False

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text

        # JS-rendered page detection signals
        js_markers = ["__NEXT_DATA__", "ng-version", "data-reactroot", "__nuxt", "__REACT"]
        soup = BeautifulSoup(html, "html.parser")
        anchor_count = len(soup.find_all("a", href=True))

        is_js_rendered = (
            len(html.strip()) < 500          # almost empty HTML
            or anchor_count == 0              # no links found at all
            or any(m in html for m in js_markers)  # JS framework detected
        )

        if is_js_rendered:
            print(f"  [DETECTED] JS-rendered page → switching to Selenium")
            use_selenium = True
        else:
            # Fast path — BeautifulSoup
            for tag in soup.find_all("a", href=True):
                href = tag["href"].strip()
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                full_url = urljoin(url, href)
                if same_domain_only:
                    if urlparse(full_url).netloc == base_domain:
                        links.add(full_url)
                else:
                    links.add(full_url)

    except requests.exceptions.RequestException as e:
        print(f"  [REQUEST FAILED] {e} → trying Selenium")
        use_selenium = True

    if use_selenium:
        selenium_links = get_links_with_selenium(url, base_domain, same_domain_only)
        links.update(selenium_links)

    return list(links)


# ── Main Crawler ───────────────────────────────────────────────────────────────

def crawl(start_url, max_pages=20, same_domain_only=True, check_load_time=True):
    """
    Crawl a website from start_url up to max_pages.

    Returns:
        dict: {
            page_url: {
                "links": [ list of URLs ],
                "load_time": { load_time_s, status, ... }
            }
        }
    """
    visited  = set()
    to_visit = [start_url]
    crawl_map = {}

    print(f"\n[CRAWLER] Starting  : {start_url}")
    print(f"[CRAWLER] Max pages : {max_pages}")
    print(f"[CRAWLER] Load time : {'ON (Selenium)' if check_load_time else 'OFF'}\n")

    while to_visit and len(visited) < max_pages:
        current_url = to_visit.pop(0)
        if current_url in visited:
            continue

        print(f"\n[CRAWLING] {current_url}")

        links     = get_all_links(current_url, same_domain_only)
        load_time = get_page_load_time(current_url) if check_load_time else None

        visited.add(current_url)
        crawl_map[current_url] = {
            "links":     links,
            "load_time": load_time
        }

        for link in links:
            if link not in visited:
                to_visit.append(link)

    print(f"\n[DONE] Crawled {len(visited)} page(s)")
    return crawl_map


# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TARGET_URL = "https://books.toscrape.com"  # safe test site

    result = crawl(TARGET_URL, max_pages=5)

    print("\n" + "=" * 55)
    print("CRAWL RESULTS")
    print("=" * 55)

    for page, data in result.items():
        links    = data["links"]
        load     = data.get("load_time")
        load_str = f"{load['load_time_s']}s ({load['status']})" if load else "N/A"
        print(f"\nPage      : {page}")
        print(f"Links     : {len(links)}")
        print(f"Load Time : {load_str}")
        for link in links[:5]:
            print(f"  → {link}")
        if len(links) > 5:
            print(f"  ... and {len(links) - 5} more")