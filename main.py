import re
import time
import random
import json
import requests
from bs4 import BeautifulSoup

# Base URL for the category
BASE_URL = "https://www.ss.com/lv/real-estate/flats/riga/centre/hand_over/"

# Request headers to mimic a regular browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "lv,en-US;q=0.9,en;q=0.8",
}


def get_total_pages(soup):
    """Extracts the total page count from pagination elements."""
    prev_link = soup.find("a", attrs={"name": "nav_id", "rel": "prev"})
    if prev_link and "href" in prev_link.attrs:
        match = re.search(r"page(\d+)\.html", prev_link["href"])
        if match:
            return int(match.group(1))

    nav_links = soup.find_all("a", class_="navi")
    page_numbers = []
    for link in nav_links:
        match = re.search(r"page(\d+)\.html", link.get("href", ""))
        if match:
            page_numbers.append(int(match.group(1)))

    return max(page_numbers) if page_numbers else 1


def parse_listings_from_page(soup):
    """Finds the main listings table and parses valid listing rows."""
    listings = []

    headline_row = soup.find("tr", id="head_line")
    if not headline_row:
        return listings

    target_table = headline_row.find_parent("table")
    if not target_table:
        return listings

    potential_rows = target_table.select("tr[id^='tr_']")

    for row in potential_rows:
        cells = row.find_all("td")

        # Skip ad rows (valid listing rows have 10 data cells)
        if len(cells) < 10:
            continue

        # Skip hidden rows
        style = row.get("style", "").lower()
        if "display: none" in style or "display:none" in style:
            continue

        # Extract cell values
        description = cells[2].text.strip()
        address = cells[3].text.strip()
        rooms = cells[4].text.strip()
        area = cells[5].text.strip()
        floor = cells[6].text.strip()
        series = cells[7].text.strip()
        price_sqm = cells[8].text.strip()
        price_month = cells[9].text.strip()

        # Extract URL
        link_tag = cells[2].find("a")
        relative_href = link_tag["href"] if link_tag else ""
        full_url = f"https://www.ss.com{relative_href}" if relative_href else ""

        # Construct individual dictionary item
        listings.append({
            "address": address,
            "rooms": rooms,
            "area_sqm": area,
            "floor": floor,
            "series": series,
            "price_per_sqm": price_sqm,
            "price_monthly": price_month,
            "description": description,
            "url": full_url
        })

    return listings


def run_scraper():
    session = requests.Session()
    session.headers.update(HEADERS)

    print("Fetching page 1 to check total pages...")
    first_page_res = session.get(BASE_URL)

    if first_page_res.status_code != 200:
        print(f"Failed to fetch initial page. Status code: {first_page_res.status_code}")
        return

    soup = BeautifulSoup(first_page_res.text, "html.parser")
    total_pages = get_total_pages(soup)
    print(f"Total pages identified: {total_pages}\n")

    all_listings = []

    for page in range(1, total_pages + 1):
        page_url = BASE_URL if page == 1 else f"{BASE_URL}page{page}.html"
        print(f"Scraping page {page}/{total_pages}: {page_url}")

        if page > 1:
            res = session.get(page_url)
            if res.status_code != 200:
                print(f"Skipping page {page} (status code {res.status_code})")
                continue
            soup = BeautifulSoup(res.text, "html.parser")

        page_data = parse_listings_from_page(soup)
        all_listings.extend(page_data)
        print(f"  -> Found {len(page_data)} listings.")

        # Politeness delay between requests
        if page < total_pages:
            time.sleep(random.uniform(1.5, 3.0))

    # Export scraped results to JSON
    output_filename = "ss_com_listings.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=4)

    print(f"\nScraping complete. Extracted {len(all_listings)} total listings.")
    print(f"Saved results to '{output_filename}'.")


if __name__ == "__main__":
    run_scraper()