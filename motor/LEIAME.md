# Motores dos reels

- `reel2d.py` — reels 2D recortados (advocacia e ficção): personagens com volume, gestos, câmera viva, cenários animados.
- `toon.py` — episódio 3D toon da @continua.br de ponta a ponta (narração Gemini → render 3D no GitHub → vídeo final).
- `toon_finaliza.py` — junta vídeo 3D, narração, trilha, efeitos, título e legenda (usado pelo toon.py).
- O motor 3D em si fica em `blender/toon/motor.py` e roda no GitHub Actions (workflow "Estúdio Toon").

Em cada conversa: `mkdir -p ~/.reel2d && cp motor/*.py ~/.reel2d/` (mais as fontes e o Kokoro, ver a skill).
