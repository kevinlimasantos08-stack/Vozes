#!/usr/bin/env python3
"""toon.py — estilo "toon com narrador" (cabeça redonda, muito movimento) para a conta de ficção.

Uso:
  python3 -I toon.py roteiro.json saida.mp4 [--audios PASTA] [--previas]
  --audios PASTA: arquivos com o número do bloco no nome (cena1.wav, 02.wav...)
Roteiro: {"serie","titulo","blocos":[{"texto","destaque","cena","emocao":{id:emo},"pausa","impacto"}],"final":{...}}
Cenas: estrada, ponto, interior, motorista, catraca, teo_close, corredor, espelho, retrato, banco
"""
import json, math, os, re, subprocess, sys, wave, random
import numpy as np
import cairo

W, H, FPS, SR = 1080, 1920, 30, 24000
LAR = (1.0, 0.55, 0.15)
TXT = (0.96, 0.96, 1.0)

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def eo(x): x = clamp(x); return 1 - (1 - x) ** 3
def eio(x): x = clamp(x); return x * x * (3 - 2 * x)
def eback(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def hx(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
def mix(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
def dark(c, f): return tuple(v * f for v in c)

def rrect(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2); c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0); c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi); c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi); c.close_path()

def ell(c, x, y, rx, ry):
    c.save(); c.translate(x, y); c.scale(rx, ry); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()

def fill_ol(c, cor, lw=6, ol=(0.07, 0.06, 0.08)):
    c.set_source_rgb(*cor); c.fill_preserve(); c.set_source_rgb(*ol); c.set_line_width(lw); c.stroke()

def fonte(c, tam, peso="Bold"):
    c.select_font_face("Poppins " + peso if peso not in ("Bold",) else "Poppins", cairo.FONT_SLANT_NORMAL,
                       cairo.FONT_WEIGHT_BOLD if peso == "Bold" else cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(tam)
def lw_(c, s): return c.text_extents(s).x_advance

# ------------------------------------------------------------------ personagens
PERS = {
    "teo": dict(pele=hx("#C08A5E"), cabelo=hx("#1A1410"), roupa=hx("#B0402F"), oculos=True, careca=False, bone=False, barba=None),
    "bento": dict(pele=hx("#7A4E33"), cabelo=hx("#2B2B2B"), roupa=hx("#2F4A6B"), oculos=False, careca=True, bone=True, barba=hx("#BFBFBF")),
    "mae": dict(pele=hx("#B9825A"), cabelo=hx("#2A1A12"), roupa=hx("#7A5C9E"), oculos=False, careca=False, bone=False, barba=None, longo=True),
    "antigo": dict(pele=hx("#D9B48F"), cabelo=hx("#3A2A1E"), roupa=hx("#4A4A3A"), oculos=False, careca=False, bone=True, barba=None, bigode=True),
}

def toon(c, x, y, s, who, emo, t, look=0.0, sepia=False):
    """Desenha o personagem com o centro da cabeça em (x, y). s = escala (cabeça ~ 170*s de raio)."""
    p = dict(PERS[who])
    if sepia:
        for k in ("pele", "cabelo", "roupa", "barba"):
            if p.get(k): v = sum(p[k]) / 3; p[k] = (v * 1.05 + 0.08, v * 0.9 + 0.05, v * 0.7)
    ph = sum(map(ord, who)) * 0.37
    resp = math.sin(t * 2.2 + ph)
    trem = (math.sin(t * 41) * 3 + math.sin(t * 57) * 2) * s if emo in ("medo", "pavor") else 0
    y += resp * 6 * s
    x += trem
    tilt = math.sin(t * 0.9 + ph) * 0.05 + look * 0.06
    c.save(); c.translate(x, y)
    # corpo
    c.save(); c.translate(0, 230 * s); c.scale(1, 1 + resp * 0.012)
    rrect(c, -150 * s, -40 * s, 300 * s, 360 * s, 120 * s); fill_ol(c, p["roupa"], 7 * s)
    if who == "teo":  # capuz e cordões
        c.set_source_rgb(*dark(p["roupa"], 0.8)); rrect(c, -110 * s, -50 * s, 220 * s, 60 * s, 30 * s); c.fill()
        c.set_source_rgb(0.95, 0.92, 0.85); c.set_line_width(6 * s)
        for dx in (-30, 30): c.move_to(dx * s, 0); c.line_to(dx * s, 70 * s); c.stroke()
    else:  # gola e crachá
        c.set_source_rgb(0.92, 0.9, 0.82); c.move_to(-50 * s, -36 * s); c.line_to(0, 20 * s); c.line_to(50 * s, -36 * s); c.close_path(); c.fill()
        c.set_source_rgb(*LAR) if not sepia else c.set_source_rgb(0.8, 0.7, 0.5)
        rrect(c, 50 * s, 40 * s, 50 * s, 34 * s, 6 * s); c.fill()
    c.restore()
    # cabeça
    c.save(); c.rotate(tilt)
    R = 170 * s
    if p.get("longo"):  # cabelo comprido atrás da cabeça
        rrect(c, -R * 1.12, -R * 0.9, R * 2.24, R * 2.3, R * 0.9); fill_ol(c, p["cabelo"], 6 * s)
    if p.get("barba"):
        ell(c, 0, 60 * s, 150 * s, 130 * s); fill_ol(c, p["barba"], 6 * s)
    ell(c, -R * 0.98, 10 * s, 30 * s, 40 * s); fill_ol(c, p["pele"], 6 * s)
    ell(c, R * 0.98, 10 * s, 30 * s, 40 * s); fill_ol(c, p["pele"], 6 * s)
    c.arc(0, 0, R, 0, 2 * math.pi); fill_ol(c, p["pele"], 7 * s)
    if p.get("barba"):
        c.save(); c.arc(0, 0, R - 4 * s, 0.15 * math.pi, 0.85 * math.pi); c.close_path(); c.set_source_rgb(*p["barba"]); c.fill(); c.restore()
        ell(c, 0, 95 * s, 55 * s, 30 * s); c.set_source_rgb(*p["pele"]); c.fill()
    # bochecha
    c.set_source_rgba(0.85, 0.35, 0.3, 0.25)
    for sx in (-1, 1): ell(c, sx * 95 * s, 50 * s, 30 * s, 18 * s); c.fill()
    # cabelo / boné
    if not p["careca"] and not p["bone"]:
        c.save(); c.arc(0, 0, R, math.pi * 1.05, math.pi * 1.95); c.line_to(R * 0.6, -R * 0.45); c.curve_to(R * 0.2, -R * 0.7, -R * 0.3, -R * 0.55, -R * 0.95, -R * 0.2)
        c.close_path(); fill_ol(c, p["cabelo"], 6 * s); c.restore()
        c.set_source_rgb(*p["cabelo"]); c.move_to(-20 * s, -R * 0.95); c.curve_to(10 * s, -R * 1.25, 50 * s, -R * 1.1, 40 * s, -R * 0.9); c.fill()
    if p["bone"]:
        c.save(); c.arc(0, -10 * s, R * 1.02, math.pi * 1.08, math.pi * 1.92); c.close_path()
        cor = hx("#1E2B44") if not sepia else (0.35, 0.28, 0.2); fill_ol(c, cor, 6 * s)
        c.set_source_rgb(*(hx("#E8B23A") if not sepia else (0.7, 0.6, 0.4))); c.rectangle(-R * 0.92, -R * 0.42, R * 1.84, 22 * s); c.fill()
        rrect(c, -R * 0.2, -R * 0.62, R * 0.4, R * 0.18, 8 * s); c.fill()
        c.move_to(-R * 0.95, -R * 0.32); c.curve_to(-R * 0.4, -R * 0.15, R * 0.4, -R * 0.15, R * 1.05, -R * 0.32)
        c.line_to(R * 1.0, -R * 0.42); c.line_to(-R * 0.95, -R * 0.42); c.close_path(); fill_ol(c, dark(cor, 0.7), 5 * s); c.restore()
    # olhos
    pisca = ((t + ph) % 3.4) < 0.11
    big = {"pavor": 1.35, "medo": 1.15}.get(emo, 1.0)
    pup = {"pavor": 0.45, "medo": 0.65}.get(emo, 1.0)
    for sx in (-1, 1):
        ex, ey = sx * 62 * s, -5 * s
        if pisca:
            c.set_source_rgb(0.07, 0.06, 0.08); c.set_line_width(8 * s); c.move_to(ex - 30 * s, ey); c.line_to(ex + 30 * s, ey); c.stroke()
        else:
            ell(c, ex, ey, 40 * s * big, 48 * s * big); fill_ol(c, (0.98, 0.98, 0.96), 6 * s)
            jit = math.sin(t * 23 + sx) * 3 * s if emo == "pavor" else 0
            ell(c, ex + look * 14 * s + jit, ey + 4 * s, 20 * s * pup, 24 * s * pup); c.set_source_rgb(0.08, 0.07, 0.09); c.fill()
            c.arc(ex + look * 14 * s - 6 * s, ey - 6 * s, 6 * s, 0, 2 * math.pi); c.set_source_rgb(1, 1, 1); c.fill()
        # sobrancelha
        c.set_source_rgb(*(p["cabelo"] if not p["careca"] else (0.25, 0.22, 0.22))); c.set_line_width(12 * s); c.set_line_cap(cairo.LINE_CAP_ROUND)
        yb = ey - 70 * s * big
        if emo in ("medo", "pavor"):
            c.move_to(ex - sx * 35 * s, yb - 8 * s); c.line_to(ex + sx * 30 * s, yb + 10 * s)
            c.move_to(ex - sx * 35 * s, yb - 8 * s); c.line_to(ex - sx * 35 * s, yb - 8 * s)
            c.new_path(); c.move_to(ex + sx * 32 * s, yb + 8 * s); c.line_to(ex - sx * 30 * s, yb - 12 * s)
        elif emo == "serio":
            c.move_to(ex + sx * 32 * s, yb + 2 * s); c.line_to(ex - sx * 30 * s, yb + 16 * s)
        else:
            c.move_to(ex - 30 * s, yb); c.curve_to(ex - 10 * s, yb - 10 * s, ex + 10 * s, yb - 10 * s, ex + 30 * s, yb)
        c.stroke()
    if p["oculos"]:
        c.set_source_rgb(0.1, 0.09, 0.1); c.set_line_width(8 * s)
        for sx in (-1, 1): rrect(c, sx * 62 * s - 54 * s, -60 * s, 108 * s, 100 * s, 30 * s); c.stroke()
        c.move_to(-8 * s, -15 * s); c.line_to(8 * s, -15 * s); c.stroke()
    if p.get("bigode"):
        c.set_source_rgb(*p["cabelo"]); ell(c, -28 * s, 62 * s, 34 * s, 12 * s); c.fill(); ell(c, 28 * s, 62 * s, 34 * s, 12 * s); c.fill()
    # boca
    c.set_source_rgb(0.07, 0.06, 0.08); c.set_line_width(8 * s)
    if emo == "pavor":
        ell(c, 0, 92 * s, 22 * s, 30 * s + math.sin(t * 30) * 3 * s); c.set_source_rgb(0.3, 0.08, 0.1); c.fill()
    elif emo == "medo":
        c.move_to(-30 * s, 95 * s)
        for i in range(1, 7): c.line_to(-30 * s + i * 10 * s, 95 * s + (5 * s if i % 2 else -5 * s))
        c.stroke()
    elif emo == "serio":
        c.move_to(-30 * s, 92 * s); c.line_to(30 * s, 92 * s); c.stroke()
    else:
        c.arc(0, 70 * s, 34 * s, 0.25 * math.pi, 0.75 * math.pi); c.stroke()
    if emo in ("medo", "pavor"):  # gota de suor
        gy = -40 * s + ((t * 30) % 60) * s
        c.move_to(R * 0.75, gy - 20 * s); c.curve_to(R * 0.85, gy, R * 0.85, gy + 18 * s, R * 0.75, gy + 18 * s)
        c.curve_to(R * 0.65, gy + 18 * s, R * 0.65, gy, R * 0.75, gy - 20 * s); c.set_source_rgba(0.6, 0.85, 1, 0.9); c.fill()
    c.restore(); c.restore()

# ------------------------------------------------------------------ ônibus e cenários
def ceu(c, top=(0.03, 0.04, 0.12), bot=(0.12, 0.08, 0.2), t=0):
    g = cairo.LinearGradient(0, 0, 0, H); g.add_color_stop_rgb(0, *top); g.add_color_stop_rgb(1, *bot); c.set_source(g); c.paint()
    rnd = random.Random(5)
    for i in range(90):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H * 0.5), rnd.uniform(1, 3)
        c.set_source_rgba(1, 1, 1, 0.3 + 0.5 * abs(math.sin(t * rnd.uniform(0.5, 2) + i))); c.arc(x, y, r, 0, 2 * math.pi); c.fill()

