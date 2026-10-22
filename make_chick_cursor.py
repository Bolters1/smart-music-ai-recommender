from PIL import Image
from pathlib import Path

# 16x16 pixel art of the exact yellow chick from JavaScript Kit demo
img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
pixels = img.load()

# Matrix mapping
# '.' = transparent
# 'B' = black outline (#000000)
# 'Y' = yellow body (#FFF04C)
# 'H' = yellow highlight (#FFFF88)
# 'E' = eye black (#000000)
# 'P' = pink/orange beak/cheek (#FF7A85)
# 'O' = orange beak tip (#FF5533)

art = [
    "................",
    ".....BBBBB......",
    "...BBHYYYYBB....",
    "..BHYYYYYYYYB...",
    ".BHYYYYYYYYYYB..",
    ".BYYYYYYYEEYYYB.",
    "BYYYYYYYYYEEYYYB",
    "BYYYYYYYYYYYYYBO",
    "BYYYYYYYYYYYYBPB",
    "BYYYYYYYYYYYBPPB",
    ".BYYYYYYYYYYYBB.",
    ".BYYYYYYYYYYB...",
    "..BYYYYYYYYB....",
    "...BBBYYYBB.....",
    ".....BBBB.......",
    "................"
]

color_map = {
    'B': (0, 0, 0, 255),
    'Y': (255, 230, 40, 255),
    'H': (255, 250, 140, 255),
    'E': (0, 0, 0, 255),
    'P': (255, 120, 140, 255),
    'O': (255, 90, 50, 255)
}

for y, row in enumerate(art):
    for x, char in enumerate(row):
        if char in color_map:
            pixels[x, y] = color_map[char]

dest_gif = Path("frontend/public/img/cursor.gif")
dest_png = Path("frontend/public/img/cursor.png")
dest_gif.parent.mkdir(parents=True, exist_ok=True)

img.save(dest_gif, format="GIF", transparency=0)
img.save(dest_png, format="PNG")
print("Successfully generated exact yellow chick cursor.gif and cursor.png!")
