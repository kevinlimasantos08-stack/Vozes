#!/usr/bin/env python3
"""reel2d — gera reels 2D recortados (1080x1920) a partir de um roteiro JSON.

Uso:
  python3 -I reel2d.py roteiro.json saida.mp4 [--assets DIR] [--preview] [--audios PASTA] [--audio-unico ARQ]

  --audios PASTA     usa vozes prontas: o arquivo que começa com o número da fala (01_, 02_...) vai para ela
  --audio-unico ARQ  um arquivo com todas as falas na ordem, separadas por ~1 s de silêncio
  --blocos PASTA     um arquivo por bloco (cena1.wav, cena2.wav...); cada um é cortado nas falas do seu bloco

Dependências: kokoro-onnx, soundfile, numpy, pillow, ffmpeg (com rubberband, opcional).
Assets (DIR, padrão ~/.reel2d): kokoro.onnx, voices.bin, Jost.ttf, Italiana.ttf
"""
import json, math, os, random, subprocess, sys, tempfile, unicodedata, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

OUT_W, OUT_H, FPS = 1080, 1920, 30
S = 1.5                                 # escala do palco em relação à saída
SC_W, SC_H = int(OUT_W * S), int(OUT_H * S)   # 1620 x 2880
FLOOR_Y = 2440                          # linha dos pés no palco
SR = 24000

# ------------------------------------------------------------------ paletas
MODOS = {
    "advocacia": {
        "destaque": (217, 196, 163),      # champanhe #D9C4A3
        "texto": (245, 241, 234),         # marfim
        "contorno": (11, 11, 11),
        "noite": False, "grao": 0.035, "vinheta": 0.45, "pilula": True,
        "trilha": "pad",
    },
    "ficcao": {
        "destaque": (255, 149, 41),       # laranja
        "texto": (255, 255, 255),
        "contorno": (10, 10, 14),
        "noite": True, "grao": 0.06, "vinheta": 0.65, "pilula": False,
        "trilha": "drone",
    },
}

# ------------------------------------------------------------------ elencos fixos
ELENCOS = {
    "advocacia": {
        "rafael": dict(nome="DR. RAFAEL", voz="pm_alex", vel=1.02, tom=0.0, pele="#C99470", cabelo="#1F1A16",
                       estilo_cabelo="curto", barba=True, roupa="#17171A", detalhe="#D9C4A3", calca="#1E1E22",
                       estilo_roupa="terno", etiqueta="#D9C4A3", oculos=False, altura=1.0),
        "rosa": dict(nome="ROSA", voz="pf_dora", vel=1.0, tom=0.0, pele="#8D5A3B", cabelo="#2A1A12",
                     estilo_cabelo="cacheado", barba=False, roupa="#3E7C74", detalhe="#F2E6D0", calca="#2F3A4A",
                     estilo_roupa="blusa", etiqueta="#5FB3A8", oculos=False, altura=0.96),
        "jorge": dict(nome="SEU JORGE", voz="pm_santa", vel=0.92, tom=-2.0, pele="#B07A55", cabelo="#BDBDBD",
                      estilo_cabelo="grisalho", barba=False, roupa="#7A5C3E", detalhe="#E8DCC6", calca="#3B3B3B",
                      estilo_roupa="camisa", etiqueta="#C9A26B", oculos=True, altura=0.97),
        "marcos": dict(nome="MARCOS", voz="pm_santa", vel=1.05, tom=1.0, pele="#E0B08C", cabelo="#4A3423",
                       estilo_cabelo="curto", barba=False, roupa="#2C4A7A", detalhe="#C23B3B", calca="#232B38",
                       estilo_roupa="terno", etiqueta="#6E95D6", oculos=False, altura=1.03),
        "bia": dict(nome="BIA", voz="pf_dora", vel=1.08, tom=2.0, pele="#E6B996", cabelo="#7A3E1C",
                    estilo_cabelo="rabo", barba=False, roupa="#B8476A", detalhe="#F5D0DA", calca="#3A4D6B",
                    estilo_roupa="blusa", etiqueta="#E07A9A", oculos=False, altura=0.93),
        "narrador": dict(nome="", voz="pm_santa", vel=1.0, tom=0.0, invisivel=True),
    },
    "ficcao": {
        "lurdes": dict(nome="DONA LURDES", voz="pf_dora", vel=0.9, tom=-1.5, pele="#D8A98A", cabelo="#D9D9D9",
                       estilo_cabelo="coque", barba=False, roupa="#5B3F7A", detalhe="#E8E0D0", calca="#2E2A33",
                       estilo_roupa="cardigan", etiqueta="#C77DDB", oculos=True, altura=0.95),
        "caio": dict(nome="CAIO", voz="pm_alex", vel=1.04, tom=0.5, pele="#9C6644", cabelo="#151515",
                     estilo_cabelo="curto", barba=False, roupa="#3D6FA8", detalhe="#DDE6F0", calca="#24262B",
                     estilo_roupa="camisa", etiqueta="#5C9BE0", oculos=False, altura=1.0),
        "nina": dict(nome="NINA", voz="pf_dora", vel=1.1, tom=3.0, pele="#E3B48F", cabelo="#3B2414",
                     estilo_cabelo="longo", barba=False, roupa="#2F7A4E", detalhe="#F2E9D8", calca="#5A3D2B",
                     estilo_roupa="blusa", etiqueta="#4FC27D", oculos=False, altura=0.97),
        "bento": dict(nome="SEU BENTO", voz="pm_santa", vel=0.94, tom=-1.5, pele="#7A4E33", cabelo="#2B2B2B",
                      estilo_cabelo="careca", barba=True, roupa="#6B6B3A", detalhe="#D8D2B0", calca="#2F2F2F",
                      estilo_roupa="uniforme", etiqueta="#C9C24F", oculos=False, altura=1.04),
        "narrador": dict(nome="", voz="pm_santa", vel=0.97, tom=-1.0, invisivel=True),
    },
}

def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + (c[3] if len(c) > 3 else 255,)

# ------------------------------------------------------------------ desenho dos personagens
K = 2  # supersampling dos sprites
CW, CH = 560, 1300       # canvas do corpo (escala do palco)
HW, HH = 380, 400        # canvas da cabeça
HEAD_ANCHOR = (280, 300) # onde o centro da cabeça cai no canvas do corpo
PAD = 260                # folga lateral para o braço levantado

