#!/usr/bin/env python3
"""Sanayi Devrimi'ni anlatan kısa bir eğitim videosu üretir.

Gereksinimler: Python 3, Pillow, numpy, ffmpeg, espeak-ng (+ isteğe bağlı mbrola-tr1).
Kullanım:  python3 make_video.py  ->  sanayi_devrimi.mp4
"""
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1280, 720, 24
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sanayi_devrimi.mp4")
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def font(size, bold=False, serif=False):
    name = "DejaVu" + ("Serif" if serif else "Sans") + ("-Bold" if bold else "") + ".ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


F_TITLE = font(84, True, True)
F_H1 = font(52, True, True)
F_BODY = font(30)
F_BODY_B = font(30, True)
F_SUB = font(28, True)
F_SMALL = font(22)

# Renk paleti: is, kömür, pirinç, kızıl gökyüzü
INK = (24, 22, 26)
PAPER = (236, 224, 200)
BRASS = (201, 150, 64)
RUST = (168, 72, 44)
SOOT = (58, 54, 56)
SKY_TOP = (62, 52, 64)
SKY_BOT = (196, 120, 78)

# ---------------------------------------------------------------- senaryo
SCENES = [
    ("title", "Sanayi Devrimi",
     "Sanayi Devrimi. İnsanlık tarihinin yönünü değiştiren büyük dönüşüm."),
    ("before", "Devrimden Önce",
     "On sekizinci yüzyıldan önce insanların çoğu köylerde yaşıyor, toprağı işliyordu. "
     "Üretim el emeğine, hayvan gücüne, rüzgâra ve suya dayanıyordu."),
    ("why", "Neden İngiltere?",
     "Devrim, on sekizinci yüzyılın ortalarında İngiltere'de başladı. "
     "Bol kömür ve demir yatakları, ticaretten gelen sermaye, geniş sömürge pazarları "
     "ve yeni fikirlere açık bir ortam bunu mümkün kıldı."),
    ("steam", "Buhar Makinesi",
     "Dönüşümün kalbinde buhar makinesi vardı. "
     "James Watt'ın bin yedi yüz altmış dokuzda geliştirdiği makine, kömürün gücünü harekete çevirdi "
     "ve fabrikaları sudan bağımsız hale getirdi."),
    ("factory", "Fabrikalar ve Tekstil",
     "İlk büyük atılım tekstilde yaşandı. Mekik ve iplik makineleri üretimi kat kat artırdı. "
     "Evlerdeki tezgâhların yerini dev fabrikalar aldı."),
    ("rail", "Demiryolu Çağı",
     "Bin sekiz yüz yirmi beşte ilk buharlı yolcu demiryolu açıldı. "
     "Trenler ve buharlı gemiler insanları, hammaddeyi ve malları hiç olmadığı kadar hızlı taşıdı."),
    ("city", "Toplumsal Etkiler",
     "Köylerden kentlere büyük bir göç başladı. Yeni bir işçi sınıfı doğdu. "
     "Uzun çalışma saatleri, çocuk işçiliği ve kirli şehirler, sendikaların ve işçi haklarının yolunu açtı."),
    ("spread", "Dünyaya Yayılış",
     "Devrim kısa sürede Belçika'ya, Fransa'ya, Almanya'ya, Amerika'ya ve Japonya'ya yayıldı. "
     "Osmanlı İmparatorluğu ise bu sürece geç ve sınırlı biçimde katılabildi."),
    ("legacy", "Mirası",
     "Bugün kullandığımız elektrik, otomobil, seri üretim ve küresel ticaret, bu dönüşümün mirasıdır. "
     "Sanayi Devrimi, modern dünyayı inşa etti."),
]

# ---------------------------------------------------------------- ses


def tts(text, path):
    for voice in ("mb-tr1", "tr"):
        r = subprocess.run(["espeak-ng", "-v", voice, "-s", "148", "-p", "45", "-w", path, text],
                           capture_output=True)
        if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 1000:
            return
    sys.exit("espeak-ng ile ses üretilemedi")


