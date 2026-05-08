import ssl
import socket
import requests
from datetime import datetime
from urllib.parse import urlparse


def check_https_redirect(url):
    """
    Check if HTTP version of the URL redirects to HTTPS.

    Returns:
        dict: { redirects_to_https, final_url }
    """
    # Force HTTP version
    parsed = urlparse(url)
    http_url = f"http://{parsed.netloc}{parsed.path or '/'}"

    try:
        response = requests.get(http_url, timeout=8, allow_redirects=True)
        final_url = response.url
        redirects = final_url.startswith("https://")
        return {
            "redirects_to_https": redirects,
            "final_url": final_url
        }
    except requests.exceptions.RequestException as e:
        return {
            "redirects_to_https": False,
            "final_url": None,
            "error": str(e)
        }


def get_ssl_cert_info(hostname, port=443):
    """
    Connect to the server and fetch SSL certificate details.

    Args:
        hostname (str): Domain name (e.g., example.com)
        port (int): Default 443

    Returns:
        dict: cert details or error info
    """
    context = ssl.create_default_context()

    try:
        with socket.create_connection((hostname, port), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        # Parse expiry date
        expire_str = cert.get("notAfter", "")
        expire_date = datetime.strptime(expire_str, "%b %d %H:%M:%S %Y %Z")
        days_remaining = (expire_date - datetime.utcnow()).days

        # Get subject CN
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))

        # Get SANs (Subject Alternative Names)
        san_list = []
        for ext in cert.get("subjectAltName", []):
            if ext[0] == "DNS":
                san_list.append(ext[1])

        return {
            "valid": True,
            "common_name": subject.get("commonName", "N/A"),
            "issued_by": issuer.get("organizationName", "N/A"),
            "expires_on": expire_date.strftime("%Y-%m-%d"),
            "days_remaining": days_remaining,
            "expiry_status": classify_expiry(days_remaining),
            "alt_names": san_list[:5],  # limit to 5 for display
            "error": None
        }

    except ssl.SSLCertVerificationError as e:
        return {"valid": False, "error": f"SSL verification failed: {e}"}
    except ssl.SSLError as e:
        return {"valid": False, "error": f"SSL error: {e}"}
    except socket.timeout:
        return {"valid": False, "error": "Connection timed out"}
    except socket.gaierror:
        return {"valid": False, "error": "DNS resolution failed"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def classify_expiry(days):
    """Label cert expiry status based on days remaining."""
    if days < 0:
        return "EXPIRED"
    elif days <= 7:
        return "CRITICAL"   # expires within a week
    elif days <= 30:
        return "WARNING"    # expires within a month
    else:
        return "OK"


def check_security_headers(url):
    """
    Check presence of important HTTP security headers.

    Returns:
        dict: { header_name: { present, value } }
    """
    important_headers = {
        "Strict-Transport-Security": "Enforces HTTPS connections",
        "Content-Security-Policy": "Prevents XSS and injection attacks",
        "X-Frame-Options": "Prevents clickjacking",
        "X-Content-Type-Options": "Prevents MIME sniffing",
        "Referrer-Policy": "Controls referrer information",
        "Permissions-Policy": "Controls browser features"
    }

    try:
        response = requests.get(url, timeout=8)
        headers = response.headers
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    results = {}
    for header, description in important_headers.items():
        present = header in headers
        results[header] = {
            "present": present,
            "value": headers.get(header, "NOT SET"),
            "description": description,
            "status": "OK" if present else "MISSING"
        }

    return results


def run_ssl_check(url):
    """
    Run all SSL and HTTPS checks for a given URL.

    Args:
        url (str): Target URL

    Returns:
        dict: full SSL report
    """
    hostname = urlparse(url).netloc
    print(f"\n[SSL CHECKER] Scanning: {url}\n")

    # 1. HTTPS redirect
    print("  [1/3] Checking HTTP → HTTPS redirect...")
    https_redirect = check_https_redirect(url)

    # 2. SSL cert info
    print("  [2/3] Checking SSL certificate...")
    cert_info = get_ssl_cert_info(hostname)

    # 3. Security headers
    print("  [3/3] Checking security headers...")
    headers = check_security_headers(url)

    report = {
        "url": url,
        "hostname": hostname,
        "https_redirect": https_redirect,
        "ssl_certificate": cert_info,
        "security_headers": headers
    }

    return report


def print_ssl_report(report):
    """Pretty print the SSL report to console."""
    print("\n" + "=" * 55)
    print("SSL & HTTPS REPORT")
    print("=" * 55)
    print(f"Target : {report['url']}")

    # HTTPS redirect
    redir = report["https_redirect"]
    status = "YES" if redir.get("redirects_to_https") else "NO"
    print(f"\n[HTTP → HTTPS Redirect] : {status}")
    if redir.get("final_url"):
        print(f"  Final URL : {redir['final_url']}")

    # SSL cert
    cert = report["ssl_certificate"]
    print(f"\n[SSL Certificate]")
    if cert.get("valid"):
        print(f"  Valid         : YES")
        print(f"  Common Name   : {cert['common_name']}")
        print(f"  Issued By     : {cert['issued_by']}")
        print(f"  Expires On    : {cert['expires_on']}")
        print(f"  Days Left     : {cert['days_remaining']} ({cert['expiry_status']})")
        if cert["alt_names"]:
            print(f"  Alt Names     : {', '.join(cert['alt_names'])}")
    else:
        print(f"  Valid         : NO")
        print(f"  Error         : {cert.get('error')}")

    # Security headers
    print(f"\n[Security Headers]")
    for header, info in report["security_headers"].items():
        if isinstance(info, dict):
            icon = "+" if info["present"] else "-"
            print(f"  [{icon}] {header:<35} {info['status']}")


if __name__ == "__main__":
    TARGET_URL = "https://example.com"
    report = run_ssl_check(TARGET_URL)
    print_ssl_report(report)
