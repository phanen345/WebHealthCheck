# 🔍 Automated Website Health & Security Checker
### A Real-World Automation Project | QA + Security Engineering

---

## 🧭 What Is This Project?

A **fully automated tool** that scans any website and generates a detailed health and security report — in seconds.

Small businesses often don't know if their website has broken pages, expired SSL certificates, missing security configurations, or compliance issues. This tool solves that by automating the entire audit process — no manual testing required.

---

## 🎯 Problem It Solves

| Problem | How This Tool Solves It |
|---|---|
| Broken links losing customers | Crawls entire site, finds every broken page |
| SSL certificate expired | Checks cert validity + days remaining |
| Website not secure enough | Audits 8 OWASP security headers |
| Site broken on mobile | Tests across 5 real device sizes |
| GDPR compliance issues | Detects cookie banners, popups, unsafe cookies |
| Forms submitting insecurely | Scans every form for security flaws |

---

## 🏗️ How It Works — Step By Step

When you run the tool, it automatically performs **7 checks in sequence:**

```
Step 1 → Crawl the website        → finds all pages & links
Step 2 → Check all links          → detects 404s, broken pages
Step 3 → SSL & HTTPS audit        → checks certificate & redirect
Step 4 → Security headers check   → OWASP header analysis
Step 5 → Form security scan       → Selenium scans all forms
Step 6 → Mobile responsive check  → Selenium tests 5 device sizes
Step 7 → Cookie & GDPR compliance → Selenium audits cookies & popups
         ↓
         Generates full HTML report with 7 tabbed sections
```

All 7 steps run automatically with **one single command:**
```bash
python main.py --url https://yourwebsite.com
```

---

## ✨ Features — Full Breakdown

### 1. 🕷️ Smart Website Crawler
- Visits every page on the website automatically
- **Detects JavaScript-rendered sites** (React, Next.js, Vue, Angular)
- Automatically switches to **Selenium browser** for JS-heavy pages
- Measures **real page load time** using browser Navigation Timing API
- Labels pages: FAST (< 2s) / ACCEPTABLE / SLOW (> 4s)

---

### 2. 🔗 Broken Link Detector
- Checks **every single link** found on the site
- Runs **10 links in parallel** for speed (ThreadPoolExecutor)
- Classifies each link: OK / BROKEN / REDIRECT / SERVER ERROR
- **Takes automatic screenshots** of broken pages as evidence
- Screenshots saved to `screenshots/` folder

---

### 3. 🔒 SSL & HTTPS Checker
- Checks if HTTP version redirects to HTTPS
- Validates SSL certificate is active and trusted
- Shows **exact expiry date** and days remaining
- Labels expiry: OK / WARNING (≤ 30 days) / CRITICAL (≤ 7 days) / EXPIRED
- Shows certificate issuer and domain coverage

---

### 4. 🛡️ Security Headers Audit (OWASP)
- Checks **8 OWASP-recommended security headers:**

| Header | Protects Against |
|---|---|
| Strict-Transport-Security | SSL stripping attacks |
| Content-Security-Policy | XSS & injection attacks |
| X-Frame-Options | Clickjacking |
| X-Content-Type-Options | MIME sniffing |
| Referrer-Policy | Data leakage |
| Permissions-Policy | Browser feature abuse |
| X-XSS-Protection | XSS (legacy browsers) |
| Cache-Control | Sensitive data caching |

- Detects **information-leaking headers** (Server, X-Powered-By) that expose backend technology
- Calculates **security score out of 100** with letter grade (A–F)
- Provides exact fix recommendation for every missing header

---

### 5. 📋 Form Security Scanner (Selenium)
- Uses Selenium to **find and analyse every form** on the website
- Checks each form for:
  - Password/payment fields submitting over **HTTP** (HIGH risk)
  - Missing **CSRF token** (MEDIUM risk — cross-site request forgery)
  - **Autocomplete enabled** on password fields (LOW risk)
  - Form action URL security (HTTP vs HTTPS)
- Identifies **sensitive forms** (login, payment, signup)
- Detects hidden CSRF token patterns automatically

---

### 6. 📱 Mobile Responsiveness Checker (Selenium)
- Tests every page across **5 real device sizes:**

| Device | Resolution |
|---|---|
| Mobile S | 320 × 568 |
| Mobile M | 375 × 667 |
| Mobile L | 425 × 926 |
| Tablet | 768 × 1024 |
| Laptop | 1280 × 800 |

- Checks per device:
  - **Horizontal scroll** (layout breaking on mobile)
  - **Missing viewport meta tag**
  - **Text too small** (< 12px font size)
  - **Touch targets too small** (buttons < 44px)
  - **Images overflowing** viewport
  - **Fixed-width elements** wider than screen
- Takes **screenshot per device** as visual evidence
- Labels each result: PASS / WARN / FAIL

---

### 7. 🍪 Cookie & GDPR Compliance Checker (Selenium)
- Detects **cookie consent banners** using 3 strategies:
  - Known CSS patterns (id/class matching)
  - Keyword scanning in visible text
  - Fixed/sticky positioned overlay detection
