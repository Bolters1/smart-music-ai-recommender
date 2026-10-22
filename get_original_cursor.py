import urllib.request
from pathlib import Path

urls = [
    "http://www.javascriptkit.com/script/script2/cursor.gif",
    "https://www.javascriptkit.com/script/script2/cursor.gif",
    "http://javascriptkit.com/script/script2/cursor.gif"
]

dest = Path("frontend/public/img/cursor.gif")
dest.parent.mkdir(parents=True, exist_ok=True)

success = False
for url in urls:
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read()
            if len(content) > 20:
                with open(dest, 'wb') as f:
                    f.write(content)
                print(f"Successfully downloaded original cursor.gif from {url} ({len(content)} bytes)")
                success = True
                break
    except Exception as e:
        print(f"Failed {url}: {e}")

if not success:
    print("Could not download directly, will generate pixel-perfect replica.")