class Boneco:
    def __init__(self, cid, spec, noite):
        self.id, self.spec = cid, spec
        self.noite = noite
        self.pele = hexc(spec["pele"]); self.cab = hexc(spec["cabelo"])
        self.roupa = hexc(spec["roupa"]); self.det = hexc(spec["detalhe"]); self.calca = hexc(spec["calca"])
        self.ol = (24, 20, 22, 255)
        self.esc = spec.get("altura", 1.0)
        self.corpo = self._grade(self._corpo())
        self.braco_d = self._grade(self._braco())
        self._cache = {}

    def _grade(self, im):
        if not self.noite:
            return im
        r, g, b, a = im.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = ImageEnhance.Brightness(rgb).enhance(0.62)
        arr = np.asarray(rgb).astype(np.float32) * np.array([0.88, 0.95, 1.15])
        rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        out = rgb.convert("RGBA"); out.putalpha(a)
        return out

    def _canvas(self, w, h):
        im = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
        return im, ImageDraw.Draw(im)

    def _fin(self, im, w, h):
        im = im.resize((int(w * self.esc), int(h * self.esc)), Image.LANCZOS)
        return im

    def _rr(self, d, box, r, fill, ow=7):
        d.rounded_rectangle([v * K for v in box], radius=r * K, fill=self.ol)
        b = (box[0] + ow, box[1] + ow, box[2] - ow, box[3] - ow)
        d.rounded_rectangle([v * K for v in b], radius=max(1, (r - ow)) * K, fill=fill)

    def _el(self, d, box, fill, ow=7):
        d.ellipse([v * K for v in box], fill=self.ol)
        b = (box[0] + ow, box[1] + ow, box[2] - ow, box[3] - ow)
        d.ellipse([v * K for v in b], fill=fill)

    def _corpo(self):
        sp = self.spec
        im, d = self._canvas(CW, CH)
        # pernas e sapatos
        self._rr(d, (188, 820, 278, 1250), 30, self.calca)
        self._rr(d, (282, 820, 372, 1250), 30, self.calca)
        self._rr(d, (168, 1215, 280, 1290), 34, (30, 26, 26, 255))
        self._rr(d, (280, 1215, 392, 1290), 34, (30, 26, 26, 255))
        # braço esquerdo (fixo)
        self._rr(d, (112, 440, 196, 800), 40, shade(self.roupa, 0.9))
        self._el(d, (110, 770, 196, 856), self.pele)
        # pescoço
        self._rr(d, (245, 400, 315, 470), 18, shade(self.pele, 0.9))
        # tronco
        self._rr(d, (150, 430, 410, 850), 60, self.roupa)
        est = sp.get("estilo_roupa", "camisa")
        if est == "terno":
            d.polygon([(v * K) for xy in [(228, 440), (280, 560), (332, 440)] for v in xy], fill=(240, 236, 228, 255))
            d.polygon([(v * K) for xy in [(268, 470), (292, 470), (300, 660), (280, 690), (260, 660)] for v in xy], fill=self.det)
            d.line([(v * K) for xy in [(235, 445), (280, 600), (280, 840)] for v in xy], fill=shade(self.roupa, 0.6), width=6 * K)
            d.line([(v * K) for xy in [(325, 445), (280, 600)] for v in xy], fill=shade(self.roupa, 0.6), width=6 * K)
        elif est == "camisa":
            d.polygon([(v * K) for xy in [(238, 438), (280, 500), (322, 438)] for v in xy], fill=self.det)
            for yy in (540, 620, 700, 780):
                d.ellipse([(v * K) for v in (274, yy, 286, yy + 12)], fill=shade(self.roupa, 0.55))
        elif est == "blusa":
            d.arc([(v * K) for v in (232, 400, 328, 490)], 20, 160, fill=self.det, width=10 * K)
            d.rounded_rectangle([(v * K) for v in (170, 760, 390, 790)], radius=8 * K, fill=shade(self.roupa, 0.8))
        elif est == "cardigan":
            d.rectangle([(v * K) for v in (262, 440, 298, 845)], fill=self.det)
            for yy in (520, 600, 680, 760):
                d.ellipse([(v * K) for v in (300, yy, 316, yy + 16)], fill=shade(self.roupa, 0.5))
        elif est == "uniforme":
            d.rectangle([(v * K) for v in (300, 520, 380, 580)], fill=self.det)
            d.line([(v * K) for xy in [(280, 445), (280, 840)] for v in xy], fill=shade(self.roupa, 0.6), width=5 * K)
        return self._fin(im, CW, CH)

    def _braco(self):
        # braço direito em canvas próprio, pivô no ombro (topo-centro)
        im, d = self._canvas(120, 460)
        self._rr(d, (18, 10, 102, 370), 40, shade(self.roupa, 0.9))
        self._el(d, (16, 340, 104, 428), self.pele)
        return self._fin(im, 120, 460)

    def _cabeca(self, olho, boca, emo, olhar):
        sp = self.spec
        im, d = self._canvas(HW, HH)
        cx, cy = HW // 2, HH // 2 + 10
        est = sp.get("estilo_cabelo", "curto")
        # cabelo de trás
        if est == "longo":
            self._rr(d, (cx - 150, cy - 160, cx + 150, cy + 190), 90, self.cab)
        if est == "rabo":
            self._el(d, (cx + 100, cy - 60, cx + 190, cy + 120), self.cab)
        if est == "coque":
            self._el(d, (cx - 60, cy - 235, cx + 60, cy - 120), self.cab)
        # orelhas
        self._el(d, (cx - 150, cy - 20, cx - 100, cy + 50), self.pele)
        self._el(d, (cx + 100, cy - 20, cx + 150, cy + 50), self.pele)
        # rosto
        self._rr(d, (cx - 125, cy - 150, cx + 125, cy + 150), 110, self.pele)
        # bochechas (camada separada para não abrir transparência)
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
        do.ellipse([(v * K) for v in (cx - 98, cy + 30, cx - 58, cy + 62)], fill=(214, 110, 100, 70))
        do.ellipse([(v * K) for v in (cx + 58, cy + 30, cx + 98, cy + 62)], fill=(214, 110, 100, 70))
        if est == "careca":
            do.arc([(v * K) for v in (cx - 70, cy - 135, cx + 10, cy - 95)], 200, 300, fill=(255, 255, 255, 90), width=8 * K)
        im.alpha_composite(ov); d = ImageDraw.Draw(im)
        # cabelo da frente
        if est in ("curto", "rabo", "longo", "coque"):
            d.chord([(v * K) for v in (cx - 132, cy - 175, cx + 132, cy + 10)], 180, 360, fill=self.ol)
            d.chord([(v * K) for v in (cx - 125, cy - 168, cx + 125, cy + 2)], 180, 360, fill=self.cab)
            if est in ("longo", "rabo"):
                d.pieslice([(v * K) for v in (cx - 140, cy - 150, cx + 20, cy - 10)], 90, 270, fill=self.cab)
        elif est == "cacheado":
            for ang in range(160, 381, 22):
                a = math.radians(ang)
                px, py = cx + math.cos(a) * 125, cy - 40 + math.sin(a) * 120
                self._el(d, (px - 48, py - 48, px + 48, py + 48), self.cab, ow=5)
            self._el(d, (cx - 70, cy - 200, cx + 70, cy - 90), self.cab, ow=5)
        elif est == "grisalho":
            d.chord([(v * K) for v in (cx - 128, cy - 165, cx + 128, cy - 40)], 180, 360, fill=self.cab)
            self._rr(d, (cx - 132, cy - 70, cx - 108, cy + 20), 10, self.cab, ow=3)
            self._rr(d, (cx + 108, cy - 70, cx + 132, cy + 20), 10, self.cab, ow=3)
        # barba
        if sp.get("barba"):
            d.chord([(v * K) for v in (cx - 118, cy - 10, cx + 118, cy + 158)], 0, 180, fill=shade(self.cab, 1.0))
            d.ellipse([(v * K) for v in (cx - 55, cy + 50, cx + 55, cy + 100)], fill=self.pele)
        # olhos
        ex = 52; ey = cy - 5
        dx = {-1: -9, 0: 0, 1: 9}[olhar]
        for sx in (-1, 1):
            x0 = cx + sx * ex
            if olho == "aberto":
                d.ellipse([(v * K) for v in (x0 - 24, ey - 28, x0 + 24, ey + 28)], fill=(250, 250, 248, 255))
                d.ellipse([(v * K) for v in (x0 - 13 + dx, ey - 14, x0 + 13 + dx, ey + 14)], fill=(28, 22, 20, 255))
                d.ellipse([(v * K) for v in (x0 - 4 + dx, ey - 9, x0 + 3 + dx, ey - 2)], fill=(255, 255, 255, 255))
            else:
                d.line([(v * K) for xy in [(x0 - 22, ey + 4), (x0 + 22, ey + 4)] for v in xy], fill=self.ol, width=6 * K)
        # sobrancelhas: pontas internas sobem (triste/medo) ou descem (bravo)
        by = ey - 48
        incl = {"neutro": 0, "feliz": -4, "triste": 12, "bravo": -16, "surpreso": 0, "medo": 12}[emo]
        lift = {"surpreso": -14, "medo": -10}.get(emo, 0)
        browc = shade(self.cab, 0.8) if sp.get("estilo_cabelo") not in ("careca",) else (60, 45, 40, 255)
        for sx in (-1, 1):
            x0 = cx + sx * ex
            yi = by + lift - (incl if emo in ("triste", "medo") else -abs(incl) if emo == "bravo" else incl)
            yo = by + lift
            d.line([(v * K) for xy in [(x0 - sx * 26, yi), (x0 + sx * 26, yo)] for v in xy], fill=browc, width=9 * K)
        # boca
        my = cy + 78
        if boca == 0:
            if emo == "feliz":
                d.arc([(v * K) for v in (cx - 34, my - 26, cx + 34, my + 14)], 20, 160, fill=self.ol, width=7 * K)
            elif emo in ("triste", "medo"):
                d.arc([(v * K) for v in (cx - 28, my, cx + 28, my + 34)], 200, 340, fill=self.ol, width=7 * K)
            elif emo == "surpreso":
                d.ellipse([(v * K) for v in (cx - 12, my - 10, cx + 12, my + 14)], fill=(92, 30, 34, 255))
            else:
                d.line([(v * K) for xy in [(cx - 26, my), (cx + 26, my)] for v in xy], fill=self.ol, width=7 * K)
        else:
            w = [0, 22, 28, 32][boca]; h = [0, 12, 24, 36][boca]
            d.ellipse([(v * K) for v in (cx - w, my - h // 2, cx + w, my + h // 2 + 6)], fill=self.ol)
            d.ellipse([(v * K) for v in (cx - w + 5, my - h // 2 + 5, cx + w - 5, my + h // 2 + 1)], fill=(110, 34, 40, 255))
            if boca >= 2:
                d.chord([(v * K) for v in (cx - w + 7, my - h // 2 + 5, cx + w - 7, my + 2)], 180, 360, fill=(250, 248, 240, 255))
        # óculos
        if sp.get("oculos"):
            for sx in (-1, 1):
                x0 = cx + sx * ex
                d.rounded_rectangle([(v * K) for v in (x0 - 38, ey - 32, x0 + 38, ey + 30)], radius=14 * K, outline=self.ol, width=7 * K)
            d.line([(v * K) for xy in [(cx - 14, ey - 6), (cx + 14, ey - 6)] for v in xy], fill=self.ol, width=6 * K)
        return self._grade(self._fin(im, HW, HH))

    def cabeca(self, olho, boca, emo, olhar):
        key = (olho, boca, emo, olhar)
        if key not in self._cache:
            self._cache[key] = self._cabeca(*key)
        return self._cache[key]

    def compor(self, olho, boca, emo, olhar, tilt, nod, gesto):
        e = self.esc
        pad = int(PAD * e)
        im = Image.new("RGBA", (self.corpo.width + 2 * pad, self.corpo.height), (0, 0, 0, 0))
        im.alpha_composite(self.corpo, (pad, 0))
        # braço direito (pivô no ombro); gesto levanta o braço para o lado
        br = self.braco_d
        ombro = (pad + int(406 * e), int(440 * e))
        piv = (br.width // 2, int(10 * e))
        ang = gesto * 62
        if abs(ang) > 0.5:
            L = br.height * 2
            sq = Image.new("RGBA", (L, L), (0, 0, 0, 0))
            sq.alpha_composite(br, (L // 2 - piv[0], L // 2 - piv[1]))
            sq = sq.rotate(ang, resample=Image.BICUBIC, center=(L // 2, L // 2))
            im.paste(sq, (ombro[0] - L // 2, ombro[1] - L // 2), sq)
        else:
            im.alpha_composite(br, (ombro[0] - piv[0], ombro[1] - piv[1]))
        hd = self.cabeca(olho, boca, emo, olhar)
        if abs(tilt) > 0.2:
            hd = hd.rotate(tilt, resample=Image.BICUBIC, center=(hd.width / 2, hd.height * 0.85))
        hx = pad + int(HEAD_ANCHOR[0] * e - hd.width / 2)
        hy = int((HEAD_ANCHOR[1] + nod) * e - hd.height / 2)
        im.alpha_composite(hd, (hx, max(0, hy)))
        return im

# ------------------------------------------------------------------ cenários
def cenario(nome, noite):
    W, H = SC_W, SC_H
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    wall_y = 2050
    def grad(c1, c2, y0, y1):
        for y in range(y0, y1, 4):
            t = (y - y0) / max(1, y1 - y0)
            c = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
            d.rectangle([0, y, W, y + 4], fill=c)
    ol = (30, 26, 26)
    if nome == "escritorio":
        grad((58, 52, 48), (40, 36, 33), 0, wall_y)
        d.rectangle([0, wall_y, W, H], fill=(74, 56, 42))
        for x in range(0, W, 180):
            d.line([x, wall_y, x - 140, H], fill=(62, 46, 34), width=6)
        # janela
        d.rectangle([120, 420, 640, 1300], fill=ol)
        grad_box = Image.new("RGB", (480, 840)); gd = ImageDraw.Draw(grad_box)
        for y in range(840):
            t = y / 840; gd.line([0, y, 480, y], fill=(int(120 + 60 * t), int(150 + 40 * t), int(190 + 20 * t)))
        for bx in range(0, 480, 70):
            hgt = random.Random(bx).randint(250, 600)
            gd.rectangle([bx, 840 - hgt, bx + 55, 840], fill=(80, 96, 120))
        im.paste(grad_box, (140, 440)); d.line([380, 440, 380, 1280], fill=ol, width=14); d.line([140, 860, 620, 860], fill=ol, width=14)
        # estante
        d.rectangle([980, 300, 1560, 1700], fill=ol); d.rectangle([996, 316, 1544, 1684], fill=(92, 66, 46))
        rng = random.Random(7)
        for sy in (330, 680, 1030, 1380):
            d.rectangle([996, sy + 300, 1544, sy + 330], fill=(70, 50, 34))
            x = 1010
            while x < 1520:
                w = rng.randint(30, 60); h = rng.randint(200, 290)
                c = rng.choice([(122, 40, 40), (40, 60, 90), (190, 160, 110), (30, 30, 30), (90, 110, 70), (217, 196, 163)])
                d.rectangle([x, sy + 300 - h, x + w, sy + 300], fill=c, outline=ol, width=3)
                x += w + 4
        # diploma
        d.rectangle([700, 500, 900, 760], fill=(142, 118, 80)); d.rectangle([720, 520, 880, 740], fill=(245, 241, 234))
        for yy in range(560, 720, 40): d.line([745, yy, 855, yy], fill=(160, 150, 130), width=5)
        # mesa ao fundo
        d.rectangle([560, 1660, 1100, 1720], fill=ol); d.rectangle([570, 1668, 1090, 1712], fill=(110, 80, 56))
    elif nome == "empresa":
        grad((200, 205, 210), (175, 180, 188), 0, wall_y)
        d.rectangle([0, wall_y, W, H], fill=(96, 100, 108))
        for x in range(60, W, 400):
            d.rectangle([x, 380, x + 330, 1650], fill=(150, 178, 196), outline=(70, 80, 90), width=10)
            d.line([x, 900, x + 330, 900], fill=(70, 80, 90), width=8)
        d.rectangle([0, 1650, W, 1700], fill=(120, 125, 132))
        for px in (300, 1300):
            d.rectangle([px, 1560, px + 120, 1700], fill=(140, 90, 60), outline=ol, width=6)
            for i in range(7):
                a = math.radians(200 + i * 22)
                d.ellipse([px + 60 + math.cos(a) * 110 - 50, 1500 + math.sin(a) * 140 - 50, px + 60 + math.cos(a) * 110 + 50, 1500 + math.sin(a) * 140 + 50], fill=(60, 120, 70), outline=ol, width=4)
        d.rectangle([560, 160, 1060, 300], fill=(40, 46, 56))
    elif nome == "rua":
        grad((150, 186, 220), (220, 200, 180), 0, 1500)
        rng = random.Random(3); x = -40
        while x < W:
            w = rng.randint(260, 420); h = rng.randint(900, 1500)
            c = rng.choice([(176, 140, 120), (150, 156, 170), (196, 176, 140), (130, 120, 130)])
            d.rectangle([x, wall_y - h, x + w, wall_y], fill=c, outline=ol, width=8)
            for wy in range(wall_y - h + 80, wall_y - 160, 170):
                for wx in range(x + 40, x + w - 80, 110):
                    d.rectangle([wx, wy, wx + 70, wy + 100], fill=(90, 110, 140), outline=ol, width=4)
            x += w + 10
        d.rectangle([0, wall_y, W, H], fill=(160, 156, 150))
        for x in range(0, W, 220): d.line([x, wall_y, x, H], fill=(140, 136, 130), width=6)
        d.rectangle([0, 2700, W, H], fill=(70, 70, 74))
        d.rectangle([1380, 700, 1410, wall_y + 200], fill=(50, 54, 60)); d.ellipse([1330, 640, 1460, 730], fill=(250, 230, 160), outline=ol, width=6)
    elif nome == "padaria":
        grad((236, 222, 196), (226, 210, 182), 0, 1300)
        for y in range(1300, wall_y, 90):
            for x in range(0, W, 90):
                d.rectangle([x, y, x + 90, y + 90], fill=(242, 242, 236), outline=(200, 200, 194), width=3)
        d.rectangle([0, wall_y, W, H], fill=(120, 74, 58))
        for x in range(0, W, 120):
            for y in range(wall_y, H, 120):
                if (x // 120 + y // 120) % 2 == 0: d.rectangle([x, y, x + 120, y + 120], fill=(104, 64, 50))
        d.rectangle([200, 260, 1420, 470], fill=(170, 46, 40), outline=ol, width=10)
        d.rectangle([150, 1500, 1470, 1640], fill=(140, 96, 64), outline=ol, width=8)
        rng = random.Random(5)
        for x in range(220, 1420, 150):
            d.ellipse([x, 1400, x + 120, 1500], fill=rng.choice([(214, 160, 90), (196, 130, 70), (230, 190, 120)]), outline=ol, width=5)
        d.rectangle([260, 620, 1360, 1000], fill=(46, 52, 48), outline=ol, width=10)
        for yy in range(680, 960, 70): d.line([310, yy, 900, yy], fill=(220, 220, 210), width=6); d.line([1150, yy, 1300, yy], fill=(220, 220, 210), width=6)
    elif nome in ("quarto", "sala"):
        grad((150, 140, 160) if nome == "quarto" else (196, 176, 150), (120, 110, 130) if nome == "quarto" else (176, 154, 128), 0, wall_y)
        d.rectangle([0, wall_y, W, H], fill=(120, 86, 62))
        for x in range(0, W, 160): d.line([x, wall_y, x, H], fill=(104, 74, 52), width=5)
        d.rectangle([560, 300, 1060, 1050], fill=ol); d.rectangle([576, 316, 1044, 1034], fill=(40, 52, 90))
        d.ellipse([860, 380, 980, 500], fill=(240, 236, 210)); d.line([810, 316, 810, 1034], fill=ol, width=12); d.line([576, 680, 1044, 680], fill=ol, width=12)
        d.rectangle([500, 260, 1120, 300], fill=(90, 70, 60))
        if nome == "sala":
            d.rectangle([120, 600, 420, 1000], fill=(142, 118, 80), outline=ol, width=8); d.rectangle([150, 630, 390, 970], fill=(110, 150, 120))
            d.ellipse([200, 2500, 1420, 2800], fill=(150, 70, 60), outline=ol, width=6)
        else:
            d.rectangle([140, 640, 380, 960], fill=(142, 118, 80), outline=ol, width=8); d.rectangle([166, 666, 354, 934], fill=(200, 170, 190))
    elif nome == "fachada":  # frente da casa 47, queimada e fechada
        grad((40, 44, 70), (70, 62, 84), 0, 900)
        d.ellipse([1230, 180, 1390, 340], fill=(240, 236, 210))
        d.rectangle([0, 900, W, wall_y], fill=(150, 136, 120))
        for x in range(0, W, 120):
            for y in range(900, wall_y, 60):
                d.rectangle([x + (60 if (y // 60) % 2 else 0), y, x + 120 + (60 if (y // 60) % 2 else 0), y + 60], outline=(132, 118, 104), width=3)
        d.polygon([(-40, 900), (W // 2, 420), (W + 40, 900)], fill=(70, 40, 34), outline=ol)
        rng = random.Random(47)
        for _ in range(22):  # fuligem
            x = rng.randint(0, W); y = rng.randint(900, 1500); r = rng.randint(60, 200)
            d.ellipse([x - r, y - r // 2, x + r, y + r], fill=(112, 100, 90))
        d.rectangle([600, 1150, 1020, wall_y], fill=ol); d.rectangle([616, 1166, 1004, wall_y], fill=(86, 56, 40))
        for yy in (1260, 1560, 1860): d.rectangle([650, yy, 970, yy + 220], outline=(64, 40, 28), width=8)
        d.ellipse([930, 1620, 970, 1660], fill=(200, 170, 90), outline=ol, width=4)
        d.rectangle([925, 1680, 975, 1720], fill=(150, 130, 70), outline=ol, width=4)
        d.rounded_rectangle([700, 1010, 920, 1120], radius=14, fill=(230, 222, 200), outline=ol, width=8)
        f47 = ImageFont.truetype(os.path.expanduser("~/.reel2d/Jost.ttf"), 90)
        d.text((810, 1065), "47", font=f47, fill=(40, 30, 28), anchor="mm")
        for wx in (140, 1180):
            d.rectangle([wx, 1150, wx + 300, 1600], fill=ol); d.rectangle([wx + 16, 1166, wx + 284, 1584], fill=(20, 18, 22))
            for k in range(4): d.rectangle([wx - 10, 1200 + k * 100, wx + 310, 1240 + k * 100], fill=(110, 84, 60), outline=ol, width=4)
        d.rectangle([0, wall_y, W, H], fill=(70, 72, 70))
        d.rectangle([520, wall_y, 1100, wall_y + 90], fill=(110, 100, 92), outline=ol, width=6)
    elif nome == "queimado":  # quarto antigo da Nina, queimado, com o desenho de giz
        grad((70, 60, 56), (46, 40, 38), 0, wall_y)
        rng = random.Random(6)
        for _ in range(40):
            x = rng.randint(0, W); y = rng.randint(0, wall_y); r = rng.randint(80, 260)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(52, 44, 42))
        d.rectangle([0, wall_y, W, H], fill=(54, 40, 32))
        for x in range(0, W, 160): d.line([x, wall_y, x - 60, H], fill=(36, 26, 22), width=7)
        d.rectangle([1180, 300, 1520, 900], fill=ol); d.rectangle([1196, 316, 1504, 884], fill=(36, 46, 84))
        d.line([1196, 316, 1504, 884], fill=(120, 130, 160), width=4); d.line([1350, 316, 1260, 884], fill=(120, 130, 160), width=3)
        # parede limpa onde o Caio tirou a fuligem
        d.rounded_rectangle([250, 560, 1050, 1240], radius=60, fill=(150, 138, 128))
        cg = (240, 240, 230); fo = (255, 120, 40); am = (255, 210, 60)
        d.rectangle([450, 820, 760, 1060], outline=cg, width=10); d.polygon([(420, 830), (605, 680), (790, 830)], outline=cg, width=10)
        d.line([420, 830, 605, 680, 790, 830], fill=cg, width=10)
        d.rectangle([570, 940, 640, 1060], outline=cg, width=8)
        for fx, fh in ((470, 170), (560, 230), (650, 200), (740, 150)):
            d.polygon([(fx - 40, 830), (fx, 830 - fh), (fx + 40, 830)], outline=fo, width=9)
            d.line([fx - 20, 830, fx, 830 - fh * 0.55, fx + 20, 830], fill=am, width=7)
        d.ellipse([820, 900, 880, 960], outline=cg, width=8); d.line([850, 960, 850, 1060], fill=cg, width=8)
        d.line([850, 990, 815, 1030], fill=cg, width=8); d.line([850, 990, 885, 1030], fill=cg, width=8)
        fg = ImageFont.truetype(os.path.expanduser("~/.reel2d/Jost.ttf"), 78)
        d.text((650, 1125), "DESCULPA VÓ", font=fg, fill=(235, 40, 60), anchor="mm")
        d.text((650, 1205), "- NINA", font=fg, fill=(235, 40, 60), anchor="mm")
        d.rectangle([60, 1700, 420, 2060], fill=(40, 32, 28), outline=ol, width=6)
        d.line([60, 1700, 420, 2060], fill=(26, 20, 18), width=10)
    else:  # casa
        grad((196, 176, 150), (176, 154, 128), 0, wall_y)
        d.rectangle([0, wall_y, W, H], fill=(140, 100, 70))
        for x in range(0, W, 160): d.line([x, wall_y, x, H], fill=(124, 88, 60), width=5)
        d.rectangle([180, 400, 760, 1200], fill=ol); d.rectangle([196, 416, 744, 1184], fill=(140, 180, 210))
        d.rectangle([120, 360, 330, 1300], fill=(170, 60, 60), outline=ol, width=6); d.rectangle([610, 360, 820, 1300], fill=(170, 60, 60), outline=ol, width=6)
        d.rounded_rectangle([900, 1420, 1580, 1900], radius=60, fill=(70, 96, 120), outline=ol, width=8)
        d.rectangle([1000, 600, 1400, 900], fill=(142, 118, 80), outline=ol, width=8); d.rectangle([1030, 630, 1370, 870], fill=(110, 150, 120))
        d.rectangle([300, 1500, 330, 2000], fill=(60, 60, 60)); d.polygon([(230, 1500), (400, 1500), (360, 1380), (270, 1380)], fill=(240, 220, 170), outline=ol)
    # sombra do chão
    d.rectangle([0, wall_y - 8, W, wall_y + 8], fill=(30, 26, 24))
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    if noite:
        im = ImageEnhance.Brightness(im).enhance(0.45)
        arr = np.asarray(im).astype(np.float32) * np.array([0.8, 0.9, 1.2])
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        luz = {"queimado": (650, 900, 620, 520, 2.1), "fachada": (810, 1300, 700, 900, 1.8)}.get(nome)
        if luz:  # lanterna / luz da varanda
            lx, ly, rx, ry, k = luz
            yy, xx = np.mgrid[0:H, 0:W]
            m = np.clip(1.25 - np.sqrt(((xx - lx) / rx) ** 2 + ((yy - ly) / ry) ** 2), 0, 1)
            m = (m * m * (3 - 2 * m)).astype(np.float32)[..., None]
            arr = np.asarray(im).astype(np.float32)
            arr = arr * (1 + (k - 1) * m) + np.array([18, 14, 6]) * m
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return im

# ------------------------------------------------------------------ móveis para poses
SEAT_Y, HEADY = 1990, 1690
def escurecer(im, noite):
    if not noite: return im
    r, g, b, a = im.split(); rgb = ImageEnhance.Brightness(Image.merge("RGB", (r, g, b))).enhance(0.62)
    arr = np.asarray(rgb).astype(np.float32) * np.array([0.88, 0.95, 1.15])
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA"); out.putalpha(a); return out

def moveis(lay, poses, bonecos, noite, vazias=()):
    """Devolve (camada de trás, camada da frente) para camas e sofá."""
    tr = Image.new("RGBA", (SC_W, SC_H), (0, 0, 0, 0)); fr = Image.new("RGBA", (SC_W, SC_H), (0, 0, 0, 0))
    dt, df = ImageDraw.Draw(tr), ImageDraw.Draw(fr); ol = (24, 20, 22, 255)
    cob = [(70, 120, 95, 255), (70, 90, 150, 255), (150, 90, 120, 255)]
    camas = [x for cid, x in lay if poses.get(cid) == "deitado"]
    for i, (cid, x) in enumerate(lay):
        if poses.get(cid) != "deitado": continue
        dt.rounded_rectangle([x - 255, 1420, x + 255, 2000], radius=50, fill=ol); dt.rounded_rectangle([x - 243, 1432, x + 243, 1988], radius=44, fill=(116, 76, 50, 255))
        dt.rounded_rectangle([x - 210, 1470, x + 210, 1540], radius=20, fill=(96, 62, 40, 255))
        dt.ellipse([x - 200, 1590, x + 200, 1800], fill=ol); dt.ellipse([x - 192, 1598, x + 192, 1792], fill=(236, 232, 224, 255))
        c = cob[i % len(cob)]
        df.rounded_rectangle([x - 262, 1805, x + 262, 2390], radius=70, fill=ol); df.rounded_rectangle([x - 254, 1813, x + 254, 2382], radius=64, fill=c)
        df.rounded_rectangle([x - 254, 1813, x + 254, 1880], radius=30, fill=tuple(min(255, int(v * 1.25)) for v in c[:3]) + (255,))
        df.line([x - 150, 1990, x - 90, 2300], fill=tuple(int(v * 0.8) for v in c[:3]) + (255,), width=8)
        df.line([x + 120, 1960, x + 170, 2320], fill=tuple(int(v * 0.8) for v in c[:3]) + (255,), width=8)
        df.rounded_rectangle([x - 270, 2330, x + 270, 2450], radius=24, fill=ol); df.rounded_rectangle([x - 262, 2338, x + 262, 2442], radius=20, fill=(116, 76, 50, 255))
    for x in vazias:
        dt.rounded_rectangle([x - 255, 1420, x + 255, 2000], radius=50, fill=ol); dt.rounded_rectangle([x - 243, 1432, x + 243, 1988], radius=44, fill=(116, 76, 50, 255))
        dt.ellipse([x - 200, 1590, x + 200, 1800], fill=ol); dt.ellipse([x - 192, 1598, x + 192, 1792], fill=(236, 232, 224, 255))
        dt.rounded_rectangle([x - 262, 1880, x + 262, 2390], radius=60, fill=ol); dt.rounded_rectangle([x - 254, 1888, x + 254, 2382], radius=54, fill=(70, 90, 150, 255))
        dt.polygon([(x - 254, 1900), (x + 60, 1900), (x - 120, 2060)], fill=(52, 68, 118, 255))
        dt.rounded_rectangle([x - 270, 2330, x + 270, 2450], radius=24, fill=ol); dt.rounded_rectangle([x - 262, 2338, x + 262, 2442], radius=20, fill=(116, 76, 50, 255))
        camas.append(x)
    if len(camas) >= 2:
        mx = (camas[0] + camas[1]) / 2
        dt.rectangle([mx - 34, 1900, mx + 34, 2440], fill=ol); dt.rectangle([mx - 28, 1910, mx + 28, 2430], fill=(100, 70, 50, 255))
        dt.polygon([(mx - 30, 1700), (mx + 30, 1700), (mx + 20, 1630), (mx - 20, 1630)], fill=(240, 210, 150, 255)); dt.rectangle([mx - 8, 1700, mx + 8, 1900], fill=(60, 60, 60, 255))
    sent = [x for cid, x in lay if poses.get(cid) == "sentado"]
    if sent:
        x0, x1 = min(sent) - 340, max(sent) + 340
        sofa, sofa2 = (128, 62, 58, 255), (104, 48, 46, 255)
        dt.rounded_rectangle([x0, 1500, x1, 2010], radius=80, fill=ol); dt.rounded_rectangle([x0 + 10, 1510, x1 - 10, 2000], radius=72, fill=sofa)
        for x in sent: dt.rounded_rectangle([x - 260, 1560, x + 260, 1980], radius=60, fill=sofa2)
        df.rounded_rectangle([x0 - 20, 1960, x1 + 20, 2330], radius=50, fill=ol); df.rounded_rectangle([x0 - 10, 1970, x1 + 10, 2320], radius=44, fill=sofa)
        df.rounded_rectangle([x0 - 10, 1970, x1 + 10, 2070], radius=40, fill=tuple(min(255, int(v * 1.2)) for v in sofa[:3]) + (255,))
        for ax in (x0 - 110, x1 - 40):
            df.rounded_rectangle([ax, 1720, ax + 150, 2340], radius=60, fill=ol); df.rounded_rectangle([ax + 10, 1730, ax + 140, 2330], radius=54, fill=sofa2)
        for cid, x in lay:
            if poses.get(cid) != "sentado": continue
            b = bonecos[cid]; e = b.esc; cl = b.calca
            df.rounded_rectangle([x - 100 * e, 1985, x + 100 * e, 2095], radius=40, fill=ol); df.rounded_rectangle([x - 92 * e, 1993, x + 92 * e, 2087], radius=36, fill=cl)
            for sx in (-1, 1):
                df.rounded_rectangle([x + sx * 50 * e - 40 * e, 2070, x + sx * 50 * e + 40 * e, 2400], radius=26, fill=ol)
                df.rounded_rectangle([x + sx * 50 * e - 33 * e, 2077, x + sx * 50 * e + 33 * e, 2393], radius=22, fill=cl)
                df.rounded_rectangle([x + sx * 50 * e - 56 * e, 2380, x + sx * 50 * e + 56 * e, 2445], radius=26, fill=(30, 26, 26, 255))
    return escurecer(tr, noite), escurecer(fr, noite)

def pose_de(cena, cid):
    p = cena.get("pose")
    return p.get(cid) if isinstance(p, dict) else p

def cabeca_y(cena, cid, esc):
    p = pose_de(cena, cid)
    if p == "deitado": return HEADY - 120 * esc
    if p == "sentado": return SEAT_Y - 830 * esc + 300 * esc
    return FLOOR_Y - CH * esc + 300 * esc

# ------------------------------------------------------------------ áudio
def dividir_audio_unico(arq, n, tmp, pref="u"):
    """Corta um arquivo com todas as falas em n pedaços, nos n-1 silêncios mais longos."""
    import soundfile as sf
    w = os.path.join(tmp, pref + "_todo.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", arq, "-ac", "1", "-ar", str(SR), w], check=True)
    a, _ = sf.read(w, dtype="float32")
    hop = int(SR * 0.02); rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a), hop)])
    quieto = rms < max(0.01, rms.max() * 0.04)
    trechos, ini = [], None
    for j, q in enumerate(quieto):
        if q and ini is None: ini = j
        if not q and ini is not None:
            if ini > 0: trechos.append((j - ini, ini, j))
            ini = None
    cortes = sorted(sorted(trechos, reverse=True)[: n - 1], key=lambda x: x[1])
    if len(cortes) < n - 1:
        sys.exit(f"Achei só {len(cortes) + 1} falas no áudio único, mas o roteiro tem {n}.")
    pts = [0] + [((c[1] + c[2]) // 2) * hop for c in cortes] + [len(a)]
    saidas = []
    for i in range(n):
        q = os.path.join(tmp, f"{pref}{i}.wav"); sf.write(q, a[pts[i]:pts[i + 1]], SR); saidas.append(q)
    return saidas

def sintetizar(falas, elenco, assets, tmp):
    import soundfile as sf
    k = None
    tem_rb = b"rubberband" in subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True).stdout
    out = []
    for i, f in enumerate(falas):
        sp = elenco[f["quem"]]
        if f.get("audio"):
            # voz pronta (ElevenLabs, Manus, gravação): usa o arquivo como está
            p = os.path.join(tmp, f"f{i}.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f["audio"], "-af", "adeclip,highpass=f=70,lowpass=f=11000,silenceremove=start_periods=1:start_threshold=-42dB:stop_periods=-1:stop_threshold=-42dB:stop_duration=0.2:stop_silence=0.12" + (f",atempo={f['_atempo']}" if f.get("_atempo", 1) != 1 else ""), "-ac", "1", "-ar", str(SR), p], check=True)
            a, _ = sf.read(p, dtype="float32")
            idx = np.where(np.abs(a) > 0.01)[0]
            if len(idx): a = a[max(0, idx[0] - 600): idx[-1] + 1200]
            a = a / (np.abs(a).max() + 1e-6) * 0.8; fd = int(0.012 * SR)
            if len(a) > 2 * fd: a[:fd] *= np.linspace(0, 1, fd); a[-fd:] *= np.linspace(1, 0, fd)
            out.append(a)
            continue
        if k is None:
            from kokoro_onnx import Kokoro
            k = Kokoro(os.path.join(assets, "kokoro.onnx"), os.path.join(assets, "voices.bin"))
        texto = f.get("fala_tts") or f["texto"]
        s, sr = k.create(texto, voice=sp["voz"], speed=sp.get("vel", 1.0), lang="pt-br")
        p = os.path.join(tmp, f"f{i}.wav"); sf.write(p, s, sr)
        tom = sp.get("tom", 0.0)
        if abs(tom) > 0.05:
            q = os.path.join(tmp, f"f{i}_t.wav")
            if tem_rb:
                af = f"rubberband=pitch={2 ** (tom / 12):.5f}:formant=preserved"
            else:
                r = 2 ** (tom / 12); af = f"asetrate={int(SR * r)},aresample={SR},atempo={1 / r:.5f}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-af", af, "-ar", str(SR), q], check=True)
            p = q
        a, _ = sf.read(p, dtype="float32")
        if a.ndim > 1: a = a.mean(axis=1)
        # apara silêncio das pontas
        idx = np.where(np.abs(a) > 0.01)[0]
        if len(idx): a = a[max(0, idx[0] - 600): idx[-1] + 1200]
        a = a / (np.abs(a).max() + 1e-6) * 0.92
        out.append(a)
    return out

def envelope(a, n_frames):
    hop = SR / FPS
    env = np.zeros(n_frames)
    for j in range(n_frames):
        seg = a[int(j * hop): int((j + 1) * hop)]
        env[j] = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
    m = env.max() + 1e-6
    return env / m

def sfx_whoosh(dur=0.32, seed=0):
    rng = np.random.default_rng(seed); n = int(SR * dur)
    x = rng.standard_normal(n).astype(np.float32)
    y = np.zeros(n, np.float32); acc = 0.0
    for i in range(n):
        a = 0.02 + 0.25 * (i / n)
        acc += a * (x[i] - acc); y[i] = acc
    env = np.sin(np.linspace(0, math.pi, n)) ** 2
    return y * env * 0.5

def sfx_pop():
    t = np.linspace(0, 0.12, int(SR * 0.12))
    return (np.sin(2 * math.pi * (600 - 2500 * t) * t) * np.exp(-t * 40) * 0.5).astype(np.float32)

def sfx_boom():
    t = np.linspace(0, 1.2, int(SR * 1.2))
    return (np.sin(2 * math.pi * (60 - 20 * t) * t) * np.exp(-t * 3.5) * 0.9).astype(np.float32)

def sfx_chime():
    t = np.linspace(0, 1.6, int(SR * 1.6))
    return ((np.sin(2 * math.pi * 880 * t) + 0.5 * np.sin(2 * math.pi * 1318.5 * t)) * np.exp(-t * 3) * 0.25).astype(np.float32)

def trilha(tipo, n):
    t = np.arange(n) / SR
    if tipo == "pad":
        notas = [110.0, 164.81, 220.0, 261.63, 329.63]
        x = sum(np.sin(2 * math.pi * f * t + i) * (0.6 + 0.4 * np.sin(2 * math.pi * 0.07 * t + i)) for i, f in enumerate(notas))
        x = x / len(notas) * 0.06
    else:
        x = (np.sin(2 * math.pi * 55 * t) * 0.6 + np.sin(2 * math.pi * 82.4 * t) * 0.3 + np.sin(2 * math.pi * 58.3 * t) * 0.3)
        x *= (0.7 + 0.3 * np.sin(2 * math.pi * 0.11 * t))
        x = x * 0.09
    fade = int(SR * 1.0)
    x[:fade] *= np.linspace(0, 1, fade); x[-fade:] *= np.linspace(1, 0, fade)
    return x.astype(np.float32)

# ------------------------------------------------------------------ alinhamento
def silabas_w(w):
    n = len(re.findall(r"[aeiouáéíóúâêôãõàAEIOUÁÉÍÓÚÂÊÔÃÕyY]+", w))
    if re.search(r"\d", w): n = max(n, len(re.sub(r"\D", "", w)) * 2)
    return max(1, n)

def alinhar(a, texto):
    """Tempo (início, fim) de cada palavra, distribuindo as sílabas só pelos trechos em que há voz."""
    ws = texto.split(); hop = int(SR * 0.01)
    rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, max(1, len(a) - hop), hop)]) if len(a) > hop else np.zeros(1)
    lim = max(0.012, rms.max() * 0.07); voz = rms > lim
    seg, ini = [], None
    for j, v in enumerate(voz):
        if v and ini is None: ini = j
        if not v and ini is not None: seg.append([ini, j]); ini = None
    if ini is not None: seg.append([ini, len(voz)])
    junt = []
    for sg in seg:
        if junt and sg[0] - junt[-1][1] < 12: junt[-1][1] = sg[1]
        else: junt.append(sg)
    junt = [(x * 0.01, y * 0.01) for x, y in junt if y - x >= 5] or [(0.0, len(a) / SR)]
    D = sum(y - x for x, y in junt)
    def real(pv):
        for x, y in junt:
            if pv <= y - x: return x + pv
            pv -= y - x
        return junt[-1][1]
    pesos = [silabas_w(w) for w in ws]; S = sum(pesos); acc = 0; out = []
    for w, pz in zip(ws, pesos):
        a0 = real(D * acc / S); acc += pz; a1 = real(D * acc / S - 1e-4)
        out.append((w, a0, max(a0 + 0.05, a1)))
    return out

# ------------------------------------------------------------------ legendas
def fonte(path, size, peso=None):
    f = ImageFont.truetype(path, size)
    if peso is not None:
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
    return f

def limpa(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", w)

def blocos(texto, destaques, auto):
    palavras = texto.split()
    chunks, cur = [], []
    for w in palavras:
        if cur and (len(cur) >= 3 or len(" ".join(cur + [w])) > 18):
            chunks.append(cur); cur = []
        cur.append(w)
        if w.endswith((".", "?", "!", ",", ";", ":")) and (len(cur) >= 2 or len(w) >= 6):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    dset = {limpa(x) for d in destaques for x in d.split()}
    res = []
    for c in chunks:
        marks = [limpa(w) in dset for w in c]
        if auto and not dset and not any(marks):
            cand = [(len(limpa(w)), i) for i, w in enumerate(c) if len(limpa(w)) >= 4]
            if cand: marks[max(cand)[1]] = True
        res.append(list(zip(c, marks)))
    return res

def render_bloco(bloco, cor_txt, cor_dest, cor_ol, f, pilula=False):
    pal = [(w.upper(), m) for w, m in bloco]
    esp = f.getlength(" ") + (14 if pilula else 0)
    larg = sum(f.getlength(w) for w, _ in pal) + esp * (len(pal) - 1)
    asc, desc = f.getmetrics()
    W, H = int(larg + 80), int(asc + desc + 60)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 40
    for w, m in pal:
        if m and pilula:
            bb = d.textbbox((x, 30), w, font=f)
            d.rounded_rectangle([bb[0] - 14, bb[1] - 12, bb[2] + 14, bb[3] + 14], radius=14, fill=cor_ol)
            d.rounded_rectangle([bb[0] - 10, bb[1] - 8, bb[2] + 10, bb[3] + 10], radius=12, fill=cor_dest)
            d.text((x, 30), w, font=f, fill=(11, 11, 11, 255))
        else:
            d.text((x + 4, 35), w, font=f, fill=(0, 0, 0, 150))
            d.text((x, 30), w, font=f, fill=cor_dest if m else cor_txt, stroke_width=7, stroke_fill=cor_ol)
        x += f.getlength(w) + esp
    return im

def render_fixa(texto, cor_txt, cor_ol, f, largura=20):
    import textwrap
    linhas = textwrap.wrap(texto.upper(), largura)
    asc, desc = f.getmetrics(); lh = asc + desc + 14
    W = int(max(f.getlength(l) for l in linhas)) + 100; H = lh * len(linhas) + 60
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=24, fill=(11, 11, 11, 200))
    for i, l in enumerate(linhas):
        d.text(((W - f.getlength(l)) / 2, 30 + i * lh), l, font=f, fill=cor_txt)
    return im

def render_etiqueta(nome, cor, f):
    w = int(f.getlength(nome)) + 36; asc, desc = f.getmetrics(); h = asc + desc + 16
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=cor)
    lum = 0.3 * cor[0] + 0.59 * cor[1] + 0.11 * cor[2]
    d.text((18, 6), nome, font=f, fill=(15, 15, 15) if lum > 140 else (255, 255, 255))
    return im

# ------------------------------------------------------------------ principal
def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    rot = json.load(open(args[0], encoding="utf-8"))
    saida = args[1]
    assets = os.path.expanduser("~/.reel2d")
    if "--assets" in args: assets = args[args.index("--assets") + 1]
    preview = "--preview" in args
    modo = rot.get("modo", "advocacia")
    M = MODOS[modo]
    elenco = dict(ELENCOS[modo]); elenco.update(rot.get("elenco_extra", {}))
    jost = os.path.join(assets, "Jost.ttf"); ital = os.path.join(assets, "Italiana.ttf")
    tmp = tempfile.mkdtemp(prefix="reel2d_")

    # achata falas
    falas = []
    for ci, c in enumerate(rot["cenas"]):
        for fi, f in enumerate(c["falas"]):
            if f["quem"] not in elenco:
                sys.exit(f"Personagem desconhecido: {f['quem']}")
            f = dict(f); f["_cena"] = ci; f["_primeira"] = fi == 0
            falas.append(f)

    base = os.path.dirname(os.path.abspath(args[0]))
    for f in falas: f["_atempo"] = f.get("vel_voz", rot.get("vel_voz", 1.0))
    for f in falas:
        if f.get("audio") and not os.path.isabs(f["audio"]):
            f["audio"] = os.path.join(base, f["audio"])
    if "--audios" in args:
        pasta = args[args.index("--audios") + 1]
        for nome in sorted(os.listdir(pasta)):
            m = re.match(r"(\d+)", nome)
            if m and nome.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac")):
                n = int(m.group(1))
                if 1 <= n <= len(falas): falas[n - 1]["audio"] = os.path.join(pasta, nome)
    if "--audio-unico" in args:
        partes = dividir_audio_unico(args[args.index("--audio-unico") + 1], len(falas), tmp)
        for f, q in zip(falas, partes): f["audio"] = q
    if "--blocos" in args:
        pasta = args[args.index("--blocos") + 1]
        grupos, arqs = {}, {}
        for i, f in enumerate(falas):
            grupos.setdefault(int(f.get("bloco", f["_cena"] + 1)), []).append(i)
        for nome in sorted(os.listdir(pasta)):
            m = re.search(r"(\d+)", nome)
            if m and nome.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac")):
                arqs[int(m.group(1))] = os.path.join(pasta, nome)
        for b, idxs in sorted(grupos.items()):
            if b not in arqs:
                print(f"AVISO: bloco {b} sem arquivo; essas falas vão no Kokoro", flush=True); continue
            for i, q in zip(idxs, dividir_audio_unico(arqs[b], len(idxs), tmp, f"b{b}_")): falas[i]["audio"] = q
    print("Vozes prontas: %d de %d falas" % (sum(1 for f in falas if f.get("audio")), len(falas)), flush=True)
    print("Sintetizando vozes...", flush=True)
    audios = sintetizar(falas, elenco, assets, tmp)
    for i, (f, a) in enumerate(zip(falas, audios)):
        if f.get("audio"):
            est = len((f.get("fala_tts") or f["texto"]).split()) / 2.3; dur = len(a) / SR
            if dur > 2.2 * est + 1 or dur < 0.45 * est:
                print(f"AVISO: fala {i + 1} tem {dur:.1f}s e o esperado era ~{est:.1f}s; confira se o corte do áudio está certo", flush=True)

    # linha do tempo
    t = 0.45 + rot.get("inicio", 0.0); GAP = rot.get("gap", 0.2)
    for f, a in zip(falas, audios):
        t += f.get("antes", 0.0)
        f["_t0"] = t; f["_dur"] = len(a) / SR; f["_pal"] = alinhar(a, f["texto"]); t += f["_dur"] + min(f.get("pausa", GAP), rot.get("pausa_max", 9))
    fim_falas = t
    final = rot.get("final", {})
    END = 2.4
    total = fim_falas + END
    n_frames = int(total * FPS)
    if preview: n_frames = min(n_frames, int(4 * FPS))
    print(f"Duração: {total:.1f}s ({n_frames} quadros)", flush=True)
    if not (20 <= total <= 45):
        print(f"AVISO: duração {total:.1f}s fora da faixa 20–45s", flush=True)

    # mix de áudio
    n = int(total * SR) + SR
    mix = np.zeros(n, np.float32)
    for f, a in zip(falas, audios):
        s = int(f["_t0"] * SR); mix[s:s + len(a)] += a * 0.95
    bed = trilha(M["trilha"], n); mix += bed
    batidas = [0.35] if rot.get("sfx_inicio") == "batida" else []
    batidas += [f["_t0"] - f.get("antes", 0) + 0.05 for f in falas if f.get("sfx") == "batida"]
    for tb in batidas:
      for k in range(3):
            tk = np.arange(int(0.25 * SR)) / SR
            bt = (np.sin(2 * math.pi * 95 * tk) * 0.9 + np.random.default_rng(k).standard_normal(len(tk)) * 0.25) * np.exp(-tk * 28)
            s0 = int((tb + k * 0.32) * SR); mix[s0:s0 + len(bt)] += bt.astype(np.float32) * 0.7
    mix[int(0.05 * SR): int(0.05 * SR) + len(sfx_pop())] += sfx_pop()
    for i, f in enumerate(falas):
        if f.get("impacto"):
            b = sfx_boom(); s = int(max(0, f["_t0"] - 0.1) * SR); mix[s:s + len(b)] += b[: n - s]
    ch = sfx_chime(); s = int(fim_falas * SR); mix[s:s + len(ch)] += ch[: n - s]

    # câmera por fala
    cenas_cache = {}
    bonecos = {}
    for cid, sp in elenco.items():
        if not sp.get("invisivel"):
            bonecos[cid] = Boneco(cid, sp, M["noite"])
    for i, f in enumerate(falas):
        cam = f.get("camera")
        if not cam:
            if f["_primeira"]: cam = "plano"
            elif elenco[f["quem"]].get("invisivel"): cam = "plano"
            else: cam = ["medio", "close"][i % 2]
        f["_cam"] = cam
        if i > 0 and f["_cena"] != falas[i - 1]["_cena"]:
            w = sfx_whoosh(dur=0.6, seed=i) * 0.12; s = int(max(0, f["_t0"] - 0.15) * SR); mix[s:s + len(w)] += w[: n - s]

    pk = np.abs(mix).max()
    if pk > 0.85: mix = mix * (0.85 / pk)
    import soundfile as sf
    wav = os.path.join(tmp, "mix.wav"); sf.write(wav, mix[: int(total * SR)], SR)

    # legendas pré-renderizadas
    f_leg = fonte(jost, 80, 700); f_tag = fonte(jost, 40, 600)
    f_fixa = fonte(jost, 58, 600)
    for f in falas:
        sp = elenco[f["quem"]]
        f["_tag"] = render_etiqueta(sp["nome"], hexc(sp.get("etiqueta", "#D9C4A3")), f_tag) if sp.get("nome") else None
        if f.get("legenda_fixa"):
            f["_blocos"] = [(f["_t0"], f["_t0"] + f["_dur"], render_fixa(f["texto"], M["texto"] + (255,), M["contorno"] + (255,), f_fixa))]
            continue
        bl = blocos(f["texto"], f.get("destaque", []), rot.get("destaque_auto", True))
        pal = f["_pal"]; ims = []; k = 0
        for j, b in enumerate(bl):
            a0 = f["_t0"] + pal[min(k, len(pal) - 1)][1]
            k += len(b)
            a1 = f["_t0"] + (pal[k][1] if k < len(pal) else f["_dur"])
            ims.append((a0, a1, render_bloco(b, M["texto"] + (255,), M["destaque"] + (255,), M["contorno"] + (255,), f_leg, M["pilula"])))
        f["_blocos"] = ims

    # sobreposições fixas
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W]
    r = np.sqrt(((xx - OUT_W / 2) / (OUT_W * 0.75)) ** 2 + ((yy - OUT_H / 2) / (OUT_H * 0.7)) ** 2)
    vin = np.clip(1 - M["vinheta"] * np.clip(r - 0.45, 0, 1) * 1.6, 0, 1)
    vin_mask = Image.fromarray((vin * 255).astype(np.uint8))
    preto = Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0))
    rng = np.random.default_rng(1)
    graos = [Image.fromarray(rng.integers(0, 255, (OUT_H, OUT_W), dtype=np.uint8)).convert("RGB") for _ in range(3)]

    # título-gancho
    titulo = rot.get("titulo", "")
    tit_im = None
    if titulo:
        f_tit = fonte(ital, 118)
        linhas = titulo.upper().split("\n")
        hs = [f_tit.getbbox(l) for l in linhas]
        Wt = max(b[2] for b in hs) + 120; Ht = sum(b[3] + 30 for b in hs) + 70
        tit_im = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0)); dt = ImageDraw.Draw(tit_im)
        dt.rounded_rectangle([0, 0, Wt - 1, Ht - 1], radius=28, fill=(11, 11, 11, 215))
        dt.rounded_rectangle([10, 10, Wt - 11, Ht - 11], radius=22, outline=M["destaque"] + (200,), width=3)
        y = 30
        for l, b in zip(linhas, hs):
            x = (Wt - b[2]) // 2
            dt.text((x + 4, y + 5), l, font=f_tit, fill=(0, 0, 0, 170))
            dt.text((x, y), l, font=f_tit, fill=M["destaque"] + (255,), stroke_width=2, stroke_fill=(11, 11, 11, 255))
            y += b[3] + 30
    selo = None
    if modo == "ficcao" and rot.get("serie"):
        fs = fonte(jost, 36, 700)
        txt = rot["serie"].upper()
        selo = Image.new("RGBA", (int(fs.getlength(txt)) + 30, 60), (0, 0, 0, 0))
        ImageDraw.Draw(selo).text((14, 8), txt, font=fs, fill=M["destaque"] + (255,), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    elif modo == "advocacia":
        fs = fonte(ital, 54)
        selo = Image.new("RGBA", (260, 80), (0, 0, 0, 0))
        ImageDraw.Draw(selo).text((14, 6), "L | S", font=fs, fill=M["destaque"] + (230,), stroke_width=2, stroke_fill=(0, 0, 0, 200))

    # cartão final
    def cartao_final():
        im = Image.new("RGB", (OUT_W, OUT_H), (11, 11, 11)); d = ImageDraw.Draw(im)
        if modo == "advocacia":
            f1 = fonte(ital, 210); f2 = fonte(jost, 44, 500); f3 = fonte(jost, 36, 400); f4 = fonte(jost, 46, 500)
            def ctr(txt, f, y, c, sp=0):
                if sp:
                    w = sum(f.getlength(ch) + sp for ch in txt) - sp; x = (OUT_W - w) / 2
                    for ch in txt: d.text((x, y), ch, font=f, fill=c); x += f.getlength(ch) + sp
                else:
                    d.text(((OUT_W - f.getlength(txt)) / 2, y), txt, font=f, fill=c)
            ctr("L | S", f1, 640, (217, 196, 163))
            d.line([340, 900, 740, 900], fill=(142, 118, 80), width=3)
            ctr("LIMA SANTOS", f2, 940, (245, 241, 234), sp=14)
            ctr("ADVOCACIA", f3, 1010, (217, 196, 163), sp=18)
            ctr("Kevin Lima Santos · Advogado", f3, 1110, (200, 192, 180))
            if final.get("texto"):
                for j, l in enumerate(final["texto"].split("\n")):
                    ctr(l, f4, 1300 + j * 64, (245, 241, 234))
        else:
            f1 = fonte(jost, 96, 800); f4 = fonte(jost, 48, 500)
            t1 = final.get("titulo", "CONTINUA...")
            d.text(((OUT_W - f1.getlength(t1)) / 2, 800), t1, font=f1, fill=M["destaque"])
            for j, l in enumerate(final.get("texto", "").split("\n")):
                if l: d.text(((OUT_W - f4.getlength(l)) / 2, 960 + j * 66), l, font=f4, fill=(240, 240, 240))
        return im
    card = cartao_final()

    # posições dos personagens por cena
    def layout(cena):
        ids = [p for p in cena["personagens"] if p in bonecos]
        if cena.get("xs") and len(cena["xs"]) == len(ids): return list(zip(ids, cena["xs"]))
        xs = {1: [810], 2: [520, 1100], 3: [360, 810, 1260]}.get(len(ids), [300 + i * 340 for i in range(len(ids))])
        return list(zip(ids, xs))

    blink_rng = random.Random(42)
    blinks = {cid: sorted(blink_rng.uniform(0, total) for _ in range(int(total / 3) + 1)) for cid in bonecos}
    envs = [envelope(a, int(len(a) / SR * FPS) + 2) for a in audios]

    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
                           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", "-af", "alimiter=limit=0.9:level=disabled", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart", saida],
                          stdin=subprocess.PIPE)
    TRANS, FUSAO = 0.55, 0.6
    def cam_de(i, tt):
        fi = falas[i]; cen = rot["cenas"][fi["_cena"]]; ly = layout(cen)
        pf = dict(ly).get(fi["quem"]); prog = max(0, min(1, (tt - fi["_t0"]) / (fi["_dur"] + 0.3)))
        fx = pf if pf is not None else SC_W / 2
        ef = bonecos[fi["quem"]].esc if fi["quem"] in bonecos else 1.0
        tp = cabeca_y(cen, fi["quem"], ef) - 300 * ef if fi["quem"] in bonecos else FLOOR_Y - CH * ef; cam = fi["_cam"]
        if cam == "plano":
            zz = 1.14 + 0.05 * prog; xx = sum(x for _, x in ly) / max(1, len(ly)) if ly else SC_W / 2
            yy = FLOOR_Y + 60 - 0.86 * SC_H / zz + SC_H / zz / 2
        elif cam == "medio":
            zz = 1.5 + 0.05 * prog; xx, yy = fx, tp + 620
        elif cam == "punch":
            loc = tt - fi["_t0"]; q = max(0, min(1, (loc - fi["_dur"] * 0.35) / 0.5)); q = q * q * (3 - 2 * q)
            zz = 1.5 + 0.35 * q; xx, yy = fx, tp + 620 - 60 * q
        else:
            zz = 1.95 + 0.07 * prog; xx, yy = fx, tp + 500
        return zz, xx, yy
    ultimo = {"frame": None, "cena": None, "t": 0}
    moveis_cache = {}
    tit_em = falas[rot["titulo_na_fala"]]["_t0"] - falas[rot["titulo_na_fala"]].get("antes", 0) if "titulo_na_fala" in rot else 0.0
    print("Renderizando...", flush=True)
    capa_salva = False
    for fr in range(n_frames):
        tt = fr / FPS
        if tt >= fim_falas:
            frame = card
            k2 = min(1, (tt - fim_falas) / 0.7)
            if k2 < 1:
                frame = Image.blend(Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0)), card, k2)
            ff.stdin.write(frame.tobytes()); continue
        # fala atual
        idx = 0
        for i, f in enumerate(falas):
            if f["_t0"] - 0.12 <= tt: idx = i
        f = falas[idx]
        cena = rot["cenas"][f["_cena"]]
        nome_cen = cena.get("cenario", "escritorio")
        if nome_cen not in cenas_cache: cenas_cache[nome_cen] = cenario(nome_cen, M["noite"])
        palco = cenas_cache[nome_cen].copy()
        lay = layout(cena)
        falando = f["quem"]
        local = tt - f["_t0"]
        env = envs[idx]; ej = int(local * FPS)
        amp = env[ej] if 0 <= ej < len(env) else 0.0
        pos_fal = dict(lay).get(falando)
        if f["_cena"] not in moveis_cache:
            moveis_cache[f["_cena"]] = moveis(lay, {c: pose_de(cena, c) for c, _ in lay}, bonecos, M["noite"], cena.get("camas_vazias", [])) if cena.get("pose") else None
        mv = moveis_cache[f["_cena"]]
        if mv: palco.paste(mv[0], (0, 0), mv[0])
        for cid, x in lay:
            b = bonecos[cid]
            fala_ele = cid == falando and 0 <= local <= f["_dur"]
            boca = 0
            if fala_ele:
                boca = 0 if amp < 0.12 else 1 if amp < 0.35 else 2 if amp < 0.65 else 3
            pisca = any(0 <= tt - bt < 0.13 for bt in blinks[cid])
            if pos_fal is None or cid == falando: olhar = 0
            else: olhar = 1 if pos_fal > x else -1
            emo = f.get("emocao", "neutro") if cid == falando else (f.get("reacao", {}).get(cid, "neutro"))
            ph = sum(map(ord, cid)) % 7
            bob = math.sin(2 * math.pi * 0.55 * tt + ph) * 5
            tilt = math.sin(2 * math.pi * 0.3 * tt + ph) * 2.2 + (amp * 3 if fala_ele else 0)
            nod = amp * 8 if fala_ele else 0
            g = 0.0
            if fala_ele and f.get("gesto"):
                g = min(1, local / 0.25) * (1 if local < f["_dur"] - 0.2 else max(0, (f["_dur"] - local) / 0.2))
            spr = b.compor("fechado" if pisca else "aberto", boca, emo, olhar, tilt, nod, g)
            pz = pose_de(cena, cid)
            if pz == "deitado":
                hd = b.cabeca("fechado" if pisca else "aberto", boca, emo, olhar)
                if abs(tilt) > 0.2: hd = hd.rotate(tilt * 0.6, resample=Image.BICUBIC, center=(hd.width / 2, hd.height * 0.6))
                palco.paste(hd, (int(x - hd.width / 2), int(HEADY - hd.height * 0.53 + bob * 0.3)), hd)
            elif pz == "sentado":
                cut = spr.crop((0, 0, spr.width, int(870 * b.esc)))
                palco.paste(cut, (int(x - spr.width / 2), int(SEAT_Y - 830 * b.esc + bob * 0.5)), cut)
            else:
                palco.paste(spr, (int(x - spr.width / 2), int(FLOOR_Y - spr.height + bob)), spr)
        if mv: palco.paste(mv[1], (0, 0), mv[1])
        # câmera (suave: desliza da fala anterior e funde na troca de cena)
        z, cx, cy = cam_de(idx, tt)
        if idx > 0 and falas[idx - 1]["_cena"] == f["_cena"]:
            k = local + 0.12
            if k < TRANS:
                e = k / TRANS; e = e * e * (3 - 2 * e)
                z0, cx0, cy0 = cam_de(idx - 1, tt)
                z, cx, cy = z0 + (z - z0) * e, cx0 + (cx - cx0) * e, cy0 + (cy - cy0) * e
        if f.get("tremor"):
            cx += math.sin(tt * 37) * 9; cy += math.cos(tt * 29) * 9
        cw, chh = SC_W / z, SC_H / z
        x0 = min(max(0, cx - cw / 2), SC_W - cw); y0 = min(max(0, cy - chh / 2), SC_H - chh)
        frame = palco.resize((OUT_W, OUT_H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))
        frame = Image.composite(frame, preto, vin_mask)
        if M["grao"] > 0:
            frame = Image.blend(frame, graos[fr % 3], M["grao"])
        if ultimo["cena"] is not None and ultimo["cena"] != f["_cena"]:
            ultimo["prev"] = ultimo["frame"]; ultimo["t"] = tt; ultimo["cena"] = f["_cena"]
        if ultimo["cena"] is None: ultimo["cena"] = f["_cena"]
        if ultimo.get("prev") is not None and tt - ultimo["t"] < FUSAO:
            e = (tt - ultimo["t"]) / FUSAO; e = e * e * (3 - 2 * e)
            frame = Image.blend(ultimo["prev"], frame, e)
        else:
            ultimo["frame"] = frame
        if selo is not None:
            frame.paste(selo, (36, 250), selo)
        # título nos primeiros 2,6 s
        tq = tt - tit_em
        if tit_im is not None and 0 <= tq < 2.6:
            a = min(1, tq / 0.15) * (1 if tq < 2.3 else max(0, (2.6 - tq) / 0.3))
            sc = 0.9 + 0.1 * min(1, tq / 0.2)
            ti = tit_im.resize((int(tit_im.width * sc), int(tit_im.height * sc)), Image.BILINEAR)
            if a < 1:
                al = ti.getchannel("A").point(lambda v: int(v * a)); ti = ti.copy(); ti.putalpha(al)
            frame.paste(ti, ((OUT_W - ti.width) // 2, 300), ti)
        # legenda
        for (a0, a1, img) in f["_blocos"]:
            if a0 <= tt < a1 or (img is f["_blocos"][-1][2] and a1 <= tt < a1 + 0.25):
                k3 = min(1, (tt - a0) / 0.09)
                sc = 0.86 + 0.14 * k3
                im2 = img.resize((int(img.width * sc), int(img.height * sc)), Image.BILINEAR) if sc < 1 else img
                yb = 1240
                frame.paste(im2, ((OUT_W - im2.width) // 2, yb + (img.height - im2.height) // 2), im2)
                if f["_tag"] is not None:
                    tg = f["_tag"]; frame.paste(tg, ((OUT_W - tg.width) // 2, yb - tg.height + 8), tg)
                break
        if not capa_salva and tt >= 1.0:
            frame.save(os.path.splitext(saida)[0] + "_capa.jpg", quality=92); capa_salva = True
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    print("OK:", saida, flush=True)

if __name__ == "__main__":
    main()
