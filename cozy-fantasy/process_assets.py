#!/usr/bin/env python3
"""Постобробка ілюстрацій Cozy Fantasy для гри.

- Фони: центр-кроп до 4:3 -> 1024x768
- Персонажі/об'єкти: прибирання білого фону (flood-fill від країв,
  щоб внутрішні білі ділянки одягу залишились), кроп по bbox,
  прозорі cutout-версії + фіксовані розміри під гру.
"""
import os
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = BASE
OUT = os.path.join(BASE, "game-assets")

THRESH = 26          # допуск "білизни" фону
WORK = 1024          # робоча ширина/висота для flood-fill


def load_rgb(path):
    im = Image.open(path).convert("RGB")
    return im


def bg_color(arr):
    """Медіанний колір рамки зображення = колір фону."""
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0)


def white_mask(arr, bg, thresh=THRESH):
    return np.all(np.abs(arr.astype(np.int16) - bg.astype(np.int16)) <= thresh, axis=-1)


def flood_fill_from_border(mask):
    """Span-fill: повертає маску білих пікселів, досяжних з рамки."""
    h, w = mask.shape
    reach = np.zeros_like(mask)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if mask[y, x] and not reach[y, x]:
                reach[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if mask[y, x] and not reach[y, x]:
                reach[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        # розбігаємось по рядку вліво/вправо
        x0 = x
        while x0 > 0 and mask[y, x0 - 1] and not reach[y, x0 - 1]:
            x0 -= 1
        x1 = x
        while x1 < w - 1 and mask[y, x1 + 1] and not reach[y, x1 + 1]:
            x1 += 1
        reach[y, x0:x1 + 1] = True
        for yy in (y - 1, y + 1):
            if 0 <= yy < h:
                xx = x0
                while xx <= x1:
                    if mask[yy, xx] and not reach[yy, xx]:
                        # новий span
                        s = xx
                        while s > 0 and mask[yy, s - 1] and not reach[yy, s - 1]:
                            s -= 1
                        e = xx
                        while e < w - 1 and mask[yy, e + 1] and not reach[yy, e + 1]:
                            e += 1
                        reach[yy, s:e + 1] = True
                        dq.append((yy, xx))
                        xx = e + 1
                    else:
                        xx += 1
    return reach


def remove_enclosed_bg(arr, bg, mask, reach, min_area=2000, max_dist=6):
    """Прибирає замкнені ділянки фону (напр. між ногами), до яких
    flood-fill не дістався, не чіпаючи дрібних світлих деталей одягу."""
    rem = mask & ~reach
    if not rem.any():
        return reach
    h, w = rem.shape
    lab = np.zeros(rem.shape, np.int32)
    cur = 0
    ys, xs = np.nonzero(rem)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        cur += 1
        lab[y0, x0] = cur
        dq = deque([(y0, x0)])
        px = []
        while dq:
            y, x = dq.popleft()
            px.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and rem[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    dq.append((yy, xx))
        px = np.array(px)
        if len(px) < min_area:
            continue
        mean = arr[px[:, 0], px[:, 1]].mean(axis=0)
        if np.abs(mean - bg).max() <= max_dist:
            reach = reach | (lab == cur)
    return reach


def cutout(path):
    """Повертає RGBA-зображення (робочий розмір) з прозорим фоном."""
    im = load_rgb(path)
    im = im.resize((WORK, WORK), Image.LANCZOS)
    arr = np.asarray(im)
    bg = bg_color(arr)
    mask = white_mask(arr, bg)
    reach = flood_fill_from_border(mask)
    reach = remove_enclosed_bg(arr, bg, mask, reach)
    alpha0 = np.where(reach, 0, 255).astype(np.uint8)
    soft = np.asarray(Image.fromarray(alpha0, "L").filter(ImageFilter.GaussianBlur(0.8)))
    # ерозія фону на 2px: всередині фону альфа суворо 0, м'який край лише по силуету
    reach_img = Image.fromarray(np.where(reach, 255, 0).astype(np.uint8), "L")
    reach_core = np.asarray(reach_img.filter(ImageFilter.MinFilter(5))) > 128
    a = np.where(reach_core, 0, soft).astype(np.uint8)
    rgba = np.dstack([arr, a]).astype(np.uint8)
    out = Image.fromarray(rgba, "RGBA")
    bbox = out.getbbox()
    if bbox:
        pad = 6
        bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                min(WORK, bbox[2] + pad), min(WORK, bbox[3] + pad))
        out = out.crop(bbox)
    return out


def fit_into(im, w, h):
    """Вписує зображення в коробку w×h зі збереженням пропорцій."""
    cw, ch = im.size
    k = min(w / cw, h / ch)
    nw, nh = max(1, round(cw * k)), max(1, round(ch * k))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im2, ((w - nw) // 2, (h - nh) // 2), im2)
    return canvas


def crop_43(im, w=1024, h=768):
    cw, ch = im.size
    k = max(w / cw, h / ch)
    nw, nh = round(cw * k), round(ch * k)
    # невеликий зсув центру вниз для інтер'єрів загалом не потрібен — центр
    im2 = im.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - w) // 2
    y0 = (nh - h) // 2
    return im2.crop((x0, y0, x0 + w, y0 + h))


def main():
    report = []

    # ---------- фони ----------
    bdir = os.path.join(SRC, "backgrounds")
    for name in sorted(os.listdir(bdir)):
        if not name.endswith(".png"):
            continue
        im = load_rgb(os.path.join(bdir, name))
        out = crop_43(im)
        dst = os.path.join(OUT, "backgrounds", name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        out.save(dst, optimize=True)
        report.append((f"backgrounds/{name}", "1024x768", os.path.getsize(dst)))

    # ---------- персонажі ----------
    targets = {
        "characters": (200, 400),
    }
    cdir = os.path.join(SRC, "characters")
    for name in sorted(os.listdir(cdir)):
        if not name.endswith(".png"):
            continue
        cut = cutout(os.path.join(cdir, name))
        dcut = os.path.join(OUT, "cutouts", name)
        os.makedirs(os.path.dirname(dcut), exist_ok=True)
        cut.save(dcut, optimize=True)
        w, h = targets["characters"]
        sized = fit_into(cut, w, h)
        dst = os.path.join(OUT, "characters", name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        sized.save(dst, optimize=True)
        report.append((f"characters/{name}", f"{w}x{h} (+cutout {cut.size[0]}x{cut.size[1]})",
                       os.path.getsize(dst)))

    # ---------- об'єкти ----------
    obj_targets = {
        "phone.png": (64, 64),
        "books.png": (100, 60),
        "bench.png": (200, 80),
        "notice.png": (150, 90),
    }
    odir = os.path.join(SRC, "objects")
    for name, (w, h) in obj_targets.items():
        cut = cutout(os.path.join(odir, name))
        dcut = os.path.join(OUT, "cutouts", name)
        os.makedirs(os.path.dirname(dcut), exist_ok=True)
        cut.save(dcut, optimize=True)
        sized = fit_into(cut, w, h)
        dst = os.path.join(OUT, "objects", name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        sized.save(dst, optimize=True)
        report.append((f"objects/{name}", f"{w}x{h} (+cutout {cut.size[0]}x{cut.size[1]})",
                       os.path.getsize(dst)))

    for path, spec, size in report:
        print(f"{path:32s} {spec:38s} {size/1024:7.1f} KB")


if __name__ == "__main__":
    main()
