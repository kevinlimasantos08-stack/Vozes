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

def volume(im, claro=1.07, escuro=0.80):
    """Dá volume ao recorte: luz vinda da esquerda, sombra suave à direita (sombreamento em degradê horizontal)."""
    a = np.asarray(im).astype(np.float32)
    alpha = a[..., 3] > 0
    if not alpha.any():
        return im
    cols = np.where(alpha.any(axis=0))[0]
    x0, x1 = cols[0], cols[-1] + 1
    t = np.clip((np.arange(a.shape[1]) - x0) / max(1, x1 - x0), 0, 1)
    f = claro + (escuro - claro) * (t ** 1.6)
    a[..., :3] *= f[None, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


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
        self._cache_br = {}

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
        return volume(im)

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
        # braço esquerdo agora é peça separada (desenhado atrás do tronco em compor)
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
        # bochechas
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
        if est == "coque":
            pass
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
        # sobrancelhas
        by = ey - 48
        incl = {"neutro": 0, "feliz": -4, "triste": 12, "bravo": -16, "surpreso": 0, "medo": 12}[emo]
        lift = {"surpreso": -14, "medo": -10}.get(emo, 0)
        browc = shade(self.cab, 0.8) if sp.get("estilo_cabelo") not in ("careca",) else (60, 45, 40, 255)
        for sx in (-1, 1):
            x0 = cx + sx * ex
            inner = (x0 - sx * 24, by + lift + (incl if sx == 1 else incl) * (1 if sx == -1 else 1))
            # inclinação: pontas internas sobem (triste) ou descem (bravo)
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

    def _braco_girado(self, ang):
        """Braço girado em torno do ombro; devolve (imagem, ponto do ombro dentro dela). Com cache por grau."""
        a = int(round(ang))
        if a not in self._cache_br:
            br = self.braco_d
            piv = (br.width // 2, int(10 * self.esc))
            L = br.height * 2
            sq = Image.new("RGBA", (L, L), (0, 0, 0, 0))
            sq.alpha_composite(br, (L // 2 - piv[0], L // 2 - piv[1]))
            if a:
                sq = sq.rotate(a, resample=Image.BICUBIC, center=(L // 2, L // 2))
            self._cache_br[a] = sq
        return self._cache_br[a]

    def compor(self, olho, boca, emo, olhar, tilt, nod, gesto, gesto_e=0.0):
        e = self.esc
        pad = int(PAD * e)
        im = Image.new("RGBA", (self.corpo.width + 2 * pad, self.corpo.height), (0, 0, 0, 0))
        # braço esquerdo atrás do tronco: gira no sentido horário para abrir
        sq = self._braco_girado(-gesto_e * 62)
        L = sq.width
        ombro_e = (pad + int(154 * e), int(440 * e))
        im.alpha_composite(sq, (ombro_e[0] - L // 2, ombro_e[1] - L // 2))
        im.alpha_composite(self.corpo, (pad, 0))
        # braço direito na frente: gira no sentido anti-horário para levantar
        sq = self._braco_girado(gesto * 62)
        ombro = (pad + int(406 * e), int(440 * e))
        im.alpha_composite(sq, (ombro[0] - L // 2, ombro[1] - L // 2))
        hd = self.cabeca(olho, boca, emo, olhar)
        if abs(tilt) > 0.2:
            hd = hd.rotate(tilt, resample=Image.BICUBIC, center=(hd.width / 2, hd.height * 0.85))
        hx = pad + int(HEAD_ANCHOR[0] * e - hd.width / 2)
        hy = int((HEAD_ANCHOR[1] + nod) * e - hd.height / 2)
        im.alpha_composite(hd, (hx, max(0, hy)))
        return im


def inclinar(im, graus, sy):
    """Inclina o boneco em torno dos pés (centro de baixo) e aplica respiração (escala vertical)."""
    if abs(graus) < 0.05 and abs(sy - 1) < 0.001:
        return im
    w, h = im.size
    r = math.radians(graus)
    c, s_ = math.cos(r), math.sin(r)
    a, b, d_, e_ = c, s_, -s_ / sy, c / sy
    cx, cy = w / 2, h
    data = (a, b, cx - a * cx - b * cy, d_, e_, cy - d_ * cx - e_ * cy)
    return im.transform((w, h), Image.AFFINE, data, resample=Image.BICUBIC)


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
        # plantas: animadas em CenarioVivo
        d.rectangle([560, 160, 1060, 300], fill=(40, 46, 56)); d.text((610, 190), "", fill=(255, 255, 255))
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
    else:  # casa
        grad((196, 176, 150), (176, 154, 128), 0, wall_y)
        d.rectangle([0, wall_y, W, H], fill=(140, 100, 70))
        for x in range(0, W, 160): d.line([x, wall_y, x, H], fill=(124, 88, 60), width=5)
        d.rectangle([180, 400, 760, 1200], fill=ol); d.rectangle([196, 416, 744, 1184], fill=(140, 180, 210))
        # cortinas: animadas em CenarioVivo
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
    return im


# ------------------------------------------------------------------ cenário vivo (elementos que se mexem)
def _ponto_suave(r, cor, a):
    """Pontinho de luz com borda suave (RGBA)."""
    m = Image.new("L", (r * 4, r * 4), 0)
    ImageDraw.Draw(m).ellipse([r, r, r * 3, r * 3], fill=a)
    im = Image.new("RGBA", m.size, cor + (0,)); im.putalpha(m.filter(ImageFilter.GaussianBlur(r * 0.6)))
    return im


def _nuvem(w, h, cor, a, seed):
    rng = random.Random(seed)
    m = Image.new("L", (w, h), 0); d = ImageDraw.Draw(m)
    for _ in range(7):
        rx = rng.uniform(0.18, 0.32) * w; ry = rng.uniform(0.3, 0.45) * h
        x = rng.uniform(rx, w - rx); y = rng.uniform(h * 0.45, h - ry)
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=a)
    im = Image.new("RGBA", (w, h), cor + (0,)); im.putalpha(m.filter(ImageFilter.GaussianBlur(h * 0.08)))
    return im


class CenarioVivo:
    """Desenha, a cada quadro, o que se mexe no cenário: nuvens, relógio, poeira na luz, plantas, cortinas, vapor, carros, pássaros."""
    OL = (30, 26, 26)

    def __init__(self, nome, noite):
        self.nome, self.noite = nome, noite
        rng = random.Random(len(nome) * 13)
        self.poeira = [(rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0.02, 0.06), rng.uniform(0, 6.28), rng.choice([3, 4, 5]))
                       for _ in range(70)]
        self.dots = {r: _ponto_suave(r, self.c((255, 244, 214)), 150) for r in (3, 4, 5)}
        self.vapor = _ponto_suave(26, self.c((255, 255, 255)), 70)
        self.nuvens = [_nuvem(rng.randint(260, 420), rng.randint(90, 140), self.c((255, 255, 255)), 200, i) for i in range(4)]
        self.cache = {}

    def c(self, cor):
        if not self.noite:
            return tuple(cor[:3])
        f = (0.45 * 0.8, 0.45 * 0.9, 0.45 * 1.2)
        return tuple(int(min(255, cor[i] * f[i])) for i in range(3))

    # ---- peças reutilizáveis
    def _ceu_com_nuvens(self, palco, box, ceu, tt, vel=18, clip_im=None):
        """Desenha nuvens passando dentro de 'box' (x0,y0,x1,y1). Se clip_im vier, ela é colada por cima (prédios)."""
        x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
        im = Image.new("RGBA", (w, h), self.c(ceu) + (255,)) if ceu else palco.crop(box).convert("RGBA")
        for i, nv in enumerate(self.nuvens):
            span = w + nv.width
            x = (i * span / len(self.nuvens) + tt * vel * (0.7 + 0.15 * i)) % span - nv.width
            y = int(h * (0.04 + 0.12 * (i % 3)))
            im.alpha_composite(nv, (int(x), y))
        if clip_im is not None:
            im.alpha_composite(clip_im)
        palco.paste(im.convert("RGB"), (x0, y0))

    def _poeira(self, palco, box, tt, n=40):
        x0, y0, x1, y1 = box
        for (u, v, vel, ph, r) in self.poeira[:n]:
            x = x0 + ((u + 0.015 * math.sin(tt * 0.7 + ph)) % 1) * (x1 - x0)
            y = y0 + ((v - tt * vel) % 1) * (y1 - y0)
            dot = self.dots[r]
            palco.paste(dot, (int(x), int(y)), dot)

    def _planta(self, d, px, base, tt, escala=1.0, ph=0.0):
        """Vaso com folhas que balançam (como uma brisa leve)."""
        e = escala; ol = self.OL
        d.polygon([(px - 70 * e, base - 150 * e), (px + 70 * e, base - 150 * e), (px + 52 * e, base), (px - 52 * e, base)],
                  fill=self.c((150, 92, 60)), outline=ol, width=6)
        for i in range(9):
            a0 = -150 + i * 15
            a = math.radians(a0 + math.sin(tt * 1.3 + ph + i * 0.7) * 6)
            comp = (190 + (i % 3) * 40) * e
            bx, by = px, base - 140 * e
            tx, ty = bx + math.cos(a) * comp, by + math.sin(a) * comp
            nx, ny = -math.sin(a) * 34 * e, math.cos(a) * 34 * e
            mx, my = (bx + tx) / 2, (by + ty) / 2
            cor = self.c((52, 112, 66) if i % 2 else (70, 136, 80))
            d.polygon([(bx, by), (mx + nx, my + ny), (tx, ty), (mx - nx, my - ny)], fill=cor, outline=ol, width=4)

    def _relogio(self, palco, cx, cy, r, tt):
        if "relogio" not in self.cache:
            im = Image.new("RGBA", (2 * r + 20, 2 * r + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.ellipse([10, 10, 2 * r + 10, 2 * r + 10], fill=self.c((142, 118, 80)) + (255,), outline=self.OL + (255,), width=6)
            d.ellipse([22, 22, 2 * r - 2, 2 * r - 2], fill=self.c((245, 241, 234)) + (255,))
            for k in range(12):
                a = math.radians(k * 30); c0 = r + 10
                d.line([c0 + math.cos(a) * (r - 22), c0 + math.sin(a) * (r - 22), c0 + math.cos(a) * (r - 12), c0 + math.sin(a) * (r - 12)],
                       fill=self.OL + (255,), width=4)
            self.cache["relogio"] = im
        im = self.cache["relogio"].copy(); d = ImageDraw.Draw(im); c0 = r + 10
        for ang, L, wd, cor in ((tt * 0.5 + 300, r * 0.5, 7, self.OL), (tt * 6 + 60, r * 0.75, 5, self.OL), (tt * 36, r * 0.8, 2, self.c((180, 40, 40)))):
            a = math.radians(ang - 90)
            d.line([c0, c0, c0 + math.cos(a) * L, c0 + math.sin(a) * L], fill=cor + (255,), width=wd)
        palco.paste(im, (cx - c0, cy - c0), im)

    # ---- por cenário
    def desenhar(self, palco, tt):
        n = self.nome; d = ImageDraw.Draw(palco)
        if n == "escritorio":
            if "predios" not in self.cache:
                pr = Image.new("RGBA", (480, 840), (0, 0, 0, 0)); pd = ImageDraw.Draw(pr)
                for bx in range(0, 480, 70):
                    hgt = random.Random(bx).randint(250, 600)
                    pd.rectangle([bx, 840 - hgt, bx + 55, 840], fill=self.c((80, 96, 120)) + (255,))
                ceu = Image.new("RGBA", (480, 840))
                cd = ImageDraw.Draw(ceu)
                for y in range(840):
                    t = y / 840; cd.line([0, y, 480, y], fill=self.c((int(120 + 60 * t), int(150 + 40 * t), int(190 + 20 * t))) + (255,))
                self.cache["predios"], self.cache["ceu"] = pr, ceu
            im = self.cache["ceu"].copy()
            for i, nv in enumerate(self.nuvens):
                span = 480 + nv.width
                x = (i * span / 4 + tt * 16 * (0.7 + 0.15 * i)) % span - nv.width
                im.alpha_composite(nv, (int(x), 10 + 60 * (i % 3)))
            im.alpha_composite(self.cache["predios"])
            palco.paste(im.convert("RGB"), (140, 440))
            d.line([380, 440, 380, 1280], fill=self.OL, width=14); d.line([140, 860, 620, 860], fill=self.OL, width=14)
            self._relogio(palco, 800, 330, 70, tt)
            self._planta(d, 1500, 2060, tt, 1.0, 0.3)
            self._poeira(palco, (180, 900, 1300, 2300), tt, 45)
        elif n == "empresa":
            for k, x in enumerate(range(60, SC_W, 400)):
                for (ya, yb) in ((390, 892), (908, 1640)):
                    box = (x + 10, ya, x + 320, yb)
                    w, h = box[2] - box[0], box[3] - box[1]
                    im = Image.new("RGBA", (w, h), self.c((150, 178, 196)) + (255,))
                    for i, nv in enumerate(self.nuvens[:2]):
                        span = SC_W + nv.width
                        gx = (i * span / 2 + tt * 20 * (0.8 + 0.2 * i)) % span - nv.width
                        im.alpha_composite(nv, (int(gx - x), 30 + 150 * i - (ya - 390)))
                    palco.paste(im.convert("RGB"), box[:2])
            self._planta(d, 360, 1700, tt, 0.8, 0.0)
            self._planta(d, 1360, 1700, tt, 0.8, 1.7)
            self._poeira(palco, (0, 700, SC_W, 2300), tt, 25)
        elif n == "rua":
            for i, nv in enumerate(self.nuvens):
                span = SC_W + nv.width
                x = (i * span / 4 + tt * 22 * (0.7 + 0.2 * i)) % span - nv.width
                big = nv.resize((int(nv.width * 1.4), int(nv.height * 1.4)))
                palco.paste(big, (int(x), 60 + 90 * (i % 3)), big)
            for j in range(3):  # pássaros
                x = (tt * (120 + 30 * j) + j * 500) % (SC_W + 200) - 100
                y = 260 + 70 * j + math.sin(tt * 2 + j) * 20
                asa = 14 * math.sin(tt * 9 + j * 2)
                d.line([x - 22, y - asa, x, y, x + 22, y - asa], fill=self.c((40, 40, 46)), width=5)
            for j, (vel, cor) in enumerate(((260, (190, 50, 50)), (-200, (60, 90, 150)))):  # carros
                x = (tt * vel + j * 700) % (SC_W + 600) - 300
                y = 2740 if vel > 0 else 2800
                d.rounded_rectangle([x, y - 70, x + 300, y], radius=22, fill=self.c(cor), outline=self.OL, width=6)
                d.rounded_rectangle([x + 60, y - 120, x + 230, y - 64], radius=18, fill=self.c((150, 190, 220)), outline=self.OL, width=6)
                for rx in (x + 60, x + 240):
                    d.ellipse([rx - 30, y - 30, rx + 30, y + 30], fill=self.OL)
            glow = 0.85 + 0.15 * math.sin(tt * 3.1)
            d.ellipse([1330, 640, 1460, 730], fill=self.c(tuple(int(v * glow) for v in (250, 230, 160))), outline=self.OL, width=6)
        elif n == "padaria":
            for j in range(16):  # vapor saindo dos pães e do café
                ph = j * 0.37
                k = (tt * 0.45 + ph) % 1
                x = 280 + (j % 8) * 150 + math.sin(tt * 1.7 + j) * 18 * k
                y = 1420 - k * 300
                a = int(255 * math.sin(math.pi * k))
                v = self.vapor.copy(); v.putalpha(v.getchannel("A").point(lambda q, a=a: q * a // 255))
                palco.paste(v, (int(x), int(y)), v)
            self._poeira(palco, (100, 500, SC_W - 100, 2200), tt, 25)
        else:  # casa
            self._ceu_com_nuvens(palco, (196, 416, 744, 1184), (140, 180, 210), tt, 14)
            for j, (x0, x1) in enumerate(((120, 330), (610, 820))):  # cortinas com brisa
                esq, dirt = [], []
                for k in range(13):
                    y = 360 + k * 78.3
                    onda = math.sin(tt * 1.6 + k * 0.55 + j * 2) * 16 * (k / 12)
                    esq.append((x0 + onda * 0.5, y)); dirt.append((x1 + onda, y))
                d.polygon(esq + dirt[::-1], fill=self.c((170, 60, 60)), outline=self.OL, width=6)
                for k in range(1, 4):
                    xx = x0 + (x1 - x0) * k / 4
                    d.line([xx, 370, xx + math.sin(tt * 1.6 + k + j * 2) * 12, 1290], fill=self.c((140, 46, 46)), width=5)
            self._planta(d, 1680 - 260, 2060, tt, 0.9, 0.9)
            self._poeira(palco, (196, 900, 1500, 2300), tt, 40)


def primeiro_plano(nome, noite):
    """Folhagem escura e desfocada em primeiro plano (dá profundidade quando a câmera se mexe)."""
    if nome not in ("escritorio", "casa", "empresa"):
        return None
    W, H = OUT_W + 400, OUT_H
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rng = random.Random(11)
    for i in range(14):
        bx, by = rng.uniform(-40, 170), H + 40
        a = math.radians(rng.uniform(-115, -60)); L = rng.uniform(360, 620)
        tx, ty = bx + math.cos(a) * L, by + math.sin(a) * L
        nx, ny = -math.sin(a) * 70, math.cos(a) * 70
        mx, my = (bx + tx) / 2, (by + ty) / 2
        g = rng.randint(28, 46)
        d.polygon([(bx, by), (mx + nx, my + ny), (tx, ty), (mx - nx, my - ny)], fill=(g - 10, g + 6, g - 8, 235))
    return im.filter(ImageFilter.GaussianBlur(14))


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
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f["audio"], "-ac", "1", "-ar", str(SR), p], check=True)
            a, _ = sf.read(p, dtype="float32")
            idx = np.where(np.abs(a) > 0.01)[0]
            if len(idx): a = a[max(0, idx[0] - 600): idx[-1] + 1200]
            out.append(a / (np.abs(a).max() + 1e-6) * 0.92)
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
    # filtro passa-baixa móvel simples
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
    t = 0.45; GAP = 0.2
    for f, a in zip(falas, audios):
        f["_t0"] = t; f["_dur"] = len(a) / SR; t += f["_dur"] + f.get("pausa", GAP)
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
        s = int(f["_t0"] * SR); mix[s:s + len(a)] += a * 1.25
    bed = trilha(M["trilha"], n); mix += bed
    mix[int(0.05 * SR): int(0.05 * SR) + len(sfx_pop())] += sfx_pop()
    for i, f in enumerate(falas):
        if f.get("impacto"):
            b = sfx_boom(); s = int(max(0, f["_t0"] - 0.1) * SR); mix[s:s + len(b)] += b[: n - s]
    ch = sfx_chime(); s = int(fim_falas * SR); mix[s:s + len(ch)] += ch[: n - s]

    # câmera por fala
    cenas_cache = {}
    vivos, frentes = {}, {}
    bonecos = {}
    for cid, sp in elenco.items():
        if not sp.get("invisivel"):
            bonecos[cid] = Boneco(cid, sp, M["noite"])
    for i, f in enumerate(falas):
        cena = rot["cenas"][f["_cena"]]
        cam = f.get("camera")
        if not cam:
            if f["_primeira"]: cam = "plano"
            elif elenco[f["quem"]].get("invisivel"): cam = "plano"
            else: cam = ["medio", "close"][i % 2]
        f["_cam"] = cam
        if i > 0 and (f["_cam"] != falas[i - 1]["_cam"] or f["quem"] != falas[i - 1]["quem"]):
            w = sfx_whoosh(seed=i) * 0.35; s = int(max(0, f["_t0"] - 0.15) * SR); mix[s:s + len(w)] += w[: n - s]

    mix = np.tanh(mix * 1.2) * 0.95
    import soundfile as sf
    wav = os.path.join(tmp, "mix.wav"); sf.write(wav, mix[: int(total * SR)], SR)

    # legendas pré-renderizadas
    f_leg = fonte(jost, 80, 700); f_tag = fonte(jost, 40, 600)
    f_fixa = fonte(jost, 58, 600)
    for f in falas:
        if f.get("legenda_fixa"):
            f["_blocos"] = [(f["_t0"], f["_t0"] + f["_dur"], render_fixa(f["texto"], M["texto"] + (255,), M["contorno"] + (255,), f_fixa))]
            sp = elenco[f["quem"]]
            f["_tag"] = render_etiqueta(sp["nome"], hexc(sp.get("etiqueta", "#D9C4A3")), f_tag) if sp.get("nome") else None
            continue
        bl = blocos(f["texto"], f.get("destaque", []), rot.get("destaque_auto", True))
        pesos = [sum(len(w) for w, _ in b) + 3 for b in bl]; tot = sum(pesos)
        t0 = f["_t0"]; ims = []
        for b, p in zip(bl, pesos):
            d = f["_dur"] * p / tot
            ims.append((t0, t0 + d, render_bloco(b, M["texto"] + (255,), M["destaque"] + (255,), M["contorno"] + (255,), f_leg, M["pilula"])))
            if any(dd for _, dd in b):
                f.setdefault("_socos", []).append(t0)
            t0 += d
        f["_blocos"] = ims
        sp = elenco[f["quem"]]
        f["_tag"] = render_etiqueta(sp["nome"], hexc(sp.get("etiqueta", "#D9C4A3")), f_tag) if sp.get("nome") else None

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
        xs = {1: [810], 2: [520, 1100], 3: [360, 810, 1260]}.get(len(ids), [300 + i * 340 for i in range(len(ids))])
        return list(zip(ids, xs))

    # quando cada cena começa (para a entrada dos personagens) e estilo de gesto de cada fala
    cena_t0 = {}
    for f in falas:
        cena_t0.setdefault(f["_cena"], f["_t0"] - 0.12)
    cena_t0[falas[0]["_cena"]] = 0.0
    trocas = sorted(v for c, v in cena_t0.items() if c != falas[0]["_cena"])
    ESTILOS = ["explica", "abre", "explica", "aponta"]
    for i, f in enumerate(falas):
        g = f.get("gesto")
        if g is True: g = "aponta"
        if g is None or g is False: g = ESTILOS[i % len(ESTILOS)] if g is None else "parado"
        f["_gesto"] = g
    ENTRADA = 0.55
    _m = Image.new("L", (360, 70), 0); ImageDraw.Draw(_m).ellipse([20, 12, 340, 58], fill=120)
    SOMBRA = Image.new("RGBA", _m.size, (0, 0, 0, 0)); SOMBRA.putalpha(_m.filter(ImageFilter.GaussianBlur(9)))
    blink_rng = random.Random(42)
    blinks = {cid: sorted(blink_rng.uniform(0, total) for _ in range(int(total / 3) + 1)) for cid in bonecos}
    envs = [envelope(a, int(len(a) / SR * FPS) + 2) for a in audios]

    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
                           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", saida],
                          stdin=subprocess.PIPE)
    print("Renderizando...", flush=True)
    capa_salva = False
    for fr in range(n_frames):
        tt = fr / FPS
        if tt >= fim_falas:
            frame = card
            k2 = min(1, (tt - fim_falas) / 0.35)
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
        if nome_cen not in vivos:
            vivos[nome_cen] = CenarioVivo(nome_cen, M["noite"]); frentes[nome_cen] = primeiro_plano(nome_cen, M["noite"])
        vivos[nome_cen].desenhar(palco, tt)
        lay = layout(cena)
        falando = f["quem"]
        local = tt - f["_t0"]
        env = envs[idx]; ej = int(local * FPS)
        amp = env[ej] if 0 <= ej < len(env) else 0.0
        pos_fal = dict(lay).get(falando)
        t_cena = tt - cena_t0[f["_cena"]]
        sprites = []
        for k_ord, (cid, x) in enumerate(lay):
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
            # corpo vivo: respira, balança o peso de um pé para o outro
            bob = math.sin(2 * math.pi * 0.55 * tt + ph) * 6
            sway = math.sin(2 * math.pi * 0.21 * tt + ph) * 12
            lean = math.sin(2 * math.pi * 0.21 * tt + ph) * 1.3
            resp = 1 + 0.007 * math.sin(2 * math.pi * 0.28 * tt + ph)
            # cabeça
            tilt = math.sin(2 * math.pi * 0.3 * tt + ph) * 2.5
            nod = 0.0
            # braços parados também se mexem um pouco
            gr = 0.05 + 0.03 * math.sin(2 * math.pi * 0.4 * tt + ph)
            ge = 0.05 + 0.03 * math.sin(2 * math.pi * 0.4 * tt + ph + 1.3)
            if fala_ele:
                io = min(1, local / 0.3) * min(1, max(0, (f["_dur"] - local) / 0.25))
                io = io * io * (3 - 2 * io)
                tilt += amp * 4 + math.sin(2 * math.pi * 0.8 * local) * 3
                nod = amp * 10 + math.sin(2 * math.pi * 1.6 * local) * 3 * io
                lean += math.sin(2 * math.pi * 0.5 * local) * 1.2 * io
                st = f["_gesto"]
                if st == "explica":
                    gr += io * (0.32 + 0.2 * math.sin(2 * math.pi * 1.2 * local) + 0.35 * amp)
                    ge += io * (0.06 + 0.05 * math.sin(2 * math.pi * 0.9 * local + 1))
                elif st == "abre":
                    v = io * (0.38 + 0.15 * math.sin(2 * math.pi * 0.9 * local) + 0.25 * amp)
                    gr += v; ge += v
                elif st == "aponta":
                    gr += io * (0.85 + 0.06 * math.sin(2 * math.pi * 1.5 * local))
                if emo in ("bravo",):
                    lean += 2.5 * io * (1 if (pos_fal or x) < SC_W / 2 else -1)
            else:
                # quem escuta vira a cabeça para quem fala e reage
                if pos_fal is not None:
                    tilt += 2.5 * (1 if pos_fal > x else -1) * -1
                kk = max(0.0, min(1.0, local / 0.25))
                if emo in ("surpreso", "medo"):
                    bob -= 28 * math.sin(math.pi * min(1, local / 0.35)) if local < 0.35 else 0
                    ge += 0.25 * kk; gr += 0.25 * kk
                elif emo == "feliz":
                    bob -= abs(math.sin(2 * math.pi * 1.6 * local)) * 10 * (1 if local < 1.2 else 0)
                elif emo == "triste":
                    nod += 10 * kk; lean *= 0.5
            spr = b.compor("fechado" if pisca else "aberto", boca, emo, olhar, tilt, nod, gr, ge)
            spr = inclinar(spr, lean, resp)
            # entrada na cena: desliza do lado mais perto com leve "freada"
            dx_in = 0.0
            if 0 <= t_cena < ENTRADA:
                k = t_cena / ENTRADA
                ke = 1 - (1 - k) ** 2.2
                dx_in = (1 - ke) * (-460 if x < SC_W / 2 else 460)
                passo = abs(math.sin(2 * math.pi * 2.6 * t_cena)) * (1 - k)
                bob -= passo * 26
            px = x + sway + dx_in
            sprites.append((spr, int(px - spr.width / 2), int(FLOOR_Y - spr.height + bob), px, b.esc, bob))
        # câmera
        cam = f["_cam"]
        dur = f["_dur"] + 0.3
        prog = max(0, min(1, (tt - f["_t0"]) / dur))
        foco_x = pos_fal if pos_fal is not None else SC_W / 2
        e_fal = bonecos[falando].esc if falando in bonecos else 1.0
        topo = FLOOR_Y - CH * e_fal
        if cam == "plano":
            z = 1.14 + 0.05 * prog; cx = sum(x for _, x in lay) / max(1, len(lay)) if lay else SC_W / 2
            cy = FLOOR_Y + 60 - 0.86 * SC_H / z + SC_H / z / 2
        elif cam == "medio":
            z = 1.5 + 0.09 * prog; cx, cy = foco_x, topo + 620
        elif cam == "punch":
            z = 1.5 if prog < 0.45 else 1.85; cx, cy = foco_x, topo + 560
        else:  # close
            z = 1.95 + 0.07 * prog; cx, cy = foco_x, topo + 500
        if f.get("tremor"):
            cx += math.sin(tt * 37) * 9; cy += math.cos(tt * 29) * 9
        # câmera na mão: pequena deriva contínua
        cx += math.sin(2 * math.pi * 0.13 * tt) * 16 + math.sin(2 * math.pi * 0.37 * tt + 1) * 6
        cy += math.sin(2 * math.pi * 0.11 * tt + 2) * 12 + math.sin(2 * math.pi * 0.41 * tt) * 4
        # panorâmica lenta durante a fala, alternando o lado
        lado = 1 if idx % 2 == 0 else -1
        cx += (prog - 0.5) * 90 * lado
        # chicote na troca de plano
        if idx > 0 and (cam != falas[idx - 1]["_cam"] or f["quem"] != falas[idx - 1]["quem"]) and 0 <= tt - f["_t0"] + 0.12 < 0.22:
            kw = (tt - f["_t0"] + 0.12) / 0.22
            cx += (1 - (1 - (1 - kw) ** 3)) * 300 * lado
        for a0 in f.get("_socos", []):
            ks = tt - a0
            if 0 <= ks < 0.45:
                z *= 1 + 0.07 * min(1, ks / 0.07) * (1 - max(0, ks - 0.07) / 0.38) ** 2
        cw, chh = SC_W / z, SC_H / z
        x0 = min(max(0, cx - cw / 2), SC_W - cw); y0 = min(max(0, cy - chh / 2), SC_H - chh)
        frame = palco.resize((OUT_W, OUT_H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))
        # profundidade de campo: fundo desfocado nos planos fechados
        desfoque = {"plano": 0, "medio": 2.0, "punch": 3.0}.get(cam, 4.0)
        if desfoque:
            frame = frame.filter(ImageFilter.GaussianBlur(desfoque))
        # personagens (nítidos) com sombra de contato no chão
        lw, lh = int(cw) + 2, int(chh) + 2
        camada = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        for (spr, sx, sy, pxc, esc, bb) in sprites:
            sw = int(SOMBRA.width * esc * (1 - min(0.35, max(0, -bb) / 120)))
            sh_ = SOMBRA.resize((max(2, sw), max(2, int(SOMBRA.height * esc))))
            camada.paste(sh_, (int(pxc - sh_.width / 2 - x0), int(FLOOR_Y - sh_.height / 2 - 6 - y0)), sh_)
        for (spr, sx, sy, pxc, esc, bb) in sprites:
            camada.paste(spr, (int(sx - x0), int(sy - y0)), spr)
        camada = camada.resize((OUT_W, OUT_H), Image.BILINEAR, box=(0, 0, cw, chh))
        frame.paste(camada, (0, 0), camada)
        fp = frentes.get(nome_cen)
        if fp is not None and cam in ("plano", "medio"):
            off = int(-(cx - SC_W / 2) * 0.5 * (OUT_W / cw)) - 200
            yfp = int((cy - SC_H * 0.55) * -0.15)
            frame.paste(fp, (off, max(0, yfp) + (90 if cam == "medio" else 0)), fp)
        frame = Image.composite(frame, preto, vin_mask)
        if M["grao"] > 0:
            frame = Image.blend(frame, graos[fr % 3], M["grao"])
        # selo
        if selo is not None:
            frame.paste(selo, (36, 250), selo)
        # título nos primeiros 2,4 s
        if tit_im is not None and tt < 2.6:
            a = min(1, tt / 0.15) * (1 if tt < 2.3 else max(0, (2.6 - tt) / 0.3))
            sc = 0.9 + 0.1 * min(1, tt / 0.2)
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
        for T in trocas:
            if T - 0.24 <= tt < T + 0.26:
                if tt < T:
                    k = (tt - (T - 0.24)) / 0.24; k = k * k * (3 - 2 * k)
                    xa, xb = OUT_W * (1 - k), OUT_W
                else:
                    k = (tt - T) / 0.26; k = k * k * (3 - 2 * k)
                    xa, xb = 0, OUT_W * (1 - k)
                if xb - xa > 1:
                    dr = ImageDraw.Draw(frame)
                    dr.rectangle([xa, 0, xb, OUT_H], fill=(11, 11, 11))
                    borda = xa if tt < T else xb
                    dr.rectangle([borda - 4, 0, borda + 4, OUT_H], fill=M["destaque"])
        if not capa_salva and tt >= 1.0:
            frame.save(os.path.splitext(saida)[0] + "_capa.jpg", quality=92); capa_salva = True
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    print("OK:", saida, flush=True)

if __name__ == "__main__":
    main()
