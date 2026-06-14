"""Canada job postings scraper.

This script fetches job listings for Canada from Indeed and extracts:
- location
- company name
- salary expectation
- degree requirements
- health insurance mention
- work from home offer
- skills mentioned in the posting

Usage:
    python canada_job_scraper.py --query "Data Analyst" --pages 3 --output jobs.csv

Note: Scraping external websites may be subject to terms of service and rate-limiting.
"""

import argparse
import csv
import logging
import random
import re
import time
from dataclasses import dataclass, field, fields
from typing import Optional
from urllib.parse import urlencode, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://ca.indeed.com"
SEARCH_URL = f"{BASE_URL}/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
}

# Skills to scan for in job descriptions
SKILLS_KEYWORDS = [
    # Languages & query
    "python", "r", "sql", "scala", "java", "julia", "bash", "shell",
    # BI & viz
    "tableau", "power bi", "looker", "qlik", "excel", "google sheets",
    # Big data & cloud
    "spark", "hadoop", "kafka", "aws", "azure", "gcp", "google cloud",
    "databricks", "snowflake", "redshift", "bigquery",
    # ML / AI
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
    "scikit-learn", "keras", "xgboost", "llm",
    # Stats & maths
    "statistics", "regression", "forecasting", "a/b testing",
    # Databases
    "postgresql", "mysql", "mongodb", "cassandra", "elasticsearch",
    # Orchestration / DevOps
    "airflow", "dbt", "docker", "kubernetes", "git",
    # General
    "data analysis", "data engineering", "data science", "etl", "elt",
    "data pipeline", "data warehouse", "data lake", "api",
]

DEGREE_PATTERNS = [
    r"\bb\.?sc\.?\b", r"\bbs\b", r"\bbachelor", r"\bm\.?sc\.?\b",
    r"\bmaster", r"\bphd\b", r"\bph\.d\b", r"\bdoctorate",
    r"\bdegree\b", r"\bdiploma\b",
]

SALARY_PATTERNS = [
    # e.g. $60,000 – $80,000 a year  /  $30–$45 an hour
    r"\$[\d,]+(?:\.\d+)?\s*(?:[-–—to]+\s*\$[\d,]+(?:\.\d+)?)?\s*(?:per\s+|a\s+)?(?:year|yr|annual|hour|hr|month|week)",
    # bare ranges: 60,000 - 80,000 per year
    r"[\d,]+(?:\.\d+)?\s*[-–—]\s*[\d,]+(?:\.\d+)?\s*(?:per\s+|a\s+)?(?:year|yr|annual|hour|hr)",
]

