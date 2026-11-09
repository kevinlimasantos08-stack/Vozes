"""Teste 3D: Dr. Rafael (estilo bloquinho) no escritório. Uso:
blender -b -P blender/teste_personagem.py -- <pasta_saida> <eevee|cycles>
Gera still_<motor>.png (1080x1920), anim_<motor>_####.png (24 quadros) e tempos_<motor>.json.
"""
import bpy, sys, os, json, time, math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "saida3d")
MOTOR = argv[1] if len(argv) > 1 else "eevee"
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def mat(nome, cor, rug=0.6, metal=0.0, sss=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    if sss and "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.25)
        b.inputs["Subsurface Scale"].default_value = 0.05
    return m


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def caixa(nome, dims, loc, material, raio=0.08, seg=5, pai=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = nome
    o.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    bv = o.modifiers.new("bevel", "BEVEL")
    bv.width = min(raio, min(dims) * 0.49)
    bv.segments = seg
    bv.limit_method = "NONE"
    bpy.ops.object.shade_smooth()
    o.data.materials.append(material)
    if pai:
        o.parent = pai
        o.matrix_parent_inverse = pai.matrix_world.inverted()
    return o


def esfera(nome, r, loc, material, pai=None, esc=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
    o = bpy.context.object
    o.name = nome
    o.scale = esc
    bpy.ops.object.shade_smooth()
    o.data.materials.append(material)
    if pai:
        o.parent = pai
        o.matrix_parent_inverse = pai.matrix_world.inverted()
    return o


# ---------------- materiais
PELE = mat("pele", srgb("#C99470"), 0.55, sss=0.15)
TERNO = mat("terno", srgb("#1B1B20"), 0.75)
CAMISA = mat("camisa", srgb("#F2EEE6"), 0.6)
GRAVATA = mat("gravata", srgb("#D9C4A3"), 0.35, 0.3)
CABELO = mat("cabelo", srgb("#1F1A16"), 0.8)
OLHO = mat("olho", srgb("#FAFAF7"), 0.15)
PUPILA = mat("pupila", srgb("#1A1412"), 0.1)
SAPATO = mat("sapato", srgb("#121212"), 0.3)
CALCA = mat("calca", srgb("#202026"), 0.8)
BOCA = mat("boca", srgb("#5A1E22"), 0.5)

# ---------------- personagem (altura ~1,75)
raiz = bpy.data.objects.new("rafael", None)
sc.collection.objects.link(raiz)
caixa("perna_e", (0.17, 0.2, 0.62), (-0.11, 0, 0.36), CALCA, 0.06, pai=raiz)
caixa("perna_d", (0.17, 0.2, 0.62), (0.11, 0, 0.36), CALCA, 0.06, pai=raiz)
caixa("sapato_e", (0.2, 0.3, 0.1), (-0.11, -0.05, 0.05), SAPATO, 0.04, pai=raiz)
caixa("sapato_d", (0.2, 0.3, 0.1), (0.11, -0.05, 0.05), SAPATO, 0.04, pai=raiz)
tronco = caixa("tronco", (0.56, 0.3, 0.62), (0, 0, 0.98), TERNO, 0.12, pai=raiz)
caixa("camisa", (0.16, 0.02, 0.4), (0, -0.155, 1.08), CAMISA, 0.01, pai=raiz)
caixa("gravata", (0.07, 0.025, 0.34), (0, -0.168, 1.05), GRAVATA, 0.015, pai=raiz)
caixa("braco_e", (0.14, 0.17, 0.55), (-0.37, 0, 0.98), TERNO, 0.07, pai=raiz)
caixa("braco_d", (0.14, 0.17, 0.55), (0.37, 0, 0.98), TERNO, 0.07, pai=raiz)
esfera("mao_e", 0.075, (-0.37, 0, 0.68), PELE, raiz)
esfera("mao_d", 0.075, (0.37, 0, 0.68), PELE, raiz)
caixa("pescoco", (0.14, 0.14, 0.1), (0, 0, 1.33), PELE, 0.04, pai=raiz)
cabeca = caixa("cabeca", (0.46, 0.42, 0.48), (0, 0, 1.6), PELE, 0.16, pai=raiz)
caixa("cabelo", (0.48, 0.44, 0.14), (0, 0.01, 1.83), CABELO, 0.07, pai=raiz)
caixa("barba", (0.44, 0.1, 0.2), (0, -0.17, 1.44), CABELO, 0.07, pai=raiz)
for sx in (-1, 1):
    esfera(f"olho_{sx}", 0.06, (sx * 0.1, -0.2, 1.63), OLHO, raiz, (1, 0.5, 1.15))
    esfera(f"pupila_{sx}", 0.032, (sx * 0.1, -0.235, 1.625), PUPILA, raiz, (1, 0.4, 1.1))
    caixa(f"sobrancelha_{sx}", (0.12, 0.03, 0.03), (sx * 0.1, -0.21, 1.73), CABELO, 0.012, pai=raiz)
boca = caixa("boca", (0.12, 0.03, 0.035), (0, -0.212, 1.52), BOCA, 0.012, pai=raiz)

# ---------------- cenário: escritório
PISO = mat("piso", srgb("#5A4232"), 0.45)
PAREDE = mat("parede", srgb("#3A3430"), 0.9)
MADEIRA = mat("madeira", srgb("#6B4A32"), 0.55)
caixa("piso", (8, 8, 0.1), (0, 1, -0.05), PISO, 0.0, 1)
caixa("parede", (8, 0.1, 4), (0, 1.8, 2), PAREDE, 0.0, 1)
caixa("estante", (1.6, 0.35, 2.6), (1.3, 1.55, 1.3), MADEIRA, 0.03, 2)
cores = ["#7A2828", "#283C5A", "#BEA06E", "#1E1E1E", "#5A6E46", "#D9C4A3"]
import random
rnd = random.Random(7)
for prat in range(4):
    z = 0.35 + prat * 0.6
    caixa(f"prat{prat}", (1.5, 0.3, 0.04), (1.3, 1.45, z - 0.04), MADEIRA, 0.01, 1)
    x = 0.6
    while x < 1.98:
        w = rnd.uniform(0.05, 0.1); h = rnd.uniform(0.32, 0.46)
        caixa(f"livro{prat}_{x:.2f}", (w, 0.24, h), (x + w / 2, 1.45, z + h / 2), mat("l", srgb(rnd.choice(cores)), 0.6), 0.01, 1)
        x += w + 0.008
JANELA = mat("janela", (0.0, 0.0, 0.0), 0.2)
em = JANELA.node_tree.nodes["Principled BSDF"]
em.inputs["Emission Color"].default_value = (*srgb("#9DB8D8"), 1)
em.inputs["Emission Strength"].default_value = 2.0
caixa("janela", (1.2, 0.05, 1.5), (-1.4, 1.74, 1.9), JANELA, 0.0, 1)
caixa("moldura", (1.3, 0.04, 0.06), (-1.4, 1.72, 1.9), MADEIRA, 0.0, 1)

# ---------------- luz e mundo
w = bpy.data.worlds.new("mundo"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.03, 0.035, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0


def luz(nome, tipo, energia, loc, rot, cor=(1, 1, 1), tamanho=1.0):
    d = bpy.data.lights.new(nome, tipo); d.energy = energia; d.color = cor
    if tipo == "AREA": d.size = tamanho
    o = bpy.data.objects.new(nome, d); sc.collection.objects.link(o)
    o.location = loc; o.rotation_euler = [math.radians(a) for a in rot]
    return o


luz("chave", "AREA", 450, (-1.6, -2.2, 3.0), (55, 0, -35), (1.0, 0.92, 0.82), 2.0)
luz("preenchimento", "AREA", 120, (2.2, -2.0, 1.8), (70, 0, 45), (0.8, 0.88, 1.0), 3.0)
luz("contra", "AREA", 300, (0.6, 1.4, 2.8), (-50, 0, 170), (1.0, 0.85, 0.65), 1.2)

# ---------------- câmera vertical
cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 50
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
alvo = bpy.data.objects.new("alvo", None); sc.collection.objects.link(alvo); alvo.location = (0, 0, 1.2)
t = cam.constraints.new("TRACK_TO"); t.target = alvo; t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"
cam.location = (0, -4.6, 1.5)
cam_d.dof.use_dof = True; cam_d.dof.focus_object = cabeca; cam_d.dof.aperture_fstop = 2.8

# animação de teste: aproximação + balanço da cabeça + boca
sc.frame_start, sc.frame_end = 1, 12
cam.keyframe_insert("location", frame=1)
cam.location = (0, -3.6, 1.55); cam.keyframe_insert("location", frame=24)
for f in range(1, 25):
    cabeca.rotation_euler = (0, math.radians(3 * math.sin(f / 4)), 0)
    cabeca.keyframe_insert("rotation_euler", frame=f)
    boca.scale = (1, 1, 1 + 2.5 * abs(math.sin(f / 2)))
    boca.keyframe_insert("scale", frame=f)

# ---------------- render
r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, 50
r.image_settings.file_format = "PNG"
if MOTOR == "eevee":
    for nome in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            r.engine = nome; break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = 32
        sc.eevee.use_shadows = True
    except Exception:
        pass
else:
    r.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4

tempos = {"motor": r.engine}
t0 = time.time()
sc.frame_set(12)
r.filepath = os.path.join(OUT, f"still_{MOTOR}.png")
bpy.ops.render.render(write_still=True)
tempos["still_s"] = round(time.time() - t0, 1)

t0 = time.time()
r.filepath = os.path.join(OUT, f"anim_{MOTOR}_")
bpy.ops.render.render(animation=True)
tempos["anim_24q_s"] = round(time.time() - t0, 1)
tempos["por_quadro_s"] = round(tempos["anim_24q_s"] / 12, 2)
json.dump(tempos, open(os.path.join(OUT, f"tempos_{MOTOR}.json"), "w"), indent=1)
print("TEMPOS", tempos)
