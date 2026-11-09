# Fase 1 — Dr. Rafael realista (MPFB2) em escritório Maison Noir, still em Cycles.
# v2: downloads com limite de tempo e cache
# Uso: blender -b --addons bl_ext.user_default.mpfb -P fase1.py -- <saida> <pasta_zips>
import importlib, sys, os, json, math, time, traceback


def dynamic_import(absolute_package_str, key):
    for amod in list(sys.modules):
        if amod.endswith(absolute_package_str):
            mod = importlib.import_module(amod)
            return getattr(mod, key)
    raise ValueError("modulo nao achado: " + absolute_package_str)


import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SAIDA = os.path.abspath(argv[0])
ZIPS = os.path.abspath(argv[1]) if len(argv) > 1 else ""
BASE = os.path.abspath(argv[2]) if len(argv) > 2 else ""
os.makedirs(SAIDA, exist_ok=True)
INFO = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print("[fase1]", s, flush=True)
    INFO.append(s)


def salvar_info():
    with open(os.path.join(SAIDA, "info.txt"), "w") as f:
        f.write("\n".join(INFO) + "\n")


HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")
LocationService = dynamic_import("mpfb.services.locationservice", "LocationService")
HumanObjectProperties = dynamic_import("mpfb.entities.objectproperties", "HumanObjectProperties")

# ---------------------------------------------------------------- pacotes de assets
dados = LocationService.get_user_data()
log("user_data:", dados)
if ZIPS and os.path.isdir(ZIPS):
    for z in sorted(os.listdir(ZIPS)):
        if z.endswith(".zip"):
            err = AssetService.fix_and_extract_asset_pack_zip(os.path.join(ZIPS, z), dados)
            log("pacote", z, "->", err or "ok")
import shutil
if BASE and os.path.isdir(BASE):
    for d in sorted(os.listdir(BASE)):
        src = os.path.join(BASE, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dados, d), dirs_exist_ok=True)
    log("assets base copiados:", sorted(os.listdir(BASE)))
for fn in ("rescan_pack_metadata", "update_all_asset_lists"):
    try:
        getattr(AssetService, fn)()
    except Exception as e:
        log("aviso", fn, e)


def nomes(sub, tipo="mhclo"):
    try:
        lst = AssetService.list_mhclo_assets(sub) if tipo == "mhclo" else AssetService.list_mhmat_assets(sub)
        return sorted(str(p) for p in lst)
    except Exception as e:
        log("erro listando", sub, e)
        return []


CATALOGO = {s: nomes(s) for s in ("eyes", "eyebrows", "eyelashes", "hair", "teeth", "tongue", "clothes")}
CATALOGO["skins"] = nomes("skins", "mhmat")
with open(os.path.join(SAIDA, "catalogo.json"), "w") as f:
    json.dump({k: [os.path.basename(x) for x in v] for k, v in CATALOGO.items()}, f, indent=1)
for k, v in CATALOGO.items():
    log("catalogo", k, len(v))


def escolher(sub, preferidos, proibidos=()):
    """Escolhe o primeiro arquivo cujo nome contém todas as palavras de um dos 'preferidos'."""
    lst = CATALOGO.get(sub, [])
    for pref in preferidos:
        palavras = pref.lower().split()
        for p in lst:
            b = os.path.basename(p).lower()
            if all(w in b for w in palavras) and not any(x in b for x in proibidos):
                return p
    return None


# ---------------------------------------------------------------- cena limpa
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

# ---------------------------------------------------------------- humano
human = HumanService.create_human()
macros = {"gender": 1.0, "age": 0.60, "muscle": 0.56, "weight": 0.52, "height": 0.58,
          "proportions": 0.65, "caucasian": 0.62, "african": 0.25, "asian": 0.13}
for k, v in macros.items():
    try:
        HumanObjectProperties.set_value(k, v, entity_reference=human)
    except Exception as e:
        log("macro falhou", k, e)
TargetService.reapply_macro_details(human)
log("macros", macros)

# pele
pele = escolher("skins", ["toigo bronze", "middleage lightskinned male", "middleage caucasian male",
                          "young lightskinned male", "young caucasian male", "male"], ("female", "tattoo", "genitals"))
log("pele:", pele)
if pele:
    for tipo in ("ENHANCED_SSS", "MAKESKIN"):
        try:
            HumanService.set_character_skin(pele, human, skin_type=tipo)
            log("pele tipo", tipo)
            break
        except Exception as e:
            log("pele falhou", tipo, e)

