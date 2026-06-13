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
import re
import time
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ca.indeed.com"
SEARCH_PATH = "/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1"
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

COMMON_SKILLS = [
    "python", "sql", "r", "excel", "tableau", "power bi", "powerbi", "spark",
    "aws", "azure", "google cloud", "machine learning", "statistics", "data visualization",
    "data analysis", "sql server", "pandas", "numpy", "sas", "alteryx", "etl",
    "business intelligence", "dashboard", "reporting", "communication", "problem solving",
    "project management", "data mining", "data warehousing", "ml", "artificial intelligence",
    "deep learning", "jira", "git", "communication", "presentation"
]

DEGREE_PATTERNS = [
    r"bachelor(?:'s)?", r"master(?:'s)?", r"phd", r"post-secondary", r"university degree",
    r"college diploma", r"high school", r"no degree", r"degree not required", r"degree required"
]

WORK_FROM_HOME_PATTERNS = [
    r"remote", r"work from home", r"telecommut", r"hybrid", r"distributed team"
]

HEALTH_INSURANCE_PATTERNS = [
    r"health insurance", r"medical insurance", r"benefits", r"dental", r"vision", r"extended health"
]


def fetch_search_page(query: str, start: int = 0):
    params = {
        "q": query,
        "l": "Canada",
        "start": start,
        "sort": "date",
        "jt": "all"
    }
    url = f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def fetch_job_details(job_url: str):
    if not job_url:
        return {}
    resp = SESSION.get(job_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    description_el = soup.select_one("div#jobDescriptionText")
    if not description_el:
        description_el = soup.select_one("div.jobsearch-JobComponent-description")
    description = description_el.get_text(separator=" ", strip=True) if description_el else ""

    salary = ""
    salary_el = soup.select_one("span.salary-snippet") or soup.select_one("div.metadata.salary-snippet-container")
    if salary_el:
        salary = salary_el.get_text(strip=True)

    degree = extract_degree_requirement(description)
    health = extract_health_insurance(description)
    work_from_home = extract_work_from_home(description)
    skills = extract_skills(description)

    return {
        "salary_expectation": salary or "",
        "degree_requirement": degree,
        "health_insurance": health,
        "work_from_home_offered": work_from_home,
        "skills_required": ", ".join(skills),
        "description": description,
    }


def parse_job_card(card):
    title_el = card.select_one("h2.jobTitle span")
    title = title_el.get_text(strip=True) if title_el else ""

    company_el = card.select_one("span.companyName")
    company = company_el.get_text(strip=True) if company_el else ""

    location_el = card.select_one("div.companyLocation")
    location = location_el.get_text(strip=True) if location_el else ""

    salary_el = card.select_one("div.metadata.salary-snippet-container")
    salary = salary_el.get_text(strip=True) if salary_el else ""

    link_el = card.select_one("a.jcs-JobTitle") or card.select_one("a.tapItem")
    job_url = urljoin(BASE_URL, link_el["href"]) if link_el and link_el.has_attr("href") else ""

    summary_el = card.select_one("div.job-snippet")
    summary = summary_el.get_text(separator=" ", strip=True) if summary_el else ""

    return {
        "job_title": title,
        "company_name": company,
        "job_location": location,
        "salary_expectation": salary,
        "job_url": job_url,
        "summary": summary,
    }


def fetch_job_details(job_url: str):
    if not job_url:
        return {}
    resp = requests.get(job_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    description_el = soup.select_one("div#jobDescriptionText")
    if not description_el:
        description_el = soup.select_one("div.jobsearch-JobComponent-description")
    description = description_el.get_text(separator=" ", strip=True) if description_el else ""

    salary = ""
    salary_el = soup.select_one("span.salary-snippet") or soup.select_one("div.metadata.salary-snippet-container")
    if salary_el:
        salary = salary_el.get_text(strip=True)

    degree = extract_degree_requirement(description)
    health = extract_health_insurance(description)
    work_from_home = extract_work_from_home(description)
    skills = extract_skills(description)

    return {
        "salary_expectation": salary or "",
        "degree_requirement": degree,
        "health_insurance": health,
        "work_from_home_offered": work_from_home,
        "skills_required": ", ".join(skills),
        "description": description,
    }


def extract_degree_requirement(text: str) -> str:
    text_lower = text.lower()
    matches = []
    for pattern in DEGREE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            matches.append(match.group(0))
    if not matches:
        return "Not explicitly stated"
    unique_matches = sorted(set(matches), key=matches.index)
    return ", ".join(unique_matches)


def extract_health_insurance(text: str) -> str:
    text_lower = text.lower()
    for pattern in HEALTH_INSURANCE_PATTERNS:
        if re.search(pattern, text_lower):
            return "Yes"
    return "No"


def extract_work_from_home(text: str) -> str:
    text_lower = text.lower()
    for pattern in WORK_FROM_HOME_PATTERNS:
        if re.search(pattern, text_lower):
            return "Yes"
    return "No"


def extract_skills(text: str):
    text_lower = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        if skill in text_lower and skill not in found:
            found.append(skill)
    return found


def save_to_csv(rows, output_file):
    if not rows:
        print("No job postings found to save.")
        return
    keys = [
        "job_title", "company_name", "job_location", "salary_expectation",
        "degree_requirement", "health_insurance", "work_from_home_offered",
        "skills_required", "job_url", "summary"
    ]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in keys})
    print(f"Saved {len(rows)} job records to {output_file}")


def scrape_jobs(query: str, pages: int = 3, delay: float = 2.0):
    job_rows = []
    for page in range(pages):
        start = page * 10
        print(f"Fetching search results page {page + 1}/{pages}...")
        soup = fetch_search_page(query, start=start)
        job_cards = soup.select("div.slider_container, div.job_seen_beacon, div.jobsearch-SerpJobCard")
        if not job_cards:
            job_cards = soup.select("a.tapItem")
        print(f"  Found {len(job_cards)} job cards on page {page + 1}")

        for card in job_cards:
            row = parse_job_card(card)
            if not row["job_url"]:
                continue
            print(f"    Parsing: {row['job_title']} @ {row['company_name']}")
            details = fetch_job_details(row["job_url"])
            row.update(details)
            job_rows.append(row)
            time.sleep(delay)

        time.sleep(delay * 1.5)

    return job_rows


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape job postings in Canada from Indeed")
    parser.add_argument("--query", default="Data Analyst", help="Search query for job title or keywords")
    parser.add_argument("--pages", type=int, default=2, help="Number of search result pages to scrape")
    parser.add_argument("--output", default="canada_jobs.csv", help="Output CSV filename")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds between page requests")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = scrape_jobs(args.query, pages=args.pages, delay=args.delay)
    save_to_csv(rows, args.output)


if __name__ == "__main__":
    main()
