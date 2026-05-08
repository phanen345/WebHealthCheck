import requests
from urllib.parse import urlparse


# Full OWASP-recommended headers with severity if missing
SECURITY_HEADERS = {
    "Strict-Transport-Security": {
        "severity": "HIGH",
        "description": "Forces HTTPS connections. Prevents SSL stripping attacks.",
        "recommendation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains"
    },
    "Content-Security-Policy": {
        "severity": "HIGH",
        "description": "Prevents XSS, clickjacking, and data injection attacks.",
        "recommendation": "Add: Content-Security-Policy: default-src 'self'"
    },
    "X-Frame-Options": {
        "severity": "MEDIUM",
        "description": "Prevents your page from being embedded in iframes (clickjacking).",
        "recommendation": "Add: X-Frame-Options: DENY or SAMEORIGIN"
    },
    "X-Content-Type-Options": {
        "severity": "MEDIUM",
        "description": "Prevents MIME-type sniffing attacks.",
        "recommendation": "Add: X-Content-Type-Options: nosniff"
    },
    "Referrer-Policy": {
        "severity": "LOW",
        "description": "Controls how much referrer info is sent with requests.",
        "recommendation": "Add: Referrer-Policy: no-referrer-when-downgrade"
    },
    "Permissions-Policy": {
        "severity": "LOW",
        "description": "Controls which browser features/APIs the page can use.",
        "recommendation": "Add: Permissions-Policy: geolocation=(), microphone=()"
    },
    "X-XSS-Protection": {
        "severity": "LOW",
        "description": "Legacy XSS filter for older browsers. Still good to have.",
        "recommendation": "Add: X-XSS-Protection: 1; mode=block"
    },
    "Cache-Control": {
        "severity": "LOW",
        "description": "Controls caching of sensitive pages.",
        "recommendation": "Add: Cache-Control: no-store for sensitive pages"
    }
}

# Headers that should NOT be present (information leakage)
UNWANTED_HEADERS = {
    "Server": "Exposes server software and version (e.g., Apache/2.4.1)",
    "X-Powered-By": "Exposes backend technology (e.g., PHP/7.4)",
    "X-AspNet-Version": "Exposes ASP.NET version",
    "X-AspNetMvc-Version": "Exposes ASP.NET MVC version"
}


def check_headers(url):
    """
    Perform a deep security header analysis on a URL.

    Args:
        url (str): Target URL

    Returns:
        dict: Full header analysis report
    """
    headers_ua = {"User-Agent": "Mozilla/5.0 (WebHealthChecker/1.0)"}

    try:
        response = requests.get(url, headers=headers_ua, timeout=10)
        response_headers = response.headers
        status_code = response.status_code
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "url": url}

    present = []
    missing = []
    warnings = []

    # Check required security headers
    for header, meta in SECURITY_HEADERS.items():
        value = response_headers.get(header)
        if value:
            entry = {
                "header": header,
                "value": value,
                "severity": meta["severity"],
                "description": meta["description"],
                "status": "PRESENT"
            }
            present.append(entry)
        else:
            entry = {
                "header": header,
                "value": "NOT SET",
                "severity": meta["severity"],
                "description": meta["description"],
                "recommendation": meta["recommendation"],
                "status": "MISSING"
            }
            missing.append(entry)

    # Check for information-leaking headers
    for header, reason in UNWANTED_HEADERS.items():
        value = response_headers.get(header)
        if value:
            warnings.append({
                "header": header,
                "value": value,
                "reason": reason,
                "status": "INFO LEAK"
            })

    # Score calculation (out of 100)
    total = len(SECURITY_HEADERS)
    high_missing = sum(1 for h in missing if h["severity"] == "HIGH")
    medium_missing = sum(1 for h in missing if h["severity"] == "MEDIUM")
    low_missing = sum(1 for h in missing if h["severity"] == "LOW")

    deductions = (high_missing * 20) + (medium_missing * 10) + (low_missing * 5)
    score = max(0, 100 - deductions)

    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 50 else "D" if score >= 25 else "F"

    summary = {
        "total_checked": total,
        "present_count": len(present),
        "missing_count": len(missing),
        "info_leaks": len(warnings),
        "high_missing": high_missing,
        "medium_missing": medium_missing,
        "low_missing": low_missing,
        "score": score,
        "grade": grade
    }

    return {
        "url": url,
        "status_code": status_code,
        "summary": summary,
        "present_headers": present,
        "missing_headers": missing,
        "info_leak_headers": warnings
    }


def print_header_report(report):
    """Pretty print header analysis to console."""
    if "error" in report:
        print(f"[ERROR] {report['error']}")
        return

    s = report["summary"]
    print("\n" + "=" * 55)
    print("SECURITY HEADER REPORT")
    print("=" * 55)
    print(f"URL    : {report['url']}")
    print(f"Score  : {s['score']}/100  |  Grade: {s['grade']}")
    print(f"Found  : {s['present_count']}/{s['total_checked']} headers present")
    print(f"Leaks  : {s['info_leaks']} information-leaking headers")

    if report["missing_headers"]:
        print(f"\n[MISSING HEADERS]")
        for h in report["missing_headers"]:
            print(f"  [{h['severity']}] {h['header']}")
            print(f"         → {h['recommendation']}")

    if report["info_leak_headers"]:
        print(f"\n[INFO LEAK HEADERS - REMOVE THESE]")
        for h in report["info_leak_headers"]:
            print(f"  {h['header']}: {h['value']}")
            print(f"         Reason: {h['reason']}")

    if report["present_headers"]:
        print(f"\n[PRESENT HEADERS]")
        for h in report["present_headers"]:
            print(f"  [+] {h['header']}: {h['value'][:60]}")


if __name__ == "__main__":
    TARGET_URL = "https://example.com"
    print(f"[HEADER CHECKER] Scanning: {TARGET_URL}")
    report = check_headers(TARGET_URL)
    print_header_report(report)
