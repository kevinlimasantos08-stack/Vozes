# motor.py — estúdio 3D toon da @continua.br (Blender 4.2, Workbench)
# Lê um roteiro 3D (JSON) com cenário, elenco, planos de câmera e ações, já com os tempos da narração,
# e renderiza os quadros PNG de uma parte do vídeo.
# Uso: blender -b -P motor.py -- <roteiro.json> <pasta_quadros> <parte> <n_partes>
import bpy, math, sys, os, json, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ROT = json.load(open(argv[0], encoding="utf-8"))
OUT = argv[1]
PARTE = int(argv[2]) if len(argv) > 2 else 1
NPARTES = int(argv[3]) if len(argv) > 3 else 1
os.makedirs(OUT, exist_ok=True)
FPS = 24
RNG = random.Random(ROT.get("semente", 7))

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
COL = sc.collection


# ================================================================== tempo
TEMPOS = ROT.get("tempos", [])          # [{"t0":..,"dur":..}] das frases da narração
DURACAO = float(ROT["duracao"])


def T(ref, base=0.0):
    """Converte referência de tempo em segundos: 3.2 | "f3" (início da frase 3) | "f3.fim" | "f3+0.5" | "+1.2" (relativo à base)."""
    if ref is None:
        return base
    if isinstance(ref, (int, float)):
        return float(ref)
    s = str(ref).replace(" ", "")
    desloc = 0.0
    for sinal in ("+", "-"):
        i = s.find(sinal, 1)
        if i > 0:
            desloc = float(s[i:]); s = s[:i]; break
    if s.startswith("+") or s.startswith("-"):
        return base + float(s)
    if s.startswith("f"):
        fim = s.endswith(".fim")
        n = int(s[1:].replace(".fim", ""))
        fr = TEMPOS[n - 1]
        return fr["t0"] + (fr["dur"] if fim else 0) + desloc
    return float(s) + desloc


def Q(t):
    return 1 + int(round(t * FPS))


NQ = Q(DURACAO)


# ================================================================== materiais e primitivas
def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


MATS = {}


def mat(cor):
    if cor not in MATS:
        m = bpy.data.materials.new(cor); m.diffuse_color = lin(cor); m.roughness = 0.8
        MATS[cor] = m
    return MATS[cor]


def _fin(o, cor, bevel=0.0, suave=False, pai=None):
    o.data.materials.append(mat(cor))
    if bevel:
        bv = o.modifiers.new("b", "BEVEL"); bv.width = bevel; bv.segments = 3
    if suave:
        for p in o.data.polygons:
            p.use_smooth = True
    if pai:
        o.parent = pai
    return o


