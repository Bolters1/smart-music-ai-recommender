import os
import requests

base_url = "https://teppyslayouts.neocities.org/10/img/"
images = [
    "button-inactive.png",
    "button-active.png",
    "main-tile.png",
    "main-top.png",
    "window-frame.png",
    "window-left.png",
    "window-right.png",
    "window-background.png",
    "gif.gif"
]

public_dir = os.path.join(os.path.dirname(__file__), 'public', 'img')
os.makedirs(public_dir, exist_ok=True)

for img in images:
    url = base_url + img
    dest = os.path.join(public_dir, img)
    print(f"Downloading {img}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(dest, 'wb') as f:
            f.write(response.content)
        print(f"  -> Saved {img}")
    except Exception as e:
        print(f"  -> Error: {e}")

print("Done downloading assets.")
