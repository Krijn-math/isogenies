from datetime import date, datetime, timedelta
import os
import requests
import unicodeit
import re
from bs4 import BeautifulSoup
import PyPDF2
import io

base = 'http://eprint.iacr.org/'
key = '/Annots'
uri = '/URI'
ank = '/A'

def get_pdf(urlid):
    pdfres = requests.get(base + urlid + ".pdf")
    pdf_io_bytes = io.BytesIO(pdfres.content)
    pdf = PyPDF2.PdfReader(pdf_io_bytes)
    return pdf

def extract_all_urls(pdf):
    urls = []

    pages = len(pdf.pages)

    for page in range(pages):
        page_slice = pdf.pages[page]
        page_obj = page_slice.get_object()
        if key in page_obj.keys():
            ann = page_obj[key]
            for a in ann:
                u = a.get_object()
                if uri in u[ank].keys():
                    urls.append(u[ank][uri])

    return urls

def extract_gits(urls):
    if urls == []:
        print("no urls given")
        return []
    
    gits = []
    gits += [ r for r in urls if 'git' in r]

    return gits

def get_repo(pdf):
    urls = extract_all_urls(pdf)

    if urls == []:
        print("no urls")
        return ['none']
    
    gits = extract_gits(urls)

    if gits == []:
        print("no git")
        return ['none']

    return gits


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

file_name = f"isogeny/papers2.txt"

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

    try:
        pdf = get_pdf(id)
        repo = get_repo(pdf)[0]
        print(repo)
    except:
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

file_name = f"isogeny/log2.txt"
with open(file_name, "a") as file:
        today = date.today()
        file.write(f"logged at {today}\n")