def lua(c, x, y, r):
    g = cairo.RadialGradient(x, y, r * 0.5, x, y, r * 3); g.add_color_stop_rgba(0, 1, 0.95, 0.8, 0.25); g.add_color_stop_rgba(1, 1, 1, 1, 0)
    c.set_source(g); c.arc(x, y, r * 3, 0, 2 * math.pi); c.fill()
    c.set_source_rgb(0.98, 0.95, 0.85); c.arc(x, y, r, 0, 2 * math.pi); c.fill()
    c.set_source_rgba(0.8, 0.78, 0.7, 0.6); c.arc(x - r * 0.3, y + r * 0.2, r * 0.18, 0, 2 * math.pi); c.fill()

def predios(c, base, off, cor, alt, seed, janelas=True):
    rnd = random.Random(seed); x = -((off % 2000))
    while x < W + 400:
        w = rnd.randint(120, 260); h = rnd.randint(int(alt * 0.5), alt)
        c.set_source_rgb(*cor); c.rectangle(x, base - h, w, h); c.fill()
        if janelas:
            for wy in range(int(base - h + 30), int(base - 30), 60):
                for wx in range(int(x + 20), int(x + w - 30), 50):
                    if rnd.random() < 0.25:
                        c.set_source_rgba(1, 0.8, 0.45, 0.55); c.rectangle(wx, wy, 22, 30); c.fill()
        x += w + rnd.randint(0, 30)

def onibus_lado(c, x, y, s, t, porta=0.0, roda=0.0):
    """Ônibus de lado (frente para a direita). (x,y) = canto inferior esquerdo."""
    c.save(); c.translate(x, y); c.scale(s, s)
    bounce = math.sin(t * 9) * 2
    c.translate(0, bounce)
    rrect(c, 0, -420, 1300, 380, 60); fill_ol(c, hx("#E8B23A"), 8)
    c.set_source_rgb(*hx("#C9541F")); c.rectangle(4, -150, 1292, 40); c.fill()
    for i in range(7):  # janelas acesas
        wx = 60 + i * 160
        if i == 6: continue
        rrect(c, wx, -380, 130, 150, 18); fill_ol(c, (1.0, 0.85, 0.5), 6)
        c.set_source_rgba(0.1, 0.08, 0.1, 0.55); ell(c, wx + 65, -270, 30, 34); c.fill()  # silhueta
    rrect(c, 1140, -380, 130, 150, 30); fill_ol(c, hx("#9FD3F0"), 6)  # para-brisa
    # porta
    c.set_source_rgb(0.1, 0.1, 0.12); c.rectangle(1010, -380, 110, 330); c.fill()
    c.set_source_rgb(*hx("#E8B23A")); c.rectangle(1010 + 55 * porta, -380, 55 * (1 - porta), 330); c.rectangle(1065 + 55 * porta, -380, 55 * (1 - porta), 330); c.fill()
    # letreiro
    rrect(c, 30, -470, 330, 60, 12); fill_ol(c, (0.08, 0.08, 0.08), 6)
    fonte(c, 44); c.set_source_rgb(1, 0.6, 0.15); c.move_to(55, -425); c.show_text("12  CENTRO")
    for rx in (260, 1060):  # rodas
        c.arc(rx, -40, 75, 0, 2 * math.pi); fill_ol(c, (0.12, 0.12, 0.13), 8)
        c.arc(rx, -40, 35, 0, 2 * math.pi); c.set_source_rgb(0.6, 0.6, 0.62); c.fill()
        c.set_source_rgb(0.3, 0.3, 0.32); c.set_line_width(6)
        for k in range(5):
            a = roda + k * 2 * math.pi / 5; c.move_to(rx, -40); c.line_to(rx + 34 * math.cos(a), -40 + 34 * math.sin(a)); c.stroke()
    # farol
    g = cairo.RadialGradient(1300, -120, 5, 1300, -120, 500); g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.6); g.add_color_stop_rgba(1, 1, 0.95, 0.7, 0)
    c.set_source(g); c.move_to(1290, -130); c.line_to(1800, -300); c.line_to(1800, 60); c.close_path(); c.fill()
    c.restore()

def neblina(c, t, y0, alpha=0.18):
    for i in range(5):
        x = ((t * 40 * (1 + i * 0.3) + i * 380) % (W + 800)) - 400
        g = cairo.RadialGradient(x, y0 + i * 40, 10, x, y0 + i * 40, 420); g.add_color_stop_rgba(0, 0.7, 0.75, 0.9, alpha); g.add_color_stop_rgba(1, 0.7, 0.75, 0.9, 0)
        c.set_source(g); c.paint()

def cena_estrada(c, lt, T, t, emo):
    ceu(c, t=t); lua(c, 820, 330, 70)
    predios(c, 1250, t * 30, (0.07, 0.07, 0.14), 650, 1)
    predios(c, 1320, t * 90, (0.04, 0.04, 0.08), 420, 2)
    c.set_source_rgb(0.08, 0.08, 0.1); c.rectangle(0, 1320, W, H); c.fill()
    c.set_source_rgb(0.95, 0.85, 0.4)
    for i in range(8):
        x = (i * 300 - (t * 700) % 300) - 100; c.rectangle(x, 1560, 150, 14); c.fill()
    # postes rápidos
    for i in range(3):
        x = (i * 700 - (t * 900) % 700) + 200
        c.set_source_rgb(0.05, 0.05, 0.06); c.rectangle(x, 700, 16, 640); c.fill()
        g = cairo.RadialGradient(x, 700, 5, x, 700, 160); g.add_color_stop_rgba(0, 1, 0.85, 0.5, 0.7); g.add_color_stop_rgba(1, 1, 0.85, 0.5, 0)
        c.set_source(g); c.arc(x, 700, 160, 0, 2 * math.pi); c.fill()
    onibus_lado(c, 90 + math.sin(t * 0.7) * 20, 1500, 0.62, t, roda=t * 14)
    neblina(c, t, 1250, 0.12)

def cena_ponto(c, lt, T, t, emo):
    ceu(c, (0.02, 0.03, 0.08), (0.08, 0.06, 0.14), t)
    predios(c, 1350, 300, (0.05, 0.05, 0.1), 800, 4)
    c.set_source_rgb(0.12, 0.12, 0.14); c.rectangle(0, 1350, W, H); c.fill()
    c.set_source_rgb(0.18, 0.18, 0.2); c.rectangle(0, 1350, W, 60); c.fill()
    flick = 0.4 if (int(t * 7) % 9 == 0) else 1.0
    lx = 260
    c.set_source_rgb(0.05, 0.05, 0.06); c.rectangle(lx, 520, 18, 840); c.fill()
    g = cairo.LinearGradient(0, 540, 0, 1400); g.add_color_stop_rgba(0, 1, 0.85, 0.5, 0.35 * flick); g.add_color_stop_rgba(1, 1, 0.85, 0.5, 0)
    c.set_source(g); c.move_to(lx - 20, 540); c.line_to(lx - 260, 1400); c.line_to(lx + 300, 1400); c.line_to(lx + 40, 540); c.close_path(); c.fill()
    c.set_source_rgb(1, 0.9, 0.6); ell(c, lx + 9, 535, 40, 18); c.fill()
    # placa 12
    px = 640
    c.set_source_rgb(0.3, 0.32, 0.36); c.rectangle(px, 760, 14, 600); c.fill()
    c.arc(px + 7, 740, 90, 0, 2 * math.pi); fill_ol(c, hx("#E8B23A"), 8)
    fonte(c, 100); c.set_source_rgb(0.1, 0.1, 0.1); s = "12"; c.move_to(px + 7 - lw_(c, s) / 2, 776); c.show_text(s)
    # banco vazio
    rrect(c, 520, 1210, 360, 34, 10); fill_ol(c, (0.35, 0.25, 0.18), 6)
    for bx in (550, 840): c.set_source_rgb(0.2, 0.2, 0.22); c.rectangle(bx, 1244, 14, 110); c.fill()
    # folhas voando
    rnd = random.Random(9)
    for i in range(8):
        x = (rnd.uniform(0, W) - t * 160 * rnd.uniform(0.6, 1.4)) % (W + 100) - 50
        y = rnd.uniform(1100, 1500) + math.sin(t * 3 + i) * 30
        c.save(); c.translate(x, y); c.rotate(t * 3 + i); c.set_source_rgba(0.6, 0.4, 0.2, 0.8); ell(c, 0, 0, 14, 7); c.fill(); c.restore()
    # ônibus chegando pela direita
    if emo.get("sem_onibus"):
        neblina(c, t, 1300, 0.2); return
    chega = eo(lt / max(0.6, T * 0.5))
    onibus_lado(c, W + 50 - chega * 700, 1480, 0.7, t * (1 - chega), porta=eio((lt - T * 0.55) / 0.8), roda=t * 14 * (1 - chega))
    neblina(c, t, 1300, 0.2)