WFH_KEYWORDS = ["remote", "work from home", "hybrid", "telecommute", "wfh"]
HEALTH_KEYWORDS = [
    "health insurance", "health benefits", "dental", "vision",
    "extended health", "benefit plan", "benefits package", "group benefits",
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class JobPosting:
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    url: str = ""
    degree_required: bool = False
    health_insurance: bool = False
    work_from_home: bool = False
    skills: str = ""          # comma-separated
    raw_snippet: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get(url: str, session: requests.Session, params: dict = None) -> Optional[BeautifulSoup]:
    """Fetch a page and return a BeautifulSoup object, or None on failure."""
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as exc:
        log.warning("Request failed for %s: %s", url, exc)
        return None


def _extract_salary(text: str) -> str:
    for pattern in SALARY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for skill in SKILLS_KEYWORDS:
        # whole-word match to avoid false positives (e.g. "r" inside "data")
        if re.search(rf"\b{re.escape(skill)}\b", text_lower):
            found.append(skill)
    return found


def _check_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _check_degree(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in DEGREE_PATTERNS)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
def _parse_listing_card(card: BeautifulSoup) -> Optional[dict]:
    """Extract basic fields from a search-result card (no detail page yet)."""
    try:
        title_el = card.select_one("h2.jobTitle span[title], h2.jobTitle a span")
        title = title_el.get_text(strip=True) if title_el else ""

        company_el = card.select_one("[data-testid='company-name'], .companyName")
        company = company_el.get_text(strip=True) if company_el else ""

        location_el = card.select_one("[data-testid='text-location'], .companyLocation")
        location = location_el.get_text(strip=True) if location_el else ""

        salary_el = card.select_one(
            "[data-testid='attribute_snippet_testid'], "
            ".salary-snippet-container, .estimated-salary"
        )
        salary_text = salary_el.get_text(" ", strip=True) if salary_el else ""

        # Job detail link
        link_el = card.select_one("h2.jobTitle a")
        href = link_el["href"] if link_el and link_el.has_attr("href") else ""
        job_url = urljoin(BASE_URL, href) if href else ""

        # Snippet visible on card
        snippet_el = card.select_one(".job-snippet, [data-testid='jobsnippet_field']")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        return dict(
            title=title,
            company=company,
            location=location,
            salary_hint=salary_text,
            url=job_url,
            snippet=snippet,
        )
    except Exception as exc:
        log.debug("Card parse error: %s", exc)
        return None


def _fetch_job_detail(url: str, session: requests.Session) -> str:
    """Return the full visible text of a job detail page."""
    if not url:
        return ""
    soup = _get(url, session)
    if not soup:
        return ""
    desc_el = soup.select_one(
        "#jobDescriptionText, .jobsearch-jobDescriptionText, [data-testid='jobDescriptionText']"
    )
    return desc_el.get_text(" ", strip=True) if desc_el else ""


def _build_posting(card_data: dict, detail_text: str) -> JobPosting:
    full_text = f"{card_data['snippet']} {detail_text}"

    salary = _extract_salary(card_data["salary_hint"]) or _extract_salary(full_text)
    skills = _extract_skills(full_text)

    return JobPosting(
        title=card_data["title"],
        company=card_data["company"],
        location=card_data["location"],
        salary=salary,
        url=card_data["url"],
        degree_required=_check_degree(full_text),
        health_insurance=_check_keywords(full_text, HEALTH_KEYWORDS),
        work_from_home=_check_keywords(full_text, WFH_KEYWORDS),
        skills=", ".join(skills),
        raw_snippet=card_data["snippet"][:300],
    )


def scrape_jobs(
    query: str,
    pages: int = 3,
    location: str = "Canada",
    delay: tuple[float, float] = (2.0, 5.0),
    fetch_details: bool = True,
) -> list[JobPosting]:
    """
    Scrape Indeed Canada for *query* across *pages* result pages.

    Parameters
    ----------
    query        : Job search query string (e.g. "Data Analyst").
    pages        : Number of search-result pages to scrape (10 results each).
    location     : Location filter passed to Indeed (default "Canada").
    delay        : (min, max) seconds to wait between requests.
    fetch_details: If True, visit each job's detail page for richer extraction.

    Returns
    -------
    List of JobPosting dataclass instances.
    """
    session = requests.Session()
    postings: list[JobPosting] = []

    for page in range(pages):
        start = page * 10
        params = {"q": query, "l": location, "start": start, "lang": "en"}
        log.info("Fetching page %d of %d (start=%d) …", page + 1, pages, start)

        soup = _get(SEARCH_URL, session, params=params)
        if soup is None:
            log.warning("Skipping page %d — no response.", page + 1)
            continue

        # Indeed wraps cards in <div class="job_seen_beacon"> or <li> tags
        cards = soup.select("div.job_seen_beacon, li.css-5lfssm")
        if not cards:
            # Fallback selector
            cards = soup.select("[data-testid='slider_item'], .result")

        log.info("  Found %d cards on page %d.", len(cards), page + 1)

        for card in cards:
            card_data = _parse_listing_card(card)
            if not card_data or not card_data["title"]:
                continue

            detail_text = ""
            if fetch_details and card_data["url"]:
                time.sleep(random.uniform(*delay))
                detail_text = _fetch_job_detail(card_data["url"], session)

            posting = _build_posting(card_data, detail_text)
            postings.append(posting)
            log.debug("  + %s @ %s", posting.title, posting.company)

        # Polite delay between search pages
        if page < pages - 1:
            wait = random.uniform(*delay)
            log.info("  Waiting %.1f s before next page …", wait)
            time.sleep(wait)

    log.info("Scraped %d postings total.", len(postings))
    return postings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def save_csv(postings: list[JobPosting], path: str) -> None:
    col_names = [f.name for f in fields(JobPosting)]
    rows = [[getattr(p, f) for f in col_names] for p in postings]
    df = pd.DataFrame(rows, columns=col_names)
    df.to_csv(path, index=False, quoting=csv.QUOTE_ALL)
    log.info("Saved %d rows → %s", len(df), path)


def print_summary(postings: list[JobPosting]) -> None:
    if not postings:
        print("No postings found.")
        return

    df = pd.DataFrame([
        {
            "Title": p.title,
            "Company": p.company,
            "Location": p.location,
            "Salary": p.salary or "—",
            "WFH": "✓" if p.work_from_home else "",
            "Degree": "✓" if p.degree_required else "",
            "Health": "✓" if p.health_insurance else "",
            "Skills (count)": len(p.skills.split(", ")) if p.skills else 0,
        }
        for p in postings
    ])
    print("\n" + "=" * 90)
    print(f"  RESULTS: {len(df)} job posting(s)")
    print("=" * 90)
    with pd.option_context("display.max_colwidth", 35, "display.width", 120):
        print(df.to_string(index=False))

    # Quick stats
    print("\n--- Summary Stats ---")
    print(f"  Remote / WFH offered  : {df['WFH'].eq('✓').sum()} ({df['WFH'].eq('✓').mean():.0%})")
    print(f"  Degree mentioned      : {df['Degree'].eq('✓').sum()} ({df['Degree'].eq('✓').mean():.0%})")
    print(f"  Health benefits noted : {df['Health'].eq('✓').sum()} ({df['Health'].eq('✓').mean():.0%})")
    print(f"  Salary mentioned      : {df['Salary'].ne('—').sum()} ({df['Salary'].ne('—').mean():.0%})")

    # Top skills
    all_skills: list[str] = []
    for p in postings:
        if p.skills:
            all_skills.extend(s.strip() for s in p.skills.split(","))
    if all_skills:
        from collections import Counter
        top = Counter(all_skills).most_common(10)
        print("\n  Top 10 skills:")
        for skill, count in top:
            bar = "█" * count
            print(f"    {skill:<25} {bar} ({count})")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scrape data-related job postings from Indeed Canada.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python canada_job_scraper.py
  python canada_job_scraper.py --query "Data Engineer" --pages 5 --output de_jobs.csv
  python canada_job_scraper.py --query "ML Engineer" --location "Toronto, ON" --no-details
        """,
    )
    p.add_argument(
        "--query", "-q",
        default="Data Analyst",
        help="Job search query (default: 'Data Analyst')",
    )
    p.add_argument(
        "--pages", "-p",
        type=int,
        default=3,
        help="Number of result pages to scrape, 10 results each (default: 3)",
    )
    p.add_argument(
        "--location", "-l",
        default="Canada",
        help="Location filter for Indeed (default: 'Canada')",
    )
    p.add_argument(
        "--output", "-o",
        default="jobs.csv",
        help="CSV output file path (default: jobs.csv)",
    )
    p.add_argument(
        "--no-details",
        action="store_true",
        help="Skip fetching individual job detail pages (faster, less data)",
    )
    p.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
        help="Minimum seconds to wait between requests (default: 2.0)",
    )
    p.add_argument(
        "--max-delay",
        type=float,
        default=5.0,
        help="Maximum seconds to wait between requests (default: 5.0)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    log.info("Query     : %s", args.query)
    log.info("Location  : %s", args.location)
    log.info("Pages     : %d (~%d listings)", args.pages, args.pages * 10)
    log.info("Output    : %s", args.output)
    log.info("Fetch details: %s", not args.no_details)

    postings = scrape_jobs(
        query=args.query,
        pages=args.pages,
        location=args.location,
        delay=(args.min_delay, args.max_delay),
        fetch_details=not args.no_details,
    )

    print_summary(postings)

    if postings:
        save_csv(postings, args.output)
    else:
        log.warning("Nothing to save.")


if __name__ == "__main__":
    main()