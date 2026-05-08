import time
from urllib.parse import urlparse
from crawler import create_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Form Risk Classifier ───────────────────────────────────────────────────────

def classify_form_risk(form_data):
    """
    Assign a risk level to a form based on its security properties.

    Risk logic:
      HIGH   → password/payment field + HTTP action (plaintext credential leak)
      HIGH   → no action URL at all on sensitive form
      MEDIUM → HTTP action on non-sensitive form
      MEDIUM → no CSRF token on POST form
      LOW    → autocomplete=on on password field
      INFO   → form looks fine but worth noting
    """
    issues   = []
    severity = "INFO"

    action      = form_data.get("action", "")
    method      = form_data.get("method", "get").lower()
    has_https   = action.startswith("https://") if action else False
    has_http    = action.startswith("http://")
    is_sensitive = form_data.get("has_password") or form_data.get("has_payment")
    has_csrf    = form_data.get("has_csrf_token")
    has_auto_pw = form_data.get("password_autocomplete_on")

    # ── HIGH severity checks ───────────────────────────────────────────────
    if is_sensitive and has_http:
        issues.append("Password/payment field submits over HTTP — credentials sent in plaintext")
        severity = "HIGH"

    if is_sensitive and not action:
        issues.append("Sensitive form has no action URL — submission target unknown")
        severity = "HIGH"

    # ── MEDIUM severity checks ─────────────────────────────────────────────
    if has_http and not is_sensitive:
        issues.append("Form submits over HTTP — data not encrypted in transit")
        if severity == "INFO":
            severity = "MEDIUM"

    if method == "post" and not has_csrf:
        issues.append("POST form missing CSRF token — vulnerable to cross-site request forgery")
        if severity == "INFO":
            severity = "MEDIUM"

    # ── LOW severity checks ────────────────────────────────────────────────
    if has_auto_pw:
        issues.append("Password field has autocomplete enabled — browser may cache credentials")
        if severity == "INFO":
            severity = "LOW"

    # ── No issues ─────────────────────────────────────────────────────────
    if not issues:
        issues.append("No critical issues detected")

    return severity, issues


# ── Single Form Analyser ───────────────────────────────────────────────────────

def analyse_form(driver, form_element, page_url):
    """
    Extract and analyse security properties of a single <form> element.

    Returns:
        dict: full form data + risk assessment
    """
    try:
        # Basic form attributes
        action = form_element.get_attribute("action") or ""
        method = form_element.get_attribute("method") or "get"
        form_id   = form_element.get_attribute("id") or "—"
        form_name = form_element.get_attribute("name") or "—"
        enctype   = form_element.get_attribute("enctype") or "application/x-www-form-urlencoded"

        # Resolve relative action URL
        if action and not action.startswith("http"):
            parsed = urlparse(page_url)
            base   = f"{parsed.scheme}://{parsed.netloc}"
            action = base + ("/" if not action.startswith("/") else "") + action

        # ── Input field inventory ──────────────────────────────────────────
        inputs = form_element.find_elements(By.TAG_NAME, "input")
        input_inventory = []
        has_password   = False
        has_payment    = False
        has_csrf_token = False
        password_autocomplete_on = False

        payment_keywords = ["card", "cvv", "ccv", "credit", "debit", "expiry", "billing"]

        for inp in inputs:
            itype  = (inp.get_attribute("type")         or "text").lower()
            iname  = (inp.get_attribute("name")         or "").lower()
            iid    = (inp.get_attribute("id")           or "").lower()
            iauto  = (inp.get_attribute("autocomplete") or "").lower()
            hidden_val = inp.get_attribute("value") if itype == "hidden" else None

            input_inventory.append({
                "type":         itype,
                "name":         iname or "—",
                "autocomplete": iauto or "not set"
            })

            if itype == "password":
                has_password = True
                if iauto not in ("off", "new-password", "current-password"):
                    password_autocomplete_on = True

            if any(kw in iname or kw in iid for kw in payment_keywords):
                has_payment = True

            # CSRF token detection — common naming patterns
            csrf_names = ["csrf", "_token", "authenticity_token", "__requestverificationtoken"]
            if itype == "hidden" and any(c in iname for c in csrf_names):
                has_csrf_token = True

        # Also check <button> and <select> counts
        buttons  = form_element.find_elements(By.TAG_NAME, "button")
        selects  = form_element.find_elements(By.TAG_NAME, "select")
        textareas = form_element.find_elements(By.TAG_NAME, "textarea")

        form_data = {
            "page_url":                page_url,
            "form_id":                 form_id,
            "form_name":               form_name,
            "action":                  action or "— (no action)",
            "method":                  method.upper(),
            "enctype":                 enctype,
            "input_count":             len(inputs),
            "button_count":            len(buttons),
            "select_count":            len(selects),
            "textarea_count":          len(textareas),
            "has_password":            has_password,
            "has_payment":             has_payment,
            "has_csrf_token":          has_csrf_token,
            "password_autocomplete_on": password_autocomplete_on,
            "inputs":                  input_inventory[:10],   # cap for display
        }

        severity, issues = classify_form_risk(form_data)
        form_data["severity"] = severity
        form_data["issues"]   = issues

        return form_data

    except Exception as e:
        return {
            "page_url": page_url,
            "error": str(e),
            "severity": "ERROR",
            "issues": [f"Failed to analyse form: {e}"]
        }


