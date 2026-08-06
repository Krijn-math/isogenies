from datetime import date, datetime, timedelta
import re
import xml.etree.ElementTree as ET
import requests
import unicodeit

ATOM = "{http://www.w3.org/2005/Atom}"


def classify_date(date_str):
    parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
    current_date = datetime.now()

    time_difference = current_date - parsed_date

    if time_difference <= timedelta(days=7):
        return 'last_week'
    elif time_difference <= timedelta(days=30):
        return 'last_month'
    elif time_difference <= timedelta(days=365):
        return 'last_year'
    else:
        return 'other'


def detexify(text):
    def repl(match):
        return str(unicodeit.replace((match.group(1))))

    pattern = r'\$(.*?)\$'
    result = re.sub(pattern, repl, text)
    return result


url = (
    "https://export.arxiv.org/api/query?"
    "search_query=all:isogeny+OR+all:isogenies"
    "&sortBy=submittedDate&sortOrder=descending"
    "&start=0&max_results=100"
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/121.0 Safari/537.36"
}

response = requests.get(url, headers=headers, timeout=30)

assert response.status_code == 200
root = ET.fromstring(response.content)

search_results = root.findall(ATOM + "entry")
total = len(search_results)

file_name = f"papers_arxiv.txt"

full_date = []

for index, result in enumerate(search_results, start=1):
    title = re.sub(r'\s+', ' ', (result.findtext(ATOM + "title") or "")).strip()
    authors = ", ".join(
        (a.findtext(ATOM + "name") or "").strip()
        for a in result.findall(ATOM + "author")
    )
    if "krijn" in authors.lower() or "reijnders" in authors.lower():
        authors = authors.replace("ij", "ĳ")
    # arxiv id looks like http://arxiv.org/abs/2608.02494v1 -> 2608.02494
    id = result.findtext(ATOM + "id").split("/abs/")[-1]
    id = re.sub(r'v\d+$', '', id)
    dates = (result.findtext(ATOM + "published") or "")[:10]

    title = detexify(title)

    # repo discovery is disabled for now
    repo = 'none'

    formatted = [title, authors, id, dates, repo]
    full_date.append(formatted)

full_date = sorted(full_date, key=lambda x: x[-2], reverse=True)

with open(file_name, "w") as file:
    for chunk in full_date:
        file.write(f"{chunk[0].lower()};;;")
        file.write(f"{chunk[1].lower()};;;")
        file.write(f"{chunk[2]};;;")
        file.write(f"{classify_date(chunk[3])};;;")
        file.write(f"{chunk[4]}\n")

file_name = f"log_arxiv.txt"
with open(file_name, "a") as file:
        today = date.today()
        file.write(f"logged at {today}\n")
