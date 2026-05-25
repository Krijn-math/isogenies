"""
Generate HTML redirect pages from forwards.txt.

Format of forwards.txt:
    identifier, url

Each line produces an <identifier>.html file that immediately redirects to <url>.
Lines starting with # and blank lines are ignored.

Usage:
    python generate_forwards.py
"""

import os

FORWARDS_FILE = "forwards.txt"
GENERATED_MARKER = "<!-- generated-forward -->"


def generate_redirect_html(url: str) -> str:
    return f"""\
<!DOCTYPE html>
{GENERATED_MARKER}
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Refresh" content="0; url='{url}'" />
  <title>Redirecting…</title>
</head>
<body>
  <p>Redirecting to <a href="{url}">{url}</a>…</p>
</body>
</html>
"""


def read_forwards(path: str) -> list[tuple[str, str]]:
    forwards = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                print(f"  Warning: line {lineno} skipped (no comma): {line!r}")
                continue
            identifier, url = line.split(",", 1)
            identifier = identifier.strip()
            url = url.strip()
            if not identifier or not url:
                print(f"  Warning: line {lineno} skipped (empty field): {line!r}")
                continue
            forwards.append((identifier, url))
    return forwards


def find_previously_generated() -> set[str]:
    """Return identifiers of HTML files we previously generated."""
    generated = set()
    for fname in os.listdir("."):
        if not fname.endswith(".html"):
            continue
        try:
            with open(fname, encoding="utf-8") as f:
                content = f.read()
            if GENERATED_MARKER in content:
                generated.add(fname[: -len(".html")])
        except OSError:
            pass
    return generated


def main():
    forwards = read_forwards(FORWARDS_FILE)
    current_identifiers = {ident for ident, _ in forwards}

    # Clean up forwards that were removed from forwards.txt
    previously_generated = find_previously_generated()
    for old_ident in previously_generated - current_identifiers:
        old_file = f"{old_ident}.html"
        os.remove(old_file)
        print(f"  Removed  {old_file} (no longer in forwards.txt)")

    # Generate / update forwards
    for identifier, url in forwards:
        out_path = f"{identifier}.html"
        html = generate_redirect_html(url)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Forward  /{identifier}  →  {url}")

    print(f"\nDone: {len(forwards)} forward(s) active.")


if __name__ == "__main__":
    main()
