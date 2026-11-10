"""Finaliza um vídeo 3D toon: põe narração, trilha, efeitos, título-gancho e legenda dinâmica (padrão da ficção).
Uso: python3 toon_finaliza.py roteiro.json video3d.mp4 narracao.wav saida.mp4
roteiro.json: {"titulo": "...", "serie": "...", "frases": [{"texto": "...", "destaque": [...]}, ...],
               "cortes": [segundos...], "impacto": segundos, "glitch": [ini, fim], "atraso": 0.3}
"""
import json, os, sys, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw
import reel2d as R

W, H, FPS, SR = 1080, 1920, 24, R.SR
M = R.MODOS["ficcao"]
assets = os.path.expanduser("~/.reel2d")
jost = os.path.join(assets, "Jost.ttf")
import soundfile as sf


def aparar(a):
    hop = int(SR * 0.02)
    rms = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a), hop)])
    on = np.where(rms > max(0.008, rms.max() * 0.05))[0]
    if len(on) == 0:
        return a
    return a[max(0, (on[0] - 2) * hop): min(len(a), (on[-1] + 4) * hop)]


def preparar(narr, frases, atraso=0.3, tmp=None):
    """Corta a narração por frase (nos silêncios), encurta as pausas longas e devolve (pedaços de áudio, fim)."""
    tmp = tmp or tempfile.mkdtemp(prefix="toon_")
    partes = R.dividir_audio_unico(narr, len(frases), tmp, "n")
    t = atraso; voz = []
    for i, (fr, q) in enumerate(zip(frases, partes)):
        a, _ = sf.read(q, dtype="float32")
        a = aparar(a)
        fr["_t0"], fr["_dur"] = t, len(a) / SR
        pausa = fr.get("pausa", 0.28) if i < len(frases) - 1 else 0
        voz.append(np.concatenate([a, np.zeros(int(pausa * SR), np.float32)])); t += len(a) / SR + pausa
    return voz, t


