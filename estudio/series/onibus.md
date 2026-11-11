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

- **Ep 3 ("Quem dirige?"):** banco do motorista vazio, volante girando sozinho; catraca marca 01 passageiro (o Téo); jornal de 15/03/2006 "Acidente com ônibus da linha 12" na porta do hospital, fotos do motorista antigo e do cobrador — o cobrador era o Seu Bento (morreu naquela noite e nunca parou de trabalhar); o letreiro muda de "12 CENTRO" para "HOSPITAL"; no último banco, uma moça grávida em trabalho de parto: a mãe do Téo, 20 anos mais nova; relógio do painel 23:58, dois minutos antes do acidente; o banco do motorista está esperando por ele.

## Perguntas em aberto
- O Téo vai assumir o volante? Se salvar o motorista antigo e o Bento, ele muda a noite em que nasceu? (gancho do Ep 3)
- O ônibus voltou no tempo ou é a lembrança dos fantasmas?
- O que causou o acidente às 00:00?
- Respondido: ninguém dirigia (o volante girava sozinho); o Seu Bento era o cobrador e morreu em 2006; o ônibus está levando o Téo de volta à noite em que ele nasceu.

## Cenas disponíveis no toon.py
estrada, ponto, interior, motorista, catraca, teo_close, corredor, espelho, retrato, banco, bilhete (emocao.lado = frente/verso), descida (Bento de costas sumindo na neblina).
Novas no Ep 3: teo_corredor (Téo correndo pelo corredor), jornal (emocao.foco = chega | titulo | fotos | bento), painel (letreiro; emocao.texto, emocao.de para trocar o texto com falha, emocao.relogio = 23:58), mae (moça grávida no último banco; emocao.dor). Também: motorista emocao.gira (volante girando sozinho), catraca emocao.fixo = "01" (contador parado).
Personagens toon: teo, bento, antigo, mae (cabelo longo). Para cenas novas, criar a função `cena_<nome>` e registrar em `CENAS`.