# ── Page-level Form Scanner ────────────────────────────────────────────────────

def scan_forms_on_page(url, driver=None):
    """
    Scan all forms on a single page.

    Returns:
        dict: { url, form_count, forms: [ form_data, ... ] }
    """
    own_driver = driver is None
    if own_driver:
        driver = create_driver(headless=True)

    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(1)   # small wait for JS-injected forms

        form_elements = driver.find_elements(By.TAG_NAME, "form")
        print(f"  [FORMS] Found {len(form_elements)} form(s) on {url[:60]}")

        forms = []
        for form_el in form_elements:
            data = analyse_form(driver, form_el, url)
            forms.append(data)

        return {
            "url":        url,
            "form_count": len(forms),
            "forms":      forms
        }

    except Exception as e:
        print(f"  [FORM ERROR] {url}: {e}")
        return {"url": url, "form_count": 0, "forms": [], "error": str(e)}
    finally:
        if own_driver:
            driver.quit()


# ── Multi-page Form Checker ────────────────────────────────────────────────────

def check_all_forms(crawl_map):
    """
    Scan forms across all crawled pages.
    Reuses a single Selenium driver for performance.

    Args:
        crawl_map (dict): Output from crawler.crawl()
                          { url: { "links": [...], "load_time": {...} } }

    Returns:
        dict: {
            "summary": { ... },
            "pages":   [ page-level results ]
        }
    """
    pages = list(crawl_map.keys())
    print(f"\n[FORM CHECKER] Scanning {len(pages)} page(s) for forms...\n")

    driver = create_driver(headless=True)
    all_pages = []

    try:
        for url in pages:
            result = scan_forms_on_page(url, driver=driver)
            all_pages.append(result)
    finally:
        driver.quit()

    # ── Flatten all forms for summary stats ───────────────────────────────
    all_forms = [f for page in all_pages for f in page.get("forms", [])]

    summary = {
        "pages_scanned":    len(pages),
        "total_forms":      len(all_forms),
        "high_risk":        sum(1 for f in all_forms if f.get("severity") == "HIGH"),
        "medium_risk":      sum(1 for f in all_forms if f.get("severity") == "MEDIUM"),
        "low_risk":         sum(1 for f in all_forms if f.get("severity") == "LOW"),
        "info":             sum(1 for f in all_forms if f.get("severity") == "INFO"),
        "password_forms":   sum(1 for f in all_forms if f.get("has_password")),
        "payment_forms":    sum(1 for f in all_forms if f.get("has_payment")),
        "missing_csrf":     sum(
            1 for f in all_forms
            if f.get("method") == "POST" and not f.get("has_csrf_token")
        ),
        "http_submissions": sum(
            1 for f in all_forms
            if isinstance(f.get("action"), str) and f["action"].startswith("http://")
        ),
    }

    print(f"\n[FORM CHECKER DONE]")
    print(f"  Total forms   : {summary['total_forms']}")
    print(f"  HIGH risk     : {summary['high_risk']}")
    print(f"  MEDIUM risk   : {summary['medium_risk']}")
    print(f"  Missing CSRF  : {summary['missing_csrf']}")
    print(f"  HTTP submit   : {summary['http_submissions']}")

    return {"summary": summary, "pages": all_pages}


# ── Console Report ─────────────────────────────────────────────────────────────

def print_form_report(report):
    print("\n" + "=" * 60)
    print("FORM SECURITY REPORT")
    print("=" * 60)

    s = report["summary"]
    print(f"  Pages scanned    : {s['pages_scanned']}")
    print(f"  Total forms      : {s['total_forms']}")
    print(f"  HIGH risk        : {s['high_risk']}")
    print(f"  MEDIUM risk      : {s['medium_risk']}")
    print(f"  Password forms   : {s['password_forms']}")
    print(f"  Payment forms    : {s['payment_forms']}")
    print(f"  Missing CSRF     : {s['missing_csrf']}")
    print(f"  HTTP submissions : {s['http_submissions']}")

    for page in report["pages"]:
        if not page.get("forms"):
            continue
        print(f"\n  Page: {page['url']}")
        for i, form in enumerate(page["forms"], 1):
            sev = form.get("severity", "INFO")
            print(f"\n    Form #{i}  [{sev}]")
            print(f"      Action  : {form.get('action')}")
            print(f"      Method  : {form.get('method')}")
            print(f"      Inputs  : {form.get('input_count')} | "
                  f"Password: {'YES' if form.get('has_password') else 'NO'} | "
                  f"CSRF: {'YES' if form.get('has_csrf_token') else 'NO'}")
            for issue in form.get("issues", []):
                icon = "!!" if sev == "HIGH" else "!" if sev == "MEDIUM" else "i"
                print(f"      [{icon}] {issue}")


# ── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from crawler import crawl

    TARGET_URL = "https://quotes.toscrape.com"   # has login form — good test

    print(f"[FORM CHECKER] Target: {TARGET_URL}")
    crawl_map = crawl(TARGET_URL, max_pages=5, check_load_time=False)
    report    = check_all_forms(crawl_map)
    print_form_report(report)