# esqueleto (antes das roupas para que elas acompanhem a pose)
rig = None
try:
    rig = HumanService.add_builtin_rig(human, "default")
    log("rig ok", rig.name if rig else None)
except Exception as e:
    log("rig falhou", e)


def add(sub, arq, tipo, **kw):
    if not arq:
        log("sem asset para", tipo)
        return None
    try:
        try:
            ob = HumanService.add_mhclo_asset(arq, human, asset_type=tipo, **kw)
        except TypeError:
            ob = HumanService.add_mhclo_asset(arq, human, asset_type=tipo)
        log("asset", tipo, os.path.basename(arq))
        return ob
    except Exception as e:
        log("asset falhou", tipo, os.path.basename(arq), e)
        return None


add("eyes", escolher("eyes", ["high-poly", "low-poly"]), "Eyes")
add("eyebrows", escolher("eyebrows", ["eyebrow001", "eyebrow"]), "Eyebrows")
add("eyelashes", escolher("eyelashes", ["eyelashes01", "eyelashes"]), "Eyelashes")
add("teeth", escolher("teeth", ["teeth_base", "teeth"]), "Teeth")
add("tongue", escolher("tongue", ["tongue01", "tongue"]), "Tongue")
add("hair", escolher("hair", ["short02", "short04", "short03", "short01", "short"], ("female",)), "Hair")
add("clothes", escolher("clothes", ["scruffy beard", "beard"], ("viking", "faun")), "Clothes")
terno = escolher("clothes", ["male worksuit", "worksuit", "suit male", "male casualsuit", "casualsuit", "male"], ("female", "beard", "moustache"))
add("clothes", terno, "Clothes")
sapato = escolher("clothes", ["shoes0", "shoes"], ("female",))
add("clothes", sapato, "Clothes")

# suavização da malha
for ob in [human] + list(human.children):
    if ob.type == "MESH" and not any(m.type == "SUBSURF" for m in ob.modifiers):
        m = ob.modifiers.new("Subdiv", "SUBSURF")
        m.levels, m.render_levels = 0, 1

# ---------------------------------------------------------------- pose: braços para baixo
if rig:
    try:
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="POSE")

        def apontar(nome, alvo):
            pb = rig.pose.bones.get(nome)
            if not pb:
                log("osso ausente", nome)
                return
            bpy.context.view_layer.update()
            atual = (pb.tail - pb.head).normalized()
            q = atual.rotation_difference(Vector(alvo).normalized())
            M = pb.matrix.copy()
            loc = M.translation.copy()
            N = q.to_matrix().to_4x4() @ M
            N.translation = loc
            pb.matrix = N
            bpy.context.view_layer.update()

        for lado, s in (("L", 1), ("R", -1)):
            apontar(f"upperarm01.{lado}", (0.20 * s, 0.06, -1.0))
            apontar(f"lowerarm01.{lado}", (0.10 * s, -0.30, -1.0))
        bpy.ops.object.mode_set(mode="OBJECT")
        log("pose aplicada")
    except Exception as e:
        log("pose falhou", e)
        traceback.print_exc()

bpy.context.view_layer.update()

# medidas do personagem
pts = [human.matrix_world @ Vector(c) for c in human.bound_box]
topo = max(p.z for p in pts)
log("altura topo", round(topo, 3))
rosto = Vector((0.0, -0.02, topo - 0.12))

# ---------------------------------------------------------------- materiais simples