def finalizar(rot, video, narr, saida):
    tmp = tempfile.mkdtemp(prefix="toon_")
    frases = rot["frases"]
    atraso = rot.get("atraso", 0.3)
    voz, fim_voz = preparar(narr, frases, atraso, tmp)
    dur_video = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]).decode())
    total = max(dur_video, fim_voz + 0.9)
    print(f"narração termina em {fim_voz:.1f}s; vídeo 3D tem {dur_video:.1f}s; final {total:.1f}s")

    # ---- mix
    n = int(total * SR) + SR
    mix = np.zeros(n, np.float32)
    s = int(atraso * SR); a_all = np.concatenate(voz); mix[s:s + len(a_all)] += a_all * 1.3
    mix += R.trilha(M["trilha"], n) * 0.9
    for c in rot.get("cortes", []):
        w = R.sfx_whoosh(seed=int(c * 10)) * 0.4; i = int(max(0, c - 0.12) * SR); mix[i:i + len(w)] += w[: n - i]
    if rot.get("impacto"):
        b = R.sfx_boom(); i = int(rot["impacto"] * SR); mix[i:i + len(b)] += b[: n - i]
    if rot.get("glitch"):
        g0, g1 = rot["glitch"]
        for k in range(int((g1 - g0) / 0.09)):
            p = R.sfx_pop() * 0.6; i = int((g0 + k * 0.09) * SR); mix[i:i + len(p)] += p[: n - i]
    mix = np.tanh(mix * 1.15) * 0.95
    wav = os.path.join(tmp, "mix.wav"); sf.write(wav, mix[: int(total * SR)], SR)

    # ---- legendas
    f_leg = R.fonte(jost, 80, 700)
    for fr in frases:
        bl = R.blocos(fr["texto"], fr.get("destaque", []), True)
        pesos = [sum(len(w) for w, _ in b) + 3 for b in bl]; tot = sum(pesos); t0 = fr["_t0"]; ims = []
        for b, p in zip(bl, pesos):
            d = fr["_dur"] * p / tot
            ims.append((t0, t0 + d, R.render_bloco(b, M["texto"] + (255,), M["destaque"] + (255,), M["contorno"] + (255,), f_leg, False)))
            t0 += d
        fr["_blocos"] = ims
    legs = [x for fr in frases for x in fr["_blocos"]]

    # ---- título-gancho e selo da série
    tit = None
    if rot.get("titulo"):
        ft = R.fonte(jost, 104, 800)
        linhas = rot["titulo"].upper().split("\n")
        bbs = [ft.getbbox(l) for l in linhas]
        Wt = max(b[2] for b in bbs) + 90; Ht = sum(b[3] + 24 for b in bbs) + 50
        tit = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0)); d = ImageDraw.Draw(tit)
        d.rounded_rectangle([0, 0, Wt - 1, Ht - 1], radius=26, fill=(10, 10, 14, 225))
        y = 22
        for l, b in zip(linhas, bbs):
            d.text(((Wt - b[2]) // 2, y), l, font=ft, fill=M["destaque"] + (255,)); y += b[3] + 24
    selo = None
    if rot.get("serie"):
        fs = R.fonte(jost, 36, 700); txt = rot["serie"].upper()
        selo = Image.new("RGBA", (int(fs.getlength(txt)) + 30, 60), (0, 0, 0, 0))
        ImageDraw.Draw(selo).text((14, 8), txt, font=fs, fill=M["destaque"] + (255,), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    # vinheta leve
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    vin = Image.fromarray((np.clip(1 - 0.35 * np.clip(rr - 0.5, 0, 1) * 1.6, 0, 1) * 255).astype(np.uint8))
    preto = Image.new("RGB", (W, H), (0, 0, 0))

    # ---- quadros
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={W}:{H},tpad=stop_mode=clone:stop_duration=30",
                            "-t", f"{total:.3f}", "-r", str(FPS), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "160k", "-shortest", "-movflags", "+faststart", saida], stdin=subprocess.PIPE)
    fr_i = 0; capa = False
    while True:
        raw = dec.stdout.read(W * H * 3)
        if len(raw) < W * H * 3:
            break
        tt = fr_i / FPS
        im = Image.frombytes("RGB", (W, H), raw)
        im = Image.composite(im, preto, vin)
        if selo is not None:
            im.paste(selo, (36, 250), selo)
        if tit is not None and tt < 2.6:
            a = min(1, tt / 0.15) * (1 if tt < 2.3 else max(0, (2.6 - tt) / 0.3))
            sc = 0.9 + 0.1 * min(1, tt / 0.2)
            ti = tit.resize((int(tit.width * sc), int(tit.height * sc)))
            if a < 1:
                al = ti.getchannel("A").point(lambda v: int(v * a)); ti.putalpha(al)
            im.paste(ti, ((W - ti.width) // 2, 330), ti)
        for (a0, a1, img) in legs:
            if a0 <= tt < a1 + (0.25 if img is legs[-1][2] else 0):
                k = min(1, (tt - a0) / 0.09); sc = 0.86 + 0.14 * k
                i2 = img.resize((int(img.width * sc), int(img.height * sc))) if sc < 1 else img
                im.paste(i2, ((W - i2.width) // 2, 1330 + (img.height - i2.height) // 2), i2)
                break
        if not capa and tt >= 1.0:
            im.save(os.path.splitext(saida)[0] + "_capa.jpg", quality=92); capa = True
        enc.stdin.write(im.tobytes()); fr_i += 1
    enc.stdin.close(); enc.wait()
    print("OK", saida)



if __name__ == "__main__":
    rot = json.load(open(sys.argv[1], encoding="utf-8"))
    if "--tempos" in sys.argv:
        voz, fim = preparar(sys.argv[3], rot["frases"], rot.get("atraso", 0.3))
        print(json.dumps([{"t0": round(f["_t0"], 2), "dur": round(f["_dur"], 2)} for f in rot["frases"]]), round(fim, 2))
    else:
        finalizar(rot, *sys.argv[2:5])
