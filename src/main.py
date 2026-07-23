import csv
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import requests
import pandas as pd
import time
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz
from RateLimiter import RateLimiter

UKSC_KEY = os.environ["UKSC_KEY"].strip()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(ROOT_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

CSV_PATH = os.path.join(DATA_DIR, "matched_companies.csv")

SEARCH_URL = "https://api.company-information.service.gov.uk/advanced-search/companies"
SEARCH_FALLBACK_URL = "https://api.company-information.service.gov.uk/search/companies"
PROFILE_URL = "https://api.company-information.service.gov.uk/company/{}"

MAX_WORKERS = 6

REQUEST_N_LIMIT = 600

REQUEST_TIME_LIMIT = 300.0 #seconds (5 minutes)

# Confidence scores for company name match

HIGH_CONFIDENCE = 95
MEDIUM_CONFIDENCE = 80
LOW_CONFIDENCE = 50
GAP = 8 # Claude Suggestion

mutex = Lock()

session = requests.Session()

rate_limiter = RateLimiter(REQUEST_N_LIMIT, REQUEST_TIME_LIMIT)

legal_suffixes = ["limited", "ltd", "plc", "llp", "llc", "inc", "incorporated", "corp", "corporation"] # Claude Suggestion

company_names = ["ACER LIMITED", "A-GAS (UK)", "Air Liquide Ltd", "Arm Limited", "AVL", "Gas Sensing", "GSS", "LS3 LIMITED", "Mediatek Inc"]

field_names = ["original_supplied_name", "matched_company_name", "company_number", "company_status", "incorporation_date", "registered_office_address", "SIC_codes", "previous_company_names", "match_confidence", "notes"]

url = "https://api.company-information.service.gov.uk/search/companies"


def get_row(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Optional[Dict]:
    retry = 1.0
    for i in range(5):
        rate_limiter.acquire()
        try:
            response = requests.get(url, params=params, auth=(UKSC_KEY, ""), timeout=timeout)
        except Exception as e:
            time.sleep(retry)
            retry *= 2
            continue

        if response.status_code == 429:
            retry_time = float(response.headers.get("Retry-After", retry))
            time.sleep(retry_time)
            retry *= 2
            continue

        if response.status_code == 404:
            print(f"Record Not Found: URL: {url} | Params: {params}")
            return None

        response.raise_for_status()
        return response.json()
    raise RuntimeError("Retry limit exceeded for Url: {url} | Params: {params}")

def get_candidate_name(candidate: Dict) -> str:
    return candidate.get("title") or candidate.get("company_name") or ""

def normalise_name(name: str) -> str:
    name = name.lower().replace("&", " and ").replace("-", " ").replace("(", " ").replace(")", " ")
    return  " ".join([t for t in name.split() if t not in legal_suffixes]).strip()


def search_candidates(name: str) -> List[Dict[str, Any]]:
    query = normalise_name(name)
    data = get_row(SEARCH_URL, params={"company_name_includes": query, "size": 20})
    items = (data or {}).get("items", [])

    if not items:
        data = get_row(SEARCH_FALLBACK_URL, params={"q": name, "items_per_page": 20})
        items = (data or {}).get("items", [])

    return items

def score_candidate(query: str, candidate: Dict) -> Dict[str, Any]:
    normalised_title = normalise_name(get_candidate_name(candidate))
    ratio = fuzz.ratio(query, normalised_title)
    token_sort_ratio = fuzz.token_sort_ratio(query, normalised_title)
    token_set_ratio = fuzz.token_set_ratio(query, normalised_title)
    score = max(ratio, token_sort_ratio, token_set_ratio)

    token_overlap = bool(set(query.split()) & set(normalised_title.split()))
    return {"candidate": candidate,
            "score": score,
            "token_overlap": token_overlap}


def rank_candidates(company_name: str, candidates: List[Dict]) -> List[Dict[str, Any]]:
    query = normalise_name(company_name)
    scored_candidates = [score_candidate(query, c) for c in candidates]

    """ print(f"  query='{query}'")
    for s in sorted(scored_candidates, key=lambda x: x["score"], reverse=True)[:5]:
        print(f"    {s['score']:.0f}  {s['candidate'].get('title')}") """
    
    scored_candidates = [s for s in scored_candidates if s['score'] >= LOW_CONFIDENCE]
    return scored_candidates

def fetch_profile(company_number: str) -> Optional[Dict]:
    return get_row(PROFILE_URL.format(company_number))

def format_address(address: Dict[str, str]) -> str:
    if not address:
        return ""
    parts = [
        address.get("premises"), address.get("address_line_1"),
        address.get("address_line_2"), address.get("locality"),
        address.get("region"), address.get("postal_code"),
        address.get("country"),
    ]
    return ", ".join(p for p in parts if p)

def format_previous_names(profile: Dict) -> str:
    prev_names = profile.get( "previous_company_names", []) or []
    formatted = []
    for p in prev_names:
        name = p.get("name", "")
        ceased = p.get("ceased_on", "")
        formatted.append(f"{name} (until {ceased})" if ceased else name)
    return "; ".join(formatted)
 
 
def format_sic_codes(profile: dict) -> str:
    return "; ".join(profile.get("sic_codes", []) or [])


def build_row(company_name: str) -> Dict[str, Any]:
    base_row = {f: "" for f in field_names}
    base_row["original_supplied_name"] = company_name

    try:
        candidates = search_candidates(company_name)
        if not candidates:
            base_row["match_confidence"] = "none"
            base_row["notes"] = "No company returned by Companies House API."
            return base_row

        ranked_candidates = rank_candidates(company_name, candidates)
        if not ranked_candidates:
            base_row["match_confidence"] = "none"
            base_row["notes"] = (
                f"{len(candidates)} candidates returned by search but none scored "
                f">= {LOW_CONFIDENCE}."
            )
            return base_row

        query_norm = normalise_name(company_name)
        exact_matches = [
            c for c in ranked_candidates
            if normalise_name(get_candidate_name(c["candidate"])) == query_norm
        ]

        if exact_matches:
            top = exact_matches[0]
            runner_up = exact_matches[1] if len(exact_matches) > 1 else None
            ambiguous = len(exact_matches) > 1
        else:
            top = ranked_candidates[0]
            runner_up = ranked_candidates[1] if len(ranked_candidates) > 1 else None
            ambiguous = (
                runner_up is not None
                and (top["score"] - runner_up["score"]) < GAP
                and runner_up["score"] >= LOW_CONFIDENCE
            )

        top_title = get_candidate_name(top["candidate"])
        top_score = top["score"] # Claude suggestion

        company_number = top["candidate"].get("company_number", "")
        company_profile = fetch_profile(company_number) if company_number else None

        if company_profile:
            base_row["matched_company_name"] = company_profile.get("company_name", top_title)
            base_row["company_number"] = company_number
            base_row["company_status"] = company_profile.get("status", "")
            base_row["incorporation_date"] = company_profile.get("date_of_creation", "")
            base_row["registered_office_address"] = format_address(
                company_profile.get("registered_office_address", {})
            )
            base_row["SIC_codes"] = format_sic_codes(company_profile)
            base_row["previous_company_names"] = format_previous_names(company_profile)

        else:

            # profile fetch failed but we still have search result level info
            base_row["matched_company_name"] = top_title
            base_row["company_number"] = company_number
            base_row["company_status"] = top["candidate"].get("status", "")
            base_row["notes"] += " Profile fetch failed, showing search-result data only."

        notes = []
        if ambiguous and runner_up:
            confidence = "low - ambiguous"
            notes.append(
                f"Top match '{top_title}' scored {top_score:.0f} but runner-up "
                f"'{get_candidate_name(runner_up["candidate"])}' scored "
                f"{runner_up['score']:.0f} - too close to call automatically."
            )
        elif top_score >= HIGH_CONFIDENCE:
            confidence = "high"
        elif top_score >= MEDIUM_CONFIDENCE:
            confidence = "medium"
        else:
            confidence = "low"
            notes.append(f"Best candidate only scored {top_score:.0f}/100 similarity.")
 
        if company_profile and company_profile.get("status") == "dissolved":
            notes.append("Matched company is dissolved.")
 
        base_row["match_confidence"] = confidence
        if notes:
            base_row["notes"] = (base_row["notes"] + " " + " ".join(notes)).strip()
 
        return base_row

    except Exception as e:
        base_row["match_confidence"] = "error"
        base_row["notes"] = f"Lookup failed: {e}"
        return base_row

def add_record_to_csv(row: Dict[str, Any], csv_path: str | Path):
    with mutex:
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, 'a', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=field_names)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            print(f"Saved batch of {len(row)} rows for  to {csv_path}")
            

def main():
    if os.path.isfile(CSV_PATH):
        os.remove(CSV_PATH)

    print()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(build_row, name): name for name in company_names}
        for future in as_completed(futures):
            name = futures[future]
            row = future.result()
            add_record_to_csv(row, CSV_PATH)
            print(f"[{row['match_confidence']}] {name} -> {row['matched_company_name'] or '(no match)'}")
 
    print(f"\nDone. Records written to {CSV_PATH}")
    print()

    df = pd.read_csv(CSV_PATH)
    print(df.head(10))

if __name__ == "__main__":
    main()