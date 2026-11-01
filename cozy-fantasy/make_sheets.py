#!/usr/bin/env python3
"""Контакт-аркуші для швидкого перегляду всіх ассетів."""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
GA = os.path.join(BASE, "game-assets")


def font(size=18):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def label(draw, xy, text, f, fill=(40, 34, 28)):
    draw.text(xy, text, font=f, fill=fill)


def sheet(paths, cell, cols, out, title, bg=(246, 242, 234), checker=False):
    f = font(16)
    ft = font(26)
    cw, ch = cell
    rows = (len(paths) + cols - 1) // cols
    pad, lab = 14, 26
    W = cols * (cw + pad) + pad
    H = rows * (ch + pad + lab) + pad + 46
    sheet = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(sheet)
    label(d, (pad, pad - 4), title, ft)
    for i, p in enumerate(paths):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = 46 + pad + r * (ch + pad + lab)
        im = Image.open(p).convert("RGBA")
        im.thumbnail((cw, ch), Image.LANCZOS)
        if checker:
            tile = Image.new("RGB", (cw, ch), (255, 255, 255))
            td = ImageDraw.Draw(tile)
            s = 12
            for yy in range(0, ch, s):
                for xx in range(0, cw, s):
                    if (xx // s + yy // s) % 2:
                        td.rectangle([xx, yy, xx + s - 1, yy + s - 1], fill=(224, 224, 228))
            tile.paste(im, ((cw - im.width) // 2, (ch - im.height) // 2), im)
            sheet.paste(tile, (x, y))
        else:
            sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2), im)
        label(d, (x + 2, y + ch + 6), os.path.basename(p), f)
    sheet.save(out, optimize=True)
    print(out, sheet.size)


def main():
    b = sorted(os.path.join(GA, "backgrounds", n) for n in os.listdir(os.path.join(GA, "backgrounds")))
    sheet(b, (360, 270), 4, os.path.join(BASE, "sheet_backgrounds.png"),
          "BACKGROUNDS  1024x768 (4:3)")

    c = sorted(os.path.join(GA, "characters", n) for n in os.listdir(os.path.join(GA, "characters")))
    sheet(c, (150, 300), 8, os.path.join(BASE, "sheet_characters.png"),
          "CHARACTERS  200x400, transparent BG", checker=True)

    o = sorted(os.path.join(GA, "objects", n) for n in os.listdir(os.path.join(GA, "objects")))
    sheet(o, (220, 120), 4, os.path.join(BASE, "sheet_objects.png"),
          "OBJECTS  game sizes, transparent BG", checker=True)


if __name__ == "__main__":
    main()