def caixa(loc, dim, cor, bevel=0.02, pai=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (dim[0] / 2, dim[1] / 2, dim[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    return _fin(o, cor, bevel, pai=pai)


def esfera(loc, esc, cor, pai=None, seg=28):
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc, segments=seg, ring_count=max(8, seg // 2))
    o = bpy.context.active_object
    o.scale = esc
    bpy.ops.object.transform_apply(scale=True)
    return _fin(o, cor, suave=True, pai=pai)


def cil(loc, r, h, cor, pai=None, rot=(0, 0, 0), seg=24):
    bpy.ops.mesh.primitive_cylinder_add(location=loc, radius=r, depth=h, rotation=rot, vertices=seg)
    return _fin(bpy.context.active_object, cor, bevel=min(r, h) * 0.25, suave=True, pai=pai)


def toro(loc, r, esp, cor, pai=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(location=loc, major_radius=r, minor_radius=esp, rotation=rot,
                                     major_segments=24, minor_segments=8)
    return _fin(bpy.context.active_object, cor, suave=True, pai=pai)


def capsula(loc, r, h, cor, pai=None):
    cil(loc, r, h, cor, pai=pai)
    esfera((loc[0], loc[1], loc[2] - h / 2), (r, r, r), cor, pai=pai, seg=16)
    esfera((loc[0], loc[1], loc[2] + h / 2), (r, r, r), cor, pai=pai, seg=16)


def vazio(nome, loc, pai=None):
    o = bpy.data.objects.new(nome, None)
    COL.objects.link(o)
    o.location = loc
    if pai:
        o.parent = pai
    return o


def planta(x, y, e=1.0):
    cil((x, y, 0.22 * e), 0.2 * e, 0.44 * e, "#C8673C")
    for k in range(6):
        a = k * math.pi / 3
        esfera((x + math.cos(a) * 0.14 * e, y + math.sin(a) * 0.14 * e, (0.62 + 0.12 * (k % 2)) * e),
               (0.18 * e, 0.18 * e, 0.24 * e), "#3F8F55", seg=14)


# ================================================================== cenários
# Cada cenário devolve: pontos nomeados {nome: (x, y, direção em graus para onde a pessoa olha)},
# limites da câmera (xmin, xmax, ymin, ymax, zmax), cor do fundo e lugares para sentar {nome: (x, y, giro, altura_assento)}.
# Direção: 0° = olhando para a frente da sala (para a câmera, -Y); 180° = de costas.

def mesa_escritorio(x, y):
    p = vazio("mesa", (x, y, 0)); p.rotation_euler.z = math.pi
    caixa((0, 0, 0.74), (1.4, 0.75, 0.05), "#D6C3A5", 0.01, pai=p)
    for dx in (-0.65, 0.65):
        caixa((dx, 0, 0.37), (0.05, 0.7, 0.72), "#6E6A66", 0.005, pai=p)
    caixa((0, 0.36, 0.95), (1.45, 0.04, 0.45), "#5B86B0", 0.01, pai=p)
    caixa((0, 0.12, 1.02), (0.6, 0.04, 0.36), "#22252B", 0.01, pai=p)
    caixa((0, 0.1, 1.02), (0.54, 0.01, 0.3), "#6CB6E2", 0.0, pai=p)
    caixa((0, 0.16, 0.82), (0.06, 0.06, 0.14), "#22252B", 0.005, pai=p)
    caixa((0, -0.12, 0.775), (0.45, 0.15, 0.02), "#30343A", 0.004, pai=p)
    cil((0.45, -0.1, 0.8), 0.04, 0.1, "#F2F0EC", pai=p)
    caixa((0, -0.62, 0.48), (0.5, 0.5, 0.08), "#2B2F36", 0.03, pai=p)
    caixa((0, -0.86, 0.78), (0.48, 0.07, 0.55), "#2B2F36", 0.03, pai=p)
    cil((0, -0.62, 0.24), 0.03, 0.45, "#6E6A66", pai=p)


def cen_escritorio():
    PAREDE, FAIXA, PISO = "#F6F1E7", "#2F6E73", "#AEB6C1"
    caixa((0, 0, -0.05), (10, 12, 0.1), PISO, 0)
    caixa((0, 5.55, 1.5), (10, 0.1, 3.0), PAREDE, 0)
    caixa((0, 5.48, 0.55), (10, 0.06, 1.1), FAIXA, 0)
    for x in (-4.55, 4.55):
        caixa((x, 0, 1.5), (0.1, 12, 3.0), PAREDE, 0)
        caixa((x * 0.987, 0, 0.55), (0.06, 12, 1.1), FAIXA, 0)
    caixa((1.8, 5.47, 1.05), (1.05, 0.08, 2.1), "#4A3B32", 0.01)
    caixa((1.8, 5.43, 1.05), (0.9, 0.04, 1.95), "#7A5E4A", 0.01)
    esfera((2.15, 5.38, 1.0), (0.04, 0.04, 0.04), "#D9C4A3")
    caixa((1.8, 5.48, 2.35), (0.6, 0.04, 0.18), "#3C8D5A", 0.005)
    for y in (-1.5, 1.5):
        caixa((-4.48, y, 1.75), (0.04, 1.8, 1.2), "#A8D2EE", 0.0)
        caixa((-4.46, y, 1.75), (0.03, 0.06, 1.2), "#F2F0EC", 0.0)
    caixa((-1.4, 5.47, 1.6), (1.4, 0.05, 0.9), "#B88A5A", 0.01)
    for i, (dx, dz, c) in enumerate([(-0.4, 0.2, "#F6E27A"), (0.0, 0.25, "#F2A0B5"), (0.35, 0.15, "#FFFFFF"),
                                     (-0.25, -0.2, "#9FD8F0"), (0.3, -0.18, "#F6E27A")]):
        caixa((-1.4 + dx, 5.44, 1.6 + dz), (0.24, 0.01, 0.3), c, 0.0, rot=(0, (i - 2) * 0.08, 0))
    for i, c in enumerate(["#3B6FB5", "#C8443C", "#E8B83A", "#3C8D5A"]):
        caixa((3.2 + i * 0.32, 5.25, 0.3), (0.28, 0.3, 0.6), c, 0.02)
    caixa((0.2, 5.5, 2.3), (0.7, 0.04, 0.45), "#22252B", 0.01)     # relógio/painel
    mesas = {"mesa1": (-2.6, 3.0), "mesa2": (-1.1, 3.0), "mesa3": (3.0, 3.2), "mesa4": (-2.6, 0.2),
             "mesa5": (-1.1, 0.2), "mesa6": (2.9, 0.4), "mesa7": (3.0, -1.8), "mesa8": (-2.4, -2.0)}
    lugares = {}
    for n, (x, y) in mesas.items():
        mesa_escritorio(x, y)
        lugares[n] = (x, y + 0.62, 0.0, 0.52)
    planta(-4.0, 5.0); planta(4.0, -0.8, 1.2); planta(-4.0, -3.2, 0.9)
    cil((4.1, 3.6, 0.5), 0.18, 1.0, "#E9EEF2"); cil((4.1, 3.6, 1.2), 0.15, 0.4, "#8FC4E8")
    pontos = {"porta": (1.8, 5.1, 180), "centro": (0.25, 0.9, 0), "frente": (0.3, -1.5, 0),
              "janela": (-3.8, 0.0, 270), "quadro": (-1.4, 4.6, 180), "bebedouro": (3.6, 3.6, 90),
              "corredor": (0.6, 2.8, 0)}
    return pontos, (-4.2, 4.2, -5.0, 5.2, 2.8), "#EDE6DA", lugares


def cen_casa():
    caixa((0, 0, -0.05), (8, 9, 0.1), "#B07A4F", 0)                     # piso de madeira
    for x in range(-4, 4):
        caixa((x + 0.5, 0, 0.002), (0.02, 9, 0.004), "#8F6140", 0)
    caixa((0, 4.05, 1.5), (8, 0.1, 3.0), "#E9D8B8", 0)
    for x in (-3.95, 3.95):
        caixa((x, 0, 1.5), (0.1, 9, 3.0), "#E2CFAE", 0)
    caixa((0, 4.0, 0.08), (8, 0.04, 0.16), "#FFFFFF", 0)
    # janela com cortinas
    caixa((-1.6, 3.98, 1.7), (1.6, 0.04, 1.3), "#A8D2EE", 0.0)
    caixa((-1.6, 3.96, 1.7), (0.05, 0.03, 1.3), "#FFFFFF", 0.0)
    for dx in (-0.95, 0.95):
        caixa((-1.6 + dx, 3.9, 1.6), (0.35, 0.08, 1.9), "#C0504D", 0.03)
    # sofá
    caixa((1.2, 2.9, 0.25), (2.4, 0.9, 0.5), "#3E6E8E", 0.06)
    caixa((1.2, 3.3, 0.7), (2.4, 0.25, 0.65), "#3E6E8E", 0.06)
    for dx in (-1.25, 1.25):
        caixa((1.2 + dx, 2.95, 0.45), (0.22, 0.9, 0.5), "#35607D", 0.06)
    for dx in (-0.55, 0.55):
        caixa((1.2 + dx, 2.85, 0.55), (1.0, 0.7, 0.15), "#4C82A6", 0.06)
    caixa((0.5, 3.1, 0.75), (0.4, 0.15, 0.35), "#E8B83A", 0.06, rot=(0.3, 0, 0.2))   # almofada
    # tapete, mesa de centro
    cil((1.0, 1.4, 0.01), 1.5, 0.02, "#D9A05B", seg=48)
    caixa((1.2, 1.5, 0.35), (1.1, 0.6, 0.06), "#6B4A33", 0.02)
    for dx in (-0.45, 0.45):
        for dy in (-0.22, 0.22):
            cil((1.2 + dx, 1.5 + dy, 0.17), 0.03, 0.34, "#6B4A33")
    cil((1.0, 1.5, 0.43), 0.05, 0.1, "#F2F0EC")
    # TV na parede da direita
    caixa((3.6, 1.8, 0.35), (0.5, 2.0, 0.7), "#5A4434", 0.02)
    caixa((3.85, 1.8, 1.45), (0.06, 1.6, 0.9), "#1C1E22", 0.02)
    caixa((3.81, 1.8, 1.45), (0.01, 1.48, 0.8), "#5BA7D8", 0.0)
    # estante e luminária
    caixa((-3.7, 1.5, 1.0), (0.4, 1.4, 2.0), "#6B4A33", 0.02)
    for k, z in enumerate((0.45, 0.95, 1.45)):
        x = 1.0
        while x < 2.1:
            w = RNG.uniform(0.06, 0.12)
            caixa((-3.62, x + w / 2, z + 0.15), (0.25, w, RNG.uniform(0.22, 0.32)),
                  RNG.choice(["#C8443C", "#3B6FB5", "#E8B83A", "#3C8D5A", "#F2F0EC"]), 0.005)
            x += w + 0.01
    cil((-2.9, 3.4, 0.8), 0.02, 1.6, "#30343A"); cil((-2.9, 3.4, 1.65), 0.22, 0.28, "#F6E7C1")
    planta(3.4, 3.6, 1.1)
    # porta
    caixa((3.9, -1.6, 1.05), (0.08, 1.0, 2.1), "#7A5E4A", 0.01)
    caixa((0.0, 4.02, 2.3), (0.9, 0.04, 0.6), "#7A9A6A", 0.01)     # quadro
    pontos = {"porta": (3.5, -1.6, 270), "centro": (0.0, 0.6, 0), "sofa_frente": (1.2, 2.0, 0),
              "janela": (-1.6, 3.2, 180), "tv": (2.8, 1.8, 90), "estante": (-3.1, 1.5, 270)}
    lugares = {"sofa": (0.7, 2.75, 0.0, 0.6), "sofa2": (1.7, 2.75, 0.0, 0.6)}
    return pontos, (-3.6, 3.6, -4.5, 3.6, 2.8), "#EFE3CF", lugares


def cen_rua():
    caixa((0, 0, -0.06), (40, 40, 0.1), "#5D6168", 0)                   # asfalto
    for y in (-0.2,):
        for x in range(-18, 19, 3):
            caixa((x, y, -0.005), (1.6, 0.12, 0.01), "#F2F0EC", 0)
    caixa((0, 3.2, 0.06), (40, 3.6, 0.14), "#B9B4AA", 0.01)            # calçada do fundo
    caixa((0, -4.2, 0.06), (40, 2.4, 0.14), "#B9B4AA", 0.01)           # calçada da frente
    cores = ["#D9A57A", "#9DB4C8", "#E3C77E", "#B98C8C", "#A9C3A0", "#D7C3B0"]
    x = -16.0
    while x < 16:
        w = RNG.uniform(3.0, 4.6); h = RNG.uniform(5.0, 11.0); c = RNG.choice(cores)
        caixa((x + w / 2, 6.6, h / 2), (w - 0.1, 3.2, h), c, 0.03)
        for wz in [1.6 + 1.5 * k for k in range(int((h - 1.4) / 1.5))]:
            for wx in [x + 0.6 + 1.0 * k for k in range(int((w - 0.8) / 1.0))]:
                caixa((wx + 0.3, 4.98, wz), (0.6, 0.06, 0.8), "#4A6584", 0.0)
        caixa((x + w / 2, 4.98, 0.9), (1.0, 0.06, 1.8), "#3A2E28", 0.0)
        x += w
    for xl in (-9, -3, 3, 9):                                          # postes
        cil((xl, 1.7, 2.0), 0.06, 4.0, "#30343A"); esfera((xl, 1.5, 4.0), (0.25, 0.25, 0.15), "#F6E7C1")
    for xa in (-6, 0.5, 6.5):                                          # árvores
        cil((xa, 2.2, 1.0), 0.12, 2.0, "#6B4A33")
        for k in range(5):
            esfera((xa + RNG.uniform(-0.5, 0.5), 2.2 + RNG.uniform(-0.4, 0.4), 2.4 + RNG.uniform(0, 0.8)),
                   (0.8, 0.8, 0.7), "#4E9A5E", seg=16)
    for (xc, yc, c) in ((-5, 1.0, "#C8443C"), (4, 1.0, "#3B6FB5"), (10, -1.4, "#E8B83A")):   # carros
        caixa((xc, yc, 0.45), (3.4, 1.6, 0.6), c, 0.12)
        caixa((xc - 0.2, yc, 0.95), (1.9, 1.4, 0.5), "#A8D2EE", 0.1)
        for dx in (-1.1, 1.1):
            for dy in (-0.75, 0.75):
                cil((xc + dx, yc + dy, 0.32), 0.32, 0.22, "#1C1E22", rot=(math.pi / 2, 0, 0))
    caixa((-1.8, 3.9, 0.45), (1.8, 0.45, 0.08), "#6B4A33", 0.02)       # banco do ponto
    caixa((-1.8, 4.1, 1.3), (2.2, 0.08, 2.4), "#9FD8F0", 0.01)
    caixa((-1.8, 4.1, 2.55), (2.4, 0.9, 0.1), "#2F6E73", 0.01)
    pontos = {"esquina": (-7.0, 3.0, 90), "ponto": (-1.8, 3.0, 0), "centro": (0.0, 2.8, 0),
              "calcada_dir": (6.0, 3.0, 270), "frente": (0.0, -3.8, 180), "faixa": (1.5, 0.0, 0)}
    lugares = {"banco": (-1.8, 3.85, 0.0, 0.5)}
    return pontos, (-15, 15, -6, 4.6, 4.0), "#A9D3EE", lugares


CENARIOS = {"escritorio": cen_escritorio, "casa": cen_casa, "rua": cen_rua}
PONTOS, LIM, FUNDO, LUGARES = CENARIOS[ROT.get("cenario", "escritorio")]()


def ponto(p):
    if isinstance(p, str):
        if p in PONTOS:
            return Vector(PONTOS[p][:2])
        if p in LUGARES:
            return Vector(LUGARES[p][:2])
        raise ValueError("ponto desconhecido: " + p)
    return Vector(p[:2])


# ================================================================== elenco
ELENCO = {
    "caio":   dict(pele="#9C6644", cabelo="#151515", camisa="#3D6FA8", calca="#24262B", estilo="curto", altura=1.0),
    "nina":   dict(pele="#E3B48F", cabelo="#3B2414", camisa="#2F7A4E", calca="#5A3D2B", estilo="longo", altura=0.95),
    "bento":  dict(pele="#7A4E33", cabelo="#2B2B2B", camisa="#6B6B3A", calca="#2F2F2F", estilo="careca", barba=True, altura=1.04),
    "lurdes": dict(pele="#D8A98A", cabelo="#D9D9D9", camisa="#5B3F7A", calca="#2E2A33", estilo="coque", oculos=True, altura=0.93),
    "rafa":   dict(pele="#C99470", cabelo="#5A3A22", camisa="#C8443C", calca="#2F3A4A", estilo="cacheado", altura=0.98),
    "figurante": dict(pele="#B07A55", cabelo="#2A2018", camisa="#8A8F98", calca="#33363C", estilo="curto", altura=1.0),
}
for k, v in ROT.get("elenco_extra", {}).items():
    ELENCO[k] = dict(ELENCO.get(v.get("base", "figurante")), **v)


class Boneco:
    def __init__(self, nome, sp):
        self.nome, self.sp = nome, sp
        pele, cab = sp["pele"], sp["cabelo"]
        self.raiz = vazio(nome, (0, 0, 0))
        self.raiz.scale = (sp.get("altura", 1.0),) * 3
        self.quadril = vazio(nome + "_quadril", (0, 0, 0.86), self.raiz)
        self.pernas = []
        for s in (-1, 1):
            p = vazio(f"{nome}_perna{s}", (0.1 * s, 0, 0), self.quadril)
            capsula((0, 0, -0.4), 0.075, 0.72, sp["calca"], pai=p)
            esfera((0, -0.06, -0.8), (0.09, 0.15, 0.06), sp.get("sapato", "#2A2A2E"), pai=p)
            self.pernas.append(p)
        self.respira = vazio(nome + "_respira", (0, 0, 0), self.quadril)
        self.tronco = vazio(nome + "_tronco", (0, 0, 0), self.respira)
        t = self.tronco
        esfera((0, 0, 0.2), (0.21, 0.15, 0.3), sp["camisa"], pai=t)
        cil((0, 0, 0.0), 0.17, 0.14, sp["calca"], pai=t)
        cil((0, 0, 0.47), 0.05, 0.1, pele, pai=t)
        self.bracos = []
        for s in (-1, 1):
            b = vazio(f"{nome}_braco{s}", (0.24 * s, 0, 0.4), t)
            capsula((0, 0, -0.24), 0.06, 0.42, sp["camisa"], pai=b)
            esfera((0, 0, -0.53), (0.065, 0.065, 0.07), pele, pai=b, seg=16)
            self.bracos.append(b)
        self.pescoco = vazio(nome + "_pescoco", (0, 0, 0.5), t)
        self.cabeca = vazio(nome + "_cabeca", (0, 0, 0), self.pescoco)
        c = self.cabeca
        esfera((0, 0, 0.27), (0.27, 0.26, 0.27), pele, pai=c)
        for s in (-1, 1):
            esfera((0.262 * s, 0.01, 0.26), (0.035, 0.05, 0.06), pele, pai=c, seg=12)   # orelhas
        est = sp.get("estilo", "curto")
        if est != "careca":
            esfera((0, 0.035, 0.33), (0.272, 0.25, 0.235), cab, pai=c)
        if est == "curto":
            esfera((-0.04, -0.12, 0.52), (0.12, 0.08, 0.06), cab, pai=c)
        elif est == "longo":
            esfera((0, 0.1, 0.12), (0.27, 0.18, 0.36), cab, pai=c)
            esfera((-0.12, -0.17, 0.47), (0.16, 0.09, 0.07), cab, pai=c)
        elif est == "coque":
            esfera((0, 0.13, 0.55), (0.11, 0.11, 0.1), cab, pai=c)
        elif est == "cacheado":
            for k in range(10):
                a = k / 10 * 2 * math.pi
                esfera((math.cos(a) * 0.2, 0.05 + math.sin(a) * 0.17, 0.42 + 0.06 * math.sin(3 * a)), (0.1, 0.1, 0.1), cab, pai=c, seg=12)
        if sp.get("barba"):
            esfera((0, -0.05, 0.13), (0.24, 0.22, 0.15), cab, pai=c)
        self.piscas, self.olhos, self.palpebras = [], [], []
        for s in (-1, 1):
            pi_ = vazio(f"{nome}_pisca{s}", (0.085 * s, -0.245, 0.29), c)
            ol = vazio(f"{nome}_olho{s}", (0, 0, 0), pi_)
            esfera((0, 0, 0), (0.042, 0.02, 0.06), "#16161A", pai=ol, seg=20)
            esfera((-0.012, -0.016, 0.022), (0.012, 0.006, 0.014), "#FFFFFF", pai=ol, seg=10)
            self.piscas.append(pi_); self.olhos.append(ol)
            pa = vazio(f"{nome}_palpebra{s}", (0.085 * s, -0.17, 0.39), c)
            esfera((0, 0, 0), (0.055, 0.03, 0.045), pele, pai=pa, seg=16)
            self.palpebras.append(pa)
        if sp.get("oculos"):
            for s in (-1, 1):
                toro((0.085 * s, -0.27, 0.29), 0.065, 0.008, "#2A2A2E", pai=c, rot=(math.pi / 2, 0, 0))
            cil((0, -0.272, 0.3), 0.007, 0.04, "#2A2A2E", pai=c, rot=(0, math.pi / 2, 0))
        self.todos = [self.raiz] + list(self.raiz.children_recursive)
        # estado ao longo do roteiro
        self.pos = Vector((0, 0)); self.giro = 0.0; self.sentado = False; self.visivel = True
        self.K = {}

    # ---- chaves acumuladas (aplicadas no final, em ordem)
    def chave(self, ob, prop, q, val, constante=False):
        self.K.setdefault((ob.name, prop), {})[int(q)] = (tuple(val) if hasattr(val, "__len__") else val, constante)

    def neutro_bracos(self, q):
        self.chave(self.bracos[0], "rotation_euler", q, (0, 0.08, 0))
        self.chave(self.bracos[1], "rotation_euler", q, (0, -0.08, 0))

    def neutro_pernas(self, q):
        for p in self.pernas:
            self.chave(p, "rotation_euler", q, (-math.pi / 2, 0, 0) if self.sentado else (0, 0, 0))

    def raiz_em(self, q, z=0.0):
        self.chave(self.raiz, "location", q, (self.pos.x, self.pos.y, z + (self.alt_assento if self.sentado else 0)))
        self.chave(self.raiz, "rotation_euler", q, (0, 0, self.giro))

    def olhos_estado(self, q, estado):
        esc = {"normal": 1.0, "sono": 1.0, "arregalado": 1.35, "fechado": 0.08, "feliz": 0.45, "bravo": 0.8}[estado]
        ex = {"arregalado": 1.35, "feliz": 1.1}.get(estado, 1.0)
        dz = {"normal": 0.10, "sono": 0.042, "arregalado": 0.13, "fechado": 0.10, "feliz": 0.1, "bravo": 0.05}[estado]
        dy = -0.236 if estado in ("sono", "bravo") else -0.17
        for i, o in enumerate(self.olhos):
            self.chave(o, "scale", q, (ex, 1, esc))
        for i, p in enumerate(self.palpebras):
            s = -1 if i == 0 else 1
            self.chave(p, "location", q, (0.085 * s, dy, 0.29 + dz))
            inc = 0.35 * s if estado == "bravo" else 0.0
            self.chave(p, "rotation_euler", q, (0, inc, 0))

    def direcao(self):
        return Vector((math.sin(self.giro), -math.cos(self.giro)))


BONECOS = {}
for quem in ROT.get("personagens", []):
    BONECOS[quem] = Boneco(quem, ELENCO[quem])


def ang_para(b, alvo):
    """Giro (rad) para o boneco b olhar para alvo: 'camera' | nome de outro boneco | ponto | graus."""
    if isinstance(alvo, (int, float)):
        return math.radians(alvo)
    if alvo == "camera":
        return 0.0
    if alvo in BONECOS:
        d = BONECOS[alvo].pos - b.pos
    elif isinstance(alvo, str) and alvo in PONTOS and alvo not in LUGARES:
        d = ponto(alvo) - b.pos
    else:
        d = ponto(alvo) - b.pos
    if d.length < 1e-4:
        return b.giro
    return math.atan2(d.x, -d.y)


def mais_perto(a, ref):
    while a - ref > math.pi:
        a -= 2 * math.pi
    while a - ref < -math.pi:
        a += 2 * math.pi
    return a


# ================================================================== ações
def acao(b, nome, t0, dur, a):
    q0 = Q(t0); q1 = Q(t0 + dur)
    if nome in ("andar", "correr"):
        destino = ponto(a["ate"])
        if b.sentado:
            b.sentado = False; b.raiz_em(q0)
        vel = 1.15 if nome == "andar" else 2.8
        dist = (destino - b.pos).length
        if a.get("dur") is None and a.get("ate_t") is None:
            dur = max(0.6, dist / vel); q1 = Q(t0 + dur)
        ini = b.pos.copy()
        g_alvo = mais_perto(math.atan2((destino - ini).x, -(destino - ini).y), b.giro) if dist > 0.05 else b.giro
        cad = (1.0 if nome == "andar" else 1.7) * (dist / max(0.1, dur)) / vel * (1 if nome == "andar" else 1.0)
        amp = 0.5 if nome == "andar" else 0.85
        for q in range(q0, q1 + 1):
            u = (q - q0) / max(1, q1 - q0)
            ue = u * u * (3 - 2 * u) if dist < 1.0 else min(1, u * 1.04)
            b.pos = ini.lerp(destino, ue)
            gk = min(1, (q - q0) / 6)
            b.giro = b.giro + (g_alvo - b.giro) * gk if q - q0 < 7 else g_alvo
            fase = 2 * math.pi * cad * (q - q0) / FPS
            fade = min(1, (q1 - q) / 6, (q - q0) / 4 + 0.2)
            sw = math.sin(fase) * amp * fade
            b.raiz_em(q, abs(math.cos(fase)) * (0.035 if nome == "andar" else 0.08) * fade)
            b.chave(b.pernas[0], "rotation_euler", q, (sw, 0, 0))
            b.chave(b.pernas[1], "rotation_euler", q, (-sw, 0, 0))
            b.chave(b.bracos[0], "rotation_euler", q, (-sw * 0.85, 0.08, 0))
            b.chave(b.bracos[1], "rotation_euler", q, (sw * 0.85, -0.08, 0))
            b.chave(b.tronco, "rotation_euler", q, (0.05 + (0.15 if nome == "correr" else 0), 0, math.sin(fase) * 0.07 * fade))
        b.pos = destino.copy(); b.giro = g_alvo
        b.chave(b.tronco, "rotation_euler", q1 + 2, (0.03, 0, 0))
        b.neutro_pernas(q1 + 2); b.neutro_bracos(q1 + 3)
        if a.get("chegar_olhando"):
            acao(b, "virar", t0 + dur, 0.4, {"para": a["chegar_olhando"]})
        return t0 + dur
    if nome == "virar":
        g = mais_perto(ang_para(b, a.get("para", "camera")), b.giro)
        b.raiz_em(q0)
        b.giro = g
        b.raiz_em(Q(t0 + max(0.25, min(dur, 0.5))))
        return t0 + dur
    if nome == "ir_para":  # teleporte (início de cena)
        b.pos = ponto(a["ate"]).copy()
        if isinstance(a["ate"], str) and a["ate"] in PONTOS:
            b.giro = math.radians(PONTOS[a["ate"]][2])
        if "olhando" in a:
            b.giro = ang_para(b, a["olhando"])
        b.sentado = False
        b.raiz_em(q0); b.neutro_pernas(q0)
        return t0
    if nome == "sentar":
        x, y, g, h = LUGARES[a["lugar"]]
        b.pos = Vector((x, y)); b.giro = math.radians(g); b.sentado = True; b.alt_assento = h - 0.86 + 0.06
        b.raiz_em(q0); b.neutro_pernas(q0); b.neutro_bracos(q0)
        return t0
    if nome == "levantar":
        b.sentado = False; b.raiz_em(q0); b.neutro_pernas(q0)
        return t0
    if nome == "digitar":
        for q in range(q0, q1, 4):
            for i, br in enumerate(b.bracos):
                b.chave(br, "rotation_euler", q, (-1.2 + 0.09 * math.sin(q * 0.9 + i * 2), 0.1 * (1 if i == 0 else -1), 0))
            b.chave(b.cabeca, "rotation_euler", q, (0.08 + 0.03 * math.sin(q * 0.13), 0, 0.05 * math.sin(q * 0.05)))
        b.neutro_bracos(q1 + 3)
        return t0 + dur
    if nome in ("olhar", "procurar"):
        def head_ang(p):
            if p in ("esq", "esquerda"): return (0, 0, 0.6)
            if p in ("dir", "direita"): return (0, 0, -0.6)
            if p == "baixo": return (0.4, 0, 0)
            if p == "cima": return (-0.35, 0, 0)
            if p == "frente": return (0, 0, 0)
            g = mais_perto(ang_para(b, p), b.giro) - b.giro
            return (0, 0, max(-1.1, min(1.1, g)))
        if nome == "olhar":
            v = head_ang(a.get("para", "frente"))
            b.chave(b.cabeca, "rotation_euler", q0, (0, 0, 0))
            b.chave(b.cabeca, "rotation_euler", q0 + 6, v)
            b.chave(b.cabeca, "rotation_euler", q1, v)
            if not a.get("manter"):
                b.chave(b.cabeca, "rotation_euler", q1 + 6, (0, 0, 0))
        else:
            seq = [(0, 0, 0), (0, 0, 0.6), (0, 0, 0.6), (0, 0, -0.6), (0, 0, -0.6), (0, 0, 0)]
            for k, v in enumerate(seq):
                b.chave(b.cabeca, "rotation_euler", int(q0 + (q1 - q0) * k / (len(seq) - 1)), v)
        return t0 + dur
    if nome == "acenar":
        b.chave(b.bracos[1], "rotation_euler", q0, (0, -0.08, 0))
        q = q0 + 6
        k = 0
        while q < q1 - 6:
            b.chave(b.bracos[1], "rotation_euler", q, (-0.2, -2.3 if k % 2 == 0 else -2.7, 0)); q += 5; k += 1
        b.chave(b.bracos[1], "rotation_euler", q1, (0, -0.08, 0))
        return t0 + dur
    if nome == "apontar":
        g = mais_perto(ang_para(b, a.get("para", "camera")), b.giro) - b.giro
        b.chave(b.bracos[1], "rotation_euler", q0, (0, -0.08, 0))
        b.chave(b.bracos[1], "rotation_euler", q0 + 5, (-1.5, 0, g))
        b.chave(b.bracos[1], "rotation_euler", q1, (-1.5, 0, g))
        b.chave(b.bracos[1], "rotation_euler", q1 + 6, (0, -0.08, 0))
        return t0 + dur
    if nome == "surpresa":
        b.olhos_estado(q0, "normal"); b.olhos_estado(q0 + 3, "arregalado")
        b.chave(b.tronco, "rotation_euler", q0, (0.03, 0, 0)); b.chave(b.tronco, "rotation_euler", q0 + 5, (-0.14, 0, 0))
        for i, s in enumerate((-1, 1)):
            b.chave(b.bracos[i], "rotation_euler", q0, (0, -0.08 * s, 0))
            b.chave(b.bracos[i], "rotation_euler", q0 + 6, (-0.4, -1.1 * s, 0))
        z0 = b.alt_assento if b.sentado else 0
        b.chave(b.raiz, "location", q0, (b.pos.x, b.pos.y, z0))
        b.chave(b.raiz, "location", q0 + 4, (b.pos.x, b.pos.y, z0 + 0.1))
        b.chave(b.raiz, "location", q0 + 8, (b.pos.x, b.pos.y, z0))
        b.chave(b.tronco, "rotation_euler", q1, (-0.06, 0, 0)); b.neutro_bracos(q1 + 4)
        b.chave(b.tronco, "rotation_euler", q1 + 6, (0.03, 0, 0))
        return t0 + dur
    if nome == "olhar_maos":
        for i, s in enumerate((-1, 1)):
            b.chave(b.bracos[i], "rotation_euler", q0, (0, -0.08 * s, 0))
            b.chave(b.bracos[i], "rotation_euler", q0 + 8, (-1.9, 0.25 * s, 0))
            b.chave(b.bracos[i], "rotation_euler", q1, (-1.9, 0.25 * s, 0))
        b.chave(b.cabeca, "rotation_euler", q0, (0, 0, 0)); b.chave(b.cabeca, "rotation_euler", q0 + 10, (0.35, 0, 0))
        b.chave(b.cabeca, "rotation_euler", q1, (0.35, 0, 0)); b.chave(b.cabeca, "rotation_euler", q1 + 8, (0, 0, 0))
        b.neutro_bracos(q1 + 8)
        return t0 + dur
    if nome == "comemorar":
        q = q0; k = 0
        z0 = b.alt_assento if b.sentado else 0
        while q < q1:
            up = k % 2 == 0
            for i, s in enumerate((-1, 1)):
                b.chave(b.bracos[i], "rotation_euler", q, (0, (-2.6 if up else -2.2) * s, 0))
            b.chave(b.raiz, "location", q, (b.pos.x, b.pos.y, z0 + (0.12 if up else 0)))
            q += 6; k += 1
        b.chave(b.raiz, "location", q1 + 2, (b.pos.x, b.pos.y, z0)); b.neutro_bracos(q1 + 4)
        b.olhos_estado(q0, "feliz"); b.olhos_estado(q1 + 4, "normal")
        return t0 + dur
    if nome == "triste":
        b.chave(b.cabeca, "rotation_euler", q0, (0, 0, 0)); b.chave(b.cabeca, "rotation_euler", q0 + 10, (0.4, 0, 0))
        b.chave(b.tronco, "rotation_euler", q0, (0.03, 0, 0)); b.chave(b.tronco, "rotation_euler", q0 + 10, (0.2, 0, 0))
        b.olhos_estado(q0, "sono")
        b.chave(b.cabeca, "rotation_euler", q1, (0.4, 0, 0)); b.chave(b.tronco, "rotation_euler", q1, (0.2, 0, 0))
        if not a.get("manter"):
            b.chave(b.cabeca, "rotation_euler", q1 + 10, (0, 0, 0)); b.chave(b.tronco, "rotation_euler", q1 + 10, (0.03, 0, 0))
            b.olhos_estado(q1 + 10, "normal")
        return t0 + dur
    if nome == "bravo":
        b.olhos_estado(q0, "bravo")
        for i, s in enumerate((-1, 1)):
            b.chave(b.bracos[i], "rotation_euler", q0, (0, -0.08 * s, 0))
            b.chave(b.bracos[i], "rotation_euler", q0 + 6, (0.5, -0.9 * s, 0.9 * s))
            b.chave(b.bracos[i], "rotation_euler", q1, (0.5, -0.9 * s, 0.9 * s))
        b.chave(b.tronco, "rotation_euler", q0 + 6, (0.12, 0, 0)); b.chave(b.tronco, "rotation_euler", q1, (0.12, 0, 0))
        b.neutro_bracos(q1 + 6); b.chave(b.tronco, "rotation_euler", q1 + 6, (0.03, 0, 0))
        return t0 + dur
    if nome == "medo":
        b.olhos_estado(q0, "arregalado")
        for q in range(q0, q1, 2):
            b.chave(b.raiz, "location", q, (b.pos.x + 0.012 * (1 if (q // 2) % 2 else -1), b.pos.y, b.alt_assento if b.sentado else 0))
        b.raiz_em(q1)
        return t0 + dur
    if nome == "gesticular":   # "falando" sem boca: cabeça e mãos acompanham
        q = q0; k = 0
        while q < q1:
            b.chave(b.cabeca, "rotation_euler", q, (0.06 * math.sin(k * 1.7), 0, 0.12 * math.sin(k * 0.9)))
            b.chave(b.bracos[1], "rotation_euler", q, (-0.6 - 0.35 * abs(math.sin(k * 1.3)), -0.2, 0.3))
            if k % 3 == 1:
                b.chave(b.bracos[0], "rotation_euler", q, (-0.5, 0.25, -0.2))
            q += 8; k += 1
        b.chave(b.cabeca, "rotation_euler", q1 + 4, (0, 0, 0)); b.neutro_bracos(q1 + 6)
        return t0 + dur
    if nome == "olhos":
        b.olhos_estado(q0, a.get("estado", "normal"))
        return t0
    if nome in ("sumir", "aparecer"):
        vis_final = nome == "aparecer"
        seq = [(0, vis_final), (2, not vis_final), (5, vis_final), (8, not vis_final), (10, vis_final), (13, not vis_final), (14, vis_final)]
        for dq, v in seq:
            for o in b.todos:
                b.chave(o, "hide_render", q0 + dq, not v, constante=True)
        b.visivel = vis_final
        return t0 + 0.6
    raise ValueError("ação desconhecida: " + nome)


# ---- monta a linha do tempo de cada personagem
for b in BONECOS.values():
    b.alt_assento = 0.0
    b.raiz_em(1); b.neutro_pernas(1); b.neutro_bracos(1); b.olhos_estado(1, "normal")
    b.chave(b.tronco, "rotation_euler", 1, (0.03, 0, 0)); b.chave(b.cabeca, "rotation_euler", 1, (0, 0, 0))
    for o in b.todos:
        b.chave(o, "hide_render", 1, False, constante=True)

PLANOS = ROT["planos"]
for i, pl in enumerate(PLANOS):
    pl["_t0"] = T(pl.get("de", 0))
for i, pl in enumerate(PLANOS):
    pl["_t1"] = PLANOS[i + 1]["_t0"] if i + 1 < len(PLANOS) else DURACAO

todas = []
for pl in PLANOS:
    for a in pl.get("acoes", []):
        t0 = T(a.get("em"), pl["_t0"])
        if "ate_t" in a:
            dur = T(a["ate_t"], pl["_t0"]) - t0
        elif a.get("dur") is not None:
            dur = float(a["dur"])
        else:
            dur = {"virar": 0.4, "acenar": 1.4, "surpresa": 0.9, "olhar": 1.2, "procurar": 2.0, "apontar": 1.2,
                   "comemorar": 1.5, "triste": 1.6, "bravo": 1.4, "medo": 1.0, "olhar_maos": 1.6}.get(a["acao"], pl["_t1"] - t0)
        todas.append((t0, dur, a))
todas.sort(key=lambda x: x[0])
for t0, dur, a in todas:
    quem = a["quem"]
    if quem not in BONECOS:
        continue
    acao(BONECOS[quem], a["acao"], t0, dur, a)

# ---- vida: respiração, balanço e piscadas automáticas
for b in BONECOS.values():
    ph = RNG.uniform(0, 6)
    for q in range(1, NQ + 24, 12):
        tt = q / FPS
        b.chave(b.respira, "rotation_euler", q, (0.015 * math.sin(tt * 1.6 + ph), 0.02 * math.sin(tt * 0.9 + ph), 0.02 * math.sin(tt * 0.7 + ph)))
        b.chave(b.pescoco, "rotation_euler", q, (0.02 * math.sin(tt * 1.1 + ph), 0.03 * math.sin(tt * 0.8 + ph), 0.04 * math.sin(tt * 0.5 + ph)))
    t = RNG.uniform(1.0, 2.5)
    for p in b.piscas:
        b.chave(p, "scale", 1, (1, 1, 1))
    while t < DURACAO:
        q = Q(t)
        for p in b.piscas:
            b.chave(p, "scale", q - 2, (1, 1, 1)); b.chave(p, "scale", q, (1, 1, 0.08)); b.chave(p, "scale", q + 3, (1, 1, 1))
        t += RNG.uniform(2.2, 4.5)

# ---- grava as chaves
for b in BONECOS.values():
    for (nome, prop), ks in b.K.items():
        ob = bpy.data.objects[nome]
        for q in sorted(ks):
            val, const = ks[q]
            setattr(ob, prop, val)
            ob.keyframe_insert(prop, frame=q)
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                if fc.data_path == prop and any(c for _, c in ks.values()):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"

# ================================================================== câmera
alvo_ob = vazio("alvo", (0, 0, 1))
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
COL.objects.link(cam)
sc.camera = cam
tc = cam.constraints.new("TRACK_TO"); tc.target = alvo_ob; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
cam_d.clip_start = 0.05
xmin, xmax, ymin, ymax, zmax = LIM


def limita(p):
    return Vector((max(xmin, min(xmax, p.x)), max(ymin, min(ymax, p.y)), max(0.3, min(zmax, p.z))))


def chave_cam(q, pos, mira, lente):
    cam.location = limita(pos); cam.keyframe_insert("location", frame=q)
    alvo_ob.location = mira; alvo_ob.keyframe_insert("location", frame=q)
    cam_d.lens = lente; cam_d.keyframe_insert("lens", frame=q)


def onde(quem, q):
    sc.frame_set(q)
    b = BONECOS[quem]
    p = b.raiz.matrix_world.translation.copy()
    g = b.raiz.matrix_world.to_euler().z
    return p, Vector((math.sin(g), -math.cos(g), 0)), b.sp.get("altura", 1.0)


bpy.context.view_layer.update()
for i, pl in enumerate(PLANOS):
    q0, q1 = Q(pl["_t0"]), max(Q(pl["_t0"]) + 1, Q(pl["_t1"]) - 1)
    tipo = pl.get("camera", "frente")
    quem = pl.get("alvo") or (list(BONECOS)[0] if BONECOS else None)
    lado = pl.get("lado", 1)
    L = pl.get("lente")
    if tipo == "geral" or quem is None:
        c = Vector(pl.get("pos", (xmax * 0.8, ymin * 0.9, zmax * 0.85)))
        m = Vector(pl.get("mira", (0, 1.5, 0.8)))
        chave_cam(q0, c, m, L or 18); chave_cam(q1, c + (m - c).normalized() * 0.3, m, L or 18)
        continue
    P, F, h = onde(quem, q0)
    lat = Vector((-F.y, F.x, 0)) * lado
    if tipo == "acompanha":
        for q in list(range(q0, q1, 3)) + [q1]:
            P, Fq, h = onde(quem, q)
            chave_cam(q, P + F * 3.2 + lat * 0.35 + Vector((0, 0, 1.75 * h)), P + Vector((0, 0, 1.0 * h)), L or 22)
    elif tipo == "costas":
        for q in list(range(q0, q1, 3)) + [q1]:
            P, Fq, h = onde(quem, q)
            chave_cam(q, P - F * 2.6 + lat * 0.4 + Vector((0, 0, 1.8 * h)), P + F * 2.0 + Vector((0, 0, 1.0 * h)), L or 22)
    elif tipo == "frente":
        chave_cam(q0, P + F * 2.7 + lat * 0.3 + Vector((0, 0, 1.6 * h)), P + Vector((0, 0, 1.25 * h)), L or 26)
        chave_cam(q1, P + F * 2.3 + lat * 0.2 + Vector((0, 0, 1.6 * h)), P + Vector((0, 0, 1.3 * h)), L or 26)
    elif tipo == "lateral":
        n = max(2, (q1 - q0) // 6)
        for k in range(n + 1):
            q = q0 + (q1 - q0) * k // n
            a = math.radians(40 - 30 * k / n) * lado
            d = F * math.cos(a) + Vector((-F.y, F.x, 0)) * math.sin(a)
            chave_cam(q, P + d * 2.6 + Vector((0, 0, 1.55 * h)), P + Vector((0, 0, 1.3 * h)), L or 26)
    elif tipo == "close":
        chave_cam(q0, P + F * 2.6 + lat * 0.2 + Vector((0, 0, 1.6 * h)), P + Vector((0, 0, 1.5 * h)), L or 32)
        chave_cam(q1, P + F * 1.8 + lat * 0.08 + Vector((0, 0, 1.64 * h)), P + Vector((0, 0, 1.55 * h)), L or 34)
    elif tipo == "detalhe":
        chave_cam(q0, P + F * 1.5 + Vector((0, 0, 1.6 * h)), P + Vector((0, 0, 1.56 * h)), L or 40)
        chave_cam(q1, P + F * 1.2 + Vector((0, 0, 1.6 * h)), P + Vector((0, 0, 1.57 * h)), L or 42)
    elif tipo == "aberto":
        base = P + F * 4.6 + lat * 2.6
        chave_cam(q0, base + Vector((0, 0, 2.4)), P + Vector((0, 0, 0.9)), L or 20)
        chave_cam(q1, base + F * 0.6 + lat * 0.3 + Vector((0, 0, 2.7)), P + Vector((0, 0, 0.8)), L or 20)
    elif tipo == "dois":   # enquadra o alvo e outro personagem
        P2, F2, h2 = onde(pl["com"], q0)
        meio = (P + P2) / 2; sep = (P2 - P); sep.z = 0
        nrm = Vector((-sep.y, sep.x, 0)).normalized()
        if nrm.dot(Vector((0, -1, 0))) < 0:
            nrm = -nrm
        dist = 2.4 + sep.length * 0.9
        chave_cam(q0, meio + nrm * dist + Vector((0, 0, 1.6)), meio + Vector((0, 0, 1.2)), L or 24)
        chave_cam(q1, meio + nrm * (dist - 0.3) + Vector((0, 0, 1.6)), meio + Vector((0, 0, 1.25)), L or 24)
    else:
        raise ValueError("câmera desconhecida: " + tipo)

# cortes secos entre planos
for pl in PLANOS[1:]:
    q = Q(pl["_t0"])
    for ad in (cam.animation_data, alvo_ob.animation_data, cam_d.animation_data):
        for fc in ad.action.fcurves:
            ant = [kp for kp in fc.keyframe_points if kp.co.x < q]
            if ant:
                max(ant, key=lambda kp: kp.co.x).interpolation = "CONSTANT"

# ================================================================== render (Workbench: cor chapada, sombra e contorno)
w = bpy.data.worlds.new("mundo"); w.color = lin(FUNDO)[:3]; sc.world = w
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.fps = FPS
por = math.ceil(NQ / NPARTES)
sc.frame_start = (PARTE - 1) * por + 1
sc.frame_end = min(NQ, PARTE * por)
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.resolution_percentage = 100
sc.display.render_aa = "16"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_shadows = True
sh.shadow_intensity = 0.3
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.cavity_ridge_factor = 0.6
sh.cavity_valley_factor = 1.0
sh.curvature_ridge_factor = 0.5
sh.curvature_valley_factor = 0.8
sh.show_object_outline = True
sh.object_outline_color = (0.08, 0.08, 0.1)
sh.show_specular_highlight = False
sc.display.light_direction = (0.45, -0.35, 0.82)
sc.display.shadow_shift = 0.1
sc.display.shadow_focus = 0.6
sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.75
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT, "f_")
print(f"motor: {NQ} quadros no total; esta parte {sc.frame_start}-{sc.frame_end}", flush=True)
bpy.ops.render.render(animation=True)
