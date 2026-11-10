"""toon.py — orquestra um episódio 3D toon da @continua.br de ponta a ponta.

  1. voz:   pede a narração ao Gemini pelo repositório Vozes (GitHub Actions) e espera o áudio
  2. 3d:    mede o tempo de cada frase, monta o roteiro 3D e manda o GitHub renderizar (4 partes em paralelo)
  3. final: junta vídeo 3D + narração + trilha + efeitos + título + legenda

Uso: python3 toon.py episodio.json [--repo ~/vozes] [--so voz|3d|final] [--saida ep.mp4]
O episódio traz: id, titulo, serie, cenario, personagens, voz (narrador), estilo, frases[{texto, destaque}],
planos[{de, camera, alvo, acoes[...]}] e, se quiser, impacto (referência de tempo).
Referências de tempo: número em segundos | "f3" (início da frase 3) | "f3.fim" | "f3+0.5" | "+1.2" (a partir do início do plano).
"""
import json, os, sys, time, subprocess, shutil
import toon_finaliza as TF

ARGS = sys.argv[1:]
EP = json.load(open(ARGS[0], encoding="utf-8"))
REPO = os.path.expanduser(ARGS[ARGS.index("--repo") + 1] if "--repo" in ARGS else "~/vozes")
SO = ARGS[ARGS.index("--so") + 1] if "--so" in ARGS else "tudo"
ID = EP["id"]
PASTA = os.path.join(os.path.dirname(os.path.abspath(ARGS[0])), ID)
os.makedirs(PASTA, exist_ok=True)
SAIDA = ARGS[ARGS.index("--saida") + 1] if "--saida" in ARGS else os.path.join(PASTA, ID + ".mp4")


def git(*a, ok=False):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True)
    if r.returncode and not ok:
        raise RuntimeError("git " + " ".join(a) + ": " + r.stderr[-400:])
    return r.stdout


