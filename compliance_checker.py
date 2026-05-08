import time
import os
from crawler import create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException


# ── Keyword Lists ──────────────────────────────────────────────────────────────

# Cookie consent related keywords
COOKIE_KEYWORDS = [
    "cookie", "cookies", "gdpr", "consent", "privacy", "we use",
    "accept all", "accept cookies", "agree", "preferences",
    "data protection", "tracking", "analytics"
]

# Popup / overlay keywords
POPUP_KEYWORDS = [
    "subscribe", "newsletter", "sign up", "signup", "offer",
    "discount", "deal", "notification", "allow", "block",
    "download", "free", "limited time", "exclusive"
]

# Cookie attributes that should be set
SECURE_COOKIE_ATTRS = {
    "httpOnly" : "Prevents JS access to cookie — protects against XSS",
    "secure"   : "Cookie only sent over HTTPS — protects against interception",
    "sameSite" : "Controls cross-site requests — protects against CSRF"
}


# ── Cookie Banner Detection ────────────────────────────────────────────────────

def detect_cookie_banner(driver):
    """
    Detect if a cookie consent banner exists on the page.
    Uses multiple strategies:
      1. Known class/id patterns
      2. Keyword scan in visible elements
      3. Fixed/sticky positioned overlays

    Returns:
        dict: { found, element_info, blocks_content, has_accept, has_reject, has_preferences }
    """
    result = {
        "found"           : False,
        "element_tag"     : None,
        "element_id"      : None,
        "element_class"   : None,
        "blocks_content"  : False,
        "has_accept_btn"  : False,
        "has_reject_btn"  : False,
        "has_preferences" : False,
        "text_snippet"    : None,
        "detection_method": None
    }

    # ── Strategy 1: Known ID/class patterns ───────────────────────────────
    known_patterns = [
        "[id*='cookie']", "[class*='cookie']",
        "[id*='consent']", "[class*='consent']",
        "[id*='gdpr']", "[class*='gdpr']",
        "[id*='privacy-banner']", "[class*='privacy-banner']",
        "[id*='cookie-notice']", "[class*='cookie-notice']",
        "[aria-label*='cookie']", "[aria-label*='consent']"
    ]

    for selector in known_patterns:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed() and el.size["height"] > 10:
                    result.update({
                        "found"           : True,
                        "element_tag"     : el.tag_name,
                        "element_id"      : el.get_attribute("id"),
                        "element_class"   : el.get_attribute("class"),
                        "text_snippet"    : el.text[:100] if el.text else "",
                        "detection_method": f"CSS selector: {selector}"
                    })
                    break
        except Exception:
            continue
        if result["found"]:
            break

    # ── Strategy 2: Keyword scan in visible text ───────────────────────────
    if not result["found"]:
        try:
            all_elements = driver.find_elements(By.CSS_SELECTOR, "div, section, aside, nav, footer")
            for el in all_elements:
                try:
                    if not el.is_displayed():
                        continue
                    text = (el.text or "").lower()
                    if any(kw in text for kw in COOKIE_KEYWORDS) and len(text) < 500:
                        result.update({
                            "found"           : True,
                            "element_tag"     : el.tag_name,
                            "element_id"      : el.get_attribute("id"),
                            "element_class"   : el.get_attribute("class"),
                            "text_snippet"    : el.text[:100],
                            "detection_method": "keyword scan"
                        })
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # ── Strategy 3: Fixed/sticky overlay ──────────────────────────────────
    if not result["found"]:
        try:
            fixed_els = driver.execute_script("""
                var els = document.querySelectorAll('*');
                var fixed = [];
                for (var i = 0; i < els.length; i++) {
                    var pos = window.getComputedStyle(els[i]).position;
                    if ((pos === 'fixed' || pos === 'sticky') && els[i].offsetHeight > 30) {
                        fixed.push({
                            tag: els[i].tagName,
                            id: els[i].id,
                            cls: els[i].className.toString().slice(0, 60),
                            text: els[i].innerText ? els[i].innerText.slice(0, 80) : ''
                        });
                    }
                }
                return fixed.slice(0, 5);
            """)
            for el in fixed_els:
                text_lower = el.get("text", "").lower()
                if any(kw in text_lower for kw in COOKIE_KEYWORDS):
                    result.update({
                        "found"           : True,
                        "element_tag"     : el.get("tag"),
                        "element_id"      : el.get("id"),
                        "element_class"   : el.get("cls"),
                        "text_snippet"    : el.get("text", "")[:100],
                        "detection_method": "fixed/sticky overlay"
                    })
                    break
        except Exception:
            pass

    if not result["found"]:
        return result

    # ── If banner found — check buttons ───────────────────────────────────
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button, a, input[type='button']")
        for btn in buttons:
            if not btn.is_displayed():
                continue
            btn_text = (btn.text or btn.get_attribute("value") or "").lower()

            if any(w in btn_text for w in ["accept", "agree", "ok", "allow", "got it"]):
                result["has_accept_btn"] = True
            if any(w in btn_text for w in ["reject", "decline", "deny", "refuse", "no thanks"]):
                result["has_reject_btn"] = True
            if any(w in btn_text for w in ["prefer", "setting", "manage", "custom", "option"]):
                result["has_preferences"] = True
    except Exception:
        pass

    # ── Does banner block content? ─────────────────────────────────────────
    try:
        body_height   = driver.execute_script("return document.body.scrollHeight")
        banner_height = driver.execute_script("""
            var el = document.querySelector('[id*="cookie"],[class*="cookie"],[id*="consent"],[class*="consent"]');
            return el ? el.offsetHeight : 0;
        """)
        if banner_height > 0 and banner_height > (body_height * 0.3):
            result["blocks_content"] = True
    except Exception:
        pass

    return result


