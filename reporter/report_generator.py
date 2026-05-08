import os
from jinja2 import Environment, FileSystemLoader
from datetime import datetime


def generate_report(results, output_file="report.html"):
    """
    Generate an HTML report from scan results.

    Args:
        results (dict): Combined output from main.py run_checks()
        output_file (str): Path to save the HTML report
    """
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_template.html")

    html = template.render(
        meta=results.get("meta", {}),
        overall=results.get("overall", {}),
        crawl=results.get("crawl", {}),
        links=results.get("links", {}),
        ssl=results.get("ssl", {}),
        headers=results.get("headers", {}),
        forms=results.get("forms", {"summary": {"total_forms":0,"high_risk":0,"medium_risk":0,"missing_csrf":0,"http_submissions":0,"password_forms":0}, "pages":[]}),
        responsive=results.get("responsive", {"summary": {"pages_tested":0,"total_pass":0,"total_warn":0,"total_fail":0,"h_scroll_pages":0,"missing_meta_pages":0,"viewports_tested":0,"overall":"N/A"}, "pages":[]}),
        compliance=results.get("compliance", {"summary": {"avg_gdpr_score":0,"has_cookie_banner":0,"has_reject_option":0,"total_popups":0,"total_cookies":0,"high_risk_cookies":0,"overall_grade":"N/A"}, "pages":[]}),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[REPORTER] Report written to: {output_file}")
    return output_file
