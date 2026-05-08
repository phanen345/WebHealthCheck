import time
from crawler import create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Device Viewport Profiles ───────────────────────────────────────────────────

DEVICES = {
    "Mobile S"  : {"width": 320,  "height": 568,  "type": "mobile"},
    "Mobile M"  : {"width": 375,  "height": 667,  "type": "mobile"},
    "Mobile L"  : {"width": 425,  "height": 926,  "type": "mobile"},
    "Tablet"    : {"width": 768,  "height": 1024, "type": "tablet"},
    "Laptop"    : {"width": 1280, "height": 800,  "type": "desktop"},
}


# ── Single Viewport Check ──────────────────────────────────────────────────────

def check_viewport(driver, url, device_name, viewport):
    """
    Load a page at a specific viewport size and check for responsive issues.

    Checks performed:
      1. Horizontal scroll (layout overflow)
      2. Viewport meta tag present
      3. Text readability (font-size >= 12px)
      4. Touch target sizes (buttons >= 44px)
      5. Images overflow
      6. Fixed-width elements wider than viewport
      7. Screenshot capture

    Returns:
        dict: { device, width, height, issues, status, screenshot }
    """
    width  = viewport["width"]
    height = viewport["height"]
    issues = []

    try:
        # ── Set viewport size ──────────────────────────────────────────────
        driver.set_window_size(width, height)
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)  # allow responsive CSS to settle

        # ── 1. Horizontal scroll check ─────────────────────────────────────
        scroll_width  = driver.execute_script("return document.body.scrollWidth")
        client_width  = driver.execute_script("return document.body.clientWidth")
        has_h_scroll  = scroll_width > client_width


        if has_h_scroll:
            issues.append({
                "type"    : "HORIZONTAL SCROLL",
                "severity": "HIGH",
                "detail"  : f"Page overflows horizontally — scrollWidth {scroll_width}px > viewportWidth {client_width}px",
                "fix"     : "Add overflow-x: hidden or fix element widths exceeding viewport"
            })

        # ── 2. Viewport meta tag ───────────────────────────────────────────
        viewport_meta = driver.execute_script("""
            var meta = document.querySelector('meta[name="viewport"]');
            return meta ? meta.getAttribute('content') : null;
        """)

        if not viewport_meta:
            issues.append({
                "type"    : "MISSING VIEWPORT META",
                "severity": "HIGH",
                "detail"  : "No <meta name='viewport'> tag found",
                "fix"     : "Add: <meta name='viewport' content='width=device-width, initial-scale=1'>"
            })
        elif "width=device-width" not in viewport_meta:
            issues.append({
                "type"    : "INCORRECT VIEWPORT META",
                "severity": "MEDIUM",
                "detail"  : f"Viewport meta exists but may be misconfigured: {viewport_meta}",
                "fix"     : "Set content='width=device-width, initial-scale=1'"
            })

        # ── 3. Font size readability ───────────────────────────────────────
        small_text_count = driver.execute_script("""
            var elements = document.querySelectorAll('p, span, li, a, td, label');
            var small = 0;
            elements.forEach(function(el) {
                var size = parseFloat(window.getComputedStyle(el).fontSize);
                if (size < 12) small++;
            });
            return small;
        """)

        if small_text_count > 0:
            issues.append({
                "type"    : "SMALL TEXT",
                "severity": "MEDIUM",
                "detail"  : f"{small_text_count} element(s) have font-size below 12px",
                "fix"     : "Ensure minimum font size is 12px for readability on mobile"
            })

        # ── 4. Touch target size (buttons/links >= 44px) ───────────────────
        small_targets = driver.execute_script("""
            var targets = document.querySelectorAll('a, button, input[type=submit], input[type=button]');
            var small = [];
            targets.forEach(function(el) {
                var rect = el.getBoundingClientRect();
                if ((rect.width > 0 || rect.height > 0) && (rect.width < 44 || rect.height < 44)) {
                    small.push({
                        tag   : el.tagName,
                        text  : el.innerText ? el.innerText.slice(0, 30) : '',
                        width : Math.round(rect.width),
                        height: Math.round(rect.height)
                    });
                }
            });
            return small.slice(0, 5);
        """)

        if small_targets:
            issues.append({
                "type"    : "SMALL TOUCH TARGETS",
                "severity": "MEDIUM",
                "detail"  : f"{len(small_targets)} button(s)/link(s) smaller than 44x44px — hard to tap on mobile",
                "fix"     : "Set minimum height/width of 44px on all interactive elements",
                "examples": small_targets
            })

        # ── 5. Image overflow check ────────────────────────────────────────
        overflow_images = driver.execute_script("""
            var imgs = document.querySelectorAll('img');
            var overflow = [];
            imgs.forEach(function(img) {
                if (img.naturalWidth > 0 && img.offsetWidth > window.innerWidth) {
                    overflow.push(img.src ? img.src.slice(0, 60) : 'unknown');
                }
            });
            return overflow.slice(0, 5);
        """)

        if overflow_images:
            issues.append({
                "type"    : "IMAGE OVERFLOW",
                "severity": "MEDIUM",
                "detail"  : f"{len(overflow_images)} image(s) wider than viewport",
                "fix"     : "Add max-width: 100% to img elements",
                "examples": overflow_images
            })

        # ── 6. Fixed-width elements wider than viewport ────────────────────
        fixed_wide = driver.execute_script("""
            var all = document.querySelectorAll('div, section, table, nav, header, footer');
            var wide = 0;
            var vw = window.innerWidth;
            all.forEach(function(el) {
                var rect = el.getBoundingClientRect();
                if (rect.width > vw + 5) wide++;
            });
            return wide;
        """)

        if fixed_wide > 0:
            issues.append({
                "type"    : "FIXED WIDTH ELEMENTS",
                "severity": "LOW",
                "detail"  : f"{fixed_wide} element(s) wider than viewport — likely fixed pixel widths",
                "fix"     : "Use max-width: 100% and avoid fixed pixel widths in layout"
            })



        # ── 7. Screenshot ──────────────────────────────────────────────────────────────────────
        import os

        BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
        SHOT_DIR    = os.path.join(BASE_DIR, "screenshots", "responsive")
        os.makedirs(SHOT_DIR, exist_ok=True)

        safe_device = device_name.replace(" ", "_").lower()
        safe_url    = url.replace("https://", "").replace("http://", "").replace("/", "_")[:30]
        shot_path   = os.path.join(SHOT_DIR, f"{safe_url}_{safe_device}.png")
        driver.save_screenshot(shot_path)
        print(f"    [SCREENSHOT] Saved: {shot_path}")
        # # ── 7. Screenshot ──────────────────────────────────────────────────
        # import os
        # os.makedirs("screenshots/responsive", exist_ok=True)
        # safe_device = device_name.replace(" ", "_").lower()
        # safe_url    = url.replace("https://", "").replace("http://", "").replace("/", "_")[:30]
        # shot_path   = f"screenshots/responsive/{safe_url}_{safe_device}.png"
        # driver.save_screenshot(shot_path)
        # print(f"    [SCREENSHOT] Saved: {shot_path}")

        # ── Classify overall status ────────────────────────────────────────
        severities = [i["severity"] for i in issues]
        if "HIGH" in severities:
            status = "FAIL"
        elif "MEDIUM" in severities:
            status = "WARN"
        elif "LOW" in severities:
            status = "PASS WITH NOTES"
        else:
            status = "PASS"

        print(f"    [{status}] {device_name} ({width}x{height}) — {len(issues)} issue(s)")

        return {
            "device"    : device_name,
            "width"     : width,
            "height"    : height,
            "type"      : viewport["type"],
            "status"    : status,
            "issues"    : issues,
            "screenshot": shot_path
        }

    except Exception as e:
        print(f"    [ERROR] {device_name}: {e}")
        return {
            "device" : device_name,
            "width"  : width,
            "height" : height,
            "type"   : viewport["type"],
            "status" : "ERROR",
            "issues" : [{"type": "ERROR", "severity": "ERROR", "detail": str(e), "fix": ""}],
            "screenshot": None
        }


