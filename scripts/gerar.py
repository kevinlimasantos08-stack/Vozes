#!/usr/bin/env python3
"""Estúdio de vozes: lê pedidos/*.json e grava os áudios em saidas/<id>/.

Motores:
  gemini      Gemini TTS (precisa do segredo GEMINI_API_KEY). Gera um arquivo por bloco (até 2 vozes): cena<N>.wav
  chatterbox  Chatterbox Multilingual (código aberto, MIT). Um arquivo por fala: <NN>_<quem>.wav
              Se existir refs/<quem>.wav, clona essa voz para manter o personagem fixo.
  urls        Baixa arquivos prontos (ex.: links do ElevenLabs): <nome>
  refs        Gera com Gemini as vozes de referência do elenco em refs/<quem>.wav (para o Chatterbox)

Formato do pedido: ver README.md.
"""
import base64, glob, json, os, sys, time, traceback, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def salvar_status(pasta, dados):
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "status.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def gemini_cliente():
    from google import genai
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise RuntimeError("Segredo GEMINI_API_KEY não configurado no repositório.")
    return genai.Client(api_key=chave)


def gemini_bloco(cli, modelo, falas, vozes, estilo_geral):
    quem = []
    for f in falas:
        if f["quem"] not in quem:
            quem.append(f["quem"])
    if len(quem) > 2:
        raise ValueError(f"Bloco com mais de 2 vozes: {quem}")
    conteudo = []
    for i, f in enumerate(falas):
        texto = f["texto"]
        if i < len(falas) - 1:
            texto = texto + " <long pause>"
        meta = {"type": "speech_metadata", "style": f.get("estilo") or estilo_geral}
        if len(quem) == 2:
            meta["speaker"] = f["quem"]
        conteudo.append({"type": "text", "text": texto, "annotations": [meta]})
    if len(quem) == 2:
        speech = {"speakers": [{"speaker": q, "voice": vozes[q]} for q in quem]}
    else:
        speech = [{"voice": vozes[quem[0]]}]
    ultimo = None
    for tentativa in range(4):
        try:
            r = cli.interactions.create(
                model=modelo,
                input=[{"type": "user_input", "content": conteudo}],
                response_format={"type": "audio"},
                generation_config={"speech_config": speech},
            )
            return base64.b64decode(r.output_audio.data)
        except Exception as e:  # limite de uso ou falha temporária: espera e tenta de novo
            ultimo = e
            time.sleep(15 * (tentativa + 1))
    raise ultimo


def rodar_gemini(p, pasta):
    cli = gemini_cliente()
    modelo = p.get("modelo", "gemini-3.8-flash-tts")
    estilo = p.get("estilo", "Português do Brasil, com sotaque brasileiro, natural e com emoção")
    feitos = []
    for b in p["blocos"]:
        audio = gemini_bloco(cli, modelo, b["falas"], p["vozes"], estilo)
        nome = f"cena{b['n']}.wav"
        with open(os.path.join(pasta, nome), "wb") as f:
            f.write(audio)
        feitos.append(nome)
        time.sleep(3)
    return feitos


def rodar_chatterbox(p, pasta):
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu", t3_model=p.get("versao", "v3"))
    feitos = []
    for i, f in enumerate(p["falas"], 1):
        ref = os.path.join(RAIZ, "refs", f"{f['quem']}.wav")
        kw = {"language_id": "pt"}
        if os.path.exists(ref):
            kw["audio_prompt_path"] = ref
        if "intensidade" in f:
            kw["exaggeration"] = float(f["intensidade"])
        try:
            wav = modelo.generate(f["texto"], **kw)
        except TypeError:
            kw.pop("exaggeration", None)
            wav = modelo.generate(f["texto"], **kw)
        nome = f"{i:02d}_{f['quem']}.wav"
        ta.save(os.path.join(pasta, nome), wav, modelo.sr)
        feitos.append(nome)
    return feitos


def rodar_urls(p, pasta):
    feitos = []
    for a in p["arquivos"]:
        req = urllib.request.Request(a["url"], headers={"User-Agent": "estudio-vozes"})
        with urllib.request.urlopen(req, timeout=120) as r, open(os.path.join(pasta, a["nome"]), "wb") as out:
            out.write(r.read())
        feitos.append(a["nome"])
    return feitos


def rodar_refs(p, pasta):
    cli = gemini_cliente()
    modelo = p.get("modelo", "gemini-3.8-flash-tts")
    os.makedirs(os.path.join(RAIZ, "refs"), exist_ok=True)
    feitos = []
    for quem, d in p["elenco"].items():
        audio = gemini_bloco(cli, modelo, [{"quem": quem, "texto": d["frase"], "estilo": d.get("estilo")}],
                             {quem: d["voz"]}, "Português do Brasil, natural")
        with open(os.path.join(RAIZ, "refs", f"{quem}.wav"), "wb") as f:
            f.write(audio)
        feitos.append(f"refs/{quem}.wav")
        time.sleep(3)
    return feitos


MOTORES = {"gemini": rodar_gemini, "chatterbox": rodar_chatterbox, "urls": rodar_urls, "refs": rodar_refs}


def main():
    pedidos = sorted(glob.glob(os.path.join(RAIZ, "pedidos", "*.json")))
    alvo = sys.argv[1] if len(sys.argv) > 1 else None
    for arq in pedidos:
        p = json.load(open(arq, encoding="utf-8"))
        pid = p["id"]
        if alvo and pid != alvo:
            continue
        pasta = os.path.join(RAIZ, "saidas", pid)
        st = os.path.join(pasta, "status.json")
        if os.path.exists(st) and json.load(open(st, encoding="utf-8")).get("ok"):
            continue  # já feito
        os.makedirs(pasta, exist_ok=True)
        t0 = time.time()
        try:
            feitos = MOTORES[p["motor"]](p, pasta)
            salvar_status(pasta, {"ok": True, "motor": p["motor"], "arquivos": feitos, "segundos": round(time.time() - t0)})
            print(f"OK {pid}: {feitos}")
        except Exception as e:
            salvar_status(pasta, {"ok": False, "motor": p.get("motor"), "erro": f"{type(e).__name__}: {e}",
                                  "detalhe": traceback.format_exc()[-1500:]})
            print(f"ERRO {pid}: {e}")


if __name__ == "__main__":
    main()
