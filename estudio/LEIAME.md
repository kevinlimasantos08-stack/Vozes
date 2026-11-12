# Estúdio diário de séries — @continua.br

Rotina de todo dia (17h): continuar **A Vizinha do 47** e **O Último Ônibus**, um episódio de cada.
Série nova (12/11): **O Último Turno**: terror 3D com narrador (Gemini Charon), bíblia em `estudio/series/turno.md`, roteiros em `estudio/roteiros/turno_epN.json`. Rodar com `cp motor/toon.py ~/.reel2d/toon3d.py; cp motor/toon_finaliza.py ~/.reel2d/; cd ~/.reel2d && python3 toon3d.py <ep>.json --repo /home/claude/vozes` (sem `-I`), ~1 h por episódio entre voz e render.

## Preparar o ambiente (sessão nova)
```bash
mkdir -p ~/.reel2d && cd ~/.reel2d
pip install --break-system-packages -q kokoro-onnx soundfile pycairo
for f in Bold Medium ExtraBold; do [ -s Poppins-$f.ttf ] || curl -sSL -o Poppins-$f.ttf https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-$f.ttf; done
[ -s Jost.ttf ] || curl -sSL -o Jost.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf"
[ -s Italiana.ttf ] || curl -sSL -o Italiana.ttf https://raw.githubusercontent.com/google/fonts/main/ofl/italiana/Italiana-Regular.ttf
mkdir -p ~/.local/share/fonts && cp *.ttf ~/.local/share/fonts/ && fc-cache -f >/dev/null
cp /home/claude/vozes/estudio/motores/*.py ~/.reel2d/
```
(O kokoro.onnx só é necessário se alguma fala ficar sem áudio pronto; com vozes do GitHub não precisa.)

## Vozes (sempre pelo estúdio Vozes, Gemini)
- Pedido em `pedidos/AAAAMMDD_<id>.json`, motor `gemini`, modelo `gemini-3.1-flash-tts-preview`.
- **Economia de cota:** juntar falas em blocos de até 2 vozes (vários falantes) — a cota grátis tem limite de pedidos por dia. Narrador: até 4 frases por bloco. Cortar depois pelas pausas e conferir quem fala pela altura da voz.
- **Cota do Gemini (~10 pedidos/dia no plano grátis):** se der HTTP 429, completar as falas que faltam pelo motor `chatterbox` do mesmo estúdio, clonando as vozes de `refs/<personagem>.wav` (já existem: nina, caio, celia, lurdes, narrador_onibus). Pedido: `{"id": "...", "motor": "chatterbox", "versao": "v3", "falas": [{"quem": "<ref>", "texto": "...", "intensidade": 0.5}]}`; leva ~1 min por fala. O Chatterbox fala mais devagar: acelerar só esses arquivos (atempo ~1.1). Avisar o Kevin na entrega quais falas saíram no Chatterbox.
- **Pedidos que falharam ficam rodando de novo a cada push** (o gerar.py refaz todo pedido sem `status.json` ok). Depois que um pedido Gemini falhar por 429 e as falas forem refeitas no Chatterbox, mover o pedido falho para `pedidos/arquivo/` para não gastar cota nem tempo.
- **Cortar blocos de várias frases:** o narrador faz pausas dentro da frase (". E…"). Conferir as pausas mais longas contra a estrutura do texto antes de aceitar o corte; se precisar, cortar em tempos fixos.
- **Conferência de legenda x voz:** motor `transcrever` (faster-whisper no GitHub): pôr o mp3 em `qa/` e o pedido `{"id": "qa-<ep>", "motor": "transcrever", "arquivos": ["qa/<ep>.mp3"]}`. (O ambiente da conversa não baixa modelos do Hugging Face.)
- **VoiceStudio (Kevin pediu em 12/11):** motor `voicestudio` com `clonar` usando `refs/<quem>_curto.wav` (4–7 s; com refs longas leva ~6 min por fala, com as curtas ~4 min). Dividir em pedidos de até 8 falas (o estúdio entrega cada pedido assim que termina; limite do job 170 min). Para cortar ref: `ffmpeg -ss A -to B -i ref.wav` (o -ss ANTES do -i; depois do -i, o afade deixou o corte mudo). Licença do modelo: CC-BY-NC (uso não comercial).
- Personagem novo sem ref: montar `refs/<id>.wav` (10–25 s, só a voz dele) a partir de falas Gemini já geradas.

## Regras de qualidade (não negociáveis)
1. Gancho forte nos 2 primeiros segundos (abertura fria com a frase mais forte do episódio; título com `titulo_na_fala` / `titulo_no_bloco`).
2. Falas naturais, curtas, sem explicar para o público; nenhum personagem some sem motivo; cenário e pose condizentes com o momento (camas, sofá, rua…).
3. Legenda no tempo da voz (os motores já alinham pela voz real); ritmo: `gap` 0.12, `pausa_max` 0.35–0.4, `vel_voz` ~1.05–1.15 se a voz estiver lenta.
4. Transições suaves (já no motor). Som sem saturação (pico ≤ 0.9).
5. 55–75 s, termina com pergunta nova para os comentários e "CONTINUA...".
6. Versão leve para celular (crf 24–26, maxrate ≤ 6M, main 4.0, faststart), até ~20 MB.

## Depois de cada episódio
Atualizar `estudio/series/<serie>.md` (o que foi revelado, perguntas em aberto) e salvar o roteiro em `estudio/roteiros/`. Commit e push.
