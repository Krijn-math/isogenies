from datetime import date, datetime, timedelta
import json
import unicodeit
import re
import json
from bs4 import BeautifulSoup

def classify_date(data):
    for obj in data:
        parsed_date = datetime.strptime(obj['lastmodified'], '%Y-%m-%d %H:%M:%S')
        current_date = datetime.now()

        time_difference = current_date - parsed_date

        if time_difference <= timedelta(days=7):
            obj['classification'] = 'last_week'
        elif time_difference <= timedelta(days=30):
            obj['classification'] = 'last_month'
        elif time_difference <= timedelta(days=365):
            obj['classification'] = 'last_year'
        else:
            obj['classification'] = 'other'
    
    return data

def detexify(text):
    def repl(match):
        return str(unicodeit.replace((match.group(1))))

    pattern = r'\$(.*?)\$'
    result = re.sub(pattern, repl, text)
    return result

def detexify_data(data):
    for obj in data:
        obj['abstract'] = detexify(obj['abstract'])
        obj['title'] = detexify(obj['title'])
    
    return data

def rekrijn_data(data):
    for obj in data:
        if 'Krijn Reijnders' in obj['authors']:
            obj['authors'] = ["Krĳn Reĳnders" if name == "Krijn Reijnders" else name for name in obj['authors']]

    return data

def lower_data(data):
    for obj in data:
        obj['title'] = obj['title'].lower()
        obj['authors'] = [author.lower() for author in obj['authors']]
    
    return data

# Load JSON data from file
with open('data.json', 'r') as f:
    data = json.load(f)
    papers = data["papers"]

# Function to filter objects in JSON based on a condition
def filter_objects(data, filter_key, filter_value):
    # Check if data is a list of objects (array of dictionaries)
    if isinstance(data, list):
        # Filter list based on the specified key-value pair
        return [obj for obj in data if filter_value in obj.get(filter_key)]
    # elif isinstance(data, dict):
        # Filter each list within a dictionary structure
        # return {k: [obj for obj in v if obj.get(filter_key) == filter_value] for k, v in data.items() if isinstance(v, list)}
    else:
        raise ValueError("The JSON structure is not supported for filtering.")


def clean_data(data):
    if isinstance(data, list):
        data = classify_date(data)
        data = detexify_data(data)
        data = rekrijn_data(data)
        data = lower_data(data)

    return data

# Example usage
# Replace 'filter_key' and 'filter_value' with actual key-value pairs you want to filter by
isogeny_data = filter_objects(papers, 'abstract', 'isogeny')
isogeny_data = clean_data(isogeny_data)

# # Write the filtered data to a new JSON file
with open('isogeny_data.json', 'w') as f:
    json.dump(isogeny_data, f, indent=4)
