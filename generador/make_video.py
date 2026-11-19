"""Genera un Reel vertical 1080x1920 de Dato Express.

Uso: python3 make_video.py guion.json salida_dir
Cada escena se renderiza a su propio mp4 y luego se concatenan.
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FONT_B = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
BG = (11, 11, 16)
YEL = (255, 212, 0)
WHITE = (255, 255, 255)
GREY = (175, 175, 190)

_font_cache = {}
def font(path, size):
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]

# ---------- easing ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_back(t):
    t = clamp(t); c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
def prog(t, start, dur): return clamp((t - start) / dur)

# ---------- texto ----------
def wrap(text, f, max_w):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            test = (cur + " " + w).strip()
            if f.getlength(test) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return lines

def text_img(text, path, size, color, max_w=900, hl=None, line_gap=1.12):
    """Imagen RGBA con el texto centrado. Las palabras entre *asteriscos* van en color hl."""
    f = font(path, size)
    plain = text.replace("*", "")
    lines = wrap(plain, f, max_w)
    # reconstruir qué palabras van resaltadas
    marked = set()
    inside = False
    for tok in text.replace("\n", " \n ").split(" "):
        if tok.startswith("*"): inside = True
        if inside and tok.strip("*") and tok != "\n": marked.add(tok.strip("*").strip(".,:;!?¿¡"))
        if tok.endswith("*") or tok.endswith("*.") or tok.endswith("*,") or tok.endswith("*?"): inside = False
    lh = int(size * line_gap)
    w = int(max(f.getlength(l) for l in lines)) + 20
    h = lh * len(lines) + int(size * 0.35)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = (w - f.getlength(l)) / 2
        for word in l.split(" "):
            c = hl if (hl and word.strip(".,:;!?¿¡") in marked) else color
            d.text((x, i * lh), word, font=f, fill=c)
            x += f.getlength(word + " ")
    return img

def place(canvas, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01: return
    if abs(scale - 1) > 0.005:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    if alpha < 0.999:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img = img.copy(); img.putalpha(a)
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))

# ---------- fondo ----------
def radial(size, color, strength):
    y, x = np.mgrid[0:size, 0:size]
    r = np.sqrt((x - size / 2) ** 2 + (y - size / 2) ** 2) / (size / 2)
    a = (clamp_arr(1 - r) ** 2) * strength
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")
def clamp_arr(a): return np.clip(a, 0, 1)

GLOW_Y = radial(1400, YEL, 0.22)
GLOW_O = radial(1200, (255, 90, 40), 0.16)
BASE = Image.new("RGBA", (W, H), BG + (255,))

def background(gt):
    c = BASE.copy()
    x1 = 540 + 380 * math.sin(gt * 0.35); y1 = 520 + 220 * math.cos(gt * 0.27)
    x2 = 540 + 420 * math.cos(gt * 0.31); y2 = 1450 + 200 * math.sin(gt * 0.23)
    c.alpha_composite(GLOW_Y, (int(x1 - 700), int(y1 - 700)))
    c.alpha_composite(GLOW_O, (int(x2 - 600), int(y2 - 600)))
    return c

def bolt(d, cx, cy, s, fill):
    pts = [(0.15, -1), (-0.55, 0.12), (-0.05, 0.12), (-0.2, 1), (0.55, -0.15), (0.05, -0.15), (0.3, -1)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=fill)

LOGO = None
def logo():
    global LOGO
    if LOGO is None:
        f = font(FONT_B, 46)
        w = int(f.getlength("DATO EXPRESS")) + 80
        img = Image.new("RGBA", (w, 80), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        bolt(d, 26, 40, 30, YEL)
        d.text((62, 8), "DATO", font=f, fill=WHITE)
        d.text((62 + f.getlength("DATO "), 8), "EXPRESS", font=f, fill=YEL)
        LOGO = img
    return LOGO

def chrome(c, gt, total, label=None):
    """Logo arriba, etiqueta de dato y barra de progreso."""
    c.alpha_composite(logo(), (int(W / 2 - logo().width / 2), 230))
    d = ImageDraw.Draw(c)
    if label:
        f = font(FONT_B, 40)
        tw = f.getlength(label)
        x0, y0 = W / 2 - tw / 2 - 34, 360
        d.rounded_rectangle((x0, y0, x0 + tw + 68, y0 + 74), radius=37, fill=YEL)
        d.text((x0 + 34, y0 + 10), label, font=f, fill=BG)
    # barra de progreso (fuera de la zona de UI de Instagram)
    y = 1575
    d.rounded_rectangle((140, y, W - 140, y + 10), radius=5, fill=(40, 40, 52))
    d.rounded_rectangle((140, y, 140 + (W - 280) * clamp(gt / total), y + 10), radius=5, fill=YEL)

def fmt_num(n):
    return f"{int(round(n)):,}".replace(",", ".")

# ---------- escenas ----------
def scene_hook(c, t, s, gt):
    d = ImageDraw.Draw(c)
    p = ease_back(prog(t, 0.0, 0.5))
    if s.get("art"):
        draw_art(c, t, s)
    else:
        bolt(d, W / 2, 590, 120 * p, YEL)
    img = s["_title"]
    place(c, img, W / 2, 1060, scale=0.6 + 0.4 * ease_back(prog(t, 0.25, 0.5)), alpha=ease_out(prog(t, 0.25, 0.3)))
    sub = s["_sub"]
    place(c, sub, W / 2, 1360 + 30 * (1 - ease_out(prog(t, 0.9, 0.4))), alpha=ease_out(prog(t, 0.9, 0.4)))

def scene_fact(c, t, s, gt):
    dur = s["dur"]
    draw_art(c, t, s)
    # número / contador grande
    if "count_from" in s:
        k = ease_out(prog(t, 0.4, s.get("count_dur", 1.6)))
        val = s["count_from"] + (s["count_to"] - s["count_from"]) * k
        num = fmt_num(val)
        f = font(FONT_B, s.get("num_size", 230))
        img = Image.new("RGBA", (int(f.getlength(num)) + 40, int(s.get("num_size", 230) * 1.3)), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((20, 0), num, font=f, fill=YEL)
        pulse = 1.0
        if s.get("pulse"):
            pulse = 1 + 0.06 * max(0, math.sin(t * 2 * math.pi * 1.2)) ** 8
        place(c, img, W / 2, 760, scale=ease_back(prog(t, 0.15, 0.45)) * pulse, alpha=ease_out(prog(t, 0.15, 0.25)))
        if s.get("num_caption"):
            place(c, s["_numcap"], W / 2, 920, alpha=ease_out(prog(t, 0.6, 0.4)))
    elif "_big" in s:
        place(c, s["_big"], W / 2, 760, scale=ease_back(prog(t, 0.15, 0.45)), alpha=ease_out(prog(t, 0.15, 0.25)))
    elif "timeline" in s:
        draw_timeline(c, t, s)
    elif "bars" in s:
        draw_bars(c, t, s)
    hy, by = s.get("head_y", 1110), s.get("body_y", 1350)
    ha, ba = s.get("head_at", 0.35), s.get("body_at", 1.8)
    place(c, s["_head"], W / 2, hy + 40 * (1 - ease_out(prog(t, ha, 0.45))), alpha=ease_out(prog(t, ha, 0.45)))
    place(c, s["_body"], W / 2, by + 40 * (1 - ease_out(prog(t, ba, 0.5))), alpha=ease_out(prog(t, ba, 0.5)))

_art_cache = {}
ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
def art_img(name, h):
    k = (name, h)
    if k not in _art_cache:
        im = Image.open(os.path.join(ART_DIR, name + ".png")).convert("RGBA")
        _art_cache[k] = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    return _art_cache[k]

def venus_img(t, r):
    """Planeta Venus dibujado: bandas de nubes que se desplazan lentamente."""
    size = 2 * r
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    dx, dy = (xx - r) / r, (yy - r) / r
    rr = np.sqrt(dx ** 2 + dy ** 2)
    inside = rr <= 1
    lon = np.arcsin(np.clip(dx / np.sqrt(np.clip(1 - dy ** 2, 1e-6, 1)), -1, 1)) + t * 0.35
    band = np.sin(dy * 9 + np.sin(lon * 3 + dy * 4) * 0.8) * 0.5 + 0.5
    base = np.array([226, 160, 70.0]); light = np.array([248, 214, 140.0])
    col = base * (1 - band[..., None]) + light * band[..., None]
    shade = np.clip(1.15 - 0.55 * np.sqrt(np.clip((dx + 0.45) ** 2 + (dy + 0.4) ** 2, 0, 4)), 0.35, 1.1)
    col = np.clip(col * shade[..., None], 0, 255)
    alpha = np.clip((1 - rr) * r, 0, 1) * 255
    arr = np.dstack([col, alpha]).astype(np.uint8)
    arr[~inside, 3] = 0
    return Image.fromarray(arr, "RGBA")

def draw_art(c, t, s):
    """Capas de ilustraciones: [{img, x, y, h, at, anim}] — anim: pop, float, spin, venus."""
    for a in s.get("art", []):
        k = ease_back(prog(t, a.get("at", 0.2), 0.55))
        if k <= 0.01: continue
        al = ease_out(prog(t, a.get("at", 0.2), 0.3))
        dy = 0
        if "float" in a.get("anim", ""):
            dy = math.sin((t - a.get("at", 0)) * 1.6 + a.get("x", 0) / 200) * 10
        if a["img"] == "venus":
            img = venus_img(t, a["h"] // 2)
        else:
            img = art_img(a["img"], a["h"])
        if "wobble" in a.get("anim", ""):
            img = img.rotate(math.sin(t * 3.2) * 4, resample=Image.BICUBIC, expand=True)
        place(c, img, a["x"], a["y"] + dy, scale=k, alpha=al)

def _label(text, path, size, color):
    f = font(path, size)
    img = Image.new("RGBA", (int(f.getlength(text)) + 20, int(size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10, 0), text, font=f, fill=color)
    return img

def draw_timeline(c, t, s):
    """Línea de tiempo: puntos [{x, name, year, at}] y tramos [{a, b, label, at}]."""
    tl = s["timeline"]; y = tl.get("y", 790)
    x0, x1 = 160, W - 160
    d = ImageDraw.Draw(c)
    lp = ease_out(prog(t, 0.2, 0.9))
    d.rounded_rectangle((x0, y - 5, x0 + (x1 - x0) * lp, y + 5), radius=5, fill=(70, 70, 88))
    pts = tl["points"]
    for p in pts:
        px = x0 + (x1 - x0) * p["x"]; k = ease_back(prog(t, p["at"], 0.45))
        if k <= 0: continue
        r = 22 * k
        d.ellipse((px - r, y - r, px + r, y + r), fill=p.get("color_rgb", YEL))
        d.ellipse((px - r * 0.45, y - r * 0.45, px + r * 0.45, y + r * 0.45), fill=BG)
        a = ease_out(prog(t, p["at"], 0.4))
        if tl.get("names_below"):
            place(c, _label(p["name"], FONT_B, 42, WHITE), px, y + 62, alpha=a)
            place(c, _label(p["year"], FONT_M, 36, GREY), px, y + 110, alpha=a)
        else:
            place(c, _label(p["name"], FONT_B, 46, WHITE), px, y - 85, alpha=a)
            place(c, _label(p["year"], FONT_M, 38, GREY), px, y + 62, alpha=a)
    for g in tl.get("gaps", []):
        a = ease_out(prog(t, g["at"], 0.5))
        if a <= 0: continue
        xa = x0 + (x1 - x0) * pts[g["a"]]["x"]; xb = x0 + (x1 - x0) * pts[g["b"]]["x"]
        gy = y + (185 if tl.get("names_below") else 135)
        col = YEL if g.get("hl") else (150, 150, 165)
        mid = (xa + xb) / 2; half = (xb - xa) / 2 * ease_out(prog(t, g["at"], 0.6)) - 28
        if half > 0:
            d.line((mid - half, gy, mid + half, gy), fill=col, width=4)
            d.line((mid - half, gy - 14, mid - half, gy + 14), fill=col, width=4)
            d.line((mid + half, gy - 14, mid + half, gy + 14), fill=col, width=4)
        place(c, _label(g["label"], FONT_B, 40, col), mid, gy + 46, alpha=a)

def draw_bars(c, t, s):
    """Barras comparativas: [{name, value, unit, at}] con escala común."""
    b = s["bars"]; items = b["items"]; vmax = max(i["value"] for i in items)
    d = ImageDraw.Draw(c)
    x0, maxw = 120, W - 240
    for n, it in enumerate(items):
        y = b.get("y", 640) + n * b.get("gap", 240)
        a = ease_out(prog(t, it["at"], 0.4))
        if a <= 0: continue
        place(c, _label(it["name"], FONT_B, 48, WHITE), x0 + _label(it["name"], FONT_B, 48, WHITE).width / 2 - 10, y, alpha=a)
        k = ease_out(prog(t, it["at"] + 0.2, 1.3))
        w = maxw * it["value"] / vmax * k
        col = YEL if it.get("hl") else (120, 120, 140)
        d.rounded_rectangle((x0, y + 50, x0 + max(w, 30), y + 120), radius=35, fill=col)
        val = f"{int(round(it['value'] * k))} {it['unit']}"
        lab = _label(val, FONT_B, 42, BG if it.get("hl") else WHITE)
        if w > lab.width + 40:
            place(c, lab, x0 + w - lab.width / 2 - 20, y + 88)

def scene_cta(c, t, s, gt):
    place(c, s["_title"], W / 2, 860, scale=0.7 + 0.3 * ease_back(prog(t, 0.0, 0.5)), alpha=ease_out(prog(t, 0, 0.3)))
    place(c, s["_sub"], W / 2, 1150, alpha=ease_out(prog(t, 0.5, 0.4)))
    d = ImageDraw.Draw(c)
    p = ease_back(prog(t, 0.9, 0.5))
    if p > 0:
        f = font(FONT_B, 54)
        txt = "SEGUIR"
        tw = f.getlength(txt); bw, bh = (tw + 140) * p, 110 * p
        d.rounded_rectangle((W / 2 - bw / 2, 1330 - bh / 2, W / 2 + bw / 2, 1330 + bh / 2), radius=int(55 * p), fill=YEL)
        if p > 0.9:
            d.text((W / 2 - tw / 2, 1330 - 38), txt, font=f, fill=BG)

def prepare(s):
    k = s["type"]
    if k == "hook":
        s["_title"] = text_img(s["title"], FONT_B, 104, WHITE, 940, YEL, 1.08)
        s["_sub"] = text_img(s["sub"], FONT_M, 52, GREY, 860)
    elif k == "fact":
        if s.get("big"):
            s["_big"] = text_img(s["big"], FONT_B, 210, YEL, 980)
        if s.get("num_caption"):
            s["_numcap"] = text_img(s["num_caption"], FONT_M, 48, GREY, 900)
        s["_head"] = text_img(s["head"], FONT_B, 76, WHITE, 920, YEL)
        s["_body"] = text_img(s["body"], FONT_M, 50, GREY, 880)
    elif k == "cta":
        s["_title"] = text_img(s["title"], FONT_B, 96, WHITE, 920, YEL)
        s["_sub"] = text_img(s["sub"], FONT_M, 56, GREY, 880, YEL)

RENDER = {"hook": scene_hook, "fact": scene_fact, "cta": scene_cta}

def render_frame(s, t, gt, total):
    c = background(gt)
    RENDER[s["type"]](c, t, s, gt)
    chrome(c, gt, total, s.get("label"))
    # fade de entrada corto
    fi = prog(t, 0, 0.18)
    if fi < 1:
        c = Image.blend(background(gt), c, fi)
    return c.convert("RGB")

def render_scene(s, start, total, out):
    n = int(round(s["dur"] * FPS))
    tmp = out[:-4] + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", "-r", str(FPS), tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        p.stdin.write(render_frame(s, t, start + t, total).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, out)
    else:
        raise SystemExit("ffmpeg falló en " + out)

# ---------- música ----------
def music(total, cuts, path, sr=44100):
    n = int(total * sr); t = np.arange(n) / sr
    out = np.zeros(n)
    bpm = 112; beat = 60 / bpm
    notes = [55.0, 55.0, 65.41, 49.0]  # A1, A1, C2, G1
    nb = int(total / beat) + 1
    for b in range(nb):
        st = int(b * beat * sr)
        # kick
        L = int(0.25 * sr); tt = np.arange(L) / sr
        kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
        seg = out[st:st + L]; seg += 0.55 * kick[:len(seg)]
        # hihat en contratiempo
        hs = int((b + 0.5) * beat * sr); L2 = int(0.05 * sr)
        hh = np.random.uniform(-1, 1, L2) * np.exp(-np.arange(L2) / sr * 80)
        seg = out[hs:hs + L2]; seg += 0.10 * hh[:len(seg)]
        # bajo
        f0 = notes[(b // 4) % 4]
        L3 = int(beat * sr); tt = np.arange(L3) / sr
        bass = np.sign(np.sin(2 * np.pi * f0 * tt)) * 0.5 + np.sin(2 * np.pi * f0 * 2 * tt) * 0.5
        bass *= np.exp(-tt * 3.5)
        seg = out[st:st + L3]; seg += 0.13 * bass[:len(seg)]
        # pad suave
        seg = out[st:st + L3]
        chord = sum(np.sin(2 * np.pi * f0 * m * tt) for m in (4, 5, 6)) / 3
        seg += (0.035 * chord * np.minimum(1, tt * 8))[:len(seg)]
    # whoosh en cada corte
    for ct in cuts:
        st = int(max(0, ct - 0.25) * sr); L = int(0.5 * sr)
        nz = np.random.uniform(-1, 1, L)
        env = np.sin(np.linspace(0, np.pi, L)) ** 2
        nz = np.convolve(nz, np.ones(12) / 12, mode="same")
        seg = out[st:st + L]; seg += 0.35 * (nz * env)[:len(seg)]
    # fade in/out
    fo = int(1.0 * sr); out[-fo:] *= np.linspace(1, 0, fo)
    fi = int(0.05 * sr); out[:fi] *= np.linspace(0, 1, fi)
    out = out / (np.abs(out).max() + 1e-9) * 0.85
    pcm = (out * 32767).astype(np.int16)
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

def mix_voice(spec, scenes, music_path, total, sr=44100):
    """Coloca cada línea de la narración al inicio de su escena y baja la música debajo de la voz.
    spec["voice"] = mp3 con todas las líneas; spec["voice_lines"] = [{start, dur}] (de vidIQ)."""
    import wave
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", spec["voice"], "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    voice = np.frombuffer(raw, np.int16).astype(np.float64) / 32768
    with wave.open(music_path) as w:
        mus = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
    n = int(total * sr)
    vtrack = np.zeros(n)
    start = 0.0
    for s, ln in zip(scenes, spec["voice_lines"]):
        a, b = int(ln["start"] * sr), int((ln["start"] + ln["dur"]) * sr)
        seg = voice[a:b]
        o = int((start + s.get("voice_delay", 0.15)) * sr)
        seg = seg[:max(0, n - o)]
        vtrack[o:o + len(seg)] += seg
        start += s["dur"]
    # ducking: envolvente suave de la voz
    env = np.abs(vtrack)
    k = int(0.3 * sr); env = np.convolve(env, np.ones(k) / k, mode="same")
    env = np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    mus_gain = 0.32 - 0.20 * env
    out = vtrack * 1.0 + mus[:n] * mus_gain
    out = out / (np.abs(out).max() + 1e-9) * 0.95
    with wave.open(music_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())

def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    outdir = sys.argv[2]; os.makedirs(outdir, exist_ok=True)
    scenes = spec["scenes"]
    for s in scenes: prepare(s)
    total = sum(s["dur"] for s in scenes)
    if len(sys.argv) > 3 and sys.argv[3] == "--preview":
        start = 0
        for i, s in enumerate(scenes):
            for frac in (0.5, 0.95):
                t = s["dur"] * frac
                render_frame(s, t, start + t, total).save(f"{outdir}/preview_{i}_{int(frac*100)}.jpg", quality=88)
            start += s["dur"]
        return
    start, files, cuts = 0, [], []
    for i, s in enumerate(scenes):
        out = f"{outdir}/scene_{i:02d}.mp4"
        render_scene(s, start, total, out)
        files.append(out); start += s["dur"]; cuts.append(start)
    with open(f"{outdir}/list.txt", "w") as f:
        for p in files: f.write(f"file '{os.path.abspath(p)}'\n")
    music(total, [0.0] + cuts[:-1], f"{outdir}/music.wav")
    if spec.get("voice"):
        mix_voice(spec, scenes, f"{outdir}/music.wav", total)
    final = spec.get("output", f"{outdir}/video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{outdir}/list.txt",
                    "-c", "copy", f"{outdir}/silent.mp4"], check=True)
    tmp = final[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{outdir}/silent.mp4", "-i", f"{outdir}/music.wav",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, final)
    print("OK", final, round(total, 2), "s")

if __name__ == "__main__":
    main()