def interior_fundo(c, t, sway=True):
    c.set_source_rgb(0.1, 0.1, 0.14); c.paint()
    vx, vy = W / 2, 820
    # teto e chão
    c.set_source_rgb(0.16, 0.16, 0.2); c.move_to(0, 0); c.line_to(W, 0); c.line_to(vx + 140, vy - 120); c.line_to(vx - 140, vy - 120); c.close_path(); c.fill()
    c.set_source_rgb(0.2, 0.17, 0.15); c.move_to(0, H); c.line_to(W, H); c.line_to(vx + 140, vy + 140); c.line_to(vx - 140, vy + 140); c.close_path(); c.fill()
    # janelas laterais com luzes passando
    for lado in (-1, 1):
        x0 = vx + lado * 140; x1 = W / 2 + lado * W / 2
        c.set_source_rgb(0.03, 0.04, 0.09)
        c.move_to(x0, vy - 90); c.line_to(x1, 250); c.line_to(x1, 900); c.line_to(x0, vy + 20); c.close_path(); c.fill()
        for i in range(5):
            k = ((t * 0.9 + i / 5) % 1)
            px = x0 + (x1 - x0) * k ** 1.6; py = (vy - 30) + (560 - (vy - 30)) * k ** 1.6
            r = 6 + 70 * k ** 1.6
            g = cairo.RadialGradient(px, py, 1, px, py, r); g.add_color_stop_rgba(0, 1, 0.8, 0.45, 0.8); g.add_color_stop_rgba(1, 1, 0.8, 0.45, 0)
            c.set_source(g); c.arc(px, py, r, 0, 2 * math.pi); c.fill()
    # luzes do teto piscando
    for i in range(5):
        k = i / 5; y = vy - 120 - (vy - 120) * (1 - k) ** 1.5
        fl = 0.3 if (int(t * 6 + i * 3) % 11 == 0) else 1
        wv = 40 + 300 * (1 - k) ** 1.5
        c.set_source_rgba(0.95, 0.95, 0.85, 0.85 * fl); rrect(c, vx - wv / 2, y, wv, 10 + 30 * (1 - k), 8); c.fill()
    # bancos em perspectiva
    for i in range(6):
        k = i / 6; e = 0.15 + 0.85 * (1 - k) ** 1.4
        yy = vy + 60 + (H - vy) * 0.75 * (1 - k) ** 1.4
        for lado in (-1, 1):
            xc = vx + lado * (90 + 520 * e)
            rrect(c, xc - 200 * e, yy - 300 * e, 400 * e, 300 * e, 40 * e); fill_ol(c, hx("#2E5E8C"), 5 * e)
            c.set_source_rgb(*hx("#3E76AA")); rrect(c, xc - 180 * e, yy - 280 * e, 360 * e, 60 * e, 20 * e); c.fill()
    # barras
    c.set_source_rgb(0.75, 0.75, 0.8); c.set_line_width(10)
    for lado in (-1, 1): c.move_to(vx + lado * 200, 0); c.line_to(vx + lado * 160, vy - 60); c.stroke()

def cena_interior(c, lt, T, t, emo):
    interior_fundo(c, t)
    e = emo.get("teo", "neutro")
    toon(c, 330, 1250, 0.95, "teo", e, t, look=0.6 if e == "neutro" else -0.3)
    # encosto da frente cobre o corpo
    rrect(c, 40, 1480, 620, 520, 60); fill_ol(c, hx("#2E5E8C"), 8)
    c.set_source_rgb(*hx("#3E76AA")); rrect(c, 70, 1500, 560, 90, 30); c.fill()

def cena_motorista(c, lt, T, t, emo):
    c.set_source_rgb(0.02, 0.02, 0.05); c.paint()
    # para-brisa com estrada vindo
    c.save(); rrect(c, 60, 180, W - 120, 820, 60); c.clip()
    g = cairo.LinearGradient(0, 180, 0, 1000); g.add_color_stop_rgb(0, 0.03, 0.04, 0.12); g.add_color_stop_rgb(1, 0.1, 0.07, 0.15); c.set_source(g); c.paint()
    c.set_source_rgb(0.08, 0.08, 0.1); c.move_to(W / 2 - 40, 620); c.line_to(W / 2 + 40, 620); c.line_to(W + 200, 1000); c.line_to(-200, 1000); c.close_path(); c.fill()
    for i in range(6):
        k = ((t * 1.2 + i / 6) % 1) ** 2
        y = 620 + 380 * k; wv = 4 + 30 * k; hgt = 6 + 60 * k
        c.set_source_rgb(0.95, 0.85, 0.4); c.rectangle(W / 2 - wv / 2, y, wv, hgt); c.fill()
    neblina(c, t, 600, 0.1)
    c.restore()
    c.set_source_rgb(0.12, 0.12, 0.14); c.set_line_width(14); rrect(c, 60, 180, W - 120, 820, 60); c.stroke()
    if emo.get("vazio"):
        rrect(c, 330, 1000, 460, 560, 80); fill_ol(c, (0.16, 0.16, 0.2), 8)
        c.set_source_rgba(0.75, 0.88, 1, 0.08 + 0.05 * math.sin(t * 9)); rrect(c, 360, 1030, 400, 500, 70); c.fill()
    else:
        quem = emo.get("quem", "bento")
        toon(c, 560, 1150, 1.0, quem, emo.get(quem, "neutro"), t, look=0.2 + (math.sin(t * 7) * 0.4 if emo.get("gira") else 0))
    # painel e volante
    c.set_source_rgb(0.08, 0.08, 0.1); c.rectangle(0, 1500, W, H); c.fill()
    g = cairo.LinearGradient(0, 1500, 0, 1560); g.add_color_stop_rgba(0, 0.3, 0.6, 1, 0.5); g.add_color_stop_rgba(1, 0.3, 0.6, 1, 0); c.set_source(g); c.rectangle(0, 1500, W, 60); c.fill()
    c.save(); c.translate(560, 1560); c.rotate(math.sin(t * 0.8) * 0.12 + (math.sin(lt * 1.7) * 0.55 if emo.get("gira") else 0))
    c.set_line_width(36); c.set_source_rgb(0.05, 0.05, 0.06); c.arc(0, 0, 230, math.pi * 1.05, math.pi * 1.95); c.stroke()
    c.set_line_width(26); c.move_to(-200, -100); c.line_to(0, 0); c.line_to(200, -100); c.stroke()
    c.restore()

def cena_catraca(c, lt, T, t, emo):
    g = cairo.RadialGradient(W / 2, 800, 50, W / 2, 800, 1100); g.add_color_stop_rgb(0, 0.14, 0.16, 0.24); g.add_color_stop_rgb(1, 0.02, 0.02, 0.05); c.set_source(g); c.paint()
    # corpo
    rrect(c, 300, 820, 480, 900, 40); fill_ol(c, (0.55, 0.57, 0.62), 8)
    c.set_source_rgb(0.42, 0.44, 0.5); rrect(c, 330, 860, 420, 120, 20); c.fill()
    gira = eio((lt - T * 0.45) / 0.7) if not emo.get("fixo") else 0.0
    num = emo["fixo"] if emo.get("fixo") else ("06" if gira > 0.6 else "07") if emo.get("reverso") else ("07" if gira > 0.6 else "06")
    c.set_source_rgb(0.05, 0.05, 0.05); rrect(c, 420, 880, 240, 80, 10); c.fill()
    fonte(c, 64); c.set_source_rgb(1, 0.25, 0.2) if gira > 0.6 else c.set_source_rgb(0.9, 0.2, 0.15)
    if emo.get("fixo"): c.set_source_rgb(1, 0.25 + 0.15 * math.sin(t * 6), 0.2)
    c.move_to(540 - lw_(c, num) / 2, 942); c.show_text(num)
    # braços (vista 3/4): elipse de rotação
    cx, cy = 540, 1150
    ang = gira * 2 * math.pi / 3 + 0.3
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for k in range(3):
        a = ang + k * 2 * math.pi / 3
        ex = cx + math.cos(a) * 380; ey = cy + math.sin(a) * 130
        prof = (math.sin(a) + 1) / 2
        c.set_source_rgb(*mix((0.45, 0.47, 0.52), (0.85, 0.87, 0.92), prof)); c.set_line_width(34 + 12 * prof)
        c.move_to(cx, cy); c.line_to(ex, ey); c.stroke()
    c.arc(cx, cy, 50, 0, 2 * math.pi); fill_ol(c, (0.7, 0.72, 0.78), 6)
    # brilho frio e poeira
    rnd = random.Random(3)
    for i in range(30):
        x = rnd.uniform(0, W); y = (rnd.uniform(0, H) - t * 20 * rnd.uniform(0.5, 1.5)) % H
        c.set_source_rgba(0.8, 0.9, 1, 0.25); c.arc(x, y, rnd.uniform(1.5, 4), 0, 2 * math.pi); c.fill()
    if 0.05 < gira < 0.95:
        c.set_source_rgba(0.7, 0.85, 1, 0.12 * math.sin(gira * math.pi)); c.paint()

def cena_teo_close(c, lt, T, t, emo):
    g = cairo.LinearGradient(0, 0, 0, H); g.add_color_stop_rgb(0, 0.06, 0.07, 0.12); g.add_color_stop_rgb(1, 0.02, 0.02, 0.04); c.set_source(g); c.paint()
    for i in range(7):  # bokeh passando
        k = ((t * 0.5 + i / 7) % 1); x = W * 1.2 - k * W * 1.5; y = 300 + (i * 173) % 900
        g = cairo.RadialGradient(x, y, 1, x, y, 120); g.add_color_stop_rgba(0, 1, 0.75, 0.4, 0.35); g.add_color_stop_rgba(1, 1, 0.75, 0.4, 0)
        c.set_source(g); c.arc(x, y, 120, 0, 2 * math.pi); c.fill()
    e = emo.get("teo", "medo")
    toon(c, W / 2, 900, 1.9, "teo", e, t, look=-0.4 if e == "medo" else 0)
    if e == "pavor":
        c.set_source_rgba(1, 0.45, 0.1, 0.10 + 0.06 * math.sin(t * 8)); c.paint()