def wav_duration(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- çizim yardımcıları


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def gradient(top, bot):
    a = np.linspace(0, 1, H)[:, None, None]
    arr = (np.array(top)[None, None] * (1 - a) + np.array(bot)[None, None] * a)
    arr = np.repeat(arr, W, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


SKY = gradient(SKY_TOP, SKY_BOT)
PAPER_BG = gradient((240, 230, 208), (214, 196, 164))
NIGHT = gradient((18, 18, 26), (52, 40, 44))

# Hafif film greni için sabit gürültü dokuları
_rng = np.random.default_rng(7)
GRAIN = [Image.fromarray((_rng.normal(0, 9, (H, W, 1)).repeat(3, 2) + 128).clip(0, 255).astype(np.uint8))
         for _ in range(4)]
VIGNETTE = None


def make_vignette():
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    v = (1 - np.clip((d - 0.6) * 0.9, 0, 0.6)) * 255
    return Image.fromarray(v.astype(np.uint8), "L")


VIGNETTE = make_vignette()


def text_center(d, xy, s, f, fill, anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def gear(d, cx, cy, r, teeth, angle, fill, hole=None):
    pts = []
    n = teeth * 4
    for i in range(n):
        a = angle + 2 * math.pi * i / n
        rr = r if (i % 4) in (0, 1) else r * 0.8
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)
    d.ellipse((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), fill=tuple(int(c * 0.8) for c in fill))
    for k in range(4):
        a = angle + k * math.pi / 2
        d.line((cx, cy, cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a)), fill=fill, width=int(r * 0.14))
    d.ellipse((cx - r * 0.15, cy - r * 0.15, cx + r * 0.15, cy + r * 0.15), fill=hole or INK)


def smoke(d, x, y, t, seed, scale=1.0, col=(120, 112, 112)):
    rnd = random.Random(seed)
    for i in range(14):
        ph = (t * 0.35 + i / 14 + rnd.random() * 0.05) % 1.0
        px = x + ph * 160 * scale + math.sin(ph * 6 + i) * 12 * scale
        py = y - ph * 260 * scale
        r = (10 + ph * 46) * scale
        a = int(200 * (1 - ph))
        c = tuple(int(cc + (255 - cc) * ph * 0.3) for cc in col) + (a,)
        d.ellipse((px - r, py - r, px + r, py + r), fill=c)


def factory(d, x, base, w, h, chimneys, t, seed, col=SOOT):
    d.rectangle((x, base - h, x + w, base), fill=col)
    # testere dişi çatı
    n = max(2, w // 60)
    sw = w / n
    for i in range(n):
        d.polygon([(x + i * sw, base - h), (x + (i + 1) * sw, base - h), (x + (i + 1) * sw, base - h - 30)], fill=col)
    # pencereler
    for i in range(int(w // 34)):
        for j in range(int((h - 20) // 40)):
            wx, wy = x + 12 + i * 34, base - h + 16 + j * 40
            if wx + 16 < x + w:
                lit = (hash((seed, i, j)) % 3) != 0
                d.rectangle((wx, wy, wx + 16, wy + 22), fill=(236, 180, 90) if lit else (40, 36, 38))
    for k, (cxo, ch) in enumerate(chimneys):
        cx = x + cxo
        d.rectangle((cx, base - h - ch, cx + 24, base - h), fill=tuple(int(c * 0.85) for c in col))
        d.rectangle((cx - 4, base - h - ch, cx + 28, base - h - ch + 10), fill=tuple(int(c * 0.7) for c in col))


def chimney_smoke_points(x, base, h, chimneys):
    return [(x + cxo + 12, base - h - ch) for cxo, ch in chimneys]


# ---------------------------------------------------------------- sahneler
# Her çizim fonksiyonu (img, t, dur) alır; t saniye cinsindendir.


def draw_title(img, t, dur):
    img.paste(NIGHT)
    ov = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(ov)
    base = 640
    for i, (x, w, hh, ch) in enumerate([(40, 260, 170, [(40, 150), (180, 110)]),
                                       (330, 300, 220, [(60, 190), (220, 140)]),
                                       (680, 240, 150, [(90, 120)]),
                                       (950, 300, 200, [(50, 170), (200, 130)])]):
        for sx, sy in chimney_smoke_points(x, base, hh, ch):
            smoke(d, sx, sy, t, i * 10 + sx, 0.9, (90, 84, 88))
        factory(d, x, base, w, hh, ch, t, i, (30, 28, 32))
    d.rectangle((0, base, W, H), fill=(20, 18, 22))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    a = ease(t / 1.6)
    gear(d, 640, 150, 60, 12, t * 0.6, BRASS)
    text_center(d, (640, 280 + (1 - a) * 30), "SANAYİ DEVRİMİ", F_TITLE, tuple(int(c * a) for c in PAPER))
    text_center(d, (640, 360), "1760 – 1840", F_H1, tuple(int(c * ease((t - 0.8) / 1.2)) for c in BRASS))


def draw_before(img, t, dur):
    img.paste(gradient((150, 196, 226), (240, 222, 170)))
    d = ImageDraw.Draw(img)
    # güneş
    d.ellipse((960, 90, 1080, 210), fill=(252, 214, 120))
    # tepeler ve tarlalar
    for k, (col, yb, amp) in enumerate([((132, 160, 92), 470, 40), ((108, 140, 74), 530, 30), ((92, 120, 60), 600, 20)]):
        pts = [(x, yb + amp * math.sin(x / 160 + k)) for x in range(0, W + 20, 20)] + [(W, H), (0, H)]
        d.polygon(pts, fill=col)
    for i in range(14):
        x = 60 + i * 90
        d.line((x, 620, x + 40, H), fill=(80, 104, 50), width=3)
    # yel değirmeni
    mx, my = 300, 360
    d.polygon([(mx - 30, my + 140), (mx + 30, my + 140), (mx + 16, my), (mx - 16, my)], fill=(190, 170, 140))
    for k in range(4):
        a = t * 1.2 + k * math.pi / 2
        ex, ey = mx + 110 * math.cos(a), my + 110 * math.sin(a)
        px, py = -math.sin(a) * 14, math.cos(a) * 14
        d.polygon([(mx, my), (ex, ey), (ex + px, ey + py), (mx + px * 0.3, my + py * 0.3)], fill=(110, 84, 60))
    d.ellipse((mx - 8, my - 8, mx + 8, my + 8), fill=INK)
    # köy evleri
    for i, x in enumerate([620, 720, 840]):
        y = 470 + i * 6
        d.rectangle((x, y, x + 80, y + 60), fill=(222, 200, 160))
        d.polygon([(x - 8, y), (x + 88, y), (x + 40, y - 40)], fill=RUST)
        d.rectangle((x + 30, y + 26, x + 50, y + 60), fill=(90, 64, 44))
    # çiftçi (çapa sallayan)
    fx, fy = 470, 560
    sw = math.sin(t * 3) * 0.5
    d.ellipse((fx - 12, fy - 90, fx + 12, fy - 66), fill=INK)
    d.line((fx, fy - 66, fx, fy - 20), fill=INK, width=8)
    d.line((fx, fy - 20, fx - 16, fy + 20), fill=INK, width=7)
    d.line((fx, fy - 20, fx + 16, fy + 20), fill=INK, width=7)
    hx, hy = fx + 50 * math.cos(-1.0 + sw), fy - 56 + 50 * math.sin(-1.0 + sw)
    d.line((fx, fy - 56, hx, hy), fill=INK, width=6)
    d.line((hx, hy, hx + 70 * math.cos(0.9 + sw), hy + 70 * math.sin(0.9 + sw)), fill=(110, 80, 50), width=5)


def draw_why(img, t, dur):
    img.paste(PAPER_BG)
    d = ImageDraw.Draw(img)
    # stilize İngiltere silüeti
    uk = [(300, 120), (340, 150), (330, 200), (360, 240), (350, 290), (400, 330), (420, 400), (460, 430),
          (440, 470), (480, 500), (420, 520), (330, 530), (270, 560), (300, 510), (330, 470), (300, 440),
          (320, 400), (280, 360), (300, 320), (260, 280), (290, 230), (260, 180)]
    d.polygon(uk, fill=(160, 140, 110), outline=INK)
    # Londra noktası (yanıp söner)
    p = 0.5 + 0.5 * math.sin(t * 4)
    r = 8 + 6 * p
    d.ellipse((420 - r, 495 - r, 420 + r, 495 + r), outline=RUST, width=3)
    d.ellipse((414, 489, 426, 501), fill=RUST)
    d.text((440, 482), "Londra", font=F_SMALL, fill=INK)
    items = [("Kömür ve demir yatakları", SOOT), ("Ticaretten gelen sermaye", BRASS),
             ("Sömürge pazarları", RUST), ("Bilim ve yeni fikirler", (70, 100, 130))]
    seg = max(1.0, (dur - 2) / len(items))
    for i, (s, col) in enumerate(items):
        a = ease((t - 0.8 - i * seg * 0.6) / 0.6)
        if a <= 0:
            continue
        y = 210 + i * 95
        x = 640 + (1 - a) * 60
        d.rounded_rectangle((x, y, x + 520, y + 70), 14, fill=tuple(int(255 - (255 - c) * a) for c in col))
        d.ellipse((x + 18, y + 17, x + 54, y + 53), fill=PAPER)
        text_center(d, (x + 36, y + 35), str(i + 1), F_BODY_B, col)
        d.text((x + 74, y + 35), s, font=F_BODY_B, fill=PAPER, anchor="lm")


def draw_steam(img, t, dur):
    img.paste(gradient((44, 38, 40), (86, 66, 52)))
    d = ImageDraw.Draw(img)
    ang = t * 2.2
    # büyük volan
    fx, fy, fr = 860, 330, 170
    d.ellipse((fx - fr, fy - fr, fx + fr, fy + fr), outline=BRASS, width=22)
    for k in range(6):
        a = ang + k * math.pi / 3
        d.line((fx, fy, fx + fr * math.cos(a), fy + fr * math.sin(a)), fill=BRASS, width=12)
    d.ellipse((fx - 26, fy - 26, fx + 26, fy + 26), fill=(150, 108, 46))
    # krank ve biyel
    crx, cry = fx + 70 * math.cos(ang), fy + 70 * math.sin(ang)
    piston_x = fx - 360 + 70 * math.cos(ang)
    d.line((piston_x, fy, crx, cry), fill=(200, 196, 190), width=14)
    d.ellipse((crx - 12, cry - 12, crx + 12, cry + 12), fill=INK)
    # silindir
    d.rounded_rectangle((260, fy - 70, 520, fy + 70), 10, fill=(110, 60, 40), outline=INK, width=4)
    d.rectangle((piston_x - 14 - 150, fy - 52, piston_x - 150 + 14, fy + 52), fill=(180, 176, 170))
    d.line((piston_x - 150, fy, piston_x, fy), fill=(200, 196, 190), width=14)
    # kazan
    d.rounded_rectangle((120, 470, 560, 620), 60, fill=(70, 70, 76), outline=INK, width=4)
    for k in range(5):
        d.ellipse((150 + k * 82, 525, 180 + k * 82, 555), fill=(110, 110, 118))
    fl = 0.5 + 0.5 * math.sin(t * 9)
    d.rounded_rectangle((260, 560, 420, 610), 8, fill=(240, int(120 + 80 * fl), 40))
    d.line((340, 470, 340, fy + 70), fill=(110, 110, 118), width=18)
    # buhar
    ov = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(ov)
    smoke(od, 300, fy - 70, t * 1.6, 3, 0.7, (230, 230, 230))
    img.paste(ov, (0, 0), ov)
    # küçük dişliler
    gear(d, 1120, 600, 70, 10, -ang * fr / 70 * 0.4, (150, 108, 46))
    gear(d, 1010, 640, 46, 8, ang * 0.9, BRASS)
    d = ImageDraw.Draw(img)
    a = ease((t - 1) / 1)
    d.rounded_rectangle((70, 70, 470, 180), 12, fill=(30, 26, 28))
    d.text((92, 92), "James Watt", font=F_BODY_B, fill=tuple(int(c * a) for c in BRASS))
    d.text((92, 132), "Buhar makinesi, 1769", font=F_SMALL, fill=tuple(int(c * a) for c in PAPER))


def draw_factory(img, t, dur):
    img.paste(SKY)
    ov = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(ov)
    base = 560
    blds = [(60, 360, 220, [(60, 200), (260, 160)]), (460, 420, 260, [(80, 240), (240, 210), (360, 150)]),
            (920, 320, 200, [(70, 190), (230, 150)])]
    grow = ease(t / 2.5)
    for i, (x, w, hh, ch) in enumerate(blds):
        ch2 = [(cx, int(c * grow)) for cx, c in ch]
        for sx, sy in chimney_smoke_points(x, base, hh, ch2):
            smoke(d, sx, sy, t, i * 7 + sx, 1.0)
        factory(d, x, base, w, hh, ch2, t, i)
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    d.rectangle((0, base, W, H), fill=(44, 40, 42))
    # dokuma tezgâhı: kayan iplikler ve gidip gelen mekik
    for k in range(12):
        y = base + 24 + k * 10
        d.line((80, y, 1200, y), fill=(206, 190, 160) if k % 2 else (176, 120, 90), width=4)
    sx = 640 + 520 * math.sin(t * 2.4)
    d.polygon([(sx - 50, base + 70), (sx, base + 52), (sx + 50, base + 70), (sx, base + 88)], fill=BRASS)
    # üretim sayacı
    n = int(1 + 49 * ease((t - 1) / max(1, dur - 3)))
    d.rounded_rectangle((60, 30, 300, 120), 12, fill=(30, 26, 28))
    d.text((80, 42), "Üretim artışı", font=F_SMALL, fill=PAPER)
    d.text((80, 72), f"×{n}", font=F_BODY_B, fill=BRASS)


def draw_rail(img, t, dur):
    img.paste(gradient((120, 150, 180), (236, 200, 150)))
    d = ImageDraw.Draw(img)
    # uzak tepeler
    pts = [(x, 420 + 30 * math.sin(x / 200)) for x in range(0, W + 20, 20)] + [(W, H), (0, H)]
    d.polygon(pts, fill=(130, 140, 110))
    d.rectangle((0, 520, W, H), fill=(110, 100, 80))
    # raylar ve traversler (kayan)
    off = (t * 300) % 60
    for i in range(-1, W // 60 + 2):
        x = i * 60 - off
        d.rectangle((x, 560, x + 26, 590), fill=(80, 60, 44))
    d.line((0, 566, W, 566), fill=(170, 170, 176), width=6)
    d.line((0, 584, W, 584), fill=(170, 170, 176), width=6)
    # telgraf direkleri (paralaks)
    off2 = (t * 160) % 400
    for i in range(-1, 5):
        x = i * 400 - off2
        d.line((x, 380, x, 540), fill=(80, 64, 50), width=6)
        d.line((x - 24, 396, x + 24, 396), fill=(80, 64, 50), width=5)
    # lokomotif
    lx = 200 + 140 * ease(t / 3)
    by = 556
    d.rectangle((lx, by - 110, lx + 230, by - 30), fill=(40, 40, 46))
    d.rounded_rectangle((lx + 200, by - 160, lx + 330, by - 30), 8, fill=(56, 30, 30))
    d.rectangle((lx + 220, by - 140, lx + 260, by - 100), fill=(236, 190, 110))
    d.rectangle((lx + 40, by - 180, lx + 70, by - 110), fill=(30, 30, 34))
    d.polygon([(lx + 30, by - 200), (lx + 80, by - 200), (lx + 70, by - 180), (lx + 40, by - 180)], fill=(30, 30, 34))
    d.polygon([(lx - 30, by - 30), (lx, by - 80), (lx, by - 30)], fill=RUST)
    wa = t * 8
    for wx, wr in [(lx + 50, 30), (lx + 130, 30), (lx + 270, 22)]:
        d.ellipse((wx - wr, by - 30 - wr, wx + wr, by - 30 + wr), fill=(26, 26, 28), outline=BRASS, width=4)
        d.line((wx, by - 30, wx + wr * math.cos(wa), by - 30 + wr * math.sin(wa)), fill=BRASS, width=4)
    d.line((lx + 50 + 20 * math.cos(wa), by - 30 + 20 * math.sin(wa),
            lx + 130 + 20 * math.cos(wa), by - 30 + 20 * math.sin(wa)), fill=(190, 190, 196), width=6)
    # vagonlar
    for k in range(3):
        vx = lx + 350 + k * 230
        d.rectangle((vx, by - 120, vx + 210, by - 34), fill=[(120, 46, 40), (60, 80, 60), (120, 46, 40)][k])
        for j in range(4):
            d.rectangle((vx + 14 + j * 50, by - 104, vx + 46 + j * 50, by - 70), fill=(236, 214, 170))
        for wx in (vx + 40, vx + 170):
            d.ellipse((wx - 18, by - 52, wx + 18, by - 16), fill=(26, 26, 28))
    ov = Image.new("RGBA", (W, H))
    smoke(ImageDraw.Draw(ov), lx + 55, by - 200, t * 1.5, 11, 0.8, (220, 220, 220))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, 600, 150), 12, fill=(30, 26, 28))
    d.text((80, 72), "1825 · Stockton – Darlington", font=F_BODY_B, fill=BRASS)
    d.text((80, 112), "İlk buharlı yolcu demiryolu", font=F_SMALL, fill=PAPER)


def draw_city(img, t, dur):
    img.paste(gradient((70, 66, 70), (150, 120, 100)))
    ov = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(ov)
    g = ease(t / max(1, dur * 0.6))
    rnd = random.Random(5)
    base = 600
    for i in range(26):
        x = i * 50 + rnd.randint(-10, 10)
        hh = int(rnd.randint(80, 300) * (0.25 + 0.75 * g))
        col = (rnd.randint(40, 70),) * 3
        d.rectangle((x, base - hh, x + 46, base), fill=col)
        for j in range(hh // 36):
            for k in range(2):
                if rnd.random() < 0.6:
                    d.rectangle((x + 8 + k * 18, base - hh + 10 + j * 36, x + 18 + k * 18, base - hh + 26 + j * 36),
                                fill=(220, 170, 90))
        if i % 5 == 2:
            d.rectangle((x + 14, base - hh - 70 * g, x + 30, base - hh), fill=(36, 34, 36))
            smoke(d, x + 22, base - hh - 70 * g, t, i, 0.8, (100, 96, 96))
    d.rectangle((0, base, W, H), fill=(96, 86, 76))
    # kente yürüyen işçiler
    for k in range(9):
        px = (k * 150 + t * 60) % (W + 100) - 50
        py = base + 60
        st = math.sin(t * 6 + k) * 10
        d.ellipse((px - 9, py - 70, px + 9, py - 52), fill=(20, 18, 20))
        d.line((px, py - 52, px, py - 18), fill=(20, 18, 20), width=6)
        d.line((px, py - 18, px - st, py + 10), fill=(20, 18, 20), width=5)
        d.line((px, py - 18, px + st, py + 10), fill=(20, 18, 20), width=5)
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    # nüfus grafiği
    d.rounded_rectangle((60, 60, 520, 230), 12, fill=(30, 26, 28))
    d.text((80, 72), "Kentte yaşayan nüfus (İngiltere)", font=F_SMALL, fill=PAPER)
    data = [("1750", 17), ("1801", 34), ("1851", 54), ("1901", 77)]
    for i, (yr, v) in enumerate(data):
        a = ease((t - 0.5 - i * 0.7) / 0.8)
        bx = 100 + i * 105
        bh = 100 * v / 80 * a
        d.rectangle((bx, 210 - bh, bx + 60, 210), fill=BRASS)
        d.text((bx + 30, 212), yr, font=font(16), fill=PAPER, anchor="mt")
        if a > 0.5:
            d.text((bx + 30, 206 - bh), f"%{v}", font=font(16, True), fill=PAPER, anchor="mb")


def draw_spread(img, t, dur):
    img.paste(PAPER_BG)
    d = ImageDraw.Draw(img)
    # yalınlaştırılmış dünya: yaklaşık konumlar (eşdikdörtgen projeksiyon)
    def P(lon, lat):
        return 640 + lon * 4.0, 390 - lat * 4.4
    for poly in [
        [(-130, 50), (-60, 55), (-55, 45), (-80, 25), (-100, 18), (-120, 32)],  # K. Amerika
        [(-80, 10), (-35, -5), (-40, -25), (-70, -50), (-75, -10)],             # G. Amerika
        [(-10, 36), (30, 38), (40, 60), (10, 62), (-8, 50)],                    # Avrupa
        [(-15, 30), (35, 30), (50, 10), (30, -35), (15, -30), (-15, 10)],       # Afrika
        [(40, 40), (140, 50), (140, 35), (100, 10), (75, 10), (50, 25)],        # Asya
        [(115, -20), (150, -20), (150, -38), (118, -34)],                       # Avustralya
    ]:
        d.polygon([P(*p) for p in poly], fill=(196, 180, 150), outline=(150, 132, 104))
    origin = P(-1, 52)
    targets = [("Belçika", P(4, 50.5), 0), ("Fransa", P(2, 46), 1), ("Almanya", P(11, 52), 2),
               ("ABD", P(-80, 40), 3), ("Japonya", P(138, 36), 4), ("Osmanlı", P(32, 40), 5)]
    label_pos = {"Belçika": (14, 12, "lt"), "Fransa": (-12, 10, "rt"), "Almanya": (14, -14, "lm"),
                 "ABD": (12, 10, "lt"), "Japonya": (-12, 12, "rt"), "Osmanlı": (14, 14, "lt")}
    seg = max(0.8, (dur - 2.5) / len(targets))
    for name, (tx, ty), i in targets:
        a = ease((t - 0.6 - i * seg) / (seg * 0.8))
        if a <= 0:
            continue
        ox, oy = origin
        mx, my = (ox + tx) / 2, min(oy, ty) - 60 - abs(tx - ox) * 0.15
        pts = []
        for s in range(31):
            u = s / 30 * a
            pts.append(((1 - u) ** 2 * ox + 2 * (1 - u) * u * mx + u * u * tx,
                        (1 - u) ** 2 * oy + 2 * (1 - u) * u * my + u * u * ty))
        col = (120, 110, 100) if name == "Osmanlı" else RUST
        d.line(pts, fill=col, width=4)
        if a >= 1:
            d.ellipse((tx - 8, ty - 8, tx + 8, ty + 8), fill=col)
            dx, dy, anc = label_pos[name]
            d.text((tx + dx, ty + dy), name, font=font(20, True), fill=INK, anchor=anc)
    ox, oy = origin
    r = 10 + 4 * math.sin(t * 4)
    d.ellipse((ox - r, oy - r, ox + r, oy + r), fill=BRASS, outline=INK, width=2)
    d.text((ox - 14, oy - 14), "İngiltere", font=font(20, True), fill=INK, anchor="rb")


def draw_legacy(img, t, dur):
    img.paste(NIGHT)
    d = ImageDraw.Draw(img)
    # zaman çizelgesi
    y = 330
    a = ease(t / 2)
    d.line((100, y, 100 + 1080 * a, y), fill=BRASS, width=6)
    events = [("1769", "Buhar\nmakinesi"), ("1825", "Demiryolu"), ("1879", "Ampul"),
              ("1886", "Otomobil"), ("1913", "Seri üretim"), ("Bugün", "Küresel\nekonomi")]
    for i, (yr, s) in enumerate(events):
        x = 140 + i * 200
        b = ease((t - 0.6 - i * 0.6) / 0.6)
        if b <= 0:
            continue
        r = 14 * b
        d.ellipse((x - r, y - r, x + r, y + r), fill=BRASS)
        d.text((x, y - 34), yr, font=F_BODY_B, fill=tuple(int(c * b) for c in PAPER), anchor="mb")
        d.multiline_text((x, y + 34), s, font=F_SMALL, fill=tuple(int(c * b) for c in (210, 196, 170)),
                         anchor="ma", align="center")
    gear(d, 640, 170, 50, 10, t * 0.8, BRASS)
    c = ease((t - (dur - 3.2)) / 1.2)
    if c > 0:
        text_center(d, (640, 560), "Modern dünyanın temeli", F_H1, tuple(int(cc * c) for cc in PAPER))


DRAW = {"title": draw_title, "before": draw_before, "why": draw_why, "steam": draw_steam,
        "factory": draw_factory, "rail": draw_rail, "city": draw_city, "spread": draw_spread,
        "legacy": draw_legacy}

# ---------------------------------------------------------------- altyazı ve kompozisyon


def wrap(text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def sentences(text):
    out, cur = [], ""
    for ch in text:
        cur += ch
        if ch in ".!?":
            out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def subtitle_at(sents, t, speech_dur):
    total = sum(len(s) for s in sents)
    acc = 0
    for s in sents:
        acc += len(s)
        if t <= speech_dur * acc / total:
            return s
    return None


def overlay(img, title, sub, t, dur, frame_idx, show_heading):
    d = ImageDraw.Draw(img, "RGBA")
    if show_heading:
        a = ease(t / 0.8) * ease((dur - t) / 0.5)
        if a > 0:
            tw = F_H1.getlength(title)
            x = W - 60 - tw
            d.rounded_rectangle((x - 24, H - 700 + 6, W - 36, H - 700 + 76), 10, fill=(18, 16, 20, int(200 * a)))
            d.text((x, H - 700 + 41), title, font=F_H1, fill=(*BRASS, int(255 * a)), anchor="lm")
    if sub:
        lines = wrap(sub, F_SUB, W - 220)
        lh = 38
        top = H - 40 - lh * len(lines)
        maxw = max(F_SUB.getlength(l) for l in lines)
        d.rounded_rectangle((W / 2 - maxw / 2 - 20, top - 12, W / 2 + maxw / 2 + 20, H - 30), 10,
                            fill=(0, 0, 0, 170))
        for i, l in enumerate(lines):
            d.text((W / 2, top + i * lh + lh / 2 - 2), l, font=F_SUB, fill=(250, 244, 230), anchor="mm")
    # film greni + vinyet
    img = Image.blend(img, GRAIN[frame_idx % 4], 0.06)
    black = Image.new("RGB", (W, H))
    img = Image.composite(img, black, VIGNETTE)
    # sahne geçişleri: kararma
    fade = min(ease(t / 0.45), ease((dur - t) / 0.45))
    if fade < 1:
        img = Image.blend(black, img, fade)
    return img


# ---------------------------------------------------------------- müzik


def make_music(path, dur, sr=22050):
    """Ağır tempolu, düşük sesli bir drone + fabrika ritmi."""
    t = np.arange(int(dur * sr)) / sr
    chords = [(110.0, 164.8, 220.0), (98.0, 146.8, 196.0), (87.3, 130.8, 174.6), (98.0, 146.8, 196.0)]
    sig = np.zeros_like(t)
    seg = 6.0
    for i, ch in enumerate(chords * int(dur // (seg * 4) + 2)):
        s0, s1 = i * seg, (i + 1) * seg + 1.0
        m = (t >= s0) & (t < s1)
        if not m.any():
            continue
        tt = t[m] - s0
        env = np.clip(tt / 1.5, 0, 1) * np.clip((s1 - s0 - tt) / 1.5, 0, 1)
        for f in ch:
            sig[m] += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) / 3
    # mekanik "tık-tık" ritmi
    beat = 60 / 84
    clicks = np.zeros_like(t)
    for k in range(int(dur / beat)):
        i0 = int(k * beat * sr)
        n = int(0.05 * sr)
        if i0 + n < len(t):
            clicks[i0:i0 + n] += np.random.default_rng(k).normal(0, 1, n) * np.exp(-np.arange(n) / (0.008 * sr)) * (
                0.6 if k % 2 else 1.0)
    out = 0.22 * sig + 0.08 * clicks
    fade = np.clip(t / 2, 0, 1) * np.clip((dur - t) / 3, 0, 1)
    out = (out * fade * 32767 * 0.5).clip(-32767, 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out.tobytes())


# ---------------------------------------------------------------- ana akış


def main():
    for tool in ("ffmpeg", "espeak-ng"):
        if not shutil.which(tool):
            sys.exit(f"{tool} bulunamadı")
    tmp = tempfile.mkdtemp(prefix="sanayi_")
    lead, tail = 0.8, 1.4
    plan = []
    for i, (key, title, text) in enumerate(SCENES):
        wav = os.path.join(tmp, f"n{i}.wav")
        tts(text, wav)
        sd = wav_duration(wav)
        plan.append((key, title, text, wav, sd, lead + sd + tail))
        print(f"[ses] {title}: {sd:.1f}s")
    total = sum(p[5] for p in plan)

    # anlatım parçalarını tek bir izde birleştir (sessizlik dolgulu)
    filt, inputs, offset = [], [], 0.0
    for i, p in enumerate(plan):
        inputs += ["-i", p[3]]
        ms = int((offset + lead) * 1000)
        filt.append(f"[{i}:a]aresample=22050,adelay={ms}|{ms}[a{i}]")
        offset += p[5]
    filt.append("".join(f"[a{i}]" for i in range(len(plan))) + f"amix=inputs={len(plan)}:normalize=0,"
                f"apad=whole_dur={total:.2f}[out]")
    narration = os.path.join(tmp, "narration.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-t", f"{total:.2f}", narration], check=True)
    music = os.path.join(tmp, "music.wav")
    make_music(music, total)

    video = os.path.join(tmp, "video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "20", "-pix_fmt", "yuv420p", video], stdin=subprocess.PIPE)
    fidx = 0
    for key, title, text, wav, sd, dur in plan:
        sents = sentences(text)
        nframes = int(round(dur * FPS))
        print(f"[görüntü] {title}: {nframes} kare")
        for f in range(nframes):
            t = f / FPS
            img = Image.new("RGB", (W, H))
            DRAW[key](img, t, dur)
            ts = t - lead
            sub = subtitle_at(sents, ts, sd) if 0 <= ts <= sd + 0.3 else None
            img = overlay(img, title, sub, t, dur, fidx, key != "title")
            enc.stdin.write(img.tobytes())
            fidx += 1
    enc.stdin.close()
    enc.wait()

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", narration, "-i", music,
                    "-filter_complex", "[1:a]volume=1.3[n];[2:a]volume=0.5[m];[n][m]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    OUT], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Tamamlandı: {OUT} ({total:.1f} sn)")


if __name__ == "__main__":
    main()