# ── Popup Detection ────────────────────────────────────────────────────────────

def detect_popups(driver):
    """
    Detect intrusive popups/overlays after page load.
    Waits 3s for delayed popups to appear.

    Returns:
        list: [ { type, text, blocks_content, has_close_btn } ]
    """
    time.sleep(3)   # wait for delayed popups
    popups = []

    try:
        # Check for modal overlays
        modal_selectors = [
            "[class*='modal']", "[class*='popup']", "[class*='overlay']",
            "[class*='dialog']", "[role='dialog']", "[role='alertdialog']",
            "[id*='modal']", "[id*='popup']"
        ]

        for selector in modal_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    try:
                        if not el.is_displayed() or el.size["height"] < 50:
                            continue

                        text = (el.text or "").lower()
                        popup_type = "GENERIC POPUP"

                        if any(kw in text for kw in ["subscribe", "newsletter", "email"]):
                            popup_type = "NEWSLETTER POPUP"
                        elif any(kw in text for kw in ["discount", "offer", "deal", "off"]):
                            popup_type = "PROMOTIONAL POPUP"
                        elif any(kw in text for kw in ["notification", "allow", "block"]):
                            popup_type = "NOTIFICATION PROMPT"
                        elif any(kw in text for kw in COOKIE_KEYWORDS):
                            continue  # already handled by cookie banner

                        # Check for close button
                        has_close = False
                        close_btns = el.find_elements(By.CSS_SELECTOR,
                            "button, [aria-label*='close'], [class*='close'], [id*='close']")
                        for btn in close_btns:
                            btn_text = (btn.text or btn.get_attribute("aria-label") or "").lower()
                            if any(w in btn_text for w in ["close", "x", "dismiss", "no thanks", "×"]):
                                has_close = True
                                break

                        popups.append({
                            "type"          : popup_type,
                            "selector"      : selector,
                            "text_snippet"  : el.text[:80] if el.text else "",
                            "has_close_btn" : has_close,
                            "blocks_content": True,   # modals always block
                            "severity"      : "MEDIUM" if has_close else "HIGH"
                        })
                    except Exception:
                        continue
            except Exception:
                continue

    except Exception as e:
        popups.append({"type": "ERROR", "error": str(e), "severity": "ERROR"})

    # Deduplicate by type
    seen = set()
    unique = []
    for p in popups:
        if p["type"] not in seen:
            seen.add(p["type"])
            unique.append(p)

    return unique


# ── Browser Cookie Security Audit ─────────────────────────────────────────────

def audit_cookies(driver, url):
    """
    Audit all cookies set by the site for security attributes.

    Returns:
        dict: { total, secure_count, issues: [...], cookies: [...] }
    """
    try:
        driver.get(url)
        time.sleep(2)
        all_cookies = driver.get_cookies()
    except Exception as e:
        return {"total": 0, "issues": [str(e)], "cookies": []}

    cookie_results = []
    issues         = []

    for cookie in all_cookies:
        name       = cookie.get("name", "unknown")
        is_secure  = cookie.get("secure", False)
        is_http    = cookie.get("httpOnly", False)
        same_site  = cookie.get("sameSite", None)
        cookie_issues = []

        if not is_secure:
            cookie_issues.append("Missing 'Secure' flag — sent over HTTP too")
        if not is_http:
            cookie_issues.append("Missing 'HttpOnly' flag — accessible via JavaScript (XSS risk)")
        if not same_site or same_site.lower() == "none":
            cookie_issues.append("Missing/weak 'SameSite' — CSRF risk")

        severity = "HIGH" if len(cookie_issues) >= 2 else "MEDIUM" if cookie_issues else "OK"

        cookie_results.append({
            "name"      : name,
            "secure"    : is_secure,
            "httpOnly"  : is_http,
            "sameSite"  : same_site or "Not set",
            "severity"  : severity,
            "issues"    : cookie_issues
        })

        issues.extend([f"[{name}] {i}" for i in cookie_issues])

    summary = {
        "total"        : len(cookie_results),
        "secure_count" : sum(1 for c in cookie_results if c["severity"] == "OK"),
        "high_risk"    : sum(1 for c in cookie_results if c["severity"] == "HIGH"),
        "medium_risk"  : sum(1 for c in cookie_results if c["severity"] == "MEDIUM"),
        "issues"       : issues,
        "cookies"      : cookie_results
    }

    return summary