def mat(nome, cor, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def caixa(nome, loc, dim, material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = nome
    o.scale = (dim[0] / 2, dim[1] / 2, dim[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    bv = o.modifiers.new("b", "BEVEL")
    bv.width, bv.segments = 0.01, 2
    o.data.materials.append(material)
    return o


preto = mat("parede", (0.035, 0.034, 0.033), 0.75)
madeira = mat("madeira", (0.09, 0.05, 0.03), 0.45)
champ = mat("champanhe", (0.78, 0.66, 0.45), 0.3, 1.0)
couro = mat("couro", (0.02, 0.018, 0.017), 0.55)
livros = [mat(f"livro{i}", c, 0.6) for i, c in enumerate(
    [(0.25, 0.05, 0.04), (0.05, 0.08, 0.15), (0.45, 0.38, 0.25), (0.06, 0.12, 0.07), (0.12, 0.1, 0.09)])]

caixa("piso", (0, 1.5, -0.01), (8, 8, 0.02), madeira)
caixa("parede", (0, 2.2, 1.6), (6, 0.1, 3.4), preto)
for x in (-1.6, -0.55, 0.55, 1.6):  # frisos champanhe
    caixa("friso", (x, 2.13, 1.6), (0.02, 0.02, 3.2), champ)
# estante com livros à direita
import random
random.seed(7)
for prat in range(4):
    z = 0.6 + prat * 0.42
    caixa("prateleira", (1.15, 2.0, z), (1.1, 0.32, 0.03), madeira)
    x = 0.65
    while x < 1.62:
        w = random.uniform(0.035, 0.07)
        h = random.uniform(0.24, 0.34)
        caixa("livro", (x + w / 2, 2.0, z + 0.015 + h / 2), (w, 0.24, h), random.choice(livros))
        x += w + 0.004
# mesa à frente, desfocada
caixa("mesa", (0, -0.55, 0.76), (1.6, 0.8, 0.05), madeira)
caixa("pasta", (-0.35, -0.5, 0.80), (0.32, 0.24, 0.03), couro)
# cadeira atrás
caixa("encosto", (0, 0.42, 1.05), (0.62, 0.08, 0.95), couro)
# luminária
bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.22, location=(-1.25, 1.9, 1.9))
abaj = bpy.context.active_object
emis = bpy.data.materials.new("abajur")
emis.use_nodes = True
eb = emis.node_tree.nodes["Principled BSDF"]
eb.inputs["Emission Color"].default_value = (1.0, 0.78, 0.5, 1)
eb.inputs["Emission Strength"].default_value = 6.0
abaj.data.materials.append(emis)

# ---------------------------------------------------------------- luz


def luz(nome, loc, energia, tam, cor, alvo):
    d = bpy.data.lights.new(nome, "AREA")
    d.energy, d.size, d.color = energia, tam, cor
    o = bpy.data.objects.new(nome, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    direc = Vector(alvo) - Vector(loc)
    o.rotation_euler = direc.to_track_quat("-Z", "Y").to_euler()
    return o


luz("chave", (-1.3, -1.5, topo + 0.4), 260, 1.4, (1.0, 0.93, 0.85), rosto)
luz("preenchimento", (1.6, -1.2, topo - 0.2), 60, 2.0, (0.85, 0.9, 1.0), rosto)
luz("recorte", (0.8, 1.2, topo + 0.6), 180, 0.8, (1.0, 0.88, 0.7), rosto)
pl = bpy.data.lights.new("abajur", "POINT")
pl.energy, pl.color = 25, (1.0, 0.75, 0.45)
plo = bpy.data.objects.new("abajur", pl)
bpy.context.collection.objects.link(plo)
plo.location = (-1.25, 1.75, 1.9)

w = bpy.data.worlds.new("mundo")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.022, 1)
bpy.context.scene.world = w

# ---------------------------------------------------------------- render
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 96
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass
try:
    sc.cycles.time_limit = 1100
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92

cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
bpy.context.collection.objects.link(cam)
sc.camera = cam
cam_d.dof.use_dof = True

tempos = {}
planos = [
    # nome, deslocamento da câmera em relação ao rosto, mira (z relativa ao rosto), lente, f-stop
    ("plano_medio", Vector((0.32, -1.55, -0.02)), -0.22, 50, 2.2),
    ("close", Vector((0.18, -0.95, 0.0)), -0.02, 85, 2.0),
]
salvar_info()
for nome, desl, mira_z, lente, fs in planos:
    cam.location = rosto + desl
    alvo = rosto + Vector((0, 0, mira_z))
    cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_d.lens = lente
    cam_d.dof.focus_distance = (rosto - cam.location).length
    cam_d.dof.aperture_fstop = fs
    sc.render.filepath = os.path.join(SAIDA, nome + ".jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    tempos[nome] = round(time.time() - t, 1)
    log("render", nome, tempos[nome], "s")
    salvar_info()

with open(os.path.join(SAIDA, "tempos.json"), "w") as f:
    json.dump(tempos, f)
try:
    bpy.ops.wm.save_as_mainfile(filepath="/tmp/rafael_fase1.blend")
except Exception as e:
    log("blend nao salvo", e)
salvar_info()
log("fim")