def cena_corredor(c, lt, T, t, emo):
    interior_fundo(c, t)
    vx, vy = W / 2, 820
    rnd = random.Random(12)
    for i in range(6):  # 6 cabeças de passageiros
        k = (i // 2) / 4 + 0.15; e = 0.15 + 0.85 * (1 - k) ** 1.4
        lado = -1 if i % 2 else 1; yy = vy + 60 + (H - vy) * 0.75 * (1 - k) ** 1.4
        xc = vx + lado * (90 + 520 * e)
        c.set_source_rgba(0.04, 0.04, 0.06, 0.95); c.arc(xc, yy - 360 * e, 85 * e, 0, 2 * math.pi); c.fill()
    # o sétimo: aparece tremulando no fundo do corredor
    ap = eo((lt - 0.4) / 1.2)
    fl = 0.6 + 0.4 * math.sin(t * 17) * math.sin(t * 5)
    a = 0.55 * ap * fl
    g = cairo.RadialGradient(vx, vy + 20, 5, vx, vy + 20, 160); g.add_color_stop_rgba(0, 0.7, 0.85, 1, a * 0.6); g.add_color_stop_rgba(1, 0.7, 0.85, 1, 0)
    c.set_source(g); c.arc(vx, vy + 20, 160, 0, 2 * math.pi); c.fill()
    c.set_source_rgba(0.75, 0.88, 1, a); c.arc(vx, vy - 40, 34, 0, 2 * math.pi); c.fill()
    rrect(c, vx - 40, vy - 5, 80, 120, 30); c.fill()
    c.set_source_rgba(0.75, 0.88, 1, a); c.rectangle(vx - 46, vy - 78, 92, 14); c.fill()  # aba do boné

def cena_espelho(c, lt, T, t, emo):
    c.set_source_rgb(0.02, 0.02, 0.05); c.paint()
    neblina(c, t, 1300, 0.08)
    c.save(); c.translate(W / 2, 760); c.rotate(-0.04 + math.sin(t * 0.7) * 0.01)
    rrect(c, -470, -230, 940, 460, 120); fill_ol(c, (0.15, 0.15, 0.17), 14)
    rrect(c, -440, -200, 880, 400, 100); c.clip()
    c.set_source_rgb(0.18, 0.16, 0.2); c.paint()
    toon(c, 40, -25 if emo.get("sorri") else 120, 1.9 if emo.get("sorri") else 2.2, "bento", emo.get("bento", "serio"), t, look=-0.7)
    g = cairo.LinearGradient(-440, -200, 440, 200); g.add_color_stop_rgba(0, 1, 1, 1, 0.12); g.add_color_stop_rgba(0.5, 1, 1, 1, 0); c.set_source(g); c.paint()
    c.restore()
    c.set_source_rgb(0.1, 0.1, 0.12); c.rectangle(W / 2 - 20, 0, 40, 540); c.fill()
    # fundo desfocado: corredor
    c.set_source_rgba(0.75, 0.88, 1, 0.05 + 0.04 * math.sin(t * 9)); c.paint()

def cena_retrato(c, lt, T, t, emo):
    c.set_source_rgb(0.08, 0.06, 0.05); c.paint()
    for y in range(0, H, 46): c.set_source_rgba(0.12, 0.09, 0.07, 1); c.rectangle(0, y, W, 4); c.fill()
    c.save(); c.translate(W / 2, 860); c.rotate(-0.06 + math.sin(t * 0.5) * 0.01)
    rrect(c, -360, -470, 720, 900, 16); fill_ol(c, (0.92, 0.88, 0.78), 6)
    c.rectangle(-320, -430, 640, 700); c.set_source_rgb(0.55, 0.45, 0.33); c.fill()
    c.save(); c.rectangle(-320, -430, 640, 700); c.clip()
    toon(c, 0, -60, 1.3, "antigo", "neutro", 0.5, sepia=True)
    rnd = random.Random(2)
    for i in range(14):  # riscos
        c.set_source_rgba(1, 0.95, 0.85, 0.25); c.set_line_width(2); x = rnd.uniform(-320, 320)
        c.move_to(x, -430); c.line_to(x + rnd.uniform(-30, 30), 270); c.stroke()
    c.restore()
    fonte(c, 44); c.set_source_rgb(0.25, 0.2, 0.15); s = "LINHA 12"; c.move_to(-lw_(c, s) / 2, 360); c.show_text(s)
    c.restore()
    g = cairo.RadialGradient(W / 2, 860, 100, W / 2, 860, 900); g.add_color_stop_rgba(0, 1, 0.8, 0.5, 0.12); g.add_color_stop_rgba(1, 0, 0, 0, 0)
    c.set_source(g); c.paint()

def cena_banco(c, lt, T, t, emo):
    interior_fundo(c, t)
    c.set_source_rgba(0, 0, 0, 0.45); c.paint()
    # banco vazio grande
    rrect(c, 380, 760, 640, 820, 90); fill_ol(c, hx("#2E5E8C"), 10)
    c.set_source_rgb(*hx("#3E76AA")); rrect(c, 420, 800, 560, 160, 50); c.fill()
    rrect(c, 360, 1400, 680, 260, 60); fill_ol(c, hx("#27527A"), 10)
    # ombro do Téo na esquerda
    c.save(); c.translate(-80, 0)
    toon(c, 150, 900, 1.3, "teo", "medo", t, look=1.0)
    c.restore()
    # calor saindo do assento
    ap = eo((lt - 0.6) / 1.5)
    c.set_line_width(10); c.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(5):
        x0 = 480 + i * 110
        c.set_source_rgba(1, 0.5, 0.15, 0.55 * ap)
        c.move_to(x0, 1400)
        for k in range(1, 12):
            y = 1400 - k * 45 - (t * 60) % 45
            c.line_to(x0 + math.sin(k * 0.9 + t * 4 + i) * 22, y)
        c.stroke()
    g = cairo.RadialGradient(700, 1350, 20, 700, 1350, 420); g.add_color_stop_rgba(0, 1, 0.45, 0.1, 0.35 * ap); g.add_color_stop_rgba(1, 1, 0.45, 0.1, 0)
    c.set_source(g); c.paint()

def cena_bilhete(c, lt, T, t, emo):
    c.set_source_rgb(0.05, 0.06, 0.1); c.paint()
    g = cairo.RadialGradient(W / 2, 820, 50, W / 2, 820, 800); g.add_color_stop_rgba(0, 1, 0.8, 0.5, 0.18); g.add_color_stop_rgba(1, 0, 0, 0, 0); c.set_source(g); c.paint()
    verso = emo.get("lado") == "verso"
    vira = eio(lt / 0.6) if verso else 1.0
    c.save(); c.translate(W / 2, 820); c.rotate(-0.05 + math.sin(t * 0.8) * 0.015); c.scale(1.15 * max(0.02, abs(math.cos((1 - vira) * math.pi / 2))), 1.15)
    rrect(c, -400, -250, 800, 500, 14); fill_ol(c, (0.93, 0.86, 0.66), 6)
    rnd = random.Random(4)
    for i in range(40):
        c.set_source_rgba(0.6, 0.45, 0.25, 0.12); c.arc(rnd.uniform(-390, 390), rnd.uniform(-240, 240), rnd.uniform(4, 30), 0, 2 * math.pi); c.fill()
    if not verso:
        c.set_source_rgb(0.75, 0.3, 0.12); c.rectangle(-400, -250, 800, 80); c.fill()
        fonte(c, 48); c.set_source_rgb(1, 0.95, 0.85); s = "PASSAGEM · LINHA 12"; c.move_to(-lw_(c, s) / 2, -195); c.show_text(s)
        fonte(c, 40, "Medium"); c.set_source_rgb(0.25, 0.18, 0.1)
        for i, l in enumerate(["CENTRO - HOSPITAL", "SAÍDA: 23:58", "DATA: 14/03/2006"]):
            c.move_to(-340, -90 + i * 80); c.show_text(l)
        c.set_source_rgba(0.7, 0.15, 0.1, 0.8); c.set_line_width(6); c.arc(250, 120, 90, 0, 2 * math.pi); c.stroke()
        fonte(c, 30); c.move_to(195, 132); c.show_text("PAGO")
    else:
        c.select_font_face("DejaVu Serif", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL); c.set_font_size(70)
        txt = ["Pro Téo.", "Eu prometi", "te levar."]
        n = int(sum(len(x) for x in txt) * clamp((lt - 0.5) / max(0.5, T * 0.6)))
        c.set_source_rgb(0.12, 0.12, 0.35)
        for i, l in enumerate(txt):
            vis = l[:max(0, n)]; n -= len(l)
            c.move_to(-320, -110 + i * 110); c.show_text(vis)
    c.restore()

def bento_costas(c, x, y, s, t, alpha=1.0):
    c.push_group()
    c.save(); c.translate(x, y)
    rrect(c, -150 * s, 190 * s, 300 * s, 420 * s, 120 * s); fill_ol(c, hx("#2F4A6B"), 7 * s)
    c.arc(0, 0, 170 * s, 0, 2 * math.pi); fill_ol(c, PERS["bento"]["pele"], 7 * s)
    c.arc(0, 30 * s, 150 * s, 0.1 * math.pi, 0.9 * math.pi); c.set_source_rgb(0.75, 0.75, 0.75); c.fill()
    c.arc(0, -10 * s, 174 * s, math.pi * 1.08, math.pi * 1.92); c.close_path(); fill_ol(c, hx("#1E2B44"), 6 * s)
    c.set_source_rgb(*hx("#E8B23A")); c.rectangle(-160 * s, -80 * s, 320 * s, 20 * s); c.fill()
    c.restore()
    c.pop_group_to_source(); c.paint_with_alpha(alpha)

def cena_descida(c, lt, T, t, emo):
    ceu(c, (0.02, 0.03, 0.08), (0.08, 0.06, 0.14), t)
    predios(c, 1350, 300, (0.05, 0.05, 0.1), 800, 4)
    c.set_source_rgb(0.12, 0.12, 0.14); c.rectangle(0, 1350, W, H); c.fill()
    px = 300
    c.set_source_rgb(0.3, 0.32, 0.36); c.rectangle(px, 760, 14, 600); c.fill()
    c.arc(px + 7, 740, 90, 0, 2 * math.pi); fill_ol(c, hx("#E8B23A"), 8)
    fonte(c, 100); c.set_source_rgb(0.1, 0.1, 0.1); s = "12"; c.move_to(px + 7 - lw_(c, s) / 2, 776); c.show_text(s)
    onibus_lado(c, 470, 1640, 0.55, 0, porta=1.0)
    k = eio(lt / max(1.0, T))
    sc = 0.62 - 0.22 * k
    bento_costas(c, 1000 - 620 * k + math.sin(t * 7) * 6, 1110 - 40 * k + abs(math.sin(t * 7)) * -12, sc, t, alpha=1 - 0.55 * k)
    neblina(c, t, 1250, 0.28)
    if emo.get("flash") and lt < 0.25:
        c.set_source_rgba(1, 1, 1, 0.5 * (1 - lt / 0.25)); c.paint()

def cena_teo_corredor(c, lt, T, t, emo):
    interior_fundo(c, t)
    k = eo(lt / max(1.0, T))
    passo = abs(math.sin(lt * 9))
    s = 0.75 + 0.55 * k
    toon(c, W / 2 + math.sin(lt * 9) * 25, 820 + 420 * k - passo * 30, s, "teo", emo.get("teo", "medo"), t, look=math.sin(lt * 3) * 0.8)
    c.set_source_rgba(0.75, 0.88, 1, 0.05 + 0.04 * math.sin(t * 9)); c.paint()

def jornal_foto(c, x, y, who, rot):
    c.save(); c.translate(x, y); c.rotate(rot)
    c.rectangle(-150, -180, 300, 360); c.set_source_rgb(0.5, 0.42, 0.32); c.fill()
    c.save(); c.rectangle(-150, -180, 300, 360); c.clip(); toon(c, 0, -10, 0.68, who, "neutro", 0.4, sepia=True); c.restore()
    c.set_source_rgb(0.15, 0.12, 0.1); c.set_line_width(4); c.rectangle(-150, -180, 300, 360); c.stroke()
    c.restore()

def cena_jornal(c, lt, T, t, emo):
    c.set_source_rgb(0.05, 0.05, 0.08); c.paint()
    g = cairo.RadialGradient(W / 2, 900, 50, W / 2, 900, 900); g.add_color_stop_rgba(0, 1, 0.85, 0.55, 0.2); g.add_color_stop_rgba(1, 0, 0, 0, 0); c.set_source(g); c.paint()
    foco = emo.get("foco"); k = eio(lt / 1.4)
    z = 1.0; tx = ty = 0.0
    if foco == "bento": z = 1.0 + 0.9 * k; tx, ty = -200 * k, -60 * k
    elif foco == "titulo": z = 1.45 + 0.1 * k; tx, ty = 0, 520 + 30 * k
    elif foco == "fotos": z = 1.35; tx = 230 - 460 * eio(lt / max(1.0, T * 0.8)); ty = 40
    elif foco == "chega": ty = 1300 * (1 - eo(lt / 0.9)); z = 0.85 + 0.15 * eo(lt / 0.9)
    c.save(); c.translate(W / 2, 900); c.translate(tx, ty)
    c.scale(z, z); c.rotate(-0.04 + math.sin(t * 0.6) * 0.01 + (0.25 * (1 - eo(lt / 0.9)) if foco == "chega" else 0))
    rrect(c, -460, -620, 920, 1240, 8); fill_ol(c, (0.86, 0.83, 0.74), 6)
    rnd = random.Random(8)
    for i in range(30):
        c.set_source_rgba(0.55, 0.45, 0.3, 0.12); c.arc(rnd.uniform(-450, 450), rnd.uniform(-610, 610), rnd.uniform(6, 40), 0, 2 * math.pi); c.fill()
    c.select_font_face("DejaVu Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(62); c.set_source_rgb(0.1, 0.09, 0.08)
    for i, l in enumerate(["ACIDENTE COM", "ÔNIBUS DA LINHA 12"]):
        c.move_to(-lw_(c, l) / 2, -480 + i * 74); c.show_text(l)
    c.set_font_size(34)
    l = "15 DE MARÇO DE 2006"; c.move_to(-lw_(c, l) / 2, -330); c.show_text(l)
    c.set_line_width(4); c.move_to(-420, -300); c.line_to(420, -300); c.stroke()
    jornal_foto(c, -200, 20, "antigo", -0.02); jornal_foto(c, 200, 20, "bento", 0.02)
    c.set_font_size(30)
    for x, l in ((-200, "MOTORISTA"), (200, "COBRADOR")):
        c.move_to(x - lw_(c, l) / 2, 250); c.show_text(l)
    c.set_source_rgba(0.2, 0.18, 0.16, 0.55)
    for i in range(6):
        c.rectangle(-420, 320 + i * 44, 840 - (i % 3) * 120, 14); c.fill()
    if foco == "bento":
        c.set_source_rgba(0.85, 0.15, 0.1, 0.9 * eio((lt - 0.6) / 0.4)); c.set_line_width(10); c.arc(200, 20, 230, 0, 2 * math.pi); c.stroke()
    c.restore()

def cena_painel(c, lt, T, t, emo):
    c.set_source_rgb(0.03, 0.03, 0.05); c.paint()
    interior_fundo(c, t); c.set_source_rgba(0, 0, 0, 0.55); c.paint()
    rrect(c, 70, 640, W - 140, 420, 40); fill_ol(c, (0.06, 0.06, 0.07), 12)
    c.set_source_rgb(0.02, 0.02, 0.02); rrect(c, 110, 680, W - 220, 340, 24); c.fill()
    txt = emo.get("texto", "12  CENTRO"); de = emo.get("de")
    if de and lt < T * 0.45:
        txt = de if int(lt * 12) % 5 else ""
    elif de and lt < T * 0.45 + 0.4:
        txt = "".join(ch if random.Random(int(t * 30) + i).random() < 0.5 else "▒" for i, ch in enumerate(txt))
    fonte(c, 150, "ExtraBold"); fl = 0.85 + 0.15 * math.sin(t * 40)
    x = W / 2 - lw_(c, txt) / 2
    g = cairo.RadialGradient(W / 2, 850, 20, W / 2, 850, 500); g.add_color_stop_rgba(0, 1, 0.55, 0.1, 0.25 * fl); g.add_color_stop_rgba(1, 1, 0.55, 0.1, 0)
    c.set_source(g); c.paint()
    c.set_source_rgba(1, 0.6, 0.15, fl); c.move_to(x, 905); c.show_text(txt)
    c.set_source_rgba(0, 0, 0, 0.35)
    for yy in range(680, 1020, 12): c.rectangle(110, yy, W - 220, 4); c.fill()
    if emo.get("relogio"):
        rrect(c, 300, 1250, 480, 200, 30); fill_ol(c, (0.06, 0.06, 0.07), 10)
        fonte(c, 120, "ExtraBold"); s2 = "23:58" if int(t * 2) % 2 or lt < 1 else "23 58"
        c.set_source_rgb(1, 0.2, 0.15); c.move_to(W / 2 - lw_(c, "23:58") / 2, 1395); c.show_text(s2)

def cena_mae(c, lt, T, t, emo):
    interior_fundo(c, t)
    c.set_source_rgba(0, 0, 0, 0.35); c.paint()
    ap = eo(lt / 1.2)
    s = 0.9 + 0.25 * ap
    dor = math.sin(t * 5) * 8 if emo.get("dor") else 0
    toon(c, W / 2 + dor, 980, s, "mae", "medo", t, look=-0.2)
    # barriga
    ell(c, W / 2 + dor, 980 + 470 * s, 150 * s, 120 * s); fill_ol(c, dark(PERS["mae"]["roupa"], 1.08), 7 * s)
    for sx in (-1, 1):
        ell(c, W / 2 + dor + sx * 110 * s, 980 + 470 * s, 40 * s, 30 * s); fill_ol(c, PERS["mae"]["pele"], 5 * s)
    rrect(c, 140, 1560, W - 280, 420, 60); fill_ol(c, hx("#2E5E8C"), 10)
    c.set_source_rgb(*hx("#3E76AA")); rrect(c, 180, 1580, W - 360, 90, 30); c.fill()
    c.set_source_rgba(0.75, 0.88, 1, 0.06 + 0.05 * math.sin(t * 7)); c.paint()

def predio_hospital(c, x, base, s, t, sombras=0.0):
    c.save(); c.translate(x, base); c.scale(s, s)
    rrect(c, -420, -900, 840, 900, 10); fill_ol(c, (0.78, 0.8, 0.84), 8)
    rnd = random.Random(21)
    for wy in range(-840, -260, 140):
        for wx in range(-370, 371, 150):
            on = rnd.random() < 0.55
            c.rectangle(wx, wy, 90, 90); c.set_source_rgb(*((1, 0.85, 0.5) if on else (0.2, 0.22, 0.3))); c.fill()
    c.set_source_rgb(0.85, 0.12, 0.12); c.rectangle(-30, -1080, 60, 180); c.fill(); c.rectangle(-90, -1020, 180, 60); c.fill()
    rrect(c, -300, -230, 600, 80, 10); fill_ol(c, (0.1, 0.12, 0.2), 5)
    fonte(c, 54); c.set_source_rgb(1, 1, 1); l = "MATERNIDADE"; c.move_to(-lw_(c, l) / 2, -170); c.show_text(l)
    c.rectangle(-140, -140, 280, 140); c.set_source_rgb(0.95, 0.9, 0.7); c.fill()
    if sombras > 0:
        for k, dx in enumerate((-70, 70)):
            c.set_source_rgba(0.05, 0.05, 0.08, 0.9 * sombras)
            c.arc(dx, -105, 26, 0, 2 * math.pi); c.fill(); rrect(c, dx - 32, -80, 64, 80, 20); c.fill()
            if k == 0: c.rectangle(dx - 34, -132, 68, 12); c.fill()
    c.restore()

def cena_hospital(c, lt, T, t, emo):
    ceu(c, (0.02, 0.03, 0.08), (0.1, 0.07, 0.16), t)
    predios(c, 1350, 200, (0.05, 0.05, 0.1), 700, 7)
    c.set_source_rgb(0.1, 0.1, 0.12); c.rectangle(0, 1350, W, H); c.fill()
    predio_hospital(c, W / 2 + 120, 1350, 0.75, t, sombras=eo((lt - 0.3) / 1.0) if emo.get("sombras") else 0)
    if emo.get("parado"):
        onibus_lado(c, -260, 1640, 0.62, 0, porta=eio((lt - 0.5) / 0.8))
    else:
        k = eo(lt / max(1.0, T)); onibus_lado(c, -900 + 650 * k, 1640, 0.62, t, roda=t * 14 * (1 - k))
    neblina(c, t, 1300, 0.15)

def cena_caminhao(c, lt, T, t, emo):
    c.set_source_rgb(0.02, 0.02, 0.05); c.paint()
    c.save(); rrect(c, 60, 180, W - 120, 1100, 60); c.clip()
    g = cairo.LinearGradient(0, 180, 0, 1280); g.add_color_stop_rgb(0, 0.03, 0.04, 0.12); g.add_color_stop_rgb(1, 0.1, 0.07, 0.15); c.set_source(g); c.paint()
    c.set_source_rgb(0.08, 0.08, 0.1); c.move_to(W / 2 - 40, 700); c.line_to(W / 2 + 40, 700); c.line_to(W + 300, 1280); c.line_to(-300, 1280); c.close_path(); c.fill()
    for i in range(6):
        k = ((t * 1.4 + i / 6) % 1) ** 2
        c.set_source_rgb(0.95, 0.85, 0.4); c.rectangle(W / 2 - (4 + 30 * k) / 2, 700 + 580 * k, 4 + 30 * k, 6 + 70 * k); c.fill()
    passa = emo.get("passa")
    k = eio(lt / max(1.2, T * 0.9)) if not passa else 1.0
    if passa:  # caminhão passa raspando pela esquerda
        q = eio(lt / 0.9); sz = 2.6 + 2.5 * q; cx = W / 2 - 120 - 900 * q; cy = 760 + 200 * q
    else:
        sz = 0.25 + 2.2 * k; cx = W / 2 - 60 * k; cy = 720 + 80 * k
    c.save(); c.translate(cx, cy); c.scale(sz, sz)
    rrect(c, -120, -150, 240, 170, 14); fill_ol(c, (0.12, 0.12, 0.14), 4)
    c.set_source_rgb(0.18, 0.2, 0.26); rrect(c, -100, -135, 200, 70, 8); c.fill()
    c.set_source_rgb(0.25, 0.25, 0.27); c.rectangle(-110, -40, 220, 30); c.fill()
    for dx in (-80, 80): c.arc(dx, -25, 14, 0, 2 * math.pi); c.set_source_rgb(0.3, 0.3, 0.3); c.fill()
    c.restore()
    c.restore()
    c.set_source_rgb(0.12, 0.12, 0.14); c.set_line_width(14); rrect(c, 60, 180, W - 120, 1100, 60); c.stroke()
    c.set_source_rgb(0.08, 0.08, 0.1); c.rectangle(0, 1500, W, H); c.fill()
    if passa:
        tr = clamp(1 - lt / 1.2)
        c.translate(math.sin(t * 60) * 20 * tr, math.cos(t * 53) * 20 * tr)
    elif k > 0.7:
        c.set_source_rgba(1, 0.1, 0.05, 0.12 * math.sin(t * 20) ** 2); c.paint()

def cena_branco(c, lt, T, t, emo):
    a = eo(lt / max(0.5, T * 0.6))
    interior_fundo(c, t)
    c.set_source_rgba(1, 1, 1, a); c.paint()

def cena_ponto_dia(c, lt, T, t, emo):
    ceu(c, (0.55, 0.7, 0.9), (0.98, 0.8, 0.6), 0)
    c.set_source_rgba(1, 0.9, 0.6, 0.8); c.arc(880, 520, 90, 0, 2 * math.pi); c.fill()
    predios(c, 1350, 300, (0.45, 0.48, 0.6), 800, 4, janelas=False)
    c.set_source_rgb(0.42, 0.42, 0.45); c.rectangle(0, 1350, W, H); c.fill()
    c.set_source_rgb(0.55, 0.55, 0.58); c.rectangle(0, 1350, W, 60); c.fill()
    px = 860
    c.set_source_rgb(0.3, 0.32, 0.36); c.rectangle(px, 760, 14, 600); c.fill()
    c.arc(px + 7, 740, 90, 0, 2 * math.pi); fill_ol(c, hx("#E8B23A"), 8)
    fonte(c, 100); c.set_source_rgb(0.1, 0.1, 0.1); s2 = "12"; c.move_to(px + 7 - lw_(c, s2) / 2, 776); c.show_text(s2)
    rrect(c, 160, 1210, 620, 34, 10); fill_ol(c, (0.45, 0.32, 0.22), 6)
    for bx in (200, 740): c.set_source_rgb(0.25, 0.25, 0.27); c.rectangle(bx, 1244, 14, 110); c.fill()
    if emo.get("bento"):
        toon(c, 620, 900, 0.72, "bento", emo.get("bento"), t, look=-0.6 if emo.get("olha") else 0.3)
        toon(c, 300, 920, 0.68, "teo", emo.get("teo", "neutro"), t, look=0.6)
    else:
        toon(c, 420, 920, 0.72, "teo", emo.get("teo", "medo"), t, look=math.sin(t * 1.5) * 0.7)

def cena_celular(c, lt, T, t, emo):
    c.set_source_rgb(0.5, 0.62, 0.8); c.paint()
    c.save(); c.translate(W / 2, 960); c.rotate(-0.03 + math.sin(t * 0.8) * 0.01)
    rrect(c, -330, -640, 660, 1280, 70); fill_ol(c, (0.08, 0.08, 0.1), 8)
    c.set_source_rgb(0.97, 0.97, 0.98); rrect(c, -300, -600, 600, 1200, 50); c.fill()
    fonte(c, 70); c.set_source_rgb(0.1, 0.1, 0.12); c.move_to(-260, -490); c.show_text("Contatos")
    rrect(c, -260, -450, 520, 80, 40); c.set_source_rgb(0.9, 0.9, 0.92); c.fill()
    fonte(c, 56, "Medium"); c.set_source_rgb(0.2, 0.2, 0.25)
    busca = "" if not emo.get("vazio") else "Mãe"[: int(clamp(lt / 0.6) * 3)]
    c.move_to(-220, -395); c.show_text(busca + ("|" if int(t * 3) % 2 else ""))
    if emo.get("vazio"):
        fonte(c, 64); c.set_source_rgba(0.45, 0.45, 0.5, eo((lt - 0.6) / 0.6)); l = "Nenhum contato"
        c.move_to(-lw_(c, l) / 2, 0); c.show_text(l)
        c.set_source_rgba(0.85, 0.15, 0.1, 0.12 * eo((lt - 0.6) / 0.6)); c.paint()
    else:
        lista = ["Aula Cálculo", "Lucas", "Pizzaria", "Renata", "Trabalho"]
        rol = -60 * eio(lt / max(1.0, T))
        for i, nome in enumerate(lista):
            y = -260 + i * 140 + rol
            c.set_source_rgb(0.85, 0.85, 0.88); c.arc(-210, y - 15, 38, 0, 2 * math.pi); c.fill()
            c.set_source_rgb(0.1, 0.1, 0.12); fonte(c, 58, "Medium"); c.move_to(-150, y); c.show_text(nome)
    c.restore()

CENAS = dict(bilhete=cena_bilhete, descida=cena_descida, estrada=cena_estrada, ponto=cena_ponto, interior=cena_interior, motorista=cena_motorista, catraca=cena_catraca,
             teo_close=cena_teo_close, corredor=cena_corredor, espelho=cena_espelho, retrato=cena_retrato, banco=cena_banco,
             teo_corredor=cena_teo_corredor, jornal=cena_jornal, painel=cena_painel, mae=cena_mae,
             hospital=cena_hospital, caminhao=cena_caminhao, branco=cena_branco, ponto_dia=cena_ponto_dia, celular=cena_celular)


# ---- Ep 5: a porta da mãe, os dois Téos, a foto e a calçada
PERS["teo2"] = dict(PERS["teo"])
PERS["mae_hoje"] = dict(pele=hx("#B9825A"), cabelo=hx("#6E6660"), roupa=hx("#7A5C9E"), oculos=True, careca=False, bone=False, barba=None, longo=True)

def casa_dia(c, t):
    ceu(c, (0.6, 0.72, 0.9), (0.98, 0.86, 0.7), 0)
    c.set_source_rgb(*hx("#D9C7A6")); c.rectangle(0, 300, W, 1100); c.fill()
    for y in range(330, 1400, 70): c.set_source_rgba(0, 0, 0, 0.05); c.rectangle(0, y, W, 4); c.fill()
    c.set_source_rgb(0.45, 0.43, 0.42); c.rectangle(0, 1400, W, H); c.fill()
    c.set_source_rgb(0.55, 0.53, 0.52); c.rectangle(0, 1400, W, 50); c.fill()

def cena_porta(c, lt, T, t, emo):
    casa_dia(c, t)
    dx0, dy0, dw, dh = 330, 520, 440, 880
    rrect(c, dx0 - 40, dy0 - 40, dw + 80, dh + 40, 10); fill_ol(c, (0.95, 0.93, 0.88), 8)
    fonte(c, 64); c.set_source_rgb(0.2, 0.2, 0.22); c.move_to(dx0 + dw / 2 - 40, dy0 - 70); c.show_text("125")
    c.save(); c.rectangle(dx0, dy0, dw, dh); c.clip()
    g = cairo.LinearGradient(0, dy0, 0, dy0 + dh); g.add_color_stop_rgb(0, 0.35, 0.28, 0.24); g.add_color_stop_rgb(1, 0.2, 0.16, 0.14); c.set_source(g); c.paint()
    if emo.get("mae"):
        ap = eo((lt - 0.2) / 0.8)
        c.save(); c.push_group(); toon(c, dx0 + dw - 90, dy0 + 260, 0.42, "mae_hoje", "neutro", t, look=-0.5); c.pop_group_to_source(); c.paint_with_alpha(0.85 * ap); c.restore()
    if emo.get("filho", True):
        olha = emo.get("olha")
        toon(c, dx0 + dw / 2 - 10, dy0 + 330, 0.62, "teo2", "serio" if olha else "neutro", t, look=(-0.1 if olha else -0.6))
    abre = eio(lt / 0.9) if emo.get("abre") else 1.0
    pw = dw * (1 - abre * 0.85)
    rrect(c, dx0, dy0, pw, dh, 6); fill_ol(c, hx("#6B3E26"), 8)
    c.set_source_rgb(0.85, 0.7, 0.3); c.arc(dx0 + pw - 40, dy0 + dh / 2, 14, 0, 2 * math.pi); c.fill()
    c.restore()
    # o Téo de costas para nós, no primeiro plano à esquerda
    e = emo.get("teo", "medo")
    toon(c, 195, 1330, 1.1, "teo", e, t, look=0.9)
    if emo.get("olha"):
        c.set_source_rgba(0.75, 0.88, 1, 0.05 + 0.04 * math.sin(t * 9)); c.paint()

def cena_dois_teos(c, lt, T, t, emo):
    g = cairo.LinearGradient(0, 0, 0, H); g.add_color_stop_rgb(0, 0.12, 0.12, 0.18); g.add_color_stop_rgb(1, 0.03, 0.03, 0.06); c.set_source(g); c.paint()
    ap = eo(lt / 0.8)
    toon(c, W / 2 - 250 * ap, 920, 1.05, "teo", "medo", t, look=0.7)
    toon(c, W / 2 + 250 * ap, 920, 1.05, "teo2", "serio", t + 0.6, look=0.0)
    # linha de falha entre os dois
    c.set_source_rgba(1, 0.55, 0.15, 0.5 + 0.3 * math.sin(t * 13)); c.set_line_width(4)
    c.move_to(W / 2, 300)
    for k in range(1, 15): c.line_to(W / 2 + math.sin(t * 20 + k * 1.7) * 14, 300 + k * 80)
    c.stroke()
    if int(t * 12) % 17 == 0:
        c.set_source_rgba(1, 1, 1, 0.08); c.paint()

def cena_foto(c, lt, T, t, emo):
    c.set_source_rgb(0.22, 0.17, 0.14); c.paint()
    c.set_source_rgb(0.4, 0.28, 0.18); c.rectangle(0, 1300, W, 70); c.fill()
    c.set_source_rgb(0.3, 0.2, 0.13); c.rectangle(0, 1370, W, 30); c.fill()
    c.save(); c.translate(W / 2, 880); s = 1.0 + 0.12 * eio(lt / max(1.0, T)); c.scale(s, s); c.rotate(0.03)
    rrect(c, -330, -420, 660, 820, 14); fill_ol(c, (0.75, 0.6, 0.35), 8)
    c.rectangle(-280, -370, 560, 620); c.set_source_rgb(0.85, 0.9, 0.92); c.fill()
    c.save(); c.rectangle(-280, -370, 560, 620); c.clip()
    c.set_source_rgb(0.9, 0.93, 0.95); c.rectangle(-280, -370, 560, 620); c.fill()
    rrect(c, -180, -330, 360, 64, 8); fill_ol(c, (0.1, 0.12, 0.2), 4)
    fonte(c, 36); c.set_source_rgb(1, 1, 1); l = "MATERNIDADE"; c.move_to(-lw_(c, l) / 2, -286); c.show_text(l)
    c.set_source_rgb(0.85, 0.12, 0.12); c.rectangle(200, -330, 20, 60); c.fill(); c.rectangle(180, -310, 60, 20); c.fill()
    rrect(c, -230, 20, 460, 200, 30); fill_ol(c, (0.75, 0.85, 0.95), 6)  # berço
    ell(c, 0, 0, 170, 90); fill_ol(c, (0.95, 0.85, 0.6), 6)  # manta
    c.arc(-90, -30, 62, 0, 2 * math.pi); fill_ol(c, hx("#C08A5E"), 5)  # bebê
    for sx in (-1, 1):
        c.set_source_rgb(0.07, 0.06, 0.08); c.set_line_width(5); c.arc(-90 + sx * 22, -36, 9, 0.1 * math.pi, 0.9 * math.pi); c.stroke()
    c.restore()
    fonte(c, 40, "Medium"); c.set_source_rgb(0.2, 0.15, 0.1); l = "TÉO · 15/03/2006"; c.move_to(-lw_(c, l) / 2, 340); c.show_text(l)
    c.restore()
    g = cairo.RadialGradient(W / 2, 880, 100, W / 2, 880, 900); g.add_color_stop_rgba(0, 1, 0.85, 0.6, 0.15); g.add_color_stop_rgba(1, 0, 0, 0, 0.3); c.set_source(g); c.paint()

def cena_calcada(c, lt, T, t, emo):
    ceu(c, (0.55, 0.68, 0.88), (0.95, 0.75, 0.55), 0)
    predios(c, 1350, 600, (0.5, 0.5, 0.62), 900, 11, janelas=False)
    c.set_source_rgb(0.5, 0.5, 0.52); c.rectangle(0, 1350, W, H); c.fill()
    c.set_source_rgb(0.6, 0.6, 0.62); c.rectangle(0, 1350, W, 50); c.fill()
    # Téo parado, meio transparente
    c.save(); c.push_group(); toon(c, W / 2, 920, 0.8, "teo", emo.get("teo", "triste"), t, look=math.sin(t * 1.3) * 0.8); c.pop_group_to_source(); c.paint_with_alpha(0.75 + 0.15 * math.sin(t * 3)); c.restore()
    # gente passando através dele
    cores = [hx("#3C6E71"), hx("#9E3D3D"), hx("#5B5B8F"), hx("#C2884A")]
    for i in range(4):
        v = 260 + i * 70; d = 1 if i % 2 else -1
        x = (W / 2 + d * (-W * 0.7 + ((t * v + i * 450) % (W * 1.4))))
        y = 980 + (i % 2) * 70
        bob = abs(math.sin(t * 8 + i)) * 10
        c.set_source_rgba(*cores[i], 0.9); c.arc(x, y - 180 - bob, 70, 0, 2 * math.pi); c.fill()
        rrect(c, x - 90, y - 110 - bob, 180, 330, 70); c.fill()

CENAS_EP5 = dict(porta=cena_porta, dois_teos=cena_dois_teos, foto=cena_foto, calcada=cena_calcada)
CENAS.update(CENAS_EP5)

# ------------------------------------------------------------------ áudio
def ler_audio(p, vel=1.0):
    af = "adeclip,highpass=f=70,lowpass=f=11000,silenceremove=start_periods=1:start_threshold=-42dB:stop_periods=-1:stop_threshold=-42dB:stop_duration=0.2:stop_silence=0.12" + (f",atempo={vel}" if vel != 1 else "")
    o = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-af", af, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(o, dtype=np.float32).copy()
def aparar(a, lim=0.01):
    i = np.where(np.abs(a) > lim)[0]
    return a if len(i) == 0 else a[max(0, i[0] - int(0.03 * SR)): i[-1] + int(0.08 * SR)]
def silabas(w): return max(1, len(re.findall(r"[aeiouáéíóúâêôãõàAEIOUÁÉÍÓÚÂÊÔÃÕ]+", w)))
def tempos_voz(texto, ini, a):
    ws = texto.split(); hop = int(SR * 0.01)
    rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, max(1, len(a) - hop), hop)])
    lim = max(0.012, rms.max() * 0.07); voz = rms > lim; seg, ini0 = [], None
    for j, v in enumerate(voz):
        if v and ini0 is None: ini0 = j
        if not v and ini0 is not None: seg.append([ini0, j]); ini0 = None
    if ini0 is not None: seg.append([ini0, len(voz)])
    jt = []
    for sg in seg:
        if jt and sg[0] - jt[-1][1] < 12: jt[-1][1] = sg[1]
        else: jt.append(sg)
    jt = [(x * 0.01, y * 0.01) for x, y in jt if y - x >= 5] or [(0, len(a) / SR)]
    D = sum(y - x for x, y in jt)
    def real(pv):
        for x, y in jt:
            if pv <= y - x: return x + pv
            pv -= y - x
        return jt[-1][1]
    ps = [silabas(w) for w in ws]; S = sum(ps); acc = 0; r = []
    for w, p in zip(ws, ps):
        a0 = real(D * acc / S); acc += p; r.append((w, ini + a0, ini + max(a0 + 0.05, real(D * acc / S - 1e-4))))
    return r

