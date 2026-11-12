# A Vizinha do 47 — bíblia da série (@continua.br)

**Estilo:** 2D recortado (motor `estudio/motores/reel2d.py`, modo `ficcao`), diálogo entre personagens.
**Vozes VoiceStudio (desde o Ep 5, pedido do Kevin):** clonadas de `refs/<personagem>_curto.wav` (refs curtas de 4–6 s; texto exato no pedido `pedidos/20261112_3_vizinha47-ep5b2.json`, campo `clonar`). ~4 min por fala no GitHub; dividir em pedidos de até 8 falas. Lurdes acelerada com atempo 1.1.
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
- **Ep 4 ("O desenho na parede"):** a Lurdes trancou o Caio dentro do 47 ("igualzinho sua mãe fez comigo"; "ele quer te levar embora daqui"); a chave estava pendurada na fechadura por fora; no quarto queimado o Caio limpa a fuligem e acha um desenho de giz: casa pegando fogo + "DESCULPA VÓ - NINA"; a Nina não lembra; a Lurdes aparece: "você desenhou isso um dia antes do fogo"; a Nina, pela primeira vez, chama ela de "vó": "o que eu fiz?". Vozes: Chatterbox (cota do Gemini esgotada).

- **Ep 5 ("O que a Nina ouviu"):** a Nina não pôs fogo — desenhou o que ouviu a mãe dizer ao telefone na noite anterior: "amanhã essa casa não existe mais"; segundo a Lurdes, a Célia não foi chamar a polícia, "foi buscar o galão"; a Célia aparece na porta do 47 de madrugada: "Nina! Sai dessa casa. Agora." / "Vim te levar embora"; a Nina: "a senhora mentiu pra mim a vida inteira!"; a Célia: "Menti pra te proteger. Dela."; a Lurdes: "Ela voltou pra terminar o que começou."

## Perguntas em aberto (para os próximos)
- A Célia veio queimar o 47 de novo (com a Nina e o Caio dentro)? (gancho do Ep 5)
- Proteger a Nina "dela" — a Lurdes é o perigo? A Lurdes mente sobre o galão?
- O que aconteceu de verdade naquela noite? Quem está dizendo a verdade, a mãe ou a "vó"?
- Respondido no Ep 5: a Nina não causou o incêndio (ela desenhou o que ouviu).
- A Nina (6 anos) causou o incêndio? Por que pediu desculpa um dia ANTES do fogo? (gancho do Ep 4)
- A mãe mentiu para proteger a Nina? Onde a Célia foi depois da confissão?
- O que a Lurdes quer: vingança, a Nina de volta ("você era dela"), ou a verdade?
- O Caio corre perigo por "querer levar a Nina embora"?
- Respondido: onde estava o Caio (trancado no 47 pela Lurdes).

## Cenários e poses já disponíveis
`quarto` (camas: pose `deitado`, `camas_vazias`), `sala` (sofá: pose `sentado`), `casa`, `rua`, `empresa`, `padaria`, `escritorio`, `fachada` (frente da casa 47 queimada, porta com o número, janelas tapadas, luz de varanda), `queimado` (quarto antigo da Nina queimado, com o desenho de giz iluminado por lanterna; use câmera `plano` para o desenho aparecer).
Personagem que fala sem estar em `personagens` vira voz fora de quadro (ex.: Caio atrás da porta no Ep 4).
Pose pode ser por personagem: `"pose": {"nina": "deitado"}`.
