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

urlid = '2023/1197'