def tempos(texto, ini, dur):
    ws = texto.split(); ps = [silabas(w) + (1.0 if w[-1] in ".,!?…:" else 0) for w in ws]; tot = sum(ps); t = ini; r = []
    for w, p in zip(ws, ps): d = dur * p / tot; r.append((w, t, t + d)); t += d
    return r
def trilha(n):
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 82.4 * t) * 0.25 + np.sin(2 * np.pi * 58.3 * t) * 0.25) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.09 * t))
    rng = np.random.default_rng(3); ruido = np.convolve(rng.standard_normal(n), np.ones(60) / 60, mode="same")  # motor do ônibus
    x = x * 0.08 + ruido * 0.10 * (1 + 0.3 * np.sin(2 * np.pi * 7 * t))
    f = int(SR * 1.2); x[:f] *= np.linspace(0, 1, f); x[-f:] *= np.linspace(1, 0, f)
    return x.astype(np.float32)
def boom():
    t = np.arange(int(1.3 * SR)) / SR; return (np.sin(2 * np.pi * (58 - 22 * t) * t) * np.exp(-t * 3.2) * 0.8).astype(np.float32)
def whoosh():
    n = int(0.35 * SR); r = np.convolve(np.random.default_rng(7).standard_normal(n), np.ones(14) / 14, mode="same")
    return (0.22 * r * np.sin(np.linspace(0, np.pi, n)) ** 2).astype(np.float32)