# ── Single Page Responsive Check ──────────────────────────────────────────────

def check_page_responsiveness(url, driver=None):
    """
    Check a single page across all device viewports.

    Returns:
        dict: { url, viewports: [...], summary }
    """
    own_driver = driver is None
    if own_driver:
        driver = create_driver(headless=True)

    print(f"\n  [RESPONSIVE] Checking: {url[:60]}")

    viewport_results = []

    try:
        for device_name, viewport in DEVICES.items():
            result = check_viewport(driver, url, device_name, viewport)
            viewport_results.append(result)

    finally:
        if own_driver:
            driver.quit()

    # ── Summary ────────────────────────────────────────────────────────────
    summary = {
        "total_viewports" : len(viewport_results),
        "pass"            : sum(1 for v in viewport_results if v["status"] == "PASS"),
        "warn"            : sum(1 for v in viewport_results if v["status"] == "WARN"),
        "fail"            : sum(1 for v in viewport_results if v["status"] == "FAIL"),
        "errors"          : sum(1 for v in viewport_results if v["status"] == "ERROR"),
        "has_h_scroll"    : any(
            any(i["type"] == "HORIZONTAL SCROLL" for i in v["issues"])
            for v in viewport_results
        ),
        "missing_viewport_meta": any(
            any(i["type"] == "MISSING VIEWPORT META" for i in v["issues"])
            for v in viewport_results
        ),
        "overall": "FAIL" if any(v["status"] == "FAIL" for v in viewport_results)
                   else "WARN" if any(v["status"] == "WARN" for v in viewport_results)
                   else "PASS"
    }

    return {
        "url"      : url,
        "viewports": viewport_results,
        "summary"  : summary
    }


