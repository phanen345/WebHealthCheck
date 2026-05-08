import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from crawler import take_screenshot


# Status code categories
def classify_status(code):
    if code is None:
        return "ERROR"
    elif 200 <= code < 300:
        return "OK"
    elif 300 <= code < 400:
        return "REDIRECT"
    elif code == 404:
        return "BROKEN"
    elif 400 <= code < 500:
        return "CLIENT ERROR"
    elif code >= 500:
        return "SERVER ERROR"
    return "UNKNOWN"


def check_link(url):
    """
    Send a HEAD request to a URL and return its status.

    Args:
        url (str): URL to check

    Returns:
        dict: { url, status_code, status_label, error }
    """
    headers = {"User-Agent": "Mozilla/5.0 (WebHealthChecker/1.0)"}

    try:
        response = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
        code = response.status_code

        # Some servers block HEAD — fallback to GET
        if code == 405:
            response = requests.get(url, headers=headers, timeout=8, stream=True)
            code = response.status_code

        return {
            "url": url,
            "status_code": code,
            "status_label": classify_status(code),
            "error": None
        }

    except requests.exceptions.ConnectionError:
        return {"url": url, "status_code": None, "status_label": "ERROR", "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"url": url, "status_code": None, "status_label": "ERROR", "error": "Timeout"}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status_code": None, "status_label": "ERROR", "error": str(e)}


def check_all_links(crawl_map, max_workers=10):
    """
    Check all links discovered by the crawler.

    Args:
        crawl_map (dict): Output from crawler.crawl() → { page: [links] }
        max_workers (int): Parallel threads for faster checking

    Returns:
        dict: {
            "summary": { total, ok, broken, redirects, errors },
            "results": [ { url, status_code, status_label, error, found_on } ]
        }
    """

    # Flatten all links with their source page
    all_links = {}
    for page, links in crawl_map.items():
        for link in links:
            if link not in all_links:
                all_links[link] = page  # track which page it was found on

    print(f"\n[LINK CHECKER] Checking {len(all_links)} unique links...\n")

    results = []

    # Use threads for speed
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in all_links}

        for future in as_completed(future_to_url):
            result = future.result()
            result["found_on"] = all_links[result["url"]]
            results.append(result)
            status = result["status_label"]
            code = result["status_code"] or "N/A"
            print(f"  [{code}] {status} → {result['url'][:70]}")

    # Build summary
    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["status_label"] == "OK"),
        "broken": sum(1 for r in results if r["status_label"] == "BROKEN"),
        "redirects": sum(1 for r in results if r["status_label"] == "REDIRECT"),
        "errors": sum(1 for r in results if r["status_label"] == "ERROR"),
        "client_errors": sum(1 for r in results if r["status_label"] == "CLIENT ERROR"),
        "server_errors": sum(1 for r in results if r["status_label"] == "SERVER ERROR"),
    }

    print(f"\n[DONE] Total: {summary['total']} | OK: {summary['ok']} | "
          f"Broken: {summary['broken']} | Redirects: {summary['redirects']} | "
          f"Errors: {summary['errors']}")

    # ── Selenium: Screenshot all broken pages as evidence ─────────────────
    broken_results = [r for r in results if r["status_label"] == "BROKEN"]
    if broken_results:
        os.makedirs("screenshots", exist_ok=True)
        print(f"\n[SCREENSHOTS] Capturing {len(broken_results)} broken page(s) via Selenium...")
        for i, r in enumerate(broken_results):
            filename = f"screenshots/broken_{i+1}.png"
            shot = take_screenshot(r["url"], filename)
            r["screenshot"] = shot  # attach path → used in HTML report

    return {"summary": summary, "results": results}


if __name__ == "__main__":
    # Standalone test — simulating crawler output
    from crawler import crawl

    TARGET_URL = "https://example.com"
    crawl_map = crawl(TARGET_URL, max_pages=5)
    report = check_all_links(crawl_map)

    print("\n" + "=" * 50)
    print("BROKEN / ERROR LINKS")
    print("=" * 50)
    for r in report["results"]:
        if r["status_label"] not in ["OK", "REDIRECT"]:
            print(f"\n  URL       : {r['url']}")
            print(f"  Status    : {r['status_label']} ({r['status_code']})")
            print(f"  Found on  : {r['found_on']}")
            if r["error"]:
                print(f"  Error     : {r['error']}")