def clique():
    t = np.arange(int(0.12 * SR)) / SR
    return (0.5 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 60) + 0.3 * np.sin(2 * np.pi * 420 * t) * np.exp(-t * 30)).astype(np.float32)

# ------------------------------------------------------------------ principal
def main():
    a = sys.argv[1:]
    rot = json.load(open(a[0], encoding="utf-8")); saida = a[1]
    previas = "--previas" in a; pasta = a[a.index("--audios") + 1] if "--audios" in a else None
    blocos = rot["blocos"]
    arqs = {}
    if pasta:
        for nome in os.listdir(pasta):
            m = re.search(r"(\d+)", nome)
            if m and nome.lower().endswith((".wav", ".mp3", ".m4a", ".ogg")): arqs[int(m.group(1))] = os.path.join(pasta, nome)
    ini = 0.5; vozes = []
    for i, b in enumerate(blocos):
        if (i + 1) in arqs:
            v = aparar(ler_audio(arqs[i + 1], rot.get("vel_voz", 1.0))); v = v / (np.abs(v).max() + 1e-6) * 0.85; dur = len(v) / SR
            fd = int(0.012 * SR); v[:fd] *= np.linspace(0, 1, fd); v[-fd:] *= np.linspace(1, 0, fd)
        else:
            v = None; dur = len(b["texto"].split()) / 2.3
        b["_ini"] = ini; b["_dur"] = dur; b["_fim"] = ini + dur + min(b.get("pausa", 0.3), rot.get("pausa_max", 9))
        b["_pal"] = tempos_voz(b["texto"], ini, v) if v is not None else tempos(b["texto"], ini, dur); vozes.append(v); ini = b["_fim"]
    fim = ini; FIN = 3.0; total = fim + FIN; nfr = int(total * FPS)
    print(f"duração: {total:.1f}s", flush=True)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); c = cairo.Context(surf)
    rng = np.random.default_rng(1); graos = []
    for _ in range(3):
        g = cairo.ImageSurface(cairo.FORMAT_ARGB32, W // 2, H // 2)
        arr = np.ndarray((H // 2, g.get_stride() // 4), np.uint32, g.get_data())
        v = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint32); al = 28
        arr[:, :W // 2] = (al << 24) | ((v * al // 255) << 16) | ((v * al // 255) << 8) | (v * al // 255); g.mark_dirty(); graos.append(g)

    def legenda(t, b):
        pal = b["_pal"]; dest = {re.sub(r"[^\wÀ-ÿ]", "", x.lower()) for d in b.get("destaque", []) for x in d.split()}
        idx = 0
        for i, (w, s, e) in enumerate(pal):
            if t >= s: idx = i
        grupos, g = [], []
        for i, (w, s, e) in enumerate(pal):
            g.append(i)
            if len(g) == 3 or w[-1] in ".,!?:…": grupos.append(g); g = []
        if g: grupos.append(g)
        gr = next(x for x in grupos if idx in x)
        tam = 76; fonte(c, tam); txt = " ".join(pal[i][0].upper() for i in gr)
        while lw_(c, txt) * 1.12 > W - 110 and tam > 50: tam -= 4; fonte(c, tam)
        x = W / 2 - lw_(c, txt) * 1.06 / 2; y = 1560
        for i in gr:
            w = pal[i][0].upper(); on = i <= idx
            cor = LAR if re.sub(r"[^\wÀ-ÿ]", "", w.lower()) in dest else TXT
            sc = 1.0 + 0.1 * clamp(1 - (t - pal[i][1]) / 0.15) if i == idx else 1.0
            c.save(); c.translate(x, y); c.scale(sc, sc)
            c.move_to(0, 0); c.text_path(w); c.set_source_rgb(0.02, 0.02, 0.04); c.set_line_width(14); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke()
            c.move_to(0, 0); c.set_source_rgba(*cor, 1 if on else 0.45); c.show_text(w); c.restore()
            x += lw_(c, w) * sc + lw_(c, " ") * 1.15

    def desenhar(f):
        t = f / FPS
        c.identity_matrix()
        if t >= fim:
            lt = t - fim; c.set_source_rgb(0.01, 0.01, 0.03); c.paint()
            for sx in (-1, 1):  # faróis se afastando
                r = 60 * (1 - eo(lt / 2.5)) + 8
                g = cairo.RadialGradient(W / 2 + sx * 80 * (1 - eo(lt / 2.5)), 1250, 1, W / 2 + sx * 80 * (1 - eo(lt / 2.5)), 1250, r * 4)
                g.add_color_stop_rgba(0, 1, 0.3, 0.2, 0.9); g.add_color_stop_rgba(1, 1, 0.3, 0.2, 0); c.set_source(g); c.paint()
            fonte(c, 120, "ExtraBold"); s = rot["final"].get("titulo", "CONTINUA...")
            p = eback(lt / 0.5); c.save(); c.translate(W / 2, 820); c.scale(p, p)
            c.set_source_rgb(*LAR); c.move_to(-lw_(c, s) / 2, 0); c.show_text(s); c.restore()
            fonte(c, 54)
            for j, l in enumerate(rot["final"].get("texto", "").split("\n")):
                c.set_source_rgba(*TXT, eo((lt - 0.4) / 0.5)); c.move_to(W / 2 - lw_(c, l) / 2, 980 + j * 76); c.show_text(l)
            return
        b = next((x for x in blocos if t < x["_fim"]), blocos[-1])
        if t < blocos[0]["_ini"]: b = blocos[0]
        lt = t - b["_ini"] + (0.5 if b is blocos[0] else 0); T = b["_fim"] - b["_ini"]
        # câmera: empurrão lento + deriva + tremor no impacto
        z = 1.0 + 0.08 * eio(lt / max(T, 0.5)); dx = math.sin(t * 0.4) * 12; dy = math.cos(t * 0.33) * 10
        if b.get("impacto") and lt < 0.6:
            k = (0.6 - lt) / 0.6; dx += math.sin(t * 70) * 18 * k; dy += math.cos(t * 63) * 18 * k; z += 0.05 * k
        if b["cena"] in ("interior", "corredor", "banco", "motorista", "teo_corredor", "mae", "painel"):
            c.translate(W / 2, H / 2); c.rotate(math.sin(t * 1.6) * 0.008); c.translate(-W / 2, -H / 2)
        c.translate(W / 2 + dx, H / 2 + dy); c.scale(z, z); c.translate(-W / 2, -H / 2)
        CENAS[b["cena"]](c, lt, T, t, b.get("emocao", {}))
        c.identity_matrix()
        # vinheta
        g = cairo.RadialGradient(W / 2, H / 2, W * 0.35, W / 2, H / 2, H * 0.75); g.add_color_stop_rgba(0, 0, 0, 0, 0); g.add_color_stop_rgba(1, 0, 0, 0, 0.75)
        c.set_source(g); c.paint()
        # grão
        c.save(); c.scale(2, 2); c.set_source_surface(graos[f % 3], 0, 0); c.paint(); c.restore()
        # corte: flash
        if 0 <= t - b["_ini"] < 0.1 and b is not blocos[0]:
            c.set_source_rgba(0, 0, 0, 1 - (t - b["_ini"]) / 0.1); c.paint()
        # selo
        fonte(c, 34); s = rot.get("serie", "").upper(); c.move_to(W / 2 - lw_(c, s) / 2, 140)
        c.text_path(s); c.set_source_rgb(0, 0, 0); c.set_line_width(6); c.stroke()
        c.set_source_rgb(*LAR); c.move_to(W / 2 - lw_(c, s) / 2, 140); c.show_text(s)
        # título
        tq = t - (blocos[rot["titulo_no_bloco"]]["_ini"] if "titulo_no_bloco" in rot else 0)
        if 0 <= tq < 2.8 and rot.get("titulo"):
            al = clamp(tq / 0.2) * clamp((2.8 - tq) / 0.3)
            fonte(c, 132, "ExtraBold"); ls = rot["titulo"].split("\n")
            for j, l in enumerate(ls):
                p = eback((tq - j * 0.15) / 0.45); c.save(); c.translate(W / 2, 480 + j * 150); c.scale(p, p)
                c.move_to(-lw_(c, l) / 2, 0); c.text_path(l); c.set_source_rgba(0.02, 0.02, 0.04, al); c.set_line_width(18); c.set_line_join(cairo.LINE_JOIN_ROUND); c.stroke()
                c.move_to(-lw_(c, l) / 2, 0); c.set_source_rgba(*LAR, al); c.show_text(l); c.restore()
        if b["_ini"] - 0.05 <= t <= b["_ini"] + b["_dur"] + 0.25: legenda(t, b)

    base = os.path.splitext(saida)[0]
    if previas:
        os.makedirs(base + "_previas", exist_ok=True); lst = []
        for i, b in enumerate(blocos + [None]):
            tt = (b["_ini"] + b["_dur"] * 0.75) if b else fim + 1.5
            desenhar(int(tt * FPS)); p = os.path.join(base + "_previas", f"p{i:02d}.png"); surf.write_to_png(p); lst.append(p)
        cols = 5; ent = sum([["-i", x] for x in lst], [])
        fl = "".join(f"[{i}:v]scale=216:-1[s{i}];" for i in range(len(lst))) + "".join(f"[s{i}]" for i in range(len(lst)))
        fl += f"xstack=inputs={len(lst)}:layout=" + "|".join(f"{(i % cols) * 216}_{(i // cols) * 384}" for i in range(len(lst))) + ":fill=black"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ent + ["-filter_complex", fl, "-frames:v", "1", base + "_previas/folha.jpg"], check=True)
        print("prévias:", base + "_previas/folha.jpg"); return

    tmpv = base + ".v.mp4"
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M", "-profile:v", "main", "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
    for f in range(nfr):
        desenhar(f); surf.flush(); pr.stdin.write(bytes(surf.get_data()))
        if f == int(1.2 * FPS): surf.write_to_png(base + "_capa.png")
        if f % 300 == 0: print(f"  quadro {f}/{nfr}", flush=True)
    pr.stdin.close(); pr.wait()
    n = int(total * SR) + SR; mx = np.zeros(n, np.float32)
    for b, v in zip(blocos, vozes):
        if v is not None: s = int(b["_ini"] * SR); mx[s:s + len(v)] += v
    mx += trilha(n)
    w, bm, ck = whoosh(), boom(), clique()
    for b in blocos[1:]:
        s = int((b["_ini"] - 0.15) * SR); mx[s:s + len(w)] += w[:n - s]
    for b in blocos:
        if b.get("impacto"): s = int(max(0, b["_ini"] - 0.05) * SR); mx[s:s + len(bm)] += bm[:n - s]
        if b["cena"] == "catraca" and not b.get("emocao", {}).get("fixo"):
            T = b["_fim"] - b["_ini"]; s = int((b["_ini"] + T * 0.45 + 0.3) * SR); mx[s:s + len(ck)] += ck[:n - s]
    mx = (mx / max(1.0, np.abs(mx).max() / 0.85) * 32767).astype(np.int16)[: int(total * SR)]
    wv = base + ".a.wav"
    with wave.open(wv, "wb") as wf: wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(mx.tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmpv, "-i", wv, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", saida], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base + "_capa.png", "-q:v", "3", base + "_capa.jpg"], check=True)
    for p in (tmpv, wv, base + "_capa.png"): os.remove(p)
    print("pronto:", saida, f"{total:.1f}s")

if __name__ == "__main__":
    main()
