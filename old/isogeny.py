from datetime import date, datetime, timedelta
import os
import requests
import unicodeit
import re
import mdtex2html
from bs4 import BeautifulSoup

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

url = "https://eprint.iacr.org/search?q=isogeny+isogenies"

response = requests.get(url)
html_content = response.text
soup = BeautifulSoup(html_content, "html.parser")

search_results = soup.find_all("div", class_="mb-4")
total = len(search_results)

file_name = f"papers.txt"

full_date = []

for index, result in enumerate(search_results, start=1):
    title = result.find("strong").get_text().strip()
    authors = result.find("span", class_="fst-italic").get_text().strip()
    if "krijn" in authors.lower() or "reijnders" in authors.lower():
        authors = authors.replace("ij", "ĳ")
    id = result.find("a", class_="paperlink").get_text().strip()
    dates = result.find("small", class_="ms-auto").get_text().strip()
    dates = dates[14:24]

    title = detexify(title)

    formatted = [title, authors, id, dates]
    full_date.append(formatted)

full_date = sorted(full_date, key=lambda x: x[-1], reverse=True)

with open(file_name, "w") as file:
    for chunk in full_date:
        file.write(f"{chunk[0].lower()};;;")
        file.write(f"{chunk[1].lower()};;;")
        file.write(f"{chunk[2]};;;")
        file.write(f"{classify_date(chunk[3])}\n")

file_name = f"log.txt"
with open(file_name, "a") as file:
        today = date.today()
        file.write(f"logged at {today}\n")
