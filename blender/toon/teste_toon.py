# Teste "3D toon" para @continua.br — Caio entra no escritório e percebe que ninguém o vê.
# Workbench (render rápido, cor chapada + sombra + contorno). 1080x1920, 24 fps, 12 s.
# Uso: blender -b -P teste_toon.py -- <pasta_quadros> [quadro_ini quadro_fim]
import bpy, math, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["/tmp/quadros"]
OUT = argv[0]
PARTE = int(argv[1]) if len(argv) > 1 else 1
NPARTES = int(argv[2]) if len(argv) > 2 else 1
os.makedirs(OUT, exist_ok=True)
FPS = 24

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


MATS = {}


def mat(cor):
    if cor not in MATS:
        m = bpy.data.materials.new(cor)
        m.diffuse_color = lin(cor)
        m.roughness = 0.8
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


def esfera(loc, esc, cor, pai=None, seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.active_object
    o.scale = esc
    bpy.ops.object.transform_apply(scale=True)
    return _fin(o, cor, suave=True, pai=pai)


def cil(loc, r, h, cor, pai=None, rot=(0, 0, 0), seg=24):
    bpy.ops.mesh.primitive_cylinder_add(location=loc, radius=r, depth=h, rotation=rot, vertices=seg)
    o = bpy.context.active_object
    return _fin(o, cor, bevel=min(r, h) * 0.25, suave=True, pai=pai)


def capsula(loc, r, h, cor, pai=None):
    """Cilindro com pontas redondas (membros)."""
    g = cil(loc, r, h, cor, pai=pai)
    esfera((loc[0], loc[1], loc[2] - h / 2), (r, r, r), cor, pai=pai)
    esfera((loc[0], loc[1], loc[2] + h / 2), (r, r, r), cor, pai=pai)
    return g


def vazio(nome, loc, pai=None):
    o = bpy.data.objects.new(nome, None)
    sc.collection.objects.link(o)
    o.location = loc
    if pai:
        o.parent = pai
    return o


# ------------------------------------------------------------------ escritório
PAREDE, FAIXA, PISO = "#F4F1EA", "#2F6E73", "#A7B0BC"
caixa((0, 1, -0.05), (10, 13, 0.1), PISO, 0)
caixa((0, 5.55, 1.5), (10, 0.1, 3.0), PAREDE, 0)
caixa((0, 5.48, 0.55), (10, 0.06, 1.1), FAIXA, 0)
for x in (-4.55, 4.55):
    caixa((x, 1, 1.5), (0.1, 13, 3.0), PAREDE, 0)
    caixa((x * 0.987, 1, 0.55), (0.06, 13, 1.1), FAIXA, 0)
caixa((0, 1, 3.05), (10, 13, 0.1), "#FFFFFF", 0)
for x in (-2.2, 0.0, 2.2):
    for y in (-1.0, 2.0, 4.5):
        caixa((x, y, 2.99), (1.2, 0.6, 0.02), "#FFFFFF", 0)
# porta (por onde o Caio entra)
caixa((1.8, 5.47, 1.05), (1.05, 0.08, 2.1), "#4A3B32", 0.01)
caixa((1.8, 5.43, 1.05), (0.9, 0.04, 1.95), "#6B5546", 0.01)
esfera((2.15, 5.38, 1.0), (0.04, 0.04, 0.04), "#D9C4A3")
caixa((1.8, 5.48, 2.35), (0.6, 0.04, 0.18), "#3C8D5A", 0.005)  # placa de saída
# janelas na parede da esquerda
for y in (0.0, 2.5):
    caixa((-4.48, y, 1.75), (0.04, 1.8, 1.2), "#9CC3E0", 0.0)
    caixa((-4.46, y, 1.75), (0.03, 0.06, 1.2), "#F2F0EC", 0.0)
# quadro de avisos com papéis
caixa((-1.4, 5.47, 1.6), (1.4, 0.05, 0.9), "#B88A5A", 0.01)
for i, (dx, dz, c) in enumerate([(-0.4, 0.2, "#F6E27A"), (0.0, 0.25, "#F2A0B5"), (0.35, 0.15, "#FFFFFF"),
                                 (-0.25, -0.2, "#9FD8F0"), (0.3, -0.18, "#F6E27A")]):
    caixa((-1.4 + dx, 5.44, 1.6 + dz), (0.24, 0.01, 0.3), c, 0.0, rot=(0, (i - 2) * 0.08, 0))
# lixeiras coloridas
for i, c in enumerate(["#3B6FB5", "#C8443C", "#E8B83A", "#3C8D5A"]):
    caixa((3.2 + i * 0.32, 5.25, 0.3), (0.28, 0.3, 0.6), c, 0.02)


def mesa(x, y, giro=0.0):
    p = vazio("mesa", (x, y, 0)); p.rotation_euler.z = giro
    caixa((0, 0, 0.74), (1.4, 0.75, 0.05), "#C9B79C", 0.01, pai=p)
    for dx in (-0.65, 0.65):
        caixa((dx, 0, 0.37), (0.05, 0.7, 0.72), "#6E6A66", 0.005, pai=p)
    caixa((0, 0.36, 0.95), (1.45, 0.04, 0.45), "#5B7FA6", 0.01, pai=p)       # divisória
    caixa((0, 0.12, 1.02), (0.6, 0.04, 0.36), "#22252B", 0.01, pai=p)        # monitor
    caixa((0, 0.1, 1.02), (0.54, 0.01, 0.3), "#5FA8D8", 0.0, pai=p)          # tela acesa
    caixa((0, 0.16, 0.82), (0.06, 0.06, 0.14), "#22252B", 0.005, pai=p)
    caixa((0, -0.12, 0.775), (0.45, 0.15, 0.02), "#30343A", 0.004, pai=p)    # teclado
    cil((0.45, -0.1, 0.8), 0.04, 0.1, "#F2F0EC", pai=p)                       # caneca
    # cadeira
    caixa((0, -0.62, 0.48), (0.5, 0.5, 0.08), "#2B2F36", 0.03, pai=p)
    caixa((0, -0.86, 0.78), (0.48, 0.07, 0.55), "#2B2F36", 0.03, pai=p)
    cil((0, -0.62, 0.24), 0.03, 0.45, "#6E6A66", pai=p)
    return p


mesas = [(-2.6, 3.0), (-1.1, 3.0), (3.0, 3.2), (-2.6, 0.2), (-1.1, 0.2), (2.9, 0.4), (3.0, -1.8), (-2.4, -2.0)]
for (x, y) in mesas:
    mesa(x, y, math.pi)  # monitores virados para a frente da sala
# plantas
for (x, y, e) in ((-4.0, 5.0, 1.0), (4.0, -0.8, 1.2), (-4.0, -2.2, 0.9)):
    cil((x, y, 0.22), 0.2 * e, 0.44 * e, "#C8673C")
    for k in range(6):
        a = k * math.pi / 3
        esfera((x + math.cos(a) * 0.14 * e, y + math.sin(a) * 0.14 * e, (0.62 + 0.12 * (k % 2)) * e),
               (0.18 * e, 0.18 * e, 0.24 * e), "#3F8F55", seg=16)
# bebedouro
cil((4.1, 3.6, 0.5), 0.18, 1.0, "#E9EEF2")
cil((4.1, 3.6, 1.2), 0.15, 0.4, "#8FC4E8")


# ------------------------------------------------------------------ personagens (cabeça redonda, olhos, sem boca)
class Boneco:
    def __init__(self, nome, pele, cabelo, camisa, calca, sapato="#2A2A2E", topete=True):
        self.raiz = vazio(nome, (0, 0, 0))
        r = self.raiz
        self.quadril = vazio(nome + "_quadril", (0, 0, 0.86), r)
        q = self.quadril
        self.pernas = []
        for s in (-1, 1):
            p = vazio(f"{nome}_perna{s}", (0.1 * s, 0, 0), q)
            capsula((0, 0, -0.4), 0.075, 0.72, calca, pai=p)
            esfera((0, -0.06, -0.8), (0.09, 0.15, 0.06), sapato, pai=p)
            self.pernas.append(p)
        self.tronco = vazio(nome + "_tronco", (0, 0, 0), q)
        t = self.tronco
        esfera((0, 0, 0.2), (0.21, 0.15, 0.3), camisa, pai=t)
        cil((0, 0, 0.0), 0.17, 0.14, calca, pai=t)
        cil((0, 0, 0.47), 0.05, 0.1, pele, pai=t)  # pescoço
        self.bracos = []
        for s in (-1, 1):
            b = vazio(f"{nome}_braco{s}", (0.24 * s, 0, 0.4), t)
            capsula((0, 0, -0.24), 0.06, 0.42, camisa, pai=b)
            esfera((0, 0, -0.53), (0.065, 0.065, 0.07), pele, pai=b)
            self.bracos.append(b)
        self.cabeca = vazio(nome + "_cabeca", (0, 0, 0.5), t)
        c = self.cabeca
        esfera((0, 0, 0.27), (0.27, 0.26, 0.27), pele, pai=c)
        esfera((0, 0.035, 0.33), (0.272, 0.25, 0.235), cabelo, pai=c)
        if topete:
            esfera((-0.04, -0.12, 0.52), (0.12, 0.08, 0.06), cabelo, pai=c)
        self.olhos, self.palpebras = [], []
        for s in (-1, 1):
            ol = vazio(f"{nome}_olho{s}", (0.085 * s, -0.245, 0.29), c)
            esfera((0, 0, 0), (0.042, 0.02, 0.06), "#16161A", pai=ol)
            esfera((-0.012, -0.016, 0.022), (0.012, 0.006, 0.014), "#FFFFFF", pai=ol, seg=12)
            self.olhos.append(ol)
            pa = vazio(f"{nome}_palpebra{s}", (0.085 * s, -0.24, 0.29 + 0.09), c)
            esfera((0, 0, 0), (0.055, 0.03, 0.045), pele, pai=pa, seg=20)
            self.palpebras.append(pa)

    # ---- chaves de animação
    def k(self, ob, prop, f, val):
        setattr(ob, prop, val)
        ob.keyframe_insert(prop, frame=f)

    def olhar(self, f, estado):
        """estado: normal | sono (pálpebra meio caída) | arregalado | fechado"""
        esc = {"normal": 1.0, "sono": 1.0, "arregalado": 1.35, "fechado": 0.08}[estado]
        ex = 1.35 if estado == "arregalado" else 1.0
        # pálpebra só aparece no sono; fora disso fica escondida dentro da cabeça
        dz = {"normal": 0.10, "sono": 0.042, "arregalado": 0.13, "fechado": 0.10}[estado]
        dy = -0.236 if estado == "sono" else -0.17
        for o in self.olhos:
            self.k(o, "scale", f, (ex, 1, esc))
        for p in self.palpebras:
            loc = p.location.copy(); loc.z = 0.29 + dz; loc.y = dy
            self.k(p, "location", f, loc)

    def piscar(self, f, base="normal"):
        self.olhar(f - 2, base); self.olhar(f, "fechado"); self.olhar(f + 3, base)


caio = Boneco("caio", "#9C6644", "#151515", "#3D6FA8", "#24262B")
colegas = [
    (Boneco("nina", "#E3B48F", "#3B2414", "#2F7A4E", "#5A3D2B", topete=False), (-1.1, 3.0 - 0.62)),
    (Boneco("bento", "#7A4E33", "#2B2B2B", "#6B6B3A", "#2F2F2F"), (2.9, 0.4 - 0.62)),
    (Boneco("lurdes", "#D8A98A", "#D9D9D9", "#5B3F7A", "#2E2A33", topete=False), (-2.6, 0.2 - 0.62)),
]
# colegas sentados de frente para a câmera, olhando o monitor e digitando (ninguém nota o Caio)
for b, (x, y) in colegas:
    b.raiz.location = (x, y + 1.24, -0.31)
    for p in b.pernas:
        p.rotation_euler.x = -math.pi / 2
    for f in range(1, 289, 6):
        for i, br in enumerate(b.bracos):
            br.rotation_euler = (-1.25 + 0.08 * math.sin(f * 0.9 + i * 2), 0, 0)
            br.keyframe_insert("rotation_euler", frame=f)
        b.cabeca.rotation_euler = (0.08 + 0.03 * math.sin(f * 0.13), 0, 0.05 * math.sin(f * 0.05))
        b.cabeca.keyframe_insert("rotation_euler", frame=f)

# ------------------------------------------------------------------ animação do Caio
A = Vector((1.8, 5.2, 0)); B = Vector((0.25, 0.9, 0))
d = (B - A).normalized()
giro_path = math.atan2(d.x, -d.y)
r = caio.raiz
WALK_END = 100
for f in range(1, 289):
    t = (f - 1) / FPS
    if f <= WALK_END:
        u = (f - 1) / (WALK_END - 1)
        pos = A.lerp(B, u)
        fase = 2 * math.pi * 1.05 * t
        sw = math.sin(fase) * (0.5 if u < 0.92 else 0.5 * (1 - (u - 0.92) / 0.08))
        caio.k(r, "location", f, (pos.x, pos.y, abs(math.cos(fase)) * 0.035))
        caio.k(r, "rotation_euler", f, (0, 0, giro_path))
        caio.k(caio.pernas[0], "rotation_euler", f, (sw, 0, 0))
        caio.k(caio.pernas[1], "rotation_euler", f, (-sw, 0, 0))
        caio.k(caio.bracos[0], "rotation_euler", f, (-sw * 0.8, 0.08, 0))
        caio.k(caio.bracos[1], "rotation_euler", f, (sw * 0.8, -0.08, 0))
        caio.k(caio.tronco, "rotation_euler", f, (0.05, 0, math.sin(fase) * 0.06))
        caio.k(caio.cabeca, "rotation_euler", f, (0, 0, -math.sin(fase) * 0.04))
caio.olhar(1, "sono")
caio.piscar(40, "sono"); caio.piscar(78, "sono")
# 100-160: vira de frente e procura alguém que o note
caio.k(r, "rotation_euler", 112, (0, 0, 0))
caio.k(r, "location", 112, (B.x, B.y, 0))
for i, (f, ang) in enumerate([(118, 0.0), (128, 0.6), (140, 0.6), (150, -0.6), (160, -0.6), (168, 0.0)]):
    caio.k(caio.cabeca, "rotation_euler", f, (0, 0, ang))
caio.k(caio.bracos[1], "rotation_euler", 118, (0, -0.08, 0))
caio.k(caio.bracos[1], "rotation_euler", 128, (-0.2, -2.3, 0))   # acena
caio.k(caio.bracos[1], "rotation_euler", 133, (-0.2, -2.7, 0))
caio.k(caio.bracos[1], "rotation_euler", 138, (-0.2, -2.3, 0))
caio.k(caio.bracos[1], "rotation_euler", 143, (-0.2, -2.7, 0))
caio.k(caio.bracos[1], "rotation_euler", 152, (0, -0.08, 0))
caio.k(caio.bracos[0], "rotation_euler", 118, (0, 0.08, 0))
caio.olhar(118, "sono"); caio.olhar(124, "normal")
caio.piscar(146)
# 168-215: a ficha cai — olhos arregalados, mãos na frente do rosto
caio.olhar(176, "normal"); caio.olhar(180, "arregalado")
caio.k(caio.tronco, "rotation_euler", 176, (0.0, 0, 0))
caio.k(caio.tronco, "rotation_euler", 182, (-0.12, 0, 0))
for i, s in enumerate((-1, 1)):
    caio.k(caio.bracos[i], "rotation_euler", 182, (0, -0.08 * s, 0))
    caio.k(caio.bracos[i], "rotation_euler", 192, (-1.9, 0.25 * s, 0))
caio.k(caio.cabeca, "rotation_euler", 192, (0, 0, 0))
caio.k(caio.cabeca, "rotation_euler", 200, (0.35, 0, 0))     # olha para as próprias mãos
caio.k(r, "location", 180, (B.x, B.y, 0)); caio.k(r, "location", 184, (B.x, B.y, 0.08)); caio.k(r, "location", 188, (B.x, B.y, 0))
caio.piscar(212, "arregalado")
caio.k(caio.cabeca, "rotation_euler", 222, (0.35, 0, 0))
caio.k(caio.cabeca, "rotation_euler", 230, (-0.05, 0, 0))   # encara a câmera
# 240-262: some piscando
for f, vis in [(1, True), (242, False), (244, True), (247, False), (250, True), (252, False), (253, True), (256, False)]:
    for o in [r] + list(r.children_recursive):
        o.hide_render = not vis
        o.keyframe_insert("hide_render", frame=f)
for fc_ob in [r] + list(r.children_recursive):
    if fc_ob.animation_data and fc_ob.animation_data.action:
        for fc in fc_ob.animation_data.action.fcurves:
            if fc.data_path == "hide_render":
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"

# ------------------------------------------------------------------ câmeras
alvo = vazio("alvo", (0, 0, 1))
cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
tc = cam.constraints.new("TRACK_TO"); tc.target = alvo; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"


def chave_cam(f, pos, mira, lente):
    cam.location = pos; cam.keyframe_insert("location", frame=f)
    alvo.location = mira; alvo.keyframe_insert("location", frame=f)
    cam_d.lens = lente; cam_d.keyframe_insert("lens", frame=f)


def corte(f):
    """Troca seca de plano no quadro f: a última chave antes de f fica constante."""
    for ad in (cam.animation_data, alvo.animation_data, cam_d.animation_data):
        for fc in ad.action.fcurves:
            ant = [kp for kp in fc.keyframe_points if kp.co.x < f]
            if ant:
                max(ant, key=lambda kp: kp.co.x).interpolation = "CONSTANT"


bpy.context.view_layer.update()
# plano 1 (1-100): câmera recua na frente do Caio enquanto ele anda
for f in range(1, 101, 3):
    sc.frame_set(f)
    p = r.matrix_world.translation.copy()
    chave_cam(f, p + Vector((-0.3, -3.2, 1.7)), p + Vector((0, 0, 1.0)), 22)
# plano 2 (101-172): de lado, girando devagar enquanto ele procura alguém
P = Vector((B.x, B.y, 0))
for i, f in enumerate(list(range(101, 173, 6)) + [172]):
    a = math.radians(35 - 30 * (f - 101) / 72)
    chave_cam(f, P + Vector((math.sin(a) * 2.6, -math.cos(a) * 2.6, 1.55)), P + Vector((0, 0, 1.3)), 26)
# plano 3 (173-236): close frontal empurrando para o rosto
chave_cam(173, P + Vector((0.2, -2.6, 1.6)), P + Vector((0, 0, 1.5)), 32)
chave_cam(236, P + Vector((0.08, -1.75, 1.64)), P + Vector((0, 0, 1.55)), 34)
# plano 4 (237-288): plano aberto do alto — o lugar vazio onde ele estava
chave_cam(237, P + Vector((2.6, -4.2, 2.4)), P + Vector((0, 0.3, 0.9)), 20)
chave_cam(288, P + Vector((3.0, -4.9, 2.75)), P + Vector((0, 0.3, 0.8)), 20)
corte(101); corte(173); corte(237)

# ------------------------------------------------------------------ tempo da animação casado com a narração
# âncoras: quadro original -> quadro novo (24 fps). Narração: "mas ninguém" 5,7s; "E foi aí" 9,4s; "percebeu" ~10,3s; "sumido" ~12,4s
ANCORAS = [(1, 1), (100, 135), (101, 136), (173, 227), (180, 248), (237, 277), (242, 297), (256, 311), (288, 351)]


def remap(x):
    for (a0, b0), (a1, b1) in zip(ANCORAS, ANCORAS[1:]):
        if x <= a1:
            return b0 + (x - a0) * (b1 - b0) / (a1 - a0)
    return ANCORAS[-1][1] + (x - ANCORAS[-1][0])


acoes = {ad.action for ad in (o.animation_data for o in list(bpy.data.objects) + [cam_d]) if ad and ad.action}
for ac in acoes:
    for fc in ac.fcurves:
        for kp in fc.keyframe_points:
            x = kp.co.x
            kp.co.x = remap(x)
            kp.handle_left.x = remap(kp.handle_left.x)
            kp.handle_right.x = remap(kp.handle_right.x)
        fc.update()
TOTAL = ANCORAS[-1][1]
por = math.ceil(TOTAL / NPARTES)
F0 = (PARTE - 1) * por + 1
F1 = min(TOTAL, PARTE * por)

# ------------------------------------------------------------------ render Workbench
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.fps = FPS
sc.frame_start, sc.frame_end = F0, F1
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
w = bpy.data.worlds.new("mundo"); w.color = (0.8, 0.8, 0.8); sc.world = w
sc.display.light_direction = (0.45, -0.35, 0.82)
sc.display.shadow_shift = 0.1
sc.display.shadow_focus = 0.6
try:
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.75
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT, "f_")
bpy.ops.render.render(animation=True)
print("FIM", F0, F1, flush=True)
