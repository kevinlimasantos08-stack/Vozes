# O Último Turno — bíblia da série (@continua.br)

**Gênero:** terror macabro. **Estilo:** 3D toon de noite (motor `blender/toon/motor.py` com `"noite"`), narrador em terceira pessoa; os personagens não falam, só agem (sentar, digitar, levantar, virar, olhar, medo, surgir/oculto).
**Orquestrador:** `motor/toon.py` (voz → 3D no GitHub, workflow "Estúdio Toon" → finalização com legenda, título e cartão "CONTINUA..."). Episódio em JSON salvo em `estudio/roteiros/turno_epN.json`.
**Voz do narrador (escolha do Kevin, 12/11):** VoiceStudio com voz descrita `"male, elderly, very low pitch"` (semente fixa = mesma voz em todos os episódios); `pausa_voz` 0.9 entre frases. Uso não comercial (CC-BY-NC).
**Duração:** ~60 s (Kevin escolheu 60 s e repositório público para ter minutos ilimitados no GitHub Actions).
**Cenário:** `escritorio` de noite (`"noite": {"fator": 0.32, "fator_personagem": 0.7, "fundo": "#06070C"}`); telas dos monitores acesas; fantasmas com `"fantasma": true` ficam pálidos e "acesos".

## Personagens
- **Rafa** (`rafa`, cacheado, camisa vermelha): novato do turno da madrugada num escritório. Senta na mesa5.
- **Os oito** (`g1`–`g8`, figurantes pálidos de pele cinza, crachá antigo): funcionários mortos. Digitam de olhos fechados nas mesas 1, 2, 3, 4, 6, 7, 8; o g8 tomou a cadeira do Rafa (mesa5).
- **O chefe** (ainda não apareceu): deixou a regra "não olhe para as outras mesas depois das três".

## Episódios
- **Ep 1 ("Quem bateu o ponto?"):** o ponto registra oito entradas às 3h com só o Rafa no prédio; primeira noite dele; regra do chefe: não olhar as outras mesas depois das três; às 3h01 teclados começam; ele levanta: todas as mesas ocupadas por gente de crachá antigo e pele cinza, de olhos fechados, digitando; alguém já está sentado na cadeira dele; em todas as telas: "você é o nono"; todos param de digitar e abrem os olhos.

## Perguntas em aberto
- O que acontece com o nono? (gancho do Ep 1)
- Quem são os oito? O que aconteceu com eles (incêndio, acidente, demissão em massa)? Em que ano?
- O chefe sabia? Por que contratou o Rafa para esse turno?
- O que eles digitam a noite inteira?

## Lições de câmera (Ep 1)
- O escritório tem 8 mesas apertadas: `frente`/`close`/`detalhe` em personagem sentado ou cercado entram na cabeça de outro boneco. Nos planos-chave use `geral` com `pos`/`mira`/`lente` fixos.
- Close do fantasma da mesa2 (g2): `"pos": [-1.1, 2.0, 1.48], "mira": [-1.1, 3.62, 1.3], "lente": 42`. Geral da sala: `"pos": [3.9, -4.7, 2.6], "mira": [-0.6, 1.4, 0.8], "lente": 19`.
- Rafa no `centro` virado para a mesa5: `pos [-0.55, 0.62, 1.55]` com lente 40 deu um close extremo do olho; para ver o rosto inteiro, use lente ~24.
- Render: 9 bonecos e 53 s levaram ~40 min (4 partes de ~35 min).
- Narração VoiceStudio sai rápida (~3 palavras/s): acelerar com `atempo=0.9` na narracao.wav e usar `pausa` de 0.6–1.4 s por frase.

## Ideias guardadas para os próximos
- Os crachás têm a mesma data; o Rafa acha a ficha de contratação dele com a mesma data, 20 anos antes.
- O ponto do Rafa mostra que ele "bateu a entrada" antes de chegar ao prédio.
- O chefe aparece de dia e não tem reflexo no vidro.
