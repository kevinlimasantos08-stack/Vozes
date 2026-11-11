# A Vizinha do 47 — bíblia da série (@continua.br)

**Estilo:** 2D recortado (motor `estudio/motores/reel2d.py`, modo `ficcao`), diálogo entre personagens.
**Vozes Gemini (estúdio Vozes):** Nina = Leda · Caio = Puck · Dona Lurdes = Gacrux · Dona Célia (mãe da Nina) = Kore.
**Elenco extra no JSON:** `celia` (ver `estudio/roteiros/vizinha47_ep3.json`, campo `elenco_extra`).

## Personagens
- **Nina:** jovem, mudou com o namorado Caio para a casa vizinha à 47. Morou no 47 até os 6 anos e não lembra.
- **Caio:** namorado da Nina, protetor, cético.
- **Dona Lurdes:** senhora de coque e óculos. Morreu no incêndio do 47 há ~20 anos, mas continua aparecendo para a Nina. A Nina criança a chamava de "vó".
- **Dona Célia:** mãe da Nina. Saiu com a Nina no colo e trancou a Lurdes por fora no 47; quando voltou com a polícia, a casa pegava fogo.

## Episódios
- **Ep 1:** casal se muda; Lurdes diz que não esperava que a Nina voltasse "depois do incêndio".
- **Ep 2 ("Quem guardou essa foto?"):** foto da Nina com 6 anos na porta 47; Lurdes guardou por 20 anos; "pergunta pra sua mãe por que ela trancou a porta"; a única vítima do incêndio se chamava Lurdes.
- **Ep 3 ("Ela trancou a porta"):** batidas às 3h; a mãe confessa; "você chamava ela de vó"; cama do Caio vazia, Lurdes no quarto: "ele foi buscar água… agora ninguém tranca mais a porta".

## Perguntas em aberto (para os próximos)
- Onde está o Caio? (gancho do Ep 3)
- O que a Lurdes quer com a Nina agora?
- O incêndio foi acidente? Quem ateou o fogo?
- A mãe é culpada?

## Cenários e poses já disponíveis
`quarto` (camas: pose `deitado`, `camas_vazias`), `sala` (sofá: pose `sentado`), `casa`, `rua`, `empresa`, `padaria`, `escritorio`.
Pose pode ser por personagem: `"pose": {"nina": "deitado"}`.