- Checks banner has:
  - Accept button
  - **Reject / Decline button** (GDPR requirement)
  - Preferences / settings option
- Detects **intrusive popups** (newsletter, promo, notification)
- Audits **every cookie** set by the site:

| Flag | What it protects |
|---|---|
| Secure | Cookie only sent over HTTPS |
| HttpOnly | JS cannot access cookie (XSS protection) |
| SameSite | Cross-site request protection |

- Calculates **GDPR compliance score** out of 100
- Saves screenshots of banners and popups as evidence

---

## 📊 Final Report

After all 7 checks, an **HTML report** is generated with 7 tabs:

| Tab | Contains |
|---|---|
| Overview | Overall score, grade, summary of all checks |
| Links | Full broken links table with source page |
| SSL & HTTPS | Cert details, expiry, redirect status |
| Headers | OWASP audit with grades and fix recommendations |
| Forms | Per-form risk cards with issues and severity |
| Responsive | Device-by-device results with issue details |
| Cookies & GDPR | Banner check, popup list, cookie security table |

Open the report in any browser — no server needed.

---

## 🧰 Tech Stack

| Layer | Technology | Usage |
|---|---|---|
| Language | Python 3.11 | Core language |
| Browser Automation | Selenium WebDriver | Forms, responsive, compliance, JS crawling |
| Browser Driver | ChromeDriver (webdriver-manager) | Headless Chrome |
| HTTP Requests | requests | Link checking, header analysis |
| HTML Parsing | BeautifulSoup4 | Link extraction from static pages |
| SSL Checking | Python ssl + socket | Certificate validation |
| Threading | concurrent.futures | Parallel link checking |
| Reporting | Jinja2 | HTML report generation |
| CLI | argparse | Command-line interface |

---

## 🤖 Selenium Automation — Where & Why

Selenium is used in **4 out of 7 checkers:**

| Module | What Selenium Does |
|---|---|
| `crawler.py` | Renders JS pages, measures load time |
| `link_checker.py` | Takes screenshots of broken pages |
| `form_checker.py` | Finds & analyses forms in real DOM |
| `responsive_checker.py` | Resizes browser, checks layout per device |
| `compliance_checker.py` | Detects banners, popups, audits cookies |

**Why not just requests?**
requests cannot run JavaScript, resize windows, interact with the DOM, or take screenshots.
Only a real browser (Selenium + headless Chrome) can do this.

---

## 🚀 How To Run

### Prerequisites
```bash
pip install requests beautifulsoup4 selenium webdriver-manager jinja2
```

### Basic Run
```bash
python main.py --url https://yourwebsite.com
```

### All Options
```bash
python main.py --url https://yourwebsite.com --depth 10 --output report.html --json
```

| Flag | Default | Meaning |
|---|---|---|
| --url | required | Target website |
| --depth | 10 | Max pages to crawl |
| --output | report.html | Report filename |
| --json | off | Also save raw JSON |

### Open Report
```bash
start report.html       # Windows
open report.html        # Mac
xdg-open report.html    # Linux
```

---

## 📁 Project Structure

```
website-checker/
├── main.py                    ← Run this (7-step orchestrator)
├── crawler.py                 ← Smart crawler with Selenium fallback
├── link_checker.py            ← Parallel link checker + screenshots
├── ssl_checker.py             ← SSL cert + HTTPS validation
├── header_checker.py          ← OWASP security header audit
├── form_checker.py            ← Selenium form security scanner
├── responsive_checker.py      ← Selenium multi-device checker
├── compliance_checker.py      ← Selenium GDPR + cookie checker
├── requirements.txt           ← All dependencies
└── reporter/
    ├── report_generator.py    ← Jinja2 report builder
    └── report_template.html   ← 7-tab HTML report template
```

---

## 💼 LinkedIn One-Liner

> Built an end-to-end automated Website Health & Security Checker using Python + Selenium WebDriver. The tool crawls websites, detects broken links, audits SSL certificates, checks 8 OWASP security headers, scans forms for CSRF/XSS risks, tests mobile responsiveness across 5 device sizes, and checks GDPR cookie compliance — all generating a professional 7-tab HTML report. Built as part of my transition from Manual Testing to QA Automation & Security Engineering.

---

## 🎤 Interview Talking Points

**"Why did you build this?"**
> As a manual tester moving into automation, I wanted a project that combines both QA and security — two areas I'm targeting. This solves a real problem for small businesses who can't afford manual audits.

**"Where did you use Selenium specifically?"**
> Selenium handles 4 of 7 checkers — JS page crawling, broken page screenshots, form DOM analysis, multi-device layout testing, and GDPR cookie detection. requests alone can't do any of these.

**"What's the difference between this and a VA scanner?"**
> This is a security posture and health checker — it finds misconfigurations and best-practice gaps. A full VA scanner like Nessus would demonstrate actual exploit payloads. The advanced phase of this project adds OWASP ZAP active scanning and CVE lookups.

---

*Project by Rai — QA Engineer transitioning to Automation & Security*
*Built with Python + Selenium | Portfolio Project 2025*
