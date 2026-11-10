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
import base64, glob, json, os, sys, time, traceback, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def salvar_status(pasta, dados):
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "status.json"), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


GL = "https://generativelanguage.googleapis.com/v1beta"
PREFERIDOS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]


def gemini_chave():
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        raise RuntimeError("Segredo GEMINI_API_KEY não configurado no repositório.")
    return k


def modelos_tts(k, pedido=None):
    c, t = _http("GET", f"{GL}/models?pageSize=200", headers={"x-goog-api-key": k})
    disp = []
    if c == 200:
        disp = [m["name"].split("/")[-1] for m in json.loads(t).get("models", []) if "tts" in m["name"]]
    ordem = ([pedido] if pedido else []) + [m for m in PREFERIDOS if m != pedido]
    if disp:
        ordem = [m for m in ordem if m in disp]
    return ordem, disp


def pcm_para_wav(pcm, sr=24000):
    import io, wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
    return b.getvalue()


def nome_tela(q):
    return q.capitalize()


def gemini_rest(k, modelo, falas, vozes, estilo_geral, simples=False):
    quem = []
    for f in falas:
        if f["quem"] not in quem:
            quem.append(f["quem"])
    if len(quem) > 2:
        raise ValueError(f"Bloco com mais de 2 vozes: {quem}")
    tons = "; ".join(f"{nome_tela(f['quem'])}: {f.get('estilo') or estilo_geral}" for f in falas)
    if len(quem) == 2:
        texto = ("Leia este diálogo em português do Brasil, com sotaque brasileiro, como uma cena curta de novela para reels, em ritmo ágil e natural. "
                 f"Tom de cada fala, na ordem: {tons}. Faça uma pausa de um segundo entre uma fala e outra.\n\n"
                 + "\n".join(f"{nome_tela(f['quem'])}: {f['texto']}" for f in falas))
        speech = {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
            {"speaker": nome_tela(q), "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": vozes[q]}}} for q in quem]}}
    else:
        corpo_txt = "\n".join(f["texto"] for f in falas)
        if simples:
            texto = corpo_txt
        else:
            # instruções separadas do texto, para o modelo não ler a orientação em voz alta
            # formato curto da documentação do Gemini TTS ("Say cheerfully: ..."): a instrução não é lida
            est = "; ".join(f.get("estilo") or estilo_geral for f in falas[:1])
            texto = f"Say in Brazilian Portuguese, {est}:\n" + corpo_txt
        speech = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": vozes[quem[0]]}}}
    corpo = {"contents": [{"parts": [{"text": texto}]}],
             "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": speech}}
    c, t = _http("POST", f"{GL}/models/{modelo}:generateContent", corpo, {"x-goog-api-key": k})
    if c != 200:
        raise RuntimeError(f"HTTP {c}: {t[:300]}")
    parte = json.loads(t)["candidates"][0]["content"]["parts"][0]["inlineData"]
    return pcm_para_wav(base64.b64decode(parte["data"]))


def gemini_bloco(k, modelos, falas, vozes, estilo_geral):
    erros = []
    for m in modelos:
        for tentativa in range(3):
            try:
                wav = gemini_rest(k, m, falas, vozes, estilo_geral)
                # conferência: se o áudio ficou muito mais longo que o texto, o modelo leu a instrução junto
                palavras = sum(len(f["texto"].split()) for f in falas)
                seg = (len(wav) - 44) / (24000 * 2)
                if seg > palavras / 2.3 * 1.4 + 2:
                    print(f"  áudio longo demais ({seg:.0f}s para {palavras} palavras); refazendo só com o texto", flush=True)
                    wav = gemini_rest(k, m, falas, vozes, estilo_geral, simples=True)
                return wav, m
            except Exception as e:
                msg = str(e)
                if "HTTP 429" in msg and tentativa < 2:
                    time.sleep(30 * (tentativa + 1)); continue
                erros.append(f"{m}: {msg[:200]}")
                break
    raise RuntimeError(" | ".join(erros))


def rodar_gemini(p, pasta):
    k = gemini_chave()
    modelos, disp = modelos_tts(k, p.get("modelo"))
    p["_disponiveis"] = disp
    estilo = p.get("estilo", "natural e com emoção")
    feitos = []
    for b in p["blocos"]:
        audio, usado = gemini_bloco(k, modelos, b["falas"], p["vozes"], estilo)
        modelos = [usado] + [m for m in modelos if m != usado]
        nome = f"cena{b['n']}.wav"
        with open(os.path.join(pasta, nome), "wb") as f:
            f.write(audio)
        feitos.append(f"{nome} ({usado})")
        time.sleep(3)
    return feitos


def rodar_chatterbox(p, pasta):
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    try:
        modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu", t3_model=p.get("versao", "v3"))
    except TypeError:  # versão instalada sem escolha de checkpoint
        modelo = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
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
    k = gemini_chave()
    modelos, _ = modelos_tts(k, p.get("modelo"))
    os.makedirs(os.path.join(RAIZ, "refs"), exist_ok=True)
    feitos = []
    for quem, d in p["elenco"].items():
        audio, usado = gemini_bloco(k, modelos, [{"quem": quem, "texto": d["frase"], "estilo": d.get("estilo")}],
                                    {quem: d["voz"]}, "natural")
        with open(os.path.join(RAIZ, "refs", f"{quem}.wav"), "wb") as f:
            f.write(audio)
        feitos.append(f"refs/{quem}.wav ({usado})")
        time.sleep(3)
    return feitos


