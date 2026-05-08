import argparse
import json
from datetime import datetime

from crawler import crawl
from link_checker import check_all_links
from ssl_checker import run_ssl_check
from header_checker import check_headers
from form_checker import check_all_forms
from responsive_checker import check_all_responsive
from compliance_checker import check_all_compliance
from reporter.report_generator import generate_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Website Health & Security Checker"
    )
    parser.add_argument(
        "--url",
        default="https://www.justwravel.com/",
        help="Target website URL (e.g. https://example.com)"
    )
    parser.add_argument(
        "--depth", type=int, default=10,
        help="Max pages to crawl (default: 10)"
    )
    parser.add_argument(
        "--output", default="report.html",
        help="Output report filename (default: report.html)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Also save raw results as JSON"
    )
    return parser.parse_args()


def run_checks(url, max_pages=10):
    """
    Run all checks and return combined results.

    Args:
        url (str): Target URL
        max_pages (int): Crawl depth

    Returns:
        dict: Full scan results
    """

    print("\n" + "=" * 60)
    print("   WEBSITE HEALTH & SECURITY CHECKER")
    print("=" * 60)
    print(f"  Target  : {url}")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {
        "meta": {
            "url": url,
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_pages": max_pages
        }
    }

    # ── Step 1: Crawl ──────────────────────────────────────
    print("\n[STEP 1/4] Crawling website...")
    crawl_map = crawl(url, max_pages=max_pages)

    # Extract just links dict for link_checker (new format: {url: {links:[], load_time:{}}})
    links_only_map = {page: data["links"] for page, data in crawl_map.items()}

    results["crawl"] = {
        "pages_found": len(crawl_map),
        "crawl_map": crawl_map
    }

    # ── Step 2: Link Check ─────────────────────────────────
    print("\n[STEP 2/4] Checking all links...")
    link_report = check_all_links(links_only_map)
    results["links"] = link_report

    # ── Step 3: SSL & HTTPS ────────────────────────────────
    print("\n[STEP 3/4] Running SSL & HTTPS checks...")
    ssl_report = run_ssl_check(url)
    results["ssl"] = ssl_report

    # ── Step 4: Security Headers ───────────────────────────
    print("\n[STEP 4/5] Analysing security headers...")
    header_report = check_headers(url)
    results["headers"] = header_report

    # ── Step 5: Form Security ───────────────────────────────
    print("\n[STEP 5/6] Scanning forms via Selenium...")
    form_report = check_all_forms(crawl_map)
    results["forms"] = form_report

    # ── Step 6: Mobile Responsiveness ──────────────────────
    print("\n[STEP 6/7] Checking mobile responsiveness via Selenium...")
    responsive_report = check_all_responsive(crawl_map, max_pages=5)
    results["responsive"] = responsive_report

    # ── Step 7: Cookie & Popup Compliance ──────────────────
    print("\n[STEP 7/7] Checking cookie & popup compliance via Selenium...")
    compliance_report = check_all_compliance(crawl_map, max_pages=3)
    results["compliance"] = compliance_report

    return results


def calculate_overall_score(results):
    """
    Calculate an overall health score (0–100) from all checks.
    """
    score = 100
    deductions = []

    # Links
    link_summary = results["links"]["summary"]
    broken = link_summary.get("broken", 0)
    errors = link_summary.get("errors", 0)
    if broken > 0:
        deduct = min(broken * 5, 25)
        score -= deduct
        deductions.append(f"-{deduct} pts: {broken} broken link(s)")
    if errors > 0:
        deduct = min(errors * 3, 15)
        score -= deduct
        deductions.append(f"-{deduct} pts: {errors} link error(s)")

    # SSL
    cert = results["ssl"].get("ssl_certificate", {})
    if not cert.get("valid"):
        score -= 30
        deductions.append("-30 pts: Invalid SSL certificate")
    else:
        expiry = cert.get("expiry_status")
        if expiry == "EXPIRED":
            score -= 30
            deductions.append("-30 pts: SSL cert EXPIRED")
        elif expiry == "CRITICAL":
            score -= 15
            deductions.append("-15 pts: SSL cert expiring in ≤7 days")
        elif expiry == "WARNING":
            score -= 5
            deductions.append("-5 pts: SSL cert expiring in ≤30 days")

    if not results["ssl"]["https_redirect"].get("redirects_to_https"):
        score -= 15
        deductions.append("-15 pts: No HTTP → HTTPS redirect")

    # Headers
    header_score = results["headers"].get("summary", {}).get("score", 100)
    header_deduct = int((100 - header_score) * 0.3)  # weighted 30%
    if header_deduct > 0:
        score -= header_deduct
        deductions.append(f"-{header_deduct} pts: Missing security headers")

    score = max(0, score)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 50 else "D" if score >= 25 else "F"

    return {
        "score": score,
        "grade": grade,
        "deductions": deductions
    }


def main():
    args = parse_args()

    # Run all checks
    results = run_checks(args.url, max_pages=args.depth)

    # Overall score
    overall = calculate_overall_score(results)
    results["overall"] = overall

    # Console summary
    print("\n" + "=" * 60)
    print("SCAN COMPLETE — OVERALL RESULTS")
    print("=" * 60)
    print(f"  Overall Score : {overall['score']}/100  |  Grade: {overall['grade']}")
    print(f"  Pages Crawled : {results['crawl']['pages_found']}")
    print(f"  Links Checked : {results['links']['summary']['total']}")
    print(f"  Broken Links  : {results['links']['summary']['broken']}")
    print(f"  SSL Valid     : {'YES' if results['ssl']['ssl_certificate'].get('valid') else 'NO'}")
    print(f"  Header Score  : {results['headers'].get('summary', {}).get('score', 'N/A')}/100")
    print(f"  Forms Found   : {results['forms']['summary']['total_forms']}")
    print(f"  High Risk     : {results['forms']['summary']['high_risk']}")
    print(f"  Missing CSRF  : {results['forms']['summary']['missing_csrf']}")
    print(f"  GDPR Score    : {results['compliance']['summary']['avg_gdpr_score']}/100")
    print(f"  Cookie Banner : {'FOUND' if results['compliance']['summary']['has_cookie_banner'] else 'MISSING'}")
    print(f"  Popups Found  : {results['compliance']['summary']['total_popups']}")
    if overall["deductions"]:
        print("\n  Deductions:")
        for d in overall["deductions"]:
            print(f"    {d}")

    # Save JSON if requested
    if args.json:
        json_file = args.output.replace(".html", ".json")
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n  JSON saved → {json_file}")

    # Generate HTML report
    print(f"\n[REPORT] Generating HTML report → {args.output}")
    generate_report(results, output_file=args.output)
    print(f"[DONE] Report saved → {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
