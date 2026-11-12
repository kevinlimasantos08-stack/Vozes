# Estúdio de vozes

Gera as vozes dos reels animados da Lima Santos Advocacia. Basta colocar um pedido em `pedidos/` (JSON):
o GitHub Actions gera os áudios e grava em `saidas/<id>/`, com um `status.json` dizendo se deu certo.

Motores:
- `gemini`: Gemini TTS, um arquivo por bloco (`cena1.wav`...), até 2 vozes por bloco. Precisa do segredo `GEMINI_API_KEY`.
- `chatterbox`: Chatterbox Multilingual (código aberto, licença MIT), um arquivo por fala. Usa `refs/<personagem>.wav` para fixar a voz.
- `voicestudio`: VoiceStudio / OmniVoice (código aberto), um arquivo por fala (`01_<quem>.wav`...). A voz de cada personagem é descrita em `vozes` (em inglês: `male`/`female`, `child`, `teenager`, `young adult`, `middle-aged`, `elderly`, `low pitch`, `moderate pitch`, `high pitch`, `whisper`), ou clonada de `refs/<personagem>.wav` informando em `clonar` o texto exato falado nesse arquivo. Atenção: a licença do modelo é CC-BY-NC (uso não comercial).
- `refs`: gera com Gemini as vozes de referência do elenco em `refs/`.
- `urls`: baixa arquivos prontos (ex.: links do ElevenLabs).

A chave fica só no segredo do repositório. Nunca coloque a chave em arquivo.