def _http(metodo, url, corpo=None, headers=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=dados, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def rodar_diagnostico(p, pasta):
    """Testa a chave em cada endereço possível e grava as respostas (sem a chave)."""
    k = os.environ.get("GEMINI_API_KEY", "")
    out = {"prefixo_chave": k[:3], "tamanho_chave": len(k)}
    corpo = {"contents": [{"parts": [{"text": "Diga em português do Brasil: Olá, tudo bem?"}]}],
             "generationConfig": {"responseModalities": ["AUDIO"],
                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}}}}
    c, t = _http("GET", "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": k})
    tts = []
    try:
        tts = [m["name"] for m in json.loads(t).get("models", []) if "tts" in m["name"]]
    except Exception:
        pass
    out["gl_listar"] = {"http": c, "modelos_tts": tts, "trecho": t[:300] if not tts else ""}
    for m in (tts[:3] or ["models/gemini-2.5-flash-preview-tts"]):
        c, t = _http("POST", f"https://generativelanguage.googleapis.com/v1beta/{m}:generateContent", corpo, {"x-goog-api-key": k})
        out[f"gl_{m}"] = {"http": c, "trecho": t[:300]}
    for m in ["gemini-2.5-flash-tts", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-tts"]:
        c, t = _http("POST", f"https://aiplatform.googleapis.com/v1beta1/publishers/google/models/{m}:generateContent?key={k}", corpo)
        out[f"vertex_{m}"] = {"http": c, "trecho": t[:300]}
    tts_corpo = {"input": {"prompt": "Fale de forma natural", "text": "Olá, tudo bem?"},
                 "voice": {"languageCode": "pt-BR", "name": "Kore", "modelName": "gemini-2.5-flash-tts"},
                 "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}
    c, t = _http("POST", f"https://texttospeech.googleapis.com/v1/text:synthesize?key={k}", tts_corpo)
    out["cloud_tts"] = {"http": c, "trecho": t[:300]}
    with open(os.path.join(pasta, "diagnostico.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return ["diagnostico.json"]


def rodar_modelos(p, pasta):
    """Lista os modelos que a chave enxerga (imagem, vídeo, voz), sem gerar nada."""
    k = gemini_chave()
    c, t = _http("GET", f"{GL}/models?pageSize=500", headers={"x-goog-api-key": k})
    out = {"http": c}
    if c == 200:
        ms = json.loads(t).get("models", [])
        out["todos"] = sorted(m["name"].split("/")[-1] + " | " + ",".join(m.get("supportedGenerationMethods", [])) for m in ms)
    else:
        out["trecho"] = t[:400]
    with open(os.path.join(pasta, "modelos.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return ["modelos.json"]


def gemini_imagem(k, modelos, prompt, proporcao="9:16", refs=()):
    partes = [{"text": prompt}]
    for r in refs:
        with open(os.path.join(RAIZ, r), "rb") as f:
            partes.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(f.read()).decode()}})
    erros = []
    for m in modelos:
        for cfg in ({"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": proporcao}}, {"responseModalities": ["IMAGE", "TEXT"]}):
            c, t = _http("POST", f"{GL}/models/{m}:generateContent", {"contents": [{"parts": partes}], "generationConfig": cfg},
                         {"x-goog-api-key": k})
            if c == 200:
                for pt in json.loads(t)["candidates"][0]["content"]["parts"]:
                    if "inlineData" in pt:
                        return base64.b64decode(pt["inlineData"]["data"]), m
                erros.append(f"{m}: sem imagem na resposta")
            else:
                erros.append(f"{m} HTTP {c}: {t[:220]}")
                if c in (404, 429, 403):
                    break
    raise RuntimeError(" | ".join(erros))


def rodar_imagens(p, pasta):
    k = gemini_chave()
    modelos = p.get("modelos", ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-3.1-flash-image"])
    feitos = []
    for im in p["imagens"]:
        dados, usado = gemini_imagem(k, modelos, im["prompt"], im.get("proporcao", "9:16"), im.get("refs", []))
        destino = os.path.join(RAIZ, im["salvar_em"]) if im.get("salvar_em") else os.path.join(pasta, im["nome"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(dados)
        feitos.append(f"{im['nome']} ({usado})")
        time.sleep(4)
    return feitos


MOTORES = {"imagens": rodar_imagens, "modelos": rodar_modelos, "diagnostico": rodar_diagnostico, "gemini": rodar_gemini, "chatterbox": rodar_chatterbox, "urls": rodar_urls, "refs": rodar_refs}


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
            salvar_status(pasta, {"ok": True, "motor": p["motor"], "arquivos": feitos, "segundos": round(time.time() - t0),
                                  "modelos": p.get("_disponiveis")})
            print(f"OK {pid}: {feitos}")
        except Exception as e:
            salvar_status(pasta, {"ok": False, "motor": p.get("motor"), "modelos": p.get("_disponiveis"), "erro": f"{type(e).__name__}: {e}",
                                  "detalhe": traceback.format_exc()[-1500:]})
            print(f"ERRO {pid}: {e}")


if __name__ == "__main__":
    main()
