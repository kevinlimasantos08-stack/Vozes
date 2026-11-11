# O Último Ônibus — bíblia da série (@continua.br)

**Estilo:** toon com narrador (motor `estudio/motores/toon.py`), um bloco por frase narrada.
**Voz Gemini (estúdio Vozes):** narrador = Enceladus (voz grave de contador de histórias).

## Personagens
- **Téo:** estudante, pega a linha 12 da madrugada. Nasceu dentro desse ônibus há 20 anos.
- **Seu Bento:** motorista da linha 12 há 20 anos. Calvo, barba grisalha, boné.
- **O motorista antigo (retrato sépia):** morreu levando a mãe do Téo em trabalho de parto ao hospital. Virou o "sétimo passageiro" que nunca descia.

## Episódios
- **Ep 1 ("Ele nunca desce"):** o ônibus para no ponto 12 vazio; a catraca gira sozinha (06→07); o passageiro invisível é o motorista antigo; ele espera o Téo; o banco ao lado está quente.
- **Ep 2 ("Pro Téo"):** passagem de 14/03/2006 no banco ("Pro Téo. Eu prometi te levar."); a mãe confirma o parto no ônibus; o fantasma só queria terminar a viagem e desce no ponto 12 — mas quem some na neblina é o Seu Bento, e o ônibus continua andando.

## Perguntas em aberto
- Quem está dirigindo o ônibus?
- O Seu Bento também estava morto? Desde quando?
- Para onde o ônibus está levando o Téo agora?

## Cenas disponíveis no toon.py
estrada, ponto, interior, motorista, catraca, teo_close, corredor, espelho, retrato, banco, bilhete (emocao.lado = frente/verso), descida (Bento de costas sumindo na neblina).
Personagens toon: teo, bento, antigo. Para cenas novas, criar a função `cena_<nome>` e registrar em `CENAS`.
