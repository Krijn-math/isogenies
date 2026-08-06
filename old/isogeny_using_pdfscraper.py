from datetime import date, datetime, timedelta
import os
import requests
import unicodeit
import re
from bs4 import BeautifulSoup
from pypdf import PdfReader
import io

base = 'http://eprint.iacr.org/'

def get_pdf(urlid):
    pdfres = requests.get(base + urlid + ".pdf")
    pdf_io_bytes = io.BytesIO(pdfres.content)
    pdf = PdfReader(pdf_io_bytes)
    pdfpages = [pdf.pages[i].extract_text() for i in range(len(pdf.pages))]

    return pdfpages




# URL
URL_REGEX = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))"""

def extract_urls(text):
    return re.findall(URL_REGEX, text, re.IGNORECASE)

def extract_all_urls(pdfpages):
    res = []

    for page in pdfpages:
        res += extract_urls(page)
        
    if res != []:
        return res
    else:
        print("no repo found")
        return ''

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

file_name = f"papers2.txt"

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

file_name = f"log2.txt"
with open(file_name, "a") as file:
        today = date.today()
        file.write(f"logged at {today}\n")
