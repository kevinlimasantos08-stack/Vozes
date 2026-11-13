# O Último Ônibus — bíblia da série (@continua.br)

**Estilo:** toon com narrador (motor `estudio/motores/toon.py`), um bloco por frase narrada.
**Voz Gemini (estúdio Vozes):** narrador = Enceladus (voz grave de contador de histórias).
**VoiceStudio (desde o Ep 4, pedido do Kevin):** narrador clonado de `refs/narrador_onibus_curto.wav` (texto exato no pedido `pedidos/20261112_2_onibus-ep4a2.json`). ~4 min por frase no GitHub; até 8 frases por pedido.

## Personagens
- **Téo:** estudante, pega a linha 12 da madrugada. Nasceu dentro desse ônibus há 20 anos.
- **Seu Bento:** motorista da linha 12 há 20 anos. Calvo, barba grisalha, boné.
- **O motorista antigo (retrato sépia):** morreu levando a mãe do Téo em trabalho de parto ao hospital. Virou o "sétimo passageiro" que nunca descia.

## Episódios
- **Ep 1 ("Ele nunca desce"):** o ônibus para no ponto 12 vazio; a catraca gira sozinha (06→07); o passageiro invisível é o motorista antigo; ele espera o Téo; o banco ao lado está quente.
- **Ep 2 ("Pro Téo"):** passagem de 14/03/2006 no banco ("Pro Téo. Eu prometi te levar."); a mãe confirma o parto no ônibus; o fantasma só queria terminar a viagem e desce no ponto 12 — mas quem some na neblina é o Seu Bento, e o ônibus continua andando.

- **Ep 3 ("Quem dirige?"):** banco do motorista vazio, volante girando sozinho; catraca marca 01 passageiro (o Téo); jornal de 15/03/2006 "Acidente com ônibus da linha 12" na porta do hospital, fotos do motorista antigo e do cobrador — o cobrador era o Seu Bento (morreu naquela noite e nunca parou de trabalhar); o letreiro muda de "12 CENTRO" para "HOSPITAL"; no último banco, uma moça grávida em trabalho de parto: a mãe do Téo, 20 anos mais nova; relógio do painel 23:58, dois minutos antes do acidente; o banco do motorista está esperando por ele.

- **Ep 4 ("Ele vai dirigir?"):** o Téo assume o volante às 23:59; um caminhão sem farol vem na contramão (era assim que todos morreram); o Téo desvia, o ônibus para inteiro na porta da maternidade; duas sombras de uniforme ajudam a mãe a descer; o Seu Bento sorri no retrovisor pela primeira vez; tudo fica branco; o Téo acorda de manhã no ponto 12 ao lado do Seu Bento, vivo, que pergunta "a gente se conhece?"; no celular, o contato da mãe não existe mais.
- **Ep 5 ("Quem abriu a porta?", Gemini):** na casa da mãe, quem abre a porta é outro Téo (mesmo rosto, óculos, nome); a mãe pergunta "filho, quem é?" e ele diz "ninguém, mãe" — não vê o Téo; na estante, foto do bebê nascido na maternidade (15/03/2006), não no ônibus: salvando a mãe, o Téo apagou a própria vida; ninguém esbarra nele o dia inteiro; à meia-noite volta ao ponto 12, a porta do ônibus abre sozinha, o Seu Bento sorri no retrovisor "como se já esperasse"; a catraca gira sozinha e marca 07: o passageiro que nunca desce.

- **Ep 6 ("Quem sobe no lugar?", Gemini):** a regra do ônibus, dita pelo Seu Bento pelo retrovisor: "pra descer desse ônibus, alguém tem que subir no seu lugar" — foi assim que o motorista antigo desceu, quando o Téo subiu pela primeira vez; agora o lugar é do Téo; seis bancos "ocupados por ninguém", seis passageiros esperando a vez de descer; à meia-noite, no ponto 12, pela primeira vez alguém espera: a mãe do Téo, grisalha; ninguém vê o Téo, mas ela vê e diz "eu lembro de você. Foi você que dirigiu naquela noite"; a porta abre, a catraca (07) espera; se ela subir, o Téo desce e ela fica no lugar dele; a mãe põe o pé no primeiro degrau.

## Perguntas em aberto
- O Téo vai deixar a mãe subir no lugar dele? (gancho do Ep 6) Por que só ela lembra dele? Quem são os outros seis passageiros?
- Respondido no Ep 6: o Téo virou passageiro do ônibus; para descer, alguém precisa subir no lugar; o Seu Bento da noite lembra dele.
- O Téo virou o sétimo passageiro (um fantasma)? (gancho do Ep 5) Tem volta? O Seu Bento da noite sabe quem ele é?
- Respondido no Ep 5: o contato sumiu porque nesta linha do tempo nasceu outro Téo, no hospital.
- O que mais o Téo mudou? Por que o contato da mãe sumiu — ela não existe mais, ou ele nunca nasceu no ônibus? (gancho do Ep 4)
- O Seu Bento vivo não lembra dele: e o motorista antigo, também está vivo?
- Respondido no Ep 4: o Téo dirigiu e evitou o acidente.
- O ônibus voltou no tempo ou é a lembrança dos fantasmas?
- O que causou o acidente às 00:00?
- Respondido: ninguém dirigia (o volante girava sozinho); o Seu Bento era o cobrador e morreu em 2006; o ônibus está levando o Téo de volta à noite em que ele nasceu.

## Cenas disponíveis no toon.py
estrada, ponto, interior, motorista, catraca, teo_close, corredor, espelho, retrato, banco, bilhete (emocao.lado = frente/verso), descida (Bento de costas sumindo na neblina).
Novas no Ep 3: teo_corredor (Téo correndo pelo corredor), jornal (emocao.foco = chega | titulo | fotos | bento), painel (letreiro; emocao.texto, emocao.de para trocar o texto com falha, emocao.relogio = 23:58), mae (moça grávida no último banco; emocao.dor). Também: motorista emocao.gira (volante girando sozinho), catraca emocao.fixo = "01" (contador parado).
Novas no Ep 4: hospital (emocao.parado, emocao.sombras), caminhao (emocao.passa), branco, ponto_dia (emocao.bento, olha, teo), celular (emocao.vazio = "Nenhum contato"); motorista aceita emocao.quem = "teo".
Novas no Ep 5: porta (emocao.abre, mae, olha), dois_teos, foto (bebê na maternidade), calcada (gente atravessando o Téo); ponto aceita emocao.sem_onibus; espelho aceita emocao.sorri (rosto mais baixo, sorriso visível); catraca com fixo não toca o clique.
Nova no Ep 6: espera (a mãe grisalha no ponto, vista de dentro do ônibus pela porta aberta; emocao.longe | perto | olha | degrau).
Personagens toon: teo, teo2 (o outro Téo), bento, antigo, mae (cabelo longo), mae_hoje (grisalha, óculos). Para cenas novas, criar a função `cena_<nome>` e registrar em `CENAS`.