# ── Multi-page Responsive Checker ─────────────────────────────────────────────

def check_all_responsive(crawl_map, max_pages=5):
    """
    Check responsiveness across crawled pages.
    Limits to max_pages to keep scan time reasonable.

    Args:
        crawl_map (dict): Output from crawler.crawl()
        max_pages (int): Max pages to test (responsive checks are slow)

    Returns:
        dict: { summary, pages: [...] }
    """
    pages = list(crawl_map.keys())[:max_pages]
    print(f"\n[RESPONSIVE CHECKER] Scanning {len(pages)} page(s) across {len(DEVICES)} device(s)...\n")

    driver     = create_driver(headless=True)
    all_pages  = []

    try:
        for url in pages:
            result = check_page_responsiveness(url, driver=driver)
            all_pages.append(result)
    finally:
        driver.quit()

    # ── Global summary ─────────────────────────────────────────────────────
    all_viewports = [v for p in all_pages for v in p["viewports"]]
    summary = {
        "pages_tested"        : len(all_pages),
        "viewports_tested"    : len(all_viewports),
        "total_pass"          : sum(1 for v in all_viewports if v["status"] == "PASS"),
        "total_warn"          : sum(1 for v in all_viewports if v["status"] == "WARN"),
        "total_fail"          : sum(1 for v in all_viewports if v["status"] == "FAIL"),
        "h_scroll_pages"      : sum(1 for p in all_pages if p["summary"]["has_h_scroll"]),
        "missing_meta_pages"  : sum(1 for p in all_pages if p["summary"]["missing_viewport_meta"]),
        "overall"             : "FAIL" if any(p["summary"]["overall"] == "FAIL" for p in all_pages)
                                else "WARN" if any(p["summary"]["overall"] == "WARN" for p in all_pages)
                                else "PASS"
    }

    print(f"\n[RESPONSIVE DONE]")
    print(f"  Pages tested  : {summary['pages_tested']}")
    print(f"  Overall       : {summary['overall']}")
    print(f"  PASS          : {summary['total_pass']}")
    print(f"  WARN          : {summary['total_warn']}")
    print(f"  FAIL          : {summary['total_fail']}")
    print(f"  H-Scroll pages: {summary['h_scroll_pages']}")

    return {"summary": summary, "pages": all_pages}


# ── Console Report ─────────────────────────────────────────────────────────────

def print_responsive_report(report):
    print("\n" + "=" * 60)
    print("MOBILE RESPONSIVENESS REPORT")
    print("=" * 60)

    s = report["summary"]
    print(f"  Pages tested        : {s['pages_tested']}")
    print(f"  Overall status      : {s['overall']}")
    print(f"  Horizontal scroll   : {s['h_scroll_pages']} page(s) affected")
    print(f"  Missing viewport tag: {s['missing_meta_pages']} page(s)")

    for page in report["pages"]:
        print(f"\n  Page: {page['url']}")
        for v in page["viewports"]:
            status = v["status"]
            icon   = "✓" if status == "PASS" else "✗" if status == "FAIL" else "!"
            print(f"    [{icon}] {v['device']:<12} {v['width']}x{v['height']} → {status}")
            for issue in v["issues"]:
                if issue["type"] != "ERROR":
                    print(f"         [{issue['severity']}] {issue['type']}: {issue['detail'][:60]}")


# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from crawler import crawl

    TARGET_URL = "https://books.toscrape.com"

    print(f"[RESPONSIVE CHECKER] Target: {TARGET_URL}")
    crawl_map = crawl(TARGET_URL, max_pages=3, check_load_time=False)
    report    = check_all_responsive(crawl_map, max_pages=3)
    print_responsive_report(report)
