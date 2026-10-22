from PIL import Image, ImageDraw
from pathlib import Path

# Create a cute 16x16 retro pixel sparkle star
img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
pixels = img.load()

# Define pixel art for a cute retro sparkle star (16x16)
art = [
    "....#...........",
    "...#W#..........",
    "...#W#..........",
    "..#WW#..........",
    ".#WWW#....#.....",
    "##WWWW###.#W#...",
    "#WWWWWWW##WW#...",
    ".##WWWWWWWW#....",
    "..##WWWWWW#.....",
    ".#WWWWWWWW##....",
    "#WW##WWWWWWW#...",
    ".#W#.###WWWW##..",
    ".....#..#WWW#...",
    ".........#WW#...",
    "..........#W#...",
    "...........#...."
]

outline_color = (60, 40, 80, 240)    # Deep retro purple outline
fill_color = (255, 220, 240, 255)     # Cute pastel pink
highlight_color = (255, 255, 255, 255)# Pure white sparkle

for y, row in enumerate(art):
    for x, char in enumerate(row):
        if char == '#':
            pixels[x, y] = outline_color
        elif char == 'W':
            # Add subtle gradient/highlight
            if x <= 5 and y <= 7:
                pixels[x, y] = highlight_color
            else:
                pixels[x, y] = fill_color

dest_png = Path('frontend/public/img/cursor.png')
dest_png.parent.mkdir(parents=True, exist_ok=True)
img.save(dest_png)

dest_gif = Path('frontend/public/img/cursor.gif')
img.save(dest_gif)
print("Saved cute retro sparkle cursor to", dest_png)