def enviar(arquivos, msg):
    git("pull", "-q", "--rebase", ok=True)
    git("add", *arquivos)
    git("commit", "-qm", msg + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    for _ in range(3):
        if subprocess.run(["git", "-C", REPO, "push", "-q"], capture_output=True).returncode == 0:
            return
        git("pull", "-q", "--rebase", ok=True)
    raise RuntimeError("não consegui enviar ao GitHub")


def esperar(caminho, minutos, rotulo):
    fim = time.time() + minutos * 60
    while time.time() < fim:
        git("pull", "-q", "--rebase", ok=True)
        if os.path.exists(os.path.join(REPO, caminho)):
            return True
        print(f"  aguardando {rotulo}...", flush=True)
        time.sleep(30)
    return False


# ---------------------------------------------------------------- 1. voz
wav = os.path.join(PASTA, "narracao.wav")
if SO in ("tudo", "voz") and not os.path.exists(wav):
    vid = ID + "-voz"
    pedido = {"id": vid, "motor": "gemini", "modelo": EP.get("modelo_voz", "gemini-3.8-flash-tts"),
              "vozes": {"narrador": EP.get("voz", "Schedar")},
              "estilo": EP.get("estilo", "narrador de mistério, voz próxima e intrigante, ritmo ágil"),
              "blocos": [{"n": 1, "falas": [{"quem": "narrador", "texto": " ".join(f["texto"] for f in EP["frases"]),
                                              "estilo": EP.get("estilo_en", "Brazilian Portuguese accent, mysterious storyteller, intimate, short dramatic pauses")}]}]}
    rel = f"pedidos/toon_{vid}.json"
    json.dump(pedido, open(os.path.join(REPO, rel), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    enviar([rel], f"Narração: {ID}")
    print("Narração pedida ao Gemini.", flush=True)
    if not esperar(f"saidas/{vid}/status.json", 12, "narração"):
        sys.exit("A narração não voltou em 12 minutos; confira a aba Actions do repositório Vozes.")
    st = json.load(open(os.path.join(REPO, f"saidas/{vid}/status.json")))
    if not st.get("ok"):
        sys.exit("Erro na narração: " + json.dumps(st, ensure_ascii=False)[:500])
    shutil.copy(os.path.join(REPO, f"saidas/{vid}/cena1.wav"), wav)
    print("Narração pronta.", flush=True)
if SO == "voz":
    sys.exit()

# ---------------------------------------------------------------- 2. tempos e roteiro 3D
voz, fim = TF.preparar(wav, EP["frases"], EP.get("atraso", 0.3))
TEMPOS = [{"t0": round(f["_t0"], 3), "dur": round(f["_dur"], 3)} for f in EP["frases"]]
DUR = round(fim + EP.get("cauda", 1.2), 2)
print("Tempos das frases:", " | ".join(f"{i + 1}: {t['t0']:.1f}s" for i, t in enumerate(TEMPOS)), f"| fim {fim:.1f}s", flush=True)


def T(ref, base=0.0):
    if ref is None:
        return base
    if isinstance(ref, (int, float)):
        return float(ref)
    s = str(ref).replace(" ", ""); desloc = 0.0
    for sinal in ("+", "-"):
        i = s.find(sinal, 1)
        if i > 0:
            desloc = float(s[i:]); s = s[:i]; break
    if s[0] in "+-":
        return base + float(s)
    if s.startswith("f"):
        fimf = s.endswith(".fim"); n = int(s[1:].replace(".fim", ""))
        return TEMPOS[n - 1]["t0"] + (TEMPOS[n - 1]["dur"] if fimf else 0) + desloc
    return float(s) + desloc


r3d = {k: EP[k] for k in ("cenario", "personagens", "planos") if k in EP}
r3d.update({"tempos": TEMPOS, "duracao": DUR, "elenco_extra": EP.get("elenco_extra", {}), "semente": EP.get("semente", 7)})
video = os.path.join(PASTA, "video3d.mp4")
if SO in ("tudo", "3d") and not os.path.exists(video):
    rel = f"toon/{ID}.json"
    os.makedirs(os.path.join(REPO, "toon"), exist_ok=True)
    json.dump(r3d, open(os.path.join(REPO, rel), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    alvo = f"saidas3d/{ID}/video3d.mp4"
    if os.path.exists(os.path.join(REPO, alvo)):
        git("rm", "-rq", f"saidas3d/{ID}", ok=True)
    enviar([rel] + ([f"saidas3d/{ID}"] if os.path.exists(os.path.join(REPO, f"saidas3d/{ID}")) else []), f"Roteiro 3D: {ID}")
    print(f"Render 3D enviado ao GitHub ({DUR:.1f}s de vídeo, 4 partes em paralelo).", flush=True)
    if not esperar(alvo, 60, "render 3D"):
        sys.exit("O render não voltou em 60 minutos; confira a aba Actions do repositório Vozes.")
    shutil.copy(os.path.join(REPO, alvo), video)
    print("Vídeo 3D pronto.", flush=True)
if SO == "3d":
    sys.exit()

# ---------------------------------------------------------------- 3. final
planos = EP["planos"]
for p in planos:
    p["_t0"] = T(p.get("de", 0))
cortes = [p["_t0"] for p in planos[1:]]
glitch = None
for p in planos:
    for a in p.get("acoes", []):
        if a["acao"] in ("sumir", "aparecer"):
            g0 = T(a.get("em"), p["_t0"]); glitch = [g0, g0 + 0.6]
rot = {"titulo": EP.get("titulo", ""), "serie": EP.get("serie", ""), "frases": EP["frases"],
       "atraso": EP.get("atraso", 0.3), "cortes": cortes, "glitch": glitch,
       "impacto": T(EP["impacto"]) if EP.get("impacto") else None}
TF.finalizar(rot, video, wav, SAIDA)
print("VÍDEO FINAL:", SAIDA, flush=True)