# ── Full Page Compliance Check ─────────────────────────────────────────────────

def check_page_compliance(url, driver=None):
    """
    Run full cookie + popup + compliance check on a single page.

    Returns:
        dict: { url, cookie_banner, popups, cookie_audit, gdpr_score, issues }
    """
    own_driver = driver is None
    if own_driver:
        driver = create_driver(headless=True)

    print(f"\n  [COMPLIANCE] Checking: {url[:60]}")

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)

        # Take screenshot before any interaction
        os.makedirs("screenshots/compliance", exist_ok=True)
        safe = url.replace("https://","").replace("http://","").replace("/","_")[:30]
        shot_path = f"screenshots/compliance/{safe}_compliance.png"
        driver.save_screenshot(shot_path)

        # Run all checks
        cookie_banner = detect_cookie_banner(driver)
        popups        = detect_popups(driver)
        cookie_audit  = audit_cookies(driver, url)

        # ── GDPR Compliance Score (0-100) ──────────────────────────────────
        score  = 100
        issues = []

        if not cookie_banner["found"]:
            score -= 30
            issues.append({
                "severity": "HIGH",
                "issue"   : "No cookie consent banner detected",
                "fix"     : "Add GDPR-compliant cookie consent banner before setting any tracking cookies"
            })
        else:
            if not cookie_banner["has_reject_btn"]:
                score -= 15
                issues.append({
                    "severity": "HIGH",
                    "issue"   : "Cookie banner has no Reject/Decline option",
                    "fix"     : "GDPR requires equal prominence for reject option"
                })
            if not cookie_banner["has_preferences"]:
                score -= 10
                issues.append({
                    "severity": "MEDIUM",
                    "issue"   : "No cookie preference/settings option found",
                    "fix"     : "Allow users to manage individual cookie categories"
                })
            if cookie_banner["blocks_content"]:
                score -= 10
                issues.append({
                    "severity": "MEDIUM",
                    "issue"   : "Cookie banner blocks page content",
                    "fix"     : "Banner should allow access to content without forced acceptance"
                })

        # Popup issues
        for popup in popups:
            if not popup.get("has_close_btn"):
                score -= 10
                issues.append({
                    "severity": "HIGH",
                    "issue"   : f"{popup['type']} has no close button — user cannot dismiss",
                    "fix"     : "Always provide a clear close/dismiss option on popups"
                })
            else:
                score -= 5
                issues.append({
                    "severity": "LOW",
                    "issue"   : f"{popup['type']} detected — may affect UX",
                    "fix"     : "Consider reducing popup frequency or using less intrusive alternatives"
                })

        # Cookie security issues
        if cookie_audit["high_risk"] > 0:
            score -= 15
            issues.append({
                "severity": "HIGH",
                "issue"   : f"{cookie_audit['high_risk']} cookie(s) missing multiple security flags",
                "fix"     : "Set Secure, HttpOnly, and SameSite=Strict on all sensitive cookies"
            })
        elif cookie_audit["medium_risk"] > 0:
            score -= 5
            issues.append({
                "severity": "MEDIUM",
                "issue"   : f"{cookie_audit['medium_risk']} cookie(s) missing some security flags",
                "fix"     : "Review and add missing Secure/HttpOnly/SameSite attributes"
            })

        score = max(0, score)
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 50 else "F"

        status_icon = "✓" if score >= 75 else "!" if score >= 50 else "✗"
        print(f"    [{status_icon}] Score: {score}/100 | Banner: {'YES' if cookie_banner['found'] else 'NO'} | "
              f"Popups: {len(popups)} | Cookies: {cookie_audit['total']}")

        return {
            "url"          : url,
            "screenshot"   : shot_path,
            "cookie_banner": cookie_banner,
            "popups"       : popups,
            "cookie_audit" : cookie_audit,
            "gdpr_score"   : score,
            "gdpr_grade"   : grade,
            "issues"       : issues
        }

    except Exception as e:
        print(f"    [ERROR] {e}")
        return {"url": url, "error": str(e), "gdpr_score": 0, "gdpr_grade": "F", "issues": []}
    finally:
        if own_driver:
            driver.quit()


