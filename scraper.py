import re

from bs4 import BeautifulSoup

from config import BASE_URL, HEADERS, REQUEST_TIMEOUT_SECONDS


def _normalize_whitespace(value):
    return " ".join(str(value).split())


def get_total_pages(soup):
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


def _extract_listing_id(relative_href, row_id):
    if relative_href:
        match = re.search(r"/([^/]+)\.html$", relative_href)
        if match:
            return match.group(1)

    return row_id.replace("tr_", "") if row_id else ""


def _extract_geo_parts(relative_href):
    if not relative_href:
        return "", "", "", ""

    segments = [segment for segment in relative_href.strip("/").split("/") if segment]
    if not segments:
        return "", "", "", ""

    if segments[0] == "lv":
        segments = segments[1:]

    if segments and segments[-1].endswith(".html"):
        segments = segments[:-1]

    if segments and segments[-1] in {"hand_over", "for_sale", "for_rent", "sale", "rent"}:
        segments = segments[:-1]

    if len(segments) >= 4:
        return segments[-4], segments[-3], segments[-2], segments[-1]

    return "", "", "", ""


def parse_listings_from_page(soup):
    listings = []
    headline_row = soup.find("tr", id="head_line")
    if not headline_row:
        return listings

    target_table = headline_row.find_parent("table")
    if not target_table:
        return listings

    for row in target_table.select("tr[id^='tr_']"):
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        style = row.get("style", "").lower()
        if "display: none" in style or "display:none" in style:
            continue

        link_tag = cells[2].find("a")
        relative_href = link_tag["href"] if link_tag else ""
        full_url = f"https://www.ss.com{relative_href}" if relative_href else ""

        listing_id = _extract_listing_id(relative_href, row.get("id", ""))
        category, subcategory, city, district = _extract_geo_parts(relative_href)

        description = _normalize_whitespace(cells[2].get_text(" ", strip=True))
        address = _normalize_whitespace(cells[3].get_text(" ", strip=True))
        rooms = _normalize_whitespace(cells[4].get_text(" ", strip=True))
        area = _normalize_whitespace(cells[5].get_text(" ", strip=True))
        floor = _normalize_whitespace(cells[6].get_text(" ", strip=True))
        series = _normalize_whitespace(cells[7].get_text(" ", strip=True))
        price_sqm = _normalize_whitespace(cells[8].get_text(" ", strip=True))
        price_month = _normalize_whitespace(cells[9].get_text(" ", strip=True))

        listings.append(
            {
                "id": listing_id,
                "category": category,
                "subcategory": subcategory,
                "city": city,
                "district": district,
                "address": address,
                "rooms": rooms,
                "area_sqm": area,
                "floor": floor,
                "series": series,
                "price_per_sqm": price_sqm,
                "price_monthly": price_month,
                "description": description,
                "url": full_url,
            }
        )

    return listings


def fetch_page(session, url):
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

