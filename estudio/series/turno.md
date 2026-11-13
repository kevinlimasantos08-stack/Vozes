# O Último Turno — bíblia da série (@continua.br)

**Gênero:** terror macabro. **Estilo:** 3D toon de noite (motor `blender/toon/motor.py` com `"noite"`), narrador em terceira pessoa; os personagens não falam, só agem (sentar, digitar, levantar, virar, olhar, medo, surgir/oculto).
**Orquestrador:** `motor/toon.py` (voz → 3D no GitHub, workflow "Estúdio Toon" → finalização com legenda, título e cartão "CONTINUA..."). Episódio em JSON salvo em `estudio/roteiros/turno_epN.json`.
**Voz do narrador:** Gemini **Charon** (estúdio Vozes), estilo `"Brazilian Portuguese accent from São Paulo, deep middle-aged male horror storyteller telling a scary story at night, natural human delivery, slow, low and ominous, <tom da frase>"`, em blocos de até 4 frases (pedido `pedidos/20261112_16_turno-ep1-gemini.json`); cortar as frases pela transcrição (motor `transcrever`) e montar a `narracao.wav` com 1,3 s entre frases. Sem atempo.
- A voz VoiceStudio descrita ("male, elderly, very low pitch") foi **reprovada pelo Kevin** (12/11): artificial, e o sotaque mudava de uma frase para outra. Não usar.
- Reserva (cota do Gemini esgotada): Chatterbox clonando `refs/narrador_turno.wav` (15 s, Charon) ou VoiceStudio clonando `refs/narrador_turno_curto.wav` (6 s; texto: "O ponto do escritório registrou oito entradas às três da manhã.").
**Duração:** ~60 s (Kevin escolheu 60 s e repositório público para ter minutos ilimitados no GitHub Actions).
**Cenário:** `escritorio` de noite (`"noite": {"fator": 0.32, "fator_personagem": 0.7, "fundo": "#06070C"}`); telas dos monitores acesas; fantasmas com `"fantasma": true` ficam pálidos e "acesos".

## Personagens
- **Rafa** (`rafa`, cacheado, camisa vermelha): novato do turno da madrugada num escritório. Senta na mesa5.
- **Os oito** (`g1`–`g8`, figurantes pálidos de pele cinza, crachá antigo): funcionários mortos. Digitam de olhos fechados nas mesas 1, 2, 3, 4, 6, 7, 8; o g8 tomou a cadeira do Rafa (mesa5).
- **O vulto** (`vulto`, figurante de terno escuro, não fantasma): apareceu na porta no fim do Ep 2 (nona entrada no ponto).
- **O chefe** (ainda não apareceu): deixou a regra "não olhe para as outras mesas depois das três".

## Episódios
- **Ep 1 ("Quem bateu o ponto?"):** o ponto registra oito entradas às 3h com só o Rafa no prédio; primeira noite dele; regra do chefe: não olhar as outras mesas depois das três; às 3h01 teclados começam; ele levanta: todas as mesas ocupadas por gente de crachá antigo e pele cinza, de olhos fechados, digitando; alguém já está sentado na cadeira dele; em todas as telas: "você é o nono"; todos param de digitar e abrem os olhos.

- **Ep 2 ("O nono funcionário", Gemini Charon):** os oito abrem os olhos e ninguém pisca; o Rafa corre para a porta: trancada pelo lado de fora; os teclados voltam a bater; na tela da mesa 2, uma ficha de contratação do turno da madrugada com admissão em 13/11/2006 — todas as telas com a mesma data; "não era pra assustar o Rafa, era pra completar a equipe"; na mesa 5, a ficha do nono funcionário: nome Rafael, foto dele, mesma data, vinte anos atrás; o relógio do ponto apita: nona entrada registrada às 3h09 — mas o Rafa não bateu o ponto; um vulto de terno escuro aparece na porta. "Então quem acabou de entrar?"

## Perguntas em aberto
- Quem acabou de entrar (o vulto de terno na porta, `vulto` no elenco)? É o chefe? Quem trancou a porta por fora? (gancho do Ep 2)
- Como o Rafa foi contratado em 13/11/2006, vinte anos antes? É o mesmo Rafa?
- Respondido no Ep 2: o nono é o Rafa — os oito querem completar a equipe; a ficha dele tem a mesma data dos crachás.
- O que acontece com o nono? (gancho do Ep 1)
- Quem são os oito? O que aconteceu com eles (incêndio, acidente, demissão em massa)? Em que ano?
- O chefe sabia? Por que contratou o Rafa para esse turno?
- O que eles digitam a noite inteira?

## Voz (lição do Ep 2)
- Na narracao.wav, separar as frases com ~2,4 s (não 1,3 s): o Charon faz pausas de até 1,6 s dentro da frase e o corte automático (dividir_audio_unico) errou a divisão com 1,3 s. Conferir a lista "Tempos das frases" antes de deixar o render seguir.
- A cota do gemini-3.1 já tinha acabado; o estúdio caiu sozinho no gemini-2.5-flash-preview-tts, mesma voz Charon.

## Lições de câmera (Ep 1)
- O escritório tem 8 mesas apertadas: `frente`/`close`/`detalhe` em personagem sentado ou cercado entram na cabeça de outro boneco. Nos planos-chave use `geral` com `pos`/`mira`/`lente` fixos.
- Close do fantasma da mesa2 (g2): `"pos": [-1.1, 2.0, 1.48], "mira": [-1.1, 3.62, 1.3], "lente": 42`. Geral da sala: `"pos": [3.9, -4.7, 2.6], "mira": [-0.6, 1.4, 0.8], "lente": 19`.
- Rafa no `centro` virado para a mesa5: `pos [-0.55, 0.62, 1.55]` com lente 40 deu um close extremo do olho; para ver o rosto inteiro, use lente ~24.
- Render: 9 bonecos e 53 s levaram ~40 min (4 partes de ~35 min).
- Com o Gemini Charon (~2,4 palavras/s) e `pausa` de 0,3–1,1 s, o Ep 1 deu ~64 s.

## Ideias guardadas para os próximos
- (usadas no Ep 2: ficha com a mesma data, 20 anos antes; ponto registrando entrada que o Rafa não bateu)
- O chefe aparece de dia e não tem reflexo no vidro.