# ── Multi-page Compliance Checker ──────────────────────────────────────────────

def check_all_compliance(crawl_map, max_pages=3):
    """
    Check cookie + popup compliance across crawled pages.
    Limited to homepage + a few pages (banners usually only on first load).

    Args:
        crawl_map (dict): Output from crawler.crawl()
        max_pages (int): Pages to check (default 3 — banner is usually on all)

    Returns:
        dict: { summary, pages }
    """
    pages = list(crawl_map.keys())[:max_pages]
    print(f"\n[COMPLIANCE CHECKER] Scanning {len(pages)} page(s)...\n")

    driver    = create_driver(headless=True)
    all_pages = []

    try:
        for url in pages:
            result = check_page_compliance(url, driver=driver)
            all_pages.append(result)
    finally:
        driver.quit()

    # ── Global summary ─────────────────────────────────────────────────────
    valid_pages = [p for p in all_pages if "error" not in p]
    avg_score   = (
        sum(p["gdpr_score"] for p in valid_pages) // len(valid_pages)
        if valid_pages else 0
    )

    summary = {
        "pages_scanned"      : len(all_pages),
        "avg_gdpr_score"     : avg_score,
        "has_cookie_banner"  : sum(1 for p in valid_pages if p.get("cookie_banner", {}).get("found")),
        "has_reject_option"  : sum(1 for p in valid_pages if p.get("cookie_banner", {}).get("has_reject_btn")),
        "total_popups"       : sum(len(p.get("popups", [])) for p in valid_pages),
        "total_cookies"      : sum(p.get("cookie_audit", {}).get("total", 0) for p in valid_pages),
        "high_risk_cookies"  : sum(p.get("cookie_audit", {}).get("high_risk", 0) for p in valid_pages),
        "overall_grade"      : "A" if avg_score >= 90 else "B" if avg_score >= 75 else "C" if avg_score >= 50 else "F"
    }

    print(f"\n[COMPLIANCE DONE]")
    print(f"  Pages scanned    : {summary['pages_scanned']}")
    print(f"  Avg GDPR Score   : {summary['avg_gdpr_score']}/100")
    print(f"  Cookie banner    : {summary['has_cookie_banner']} page(s)")
    print(f"  Has reject option: {summary['has_reject_option']} page(s)")
    print(f"  Popups found     : {summary['total_popups']}")
    print(f"  Cookies audited  : {summary['total_cookies']}")
    print(f"  High risk cookies: {summary['high_risk_cookies']}")

    return {"summary": summary, "pages": all_pages}


# ── Console Report ─────────────────────────────────────────────────────────────

def print_compliance_report(report):
    print("\n" + "=" * 60)
    print("COOKIE & POPUP COMPLIANCE REPORT")
    print("=" * 60)

    s = report["summary"]
    print(f"  Avg GDPR Score   : {s['avg_gdpr_score']}/100  Grade: {s['overall_grade']}")
    print(f"  Cookie Banner    : {'FOUND' if s['has_cookie_banner'] else 'MISSING'}")
    print(f"  Reject Option    : {'YES' if s['has_reject_option'] else 'NO'}")
    print(f"  Popups Detected  : {s['total_popups']}")
    print(f"  Cookies Audited  : {s['total_cookies']}")
    print(f"  High Risk Cookies: {s['high_risk_cookies']}")

    for page in report["pages"]:
        print(f"\n  Page: {page['url']}")
        print(f"    GDPR Score  : {page.get('gdpr_score', 'N/A')}/100")

        banner = page.get("cookie_banner", {})
        print(f"    Cookie Banner: {'YES' if banner.get('found') else 'NO'}")
        if banner.get("found"):
            print(f"      Accept btn : {'YES' if banner.get('has_accept_btn') else 'NO'}")
            print(f"      Reject btn : {'YES' if banner.get('has_reject_btn') else 'NO'}")
            print(f"      Preferences: {'YES' if banner.get('has_preferences') else 'NO'}")

        if page.get("popups"):
            print(f"    Popups ({len(page['popups'])}):")
            for p in page["popups"]:
                print(f"      [{p['severity']}] {p['type']} — Close btn: {'YES' if p.get('has_close_btn') else 'NO'}")

        if page.get("issues"):
            print(f"    Issues:")
            for i in page["issues"]:
                print(f"      [{i['severity']}] {i['issue']}")


# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from crawler import crawl

    TARGET_URL = "https://quotes.toscrape.com"

    print(f"[COMPLIANCE CHECKER] Target: {TARGET_URL}")
    crawl_map = crawl(TARGET_URL, max_pages=3, check_load_time=False)
    report    = check_all_compliance(crawl_map, max_pages=3)
    print_compliance_report(report)
