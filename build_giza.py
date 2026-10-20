"""
Giza Plateau - procedural 3D reconstruction for Blender 4.5 (bpy).

Coordinate system: metres, +X east, +Y north, +Z up.
Origin: centre of the Great Pyramid of Khufu.
The model represents the monuments in their present, ruined state, with the
surviving casing at the apex of Khafre and the granite facing at the base of
Menkaure.

Run with the Blender Python module:
    .venv\\Scripts\\python.exe build_giza.py
"""
from __future__ import annotations

import bpy
import bmesh
import math
import os
import random
import json
from math import sin, cos, tan, radians, pi, exp, floor
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, "textures")
RENDERS = os.path.join(ROOT, "renders")
os.makedirs(RENDERS, exist_ok=True)
random.seed(20251020)

# --------------------------------------------------------------------------
# Site data.  Coordinates from Wikipedia/Wikidata; dimensions from Lehner,
# Verner and Petrie as summarised in the monument articles.
# --------------------------------------------------------------------------
LAT0, LON0 = 29.97916667, 31.13416667
MLAT = 111132.95
MLON = 111319.49 * cos(radians(LAT0))


def en(lat, lon):
    return ((lon - LON0) * MLON, (lat - LAT0) * MLAT)


KHUFU = dict(name="Khufu", lat=29.97916667, lon=31.13416667,
             base_x=230.33, base_y=230.33, h0=146.6, h=138.5,
             angle=51 + 50 / 60 + 40 / 3600, z=0.0)
KHAFRE = dict(name="Khafre", lat=29.97611111, lon=31.13083333,
              base_x=215.25, base_y=215.25, h0=143.5, h=136.4,
              angle=53 + 10 / 60, z=7.0)
MENKAURE = dict(name="Menkaure", lat=29.9725, lon=31.12833333,
                base_x=102.2, base_y=104.6, h0=65.0, h=61.0,
                angle=51 + 20 / 60 + 25 / 3600, z=3.5)
SPHINX = dict(lat=29.97526, lon=31.13758, z=-12.0)

for d in (KHUFU, KHAFRE, MENKAURE):
    d["x"], d["y"] = en(d["lat"], d["lon"])
SPHINX["x"], SPHINX["y"] = en(SPHINX["lat"], SPHINX["lon"])

KX, KY = KHUFU["x"], KHUFU["y"]
FX, FY = KHAFRE["x"], KHAFRE["y"]
MX, MY = MENKAURE["x"], MENKAURE["y"]
SX, SY = SPHINX["x"], SPHINX["y"]


def clamp(v, a, b):
    return max(a, min(b, v))


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def hash2(ix, iy, seed):
    h = sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453123
    return h - floor(h)


def vnoise(x, y, seed):
    ix, iy = floor(x), floor(y)
    fx, fy = x - ix, y - iy
    u, v = smoothstep(fx), smoothstep(fy)
    a = hash2(ix, iy, seed)
    b = hash2(ix + 1, iy, seed)
    c = hash2(ix, iy + 1, seed)
    d = hash2(ix + 1, iy + 1, seed)
    return lerp(lerp(a, b, u), lerp(c, d, u), v)


def fbm(x, y, scale, octaves=5, seed=1, persistence=0.55):
    total = 0.0
    norm = 0.0
    amp = 1.0
    f = 1.0 / scale
    for o in range(octaves):
        total += amp * vnoise(x * f, y * f, seed + o * 17)
        norm += amp
        amp *= persistence
        f *= 2.0
    return total / norm


def pad_weight(x, y, cx, cy, hx, hy, feather):
    dx = max(abs(x - cx) - hx, 0.0)
    dy = max(abs(y - cy) - hy, 0.0)
    d = math.hypot(dx, dy)
    return smoothstep(1.0 - d / feather)


def terrain_z(x, y):
    """Present-day plateau surface (metres above the Khufu datum)."""
    z = -0.0115 * x + 0.0022 * y
    z += 3.2 * (fbm(x, y, 620, 4, 11) - 0.5)
    z += 1.25 * (fbm(x, y, 160, 4, 29) - 0.5)
    z += 0.45 * (fbm(x, y, 38, 3, 41) - 0.5)

    # low limestone ridge closing the western horizon
    z += 26.0 * exp(-(((x + 1550) / 380) ** 2)) * (0.7 + 0.3 * fbm(x, y, 300, 3, 53))
    # the plateau drops toward the Nile floodplain in the east
    z -= 17.0 * smoothstep((x - 620) / 520.0)
    # and gently toward the north-east
    z -= 4.0 * smoothstep((-y + 450) / 900.0)

    # level construction terraces
    for (cx, cy, hx, hy, pz, feather) in (
        (0, 0, 175, 175, 0.0, 95),
        (FX, FY, 160, 160, KHAFRE["z"], 85),
        (MX, MY, 105, 115, MENKAURE["z"], 75),
    ):
        w = pad_weight(x, y, cx, cy, hx, hy, feather)
        z = z * (1 - w) + pz * w

    # Sphinx enclosure: a quarried pit with steep rock walls
    q = ((x - (SX + 5)) / 82.0) ** 4 + ((y - SY) / 55.0) ** 4
    w = smoothstep((1.18 - q) / 0.28)
    z = z * (1 - w) + SPHINX["z"] * w

    # modest quarry spoil south-east of Khufu
    q2 = ((x - 250) / 160.0) ** 2 + ((y + 180) / 90.0) ** 2
    z += 2.2 * exp(-q2) * (0.6 + 0.4 * fbm(x, y, 60, 3, 71))
    return z


# --------------------------------------------------------------------------
# Scene / helpers
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 40
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPENIMAGEDENOISE"
scene.cycles.max_bounces = 6
scene.cycles.diffuse_bounces = 3
scene.cycles.glossy_bounces = 3
scene.cycles.transmission_bounces = 1
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.compression = 35
scene.view_settings.view_transform = "AgX"
for look in ("AgX - Medium High Contrast", "AgX - Punchy", "Medium High Contrast"):
    try:
        scene.view_settings.look = look
        break
    except Exception:
        pass
scene.view_settings.exposure = -0.05
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.use_file_extension = True
scene.render.threads_mode = "AUTO"

scene["title"] = "Giza Plateau - Khufu, Khafre, Menkaure and the Great Sphinx"
scene["units"] = "metres; X=east, Y=north, Z=up; origin at Khufu centre"
scene["datum"] = "Khufu pyramid base = 0 m"
scene["coordinates"] = {
    "khufu": [KHUFU["lat"], KHUFU["lon"]],
    "khafre": [KHAFRE["lat"], KHAFRE["lon"]],
    "menkaure": [MENKAURE["lat"], MENKAURE["lon"]],
    "sphinx": [SPHINX["lat"], SPHINX["lon"]],
}
scene["dimensions"] = {
    "khufu": {"base_m": [230.33, 230.33], "original_height_m": 146.6, "present_height_m": 138.5, "slope_deg": KHUFU["angle"]},
    "khafre": {"base_m": [215.25, 215.25], "original_height_m": 143.5, "present_height_m": 136.4, "slope_deg": KHAFRE["angle"]},
    "menkaure": {"base_m": [102.2, 104.6], "original_height_m": 65.0, "present_height_m": 61.0, "slope_deg": MENKAURE["angle"]},
    "sphinx": {"length_m": 73, "width_m": 19, "height_m": 20},
}
scene["source"] = "Dimensions: Lehner 1997; Verner 2001; Petrie 1883; coordinates: Wikipedia/Wikidata"


def new_collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c


COL_TERRAIN = new_collection("Terrain")
COL_MONUMENTS = new_collection("Monuments")
COL_MASTABAS = new_collection("Mastabas")
COL_TEMPLES = new_collection("Temples")
COL_SPHINX = new_collection("Sphinx")
COL_ROCKS = new_collection("Rocks")
COL_ANN = new_collection("Annotations")

for c in COL_ANN.objects:
    c.hide_render = True


def load_image(filename, non_color=False):
    path = os.path.join(TEX, filename)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def image_material(name, prefix, tile_hint=8.0, normal_strength=0.8,
                   base_tint=(1, 1, 1), roughness_mul=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_tint, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["IOR"].default_value = 1.5

    color = nodes.new("ShaderNodeTexImage")
    color.image = load_image(prefix + "_color.png")
    color.interpolation = "Linear"
    color.extension = "REPEAT"
    if tuple(base_tint) != (1, 1, 1):
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        mix.inputs[2].default_value = (*base_tint, 1.0)
        links.new(color.outputs["Color"], mix.inputs[1])
        links.new(mix.outputs[0], bsdf.inputs["Base Color"])
    else:
        links.new(color.outputs["Color"], bsdf.inputs["Base Color"])

    nrm = nodes.new("ShaderNodeTexImage")
    nrm.image = load_image(prefix + "_normal.png", non_color=True)
    nrm.interpolation = "Linear"
    nrm.extension = "REPEAT"
    nmap = nodes.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = normal_strength
    links.new(nrm.outputs["Color"], nmap.inputs["Color"])
    links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    if os.path.exists(os.path.join(TEX, prefix + "_rough.png")):
        rough = nodes.new("ShaderNodeTexImage")
        rough.image = load_image(prefix + "_rough.png", non_color=True)
        rough.interpolation = "Linear"
        rough.extension = "REPEAT"
        try:
            links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
        except Exception:
            pass
    mat["tile_hint_m"] = tile_hint
    mat["roughness_mul"] = roughness_mul
    return mat


MAT_LIMESTONE = image_material("Limestone core", "limestone_core", 16.0, 0.42)
MAT_PYRAMID = image_material("Pyramid limestone", "pyramid", 220.0, 0.48)
MAT_CASING = image_material("Tura limestone casing", "casing", 8.0, 0.32)
MAT_GRANITE = image_material("Aswan granite", "granite", 4.0, 0.65)
MAT_SAND = image_material("Desert sand", "sand", 55.0, 1.0)
MAT_ROCK = image_material("Mokattam bedrock", "rock", 18.0, 0.85)
MAT_ENCLOSURE = image_material("Enclosure rock", "rock", 18.0, 0.9, base_tint=(0.50, 0.43, 0.34))
MAT_SPHINX = image_material("Sphinx limestone", "sphinx", 16.0, 0.85)
MAT_SPHINX_SCAN = image_material("Sphinx scan limestone", "sphinx", 16.0, 0.65)
MAT_SPHINX_BODY = image_material("Sphinx body limestone", "pyramid", 40.0, 0.65, base_tint=(0.88, 0.78, 0.64))
MAT_MUDBRICK = image_material("Mudbrick", "mudbrick", 8.0, 0.7)
MAT_NEMES = image_material("Nemes", "nemes", 8.0, 0.45)
MAT_BASALT = image_material("Basalt pavement", "granite", 5.0, 0.7, base_tint=(0.24, 0.23, 0.21))
MAT_ALABASTER = image_material("Alabaster", "casing", 6.0, 0.3, base_tint=(1.0, 0.98, 0.9))
MAT_DARK = bpy.data.materials.new("Entrance shadow")
MAT_DARK.use_nodes = True
MAT_DARK.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.018, 0.014, 0.011, 1)
MAT_DARK.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
MAT_DARK.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.1
MAT_INK = bpy.data.materials.new("Ink")
MAT_INK.use_nodes = True
MAT_INK.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.025, 0.02, 1)
MAT_INK.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0


# --------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------
class MB:
    def __init__(self, tile=8.0):
        self.v = []
        self.f = []
        self.uv = []
        self.tile = tile

    def add(self, pts, uvs=None, face=None):
        i0 = len(self.v)
        self.v.extend([tuple(p) for p in pts])
        n = len(pts)
        if face is None:
            face = tuple(range(n))
        self.f.append(tuple(i0 + k for k in face))
        if uvs is None:
            p0, p1, p2, p3 = pts[0], pts[1], pts[2], pts[3]
            lu = (Vector(p1) - Vector(p0)).length / self.tile
            lv = (Vector(p3) - Vector(p0)).length / self.tile
            uvs = [(0, 0), (lu, 0), (lu, lv), (0, lv)]
        self.uv.extend(uvs)

    def quad(self, p0, p1, p2, p3, uvs=None):
        self.add([p0, p1, p2, p3], uvs)

    def tri(self, p0, p1, p2, uvs=None):
        self.add([p0, p1, p2], uvs if uvs else [(0, 0), (1, 0), (0.5, 1)], face=(0, 1, 2))

    def box(self, cx, cy, cz, sx, sy, sz, rot=0.0, top_scale=(1.0, 1.0), cap=True):
        """Axis-aligned (then Z-rotated) box, sizes are full extents."""
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        ang = rot
        ca, sa = cos(ang), sin(ang)

        def rp(px, py, pz):
            return (cx + px * ca - py * sa, cy + px * sa + py * ca, cz + pz)

        b = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz)]
        txs, tys = hx * top_scale[0], hy * top_scale[1]
        t = [(-txs, -tys, hz), (txs, -tys, hz), (txs, tys, hz), (-txs, tys, hz)]
        b = [rp(*p) for p in b]
        t = [rp(*p) for p in t]
        self.quad(b[0], b[1], t[1], t[0])
        self.quad(b[1], b[2], t[2], t[1])
        self.quad(b[2], b[3], t[3], t[2])
        self.quad(b[3], b[0], t[0], t[3])
        if cap:
            self.quad(t[0], t[1], t[2], t[3])

    def cylinder(self, cx, cy, z0, z1, r0, r1=None, segments=12, cap=True):
        r1 = r0 if r1 is None else r1
        ring0, ring1 = [], []
        for i in range(segments):
            a = 2 * pi * i / segments
            ring0.append((cx + r0 * cos(a), cy + r0 * sin(a), z0))
            ring1.append((cx + r1 * cos(a), cy + r1 * sin(a), z1))
        for i in range(segments):
            j = (i + 1) % segments
            u0 = 2 * pi * r0 * i / segments / self.tile
            u1 = 2 * pi * r0 * (i + 1) / segments / self.tile
            self.quad(ring0[i], ring0[j], ring1[j], ring1[i],
                      [(u0, z0 / self.tile), (u1, z0 / self.tile), (u1, z1 / self.tile), (u0, z1 / self.tile)])
        if cap:
            c0 = (cx, cy, z0)
            for i in range(segments):
                j = (i + 1) % segments
                self.tri(c0, ring0[j], ring0[i])
            c1 = (cx, cy, z1)
            for i in range(segments):
                j = (i + 1) % segments
                self.tri(c1, ring1[i], ring1[j])

    def finish(self, name, mat, coll, smooth=False, recalc=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        if not me.validate():
            pass
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        uvl = me.uv_layers.new(name="UVMap")
        for i, loop in enumerate(me.loops):
            if i < len(self.uv):
                uvl.data[i].uv = self.uv[i]
        me.materials.append(mat)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        obj = bpy.data.objects.new(name, me)
        coll.objects.link(obj)
        return obj


def terrain_mesh():
    n = 380
    span = 10000.0
    half = span / 2
    step = span / n
    verts = []
    uvs = []
    faces = []
    for j in range(n + 1):
        y = -half + j * step
        for i in range(n + 1):
            x = -half + i * step
            verts.append((x, y, terrain_z(x, y)))
            uvs.append((x / 55.0, y / 55.0))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b = a + 1
            c = a + (n + 1) + 1
            d = a + (n + 1)
            faces.append((a, b, c, d))
    me = bpy.data.meshes.new("Giza plateau")
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for k, li in enumerate(poly.loop_indices):
            vi = me.loops[li].vertex_index
            uvl.data[li].uv = uvs[vi]
    me.materials.append(MAT_SAND)
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new("Giza plateau", me)
    COL_TERRAIN.objects.link(obj)
    # edge skirt hiding the world horizon
    sk = MB(tile=55)
    edges = [
        [(-half, -half), (half, -half)],
        [(half, -half), (half, half)],
        [(half, half), (-half, half)],
        [(-half, half), (-half, -half)],
    ]
    for (x0, y0), (x1, y1) in edges:
        nseg = max(2, int(math.hypot(x1 - x0, y1 - y0) / step))
        for i in range(nseg):
            ax = lerp(x0, x1, i / nseg)
            ay = lerp(y0, y1, i / nseg)
            bx = lerp(x0, x1, (i + 1) / nseg)
            by = lerp(y0, y1, (i + 1) / nseg)
            sk.quad((ax, ay, terrain_z(ax, ay)), (bx, by, terrain_z(bx, by)),
                    (bx, by, -90), (ax, ay, -90))
    sk.finish("Plateau edge", MAT_SAND, COL_TERRAIN)
    return obj


# --------------------------------------------------------------------------
# Pyramids
# --------------------------------------------------------------------------
def pyramid_core(name, cx, cy, z0, bx, by, h0, hcur, angle, mat,
                 collec=COL_MONUMENTS, ch_bottom=1.45, ch_top=0.70, lip=0.16,
                 major_every=8, major_lip=0.55):
    tan_a = tan(radians(angle))
    ax, ay = bx / 2, by / 2
    m = MB(tile=16.0)
    z = 0.0
    course_idx = 0
    while z < hcur - 0.03:
        ch = min(lerp(ch_bottom, ch_top, z / h0), hcur - z)
        ax0 = ax * (1 - z / h0)
        ay0 = ay * (1 - z / h0)
        inset = ch / tan_a
        lip_i = major_lip if course_idx % major_every == 0 else lip
        # split the horizontal set-back into the sloping face + a narrow ledge
        slope = max(inset - lip_i, inset * 0.35)
        ledge = max(inset - slope, 0.0)
        axs, ays = max(ax0 - slope, 0.02), max(ay0 - slope, 0.02)
        axn, ayn = max(axs - ledge, 0.01), max(ays - ledge, 0.01)
        z1 = z + ch

        # four sloping faces
        # south (y-)
        m.quad((-ax0, -ay0, z0 + z), (ax0, -ay0, z0 + z),
               (axs, -ays, z0 + z1), (-axs, -ays, z0 + z1),
               [(0, z / 220), (2 * ax0 / 220, z / 220), (2 * axs / 220, z1 / 220), (0, z1 / 220)])
        # east (x+)
        m.quad((ax0, -ay0, z0 + z), (ax0, ay0, z0 + z),
               (axs, ays, z0 + z1), (axs, -ays, z0 + z1),
               [(0, z / 220), (2 * ay0 / 220, z / 220), (2 * ays / 220, z1 / 220), (0, z1 / 220)])
        # north (y+)
        m.quad((ax0, ay0, z0 + z), (-ax0, ay0, z0 + z),
               (-axs, ays, z0 + z1), (axs, ays, z0 + z1),
               [(0, z / 220), (2 * ax0 / 220, z / 220), (2 * axs / 220, z1 / 220), (0, z1 / 220)])
        # west (x-)
        m.quad((-ax0, ay0, z0 + z), (-ax0, -ay0, z0 + z),
               (-axs, -ays, z0 + z1), (-axs, ays, z0 + z1),
               [(0, z / 220), (2 * ay0 / 220, z / 220), (2 * ays / 220, z1 / 220), (0, z1 / 220)])

        # horizontal ledge to the next course
        m.quad((-axs, -ays, z0 + z1), (axs, -ays, z0 + z1),
               (axn, -ayn, z0 + z1), (-axn, -ayn, z0 + z1))
        m.quad((axs, -ays, z0 + z1), (axs, ays, z0 + z1),
               (axn, ayn, z0 + z1), (axn, -ayn, z0 + z1))
        m.quad((axs, ays, z0 + z1), (-axs, ays, z0 + z1),
               (-axn, ayn, z0 + z1), (axn, ayn, z0 + z1))
        m.quad((-axs, ays, z0 + z1), (-axs, -ays, z0 + z1),
               (-axn, -ayn, z0 + z1), (-axn, ayn, z0 + z1))
        z = z1
        course_idx += 1

    # flat, ragged summit platform
    axf = max(ax * (1 - hcur / h0), 0.4)
    ayf = max(ay * (1 - hcur / h0), 0.4)
    m.quad((-axf, -ayf, z0 + hcur), (axf, -ayf, z0 + hcur),
           (axf, ayf, z0 + hcur), (-axf, ayf, z0 + hcur),
           [(-axf / 220, -ayf / 220), (axf / 220, -ayf / 220), (axf / 220, ayf / 220), (-axf / 220, ayf / 220)])
    obj = m.finish(name, mat, collec, smooth=True)
    obj.location = (cx, cy, 0.0)
    return obj


def casing(name, cx, cy, z0, bx, by, h0, zb, zt, angle, mat,
           collec=COL_MONUMENTS, subdiv=4, extra=0.18):
    tan_a = tan(radians(angle))
    ax = bx / 2
    ay = by / 2
    abx = ax * (1 - zb / h0) + extra
    aby = ay * (1 - zb / h0) + extra
    atx = max(ax * (1 - zt / h0), 0.25)
    aty = max(ay * (1 - zt / h0), 0.25)
    m = MB(tile=8.0)
    for k in range(subdiv):
        f0 = k / subdiv
        f1 = (k + 1) / subdiv
        zA, zB = lerp(zb, zt, f0), lerp(zb, zt, f1)
        a0x, a0y = lerp(abx, atx, f0), lerp(aby, aty, f0)
        a1x, a1y = lerp(abx, atx, f1), lerp(aby, aty, f1)

        def side(p0, p1, q1, q0, w0, w1):
            m.quad(p0, p1, q1, q0,
                   [(0, zA / 8), (w0 / 8, zA / 8), (w1 / 8, zB / 8), (0, zB / 8)])

        side((-a0x, -a0y, z0 + zA), (a0x, -a0y, z0 + zA),
             (a1x, -a1y, z0 + zB), (-a1x, -a1y, z0 + zB), 2 * a0x, 2 * a1x)
        side((a0x, -a0y, z0 + zA), (a0x, a0y, z0 + zA),
             (a1x, a1y, z0 + zB), (a1x, -a1y, z0 + zB), 2 * a0y, 2 * a1y)
        side((a0x, a0y, z0 + zA), (-a0x, a0y, z0 + zA),
             (-a1x, a1y, z0 + zB), (a1x, a1y, z0 + zB), 2 * a0x, 2 * a1x)
        side((-a0x, a0y, z0 + zA), (-a0x, -a0y, z0 + zA),
             (-a1x, -a1y, z0 + zB), (-a1x, a1y, z0 + zB), 2 * a0y, 2 * a1y)

    m.quad((-atx, -aty, z0 + zt), (atx, -aty, z0 + zt),
           (atx, aty, z0 + zt), (-atx, aty, z0 + zt),
           [(-atx / 8, -aty / 8), (atx / 8, -aty / 8), (atx / 8, aty / 8), (-atx / 8, aty / 8)])
    obj = m.finish(name, mat, collec, smooth=True)
    obj.location = (cx, cy, 0.0)
    return obj


def north_face_z(d, z):
    return d["base_y"] / 2 * (1 - z / d["h0"])


def add_entrance(d, z, width=1.4, height=2.8, coll=COL_MONUMENTS):
    """Dark doorway lying in the sloping north face."""
    ang = radians(d["angle"])
    yface = d["base_y"] / 2 * (1 - z / d["h0"])
    # tangent down the face and the outward normal
    v = Vector((0, -1 / tan(ang), 1)).normalized()
    n = Vector((0, sin(ang), cos(ang))).normalized()
    c = Vector((d["x"] + 7.2, d["y"] + yface, d["z"] + z)) + n * 0.05
    u = Vector((1, 0, 0))
    pts = [c - u * width / 2 - v * height / 2,
           c + u * width / 2 - v * height / 2,
           c + u * width / 2 + v * height / 2,
           c - u * width / 2 + v * height / 2]
    m = MB()
    m.quad(pts[0], pts[1], pts[2], pts[3], [(0, 0), (1, 0), (1, 1), (0, 1)])
    m.finish(d["name"] + " entrance", MAT_DARK, coll)
    # rubble ramp below the entrance
    r = MB(tile=8)
    base = Vector((d["x"] + 7.2, d["y"] + yface + 1.2, d["z"] + 0.05))
    r.quad(base + Vector((-3.2, 0, 0)), base + Vector((3.2, 0, 0)),
           base + Vector((1.5, -5.0, 2.2)), base + Vector((-1.5, -5.0, 2.2)))
    r.finish(d["name"] + " entrance ramp", MAT_ROCK, coll)


def granite_facing(d, heights, coll=COL_MONUMENTS):
    """Ruined red-granite casing at the base of Menkaure (per-face heights)."""
    ang = radians(d["angle"])
    tan_a = tan(ang)
    ax, ay = d["base_x"] / 2, d["base_y"] / 2
    m = MB(tile=4.0)
    spec = {
        "south": ((-ax, -ay), (ax, -ay), heights[0], 2 * ax),
        "east": ((ax, -ay), (ax, ay), heights[1], 2 * ay),
        "north": ((ax, ay), (-ax, ay), heights[2], 2 * ax),
        "west": ((-ax, ay), (-ax, -ay), heights[3], 2 * ay),
    }
    for key, (p0, p1, hgt, width) in spec.items():
        zt = hgt
        q0 = (p0[0] - (ax - ax * (1 - zt / d["h0"])) * (1 if p0[0] > 0 else -1) * 0, p0[1], d["z"] + zt)
        # shrink the top footprint toward the centre
        sx = ax * (1 - zt / d["h0"])
        sy = ay * (1 - zt / d["h0"])
        q1 = (math.copysign(sx, p1[0]) if p1[0] != 0 else 0,
              math.copysign(sy, p1[1]) if p1[1] != 0 else 0, d["z"] + zt)
        q0 = (math.copysign(sx, p0[0]) if p0[0] != 0 else 0,
              math.copysign(sy, p0[1]) if p0[1] != 0 else 0, d["z"] + zt)
        m.quad((p0[0], p0[1], d["z"]), (p1[0], p1[1], d["z"]),
               q1, q0,
               [(0, 0), (width / 4, 0), (width / 4, zt / 4), (0, zt / 4)])
        m.quad(q0, q1, (q1[0] * 0.985, q1[1] * 0.985, q1[2]),
               (q0[0] * 0.985, q0[1] * 0.985, q0[2]))
    obj = m.finish("Menkaure granite facing", MAT_GRANITE, coll)
    obj.location = (d["x"], d["y"], 0.0)
    return obj


def build_main_pyramids():
    pyramid_core("Khufu pyramid", KX, KY, KHUFU["z"], KHUFU["base_x"], KHUFU["base_y"],
                 KHUFU["h0"], KHUFU["h"], KHUFU["angle"], MAT_PYRAMID,
                 ch_bottom=1.50, ch_top=0.62, lip=0.055)
    add_entrance(KHUFU, 17.0, coll=COL_MONUMENTS)

    # Khafre: stepped core, smooth Tura casing preserved near the apex
    zc = 126.0
    pyramid_core("Khafre pyramid", FX, FY, KHAFRE["z"], KHAFRE["base_x"], KHAFRE["base_y"],
                 KHAFRE["h0"], zc, KHAFRE["angle"], MAT_PYRAMID,
                 ch_bottom=1.55, ch_top=0.75, lip=0.07)
    casing("Khafre casing cap", FX, FY, KHAFRE["z"], KHAFRE["base_x"], KHAFRE["base_y"],
           KHAFRE["h0"], zc, KHAFRE["h"], KHAFRE["angle"], MAT_CASING,
           subdiv=5, extra=0.30)
    add_entrance(KHAFRE, 11.0, width=1.5, height=3.0, coll=COL_MONUMENTS)

    # Menkaure: smaller, with surviving granite at the base
    pyramid_core("Menkaure pyramid", MX, MY, MENKAURE["z"], MENKAURE["base_x"],
                 MENKAURE["base_y"], MENKAURE["h0"], MENKAURE["h"],
                 MENKAURE["angle"], MAT_PYRAMID, ch_bottom=1.25, ch_top=0.65, lip=0.055)
    granite_facing(MENKAURE, (4.0, 5.2, 8.6, 6.4))
    add_entrance(MENKAURE, 4.0, width=1.2, height=2.2, coll=COL_MONUMENTS)


def build_queens():
    # Khufu's three queens, east of the Great Pyramid
    for i, (yoff, bx, h0, hcur) in enumerate((
            (60, 49.5, 30.25, 27.8),
            (0, 47.0, 30.0, 26.6),
            (-60, 46.5, 29.5, 25.8))):
        cx, cy = KX + 174, KY + yoff
        z = terrain_z(cx, cy)
        pyramid_core(f"Khufu queen G1-{chr(97 + i)}", cx, cy, z, bx, bx, h0, hcur,
                     51.5, MAT_PYRAMID, ch_bottom=0.85, ch_top=0.5, lip=0.04)
    # Menkaure's three queens, south of the pyramid
    for i, (xoff, bx, h0, hcur) in enumerate((
            (10, 44.0, 28.0, 25.5),
            (-52, 31.0, 21.0, 18.5),
            (-110, 31.0, 21.0, 18.0))):
        cx, cy = MX + xoff, MY - 140
        z = terrain_z(cx, cy)
        pyramid_core(f"Menkaure queen G3-{chr(97 + i)}", cx, cy, z, bx, bx, h0, hcur,
                     51.3, MAT_PYRAMID, ch_bottom=0.8, ch_top=0.5, lip=0.04)


# --------------------------------------------------------------------------
# Rock chunks / talus
# --------------------------------------------------------------------------
ICO_V = [(-1, 1.618, 0), (1, 1.618, 0), (-1, -1.618, 0), (1, -1.618, 0),
         (0, -1, 1.618), (0, 1, 1.618), (0, -1, -1.618), (0, 1, -1.618),
         (1.618, 0, -1), (1.618, 0, 1), (-1.618, 0, -1), (-1.618, 0, 1)]
ICO_F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
         (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
         (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]


def add_rock(m, cx, cy, cz, size, seed):
    rnd = random.Random(seed)
    sx = size * rnd.uniform(0.7, 1.5)
    sy = size * rnd.uniform(0.6, 1.3)
    sz = size * rnd.uniform(0.35, 0.8)
    rot = rnd.uniform(0, 2 * pi)
    ca, sa = cos(rot), sin(rot)
    base = len(m.v)
    for (vx, vy, vz) in ICO_V:
        px = vx * sx * rnd.uniform(0.85, 1.12)
        py = vy * sy * rnd.uniform(0.85, 1.12)
        pz = vz * sz * rnd.uniform(0.75, 1.15)
        m.v.append((cx + px * ca - py * sa, cy + px * sa + py * ca, cz + pz + sz * 0.35))
    for f in ICO_F:
        m.f.append(tuple(base + i for i in f))


def build_rocks():
    m = MB()
    # talus around each pyramid base
    for d in (KHUFU, KHAFRE, MENKAURE):
        ax, ay = d["base_x"] / 2, d["base_y"] / 2
        n = 46 if d is not MENKAURE else 24
        for k in range(n):
            side = random.randrange(4)
            t = random.uniform(-0.48, 0.48)
            off = random.uniform(3, 22)
            if side == 0:
                x, y = d["x"] + t * 2 * ax, d["y"] - ay - off
            elif side == 1:
                x, y = d["x"] + ax + off, d["y"] + t * 2 * ay
            elif side == 2:
                x, y = d["x"] + t * 2 * ax, d["y"] + ay + off
            else:
                x, y = d["x"] - ax - off, d["y"] + t * 2 * ay
            add_rock(m, x, y, terrain_z(x, y) - 0.3, random.uniform(0.8, 4.0), random.randrange(1 << 30))
    # scattered boulders on the plateau
    for k in range(90):
        x, y = random.uniform(-1200, 900), random.uniform(-1250, 700)
        if abs(x - 0) < 260 and abs(y) < 260:
            continue
        add_rock(m, x, y, terrain_z(x, y) - 0.25, random.uniform(0.4, 2.6), 9000 + k)
    m.finish("Limestone boulders", MAT_ROCK, COL_ROCKS)


# --------------------------------------------------------------------------
# Mastaba fields
# --------------------------------------------------------------------------
def dist_point_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy), 0, 1)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


CAUSEWAYS = [
    [(-170, -342), (-80, -365), (40, -395), (150, -420), (226, -440)],
    [(172, -10), (260, 35), (360, 85), (470, 130)],
    [(MX + 20, MY - 110), (MX + 55, MY - 70), (-420, -590), (-300, -555), (-200, -520)],
]

EXCLUDE_RECTS = [
    # Sphinx and its enclosure / valley temple
    (220, -530, 440, -350),
    # Khafre valley temple
    (205, -485, 280, -410),
    # Khufu mortuary temple
    (120, -55, 205, 55),
    # Khafre mortuary temple
    (-225, -400, -130, -285),
    # Menkaure mortuary temple
    (-530, -845, -470, -800),
]
EXCLUDE_CIRCLES = [
    (KX, KY, 205), (FX, FY, 195), (MX, MY, 130),
    (KX + 174, KY + 60, 58), (KX + 174, KY, 55), (KX + 174, KY - 60, 54),
    (MX + 10, MY - 140, 55), (MX - 52, MY - 140, 40), (MX - 110, MY - 140, 40),
]


def excluded(x, y, margin=0.0):
    for (x0, y0, x1, y1) in EXCLUDE_RECTS:
        if x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin:
            return True
    for (cx, cy, r) in EXCLUDE_CIRCLES:
        if math.hypot(x - cx, y - cy) < r + margin:
            return True
    for line in CAUSEWAYS:
        for a, b in zip(line, line[1:]):
            if dist_point_segment(x, y, a[0], a[1], b[0], b[1]) < 18 + margin:
                return True
    return False


def build_mastabas():
    mud = MB(tile=8.0)
    stone = MB(tile=10.0)
    fields = [
        (-640, -175, -170, 440, 33, 24, 0.68),
        (135, 485, -165, 330, 31, 22, 0.50),
        (-250, -65, -260, -75, 27, 22, 0.30),
        (-780, -410, -980, -870, 29, 20, 0.50),
        (470, 850, -260, 260, 44, 34, 0.25),
    ]
    count = 0
    for (x0, x1, y0, y1, dx, dy, density) in fields:
        y = y0
        row = 0
        while y < y1:
            x = x0 + (dx * 0.5 if row % 2 else 0)
            while x < x1:
                count += 1
                if random.random() > density:
                    x += dx
                    continue
                cx = x + random.uniform(-4, 4)
                cy = y + random.uniform(-3, 3)
                if excluded(cx, cy, 4):
                    x += dx
                    continue
                w = random.uniform(7, 19)
                d = random.uniform(5, 12)
                h = random.uniform(1.4, 3.6)
                z = terrain_z(cx, cy) - 0.35
                rot = random.uniform(-0.035, 0.035)
                m = mud if random.random() < 0.90 else stone
                batter = random.uniform(0.10, 0.20)
                m.box(cx, cy, z + h / 2, w, d, h, rot=rot,
                      top_scale=(max(0.45, 1 - 2 * batter * h / w),
                                 max(0.45, 1 - 2 * batter * h / d)))
                # small offering chapel on the east face
                if random.random() < 0.35:
                    m.box(cx + w / 2 + 1.3, cy, z + 1.2, 2.8, 3.6, 2.4, rot=rot,
                          top_scale=(0.9, 0.9))
                x += dx
            y += dy
            row += 1
            if count > 500:
                break
        if count > 500:
            break
    mud.finish("West and south mastabas", MAT_MUDBRICK, COL_MASTABAS)
    stone.finish("Limestone mastabas", MAT_LIMESTONE, COL_MASTABAS)


# --------------------------------------------------------------------------
# Temples and causeways
# --------------------------------------------------------------------------
def temple(name, cx, cy, w, d, z, wall_h=5.0, wall_t=2.0, door_side="east",
           column_rows=3, column_cols=4, column_h=4.5, mat=MAT_LIMESTONE):
    col = COL_TEMPLES
    # platform
    p = MB(tile=8)
    p.box(cx, cy, z + 0.6, w + 6, d + 6, 1.2, top_scale=(1, 1))
    p.finish(name + " platform", MAT_ROCK, col)
    # paved floor
    f = MB(tile=8)
    f.box(cx, cy, z + 1.25, w, d, 0.25)
    f.finish(name + " pavement", MAT_BASALT, col)
    # walls with one doorway
    wb = MB(tile=8)
    gap = 4.0
    for side in ("north", "south", "east", "west"):
        if side in ("north", "south"):
            length = w
            if side == door_side:
                seg = (length - gap) / 2
                wb.box(cx - (gap / 2 + seg / 2), cy + (-d / 2 if side == "south" else d / 2), z + 1.4 + wall_h / 2,
                       seg, wall_t, wall_h)
                wb.box(cx + (gap / 2 + seg / 2), cy + (-d / 2 if side == "south" else d / 2), z + 1.4 + wall_h / 2,
                       seg, wall_t, wall_h)
            else:
                wb.box(cx, cy + (-d / 2 if side == "south" else d / 2), z + 1.4 + wall_h / 2,
                       length, wall_t, wall_h)
        else:
            length = d
            if side == door_side:
                seg = (length - gap) / 2
                wb.box(cx + (-w / 2 if side == "west" else w / 2), cy - (gap / 2 + seg / 2), z + 1.4 + wall_h / 2,
                       wall_t, seg, wall_h)
                wb.box(cx + (-w / 2 if side == "west" else w / 2), cy + (gap / 2 + seg / 2), z + 1.4 + wall_h / 2,
                       wall_t, seg, wall_h)
            else:
                wb.box(cx + (-w / 2 if side == "west" else w / 2), cy, z + 1.4 + wall_h / 2,
                       wall_t, length, wall_h)
    wb.finish(name + " walls", mat, col)
    # columns
    cb = MB(tile=6)
    xs = [lerp(-w * 0.32, w * 0.32, i / max(1, column_cols - 1)) for i in range(column_cols)]
    ys = [lerp(-d * 0.30, d * 0.30, i / max(1, column_rows - 1)) for i in range(column_rows)]
    for x in xs:
        for y in ys:
            h = column_h * random.uniform(0.35, 1.0)
            cb.cylinder(cx + x, cy + y, z + 1.4, z + 1.4 + h, random.uniform(0.8, 1.35), segments=10)
    cb.finish(name + " columns", MAT_GRANITE if random.random() < 0.5 else MAT_LIMESTONE, col)


def causeway(name, points, width=5.0):
    m = MB(tile=8)
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(length / 11))
        for k in range(n):
            if random.random() < 0.18:
                continue
            t0, t1 = k / n, (k + 1) / n
            x0, y0 = lerp(a[0], b[0], t0), lerp(a[1], b[1], t0)
            x1, y1 = lerp(a[0], b[0], t1), lerp(a[1], b[1], t1)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ang = math.atan2(y1 - y0, x1 - x0)
            h = random.uniform(2.0, 4.2)
            z = terrain_z(cx, cy) + h / 2 - 0.2
            m.box(cx, cy, z, length * 1.02, width, h, rot=ang, top_scale=(1.0, 0.9))
    m.finish(name, MAT_LIMESTONE, COL_TEMPLES)


def build_temples():
    temple("Khufu mortuary temple", 158, 0, 58, 42, terrain_z(158, 0), 4.2, 2.2,
           "east", 3, 5, 4.2)
    temple("Khafre mortuary temple", -172, -342, 66, 52, terrain_z(-172, -342), 6.2, 2.6,
           "east", 4, 5, 6.0)
    temple("Khafre valley temple", 242, -444, 48, 46, terrain_z(242, -444), 8.0, 3.0,
           "east", 3, 4, 7.0)
    temple("Menkaure mortuary temple", -500, -820, 42, 32, terrain_z(-500, -820), 4.0, 2.0,
           "south", 2, 3, 3.8)
    causeway("Khafre causeway", CAUSEWAYS[0], 5.5)
    causeway("Khufu causeway", CAUSEWAYS[1], 5.0)
    causeway("Menkaure causeway", CAUSEWAYS[2], 4.5)
    # Khufu boat pits, east of the pyramid
    b = MB(tile=8)
    for i in range(2):
        b.box(128, KY + 38 + i * 12, terrain_z(128, KY + 38 + i * 12) + 0.3, 30, 8, 0.8)
    b.finish("Khufu boat pits", MAT_LIMESTONE, COL_TEMPLES)


# --------------------------------------------------------------------------
# Sphinx
# --------------------------------------------------------------------------
def loft(m, rings, close_start=False, close_end=False, cap_start=True, cap_end=False):
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(len(r0)):
            k = (j + 1) % len(r0)
            m.quad(r0[j], r0[k], r1[k], r1[j])
    if close_start and len(rings[0]) > 2:
        c = tuple(sum(p[d] for p in rings[0]) / len(rings[0]) for d in range(3))
        for j in range(len(rings[0])):
            k = (j + 1) % len(rings[0])
            m.tri(c, rings[0][k], rings[0][j])


def loft_uv(m, rings, tile=16.0):
    """Loft rings along X with continuous UVs (no per-quad repetition)."""
    n = len(rings[0])
    cum = []
    for ring in rings:
        c = [0.0]
        for j in range(n):
            a, b = ring[j], ring[(j + 1) % n]
            c.append(c[-1] + math.dist(a, b))
        cum.append(c)
    for i in range(len(rings) - 1):
        x0, x1 = rings[i][0][0], rings[i + 1][0][0]
        v0, v1 = x0 / tile, x1 / tile
        for j in range(n):
            k = (j + 1) % n
            m.quad(rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j],
                   [(cum[i][j] / tile, v0), (cum[i][j + 1] / tile, v0),
                    (cum[i + 1][j + 1] / tile, v1), (cum[i + 1][j] / tile, v1)])


def sphinx_mesh():
    N = 28

    def ring(x, wy, h, base=0.0):
        pts = []
        for j in range(N):
            a = 2 * pi * j / N
            yn = 0.5 + 0.5 * sin(a)
            y = wy * cos(a) * (0.82 + 0.18 * yn)
            z = base + h * (yn ** 0.55)
            pts.append((SX + x, SY + y, SPHINX["z"] + z))
        return pts

    body = MB(tile=16)
    profile = [
        (-31, 2.2, 5.5),
        (-28, 5.0, 8.5),
        (-23, 7.6, 10.8),
        (-16, 8.8, 11.6),
        (-8, 9.2, 12.0),
        (0, 9.4, 12.2),
        (8, 9.2, 12.6),
        (15, 8.6, 12.9),
        (20, 7.0, 12.2),
        (23, 5.2, 11.2),
    ]
    rings = [ring(x, wy, h) for (x, wy, h) in profile]
    loft(body, rings, close_start=True)
    # rear cap
    c = (SX - 32, SY, SPHINX["z"] + 5.8)
    r0 = rings[0]
    for j in range(N):
        k = (j + 1) % N
        body.tri(c, r0[k], r0[j])
    body_obj = body.finish("Sphinx body", MAT_SPHINX, COL_SPHINX, smooth=True)

    # haunches and chest (overlapping masses, union by intersection)
    add = MB(tile=16)
    for sy in (-1, 1):
        # ellipsoid-ish haunch via lofted circular rings would be cleaner;
        # an ico sphere is enough at this scale, heavily displaced later.
        base = len(add.v)
        rx, ry, rz = 10.0, 4.4, 6.2
        for (vx, vy, vz) in ICO_V:
            add.v.append((SX - 19 + vx * rx, SY + sy * 5.6 + vy * ry,
                          SPHINX["z"] + 5.0 + vz * rz))
        for f in ICO_F:
            add.f.append(tuple(base + i for i in f))
    # chest
    base = len(add.v)
    for (vx, vy, vz) in ICO_V:
        add.v.append((SX + 12 + vx * 7.8, SY + vy * 8.4, SPHINX["z"] + 7.0 + vz * 6.4))
    for f in ICO_F:
        add.f.append(tuple(base + i for i in f))
    add.finish("Sphinx chest and haunches", MAT_SPHINX, COL_SPHINX, smooth=True)

    # forelegs: long rounded beams reaching forward, paws on the ground
    legs = MB(tile=16)
    for sy in (-1, 1):
        rings = []
        for (x, w, h) in ((7, 2.6, 4.6), (14, 2.8, 4.2), (21, 2.8, 3.4),
                          (27, 2.9, 2.6), (31, 3.1, 1.9)):
            pts = []
            for j in range(16):
                a = 2 * pi * j / 16
                yn = 0.5 + 0.5 * sin(a)
                pts.append((SX + x, SY + sy * 5.6 + w * cos(a), SPHINX["z"] + 0.2 + h * (yn ** 0.5)))
            rings.append(pts)
        loft(legs, rings)
        # paw
        base = len(legs.v)
        for (vx, vy, vz) in ICO_V:
            legs.v.append((SX + 32 + vx * 3.6, SY + sy * 5.8 + vy * 2.4,
                           SPHINX["z"] + 0.8 + vz * 1.0))
        for f in ICO_F:
            legs.f.append(tuple(base + i for i in f))
        for toe in (-1, 0, 1):
            base = len(legs.v)
            for (vx, vy, vz) in ICO_V:
                legs.v.append((SX + 35.2 + vx * 1.3, SY + sy * 5.8 + toe * 1.35 + vy * 0.6,
                               SPHINX["z"] + 0.55 + vz * 0.55))
            for f in ICO_F:
                legs.f.append(tuple(base + i for i in f))
    legs.finish("Sphinx forelegs", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # neck
    neck = MB(tile=16)
    rings = []
    for (x, z, rx, ry) in ((21.0, 10.0, 5.0, 4.4), (23.0, 12.5, 4.5, 4.0),
                           (25.0, 15.0, 4.0, 3.6), (26.5, 17.0, 3.6, 3.2)):
        pts = []
        for j in range(20):
            a = 2 * pi * j / 20
            pts.append((SX + x, SY + ry * cos(a), SPHINX["z"] + z + rx * 0.65 * sin(a)))
        rings.append(pts)
    loft(neck, rings)
    neck.finish("Sphinx neck", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # head (human) - deliberately slightly small, as on the monument
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=1.0,
                                        location=(SX + 29.5, SY, SPHINX["z"] + 17.2))
    head = bpy.context.object
    head.name = "Sphinx head"
    head.scale = (3.5, 3.3, 4.4)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    head.data.materials.append(MAT_SPHINX)
    for c in list(head.users_collection):
        c.objects.unlink(head)
    COL_SPHINX.objects.link(head)
    bpy.ops.object.shade_smooth()

    # face details (subtle: the face is heavily weathered)
    details = MB(tile=4)
    # brow ridge
    for sy in (-1, 1):
        details.box(SX + 32.2, SY + sy * 1.75, SPHINX["z"] + 18.5, 0.9, 2.1, 0.45, rot=0.10 * sy)
        # eye socket (dark recess is suggested by a shallow dark inlay)
        # mouth
    details.box(SX + 32.5, SY, SPHINX["z"] + 15.3, 0.8, 2.6, 0.28)
    # damaged nose stump
    details.box(SX + 32.7, SY, SPHINX["z"] + 16.6, 1.0, 1.1, 1.4, top_scale=(0.7, 0.7))
    # chin
    details.box(SX + 31.8, SY, SPHINX["z"] + 14.0, 2.2, 2.4, 1.2, top_scale=(1.1, 0.9))
    details_obj = details.finish("Sphinx face", MAT_SPHINX, COL_SPHINX, smooth=True)

    # nemes hood: a thick, flared shell wrapping the back and sides of the head
    nem = MB(tile=8)
    zs = [12.0, 13.4, 15.4, 17.6, 19.6, 21.2, 22.2]
    a_vals = [9.2, 8.8, 7.4, 6.2, 5.2, 4.4, 3.5]
    b_vals = [9.8, 9.4, 8.1, 6.9, 5.9, 5.0, 4.0]
    cx = 22.0
    M = 22
    outer, inner = [], []
    for z, a, b in zip(zs, a_vals, b_vals):
        ro, ri = [], []
        for j in range(M + 1):
            phi = radians(72 + (360 - 144) * j / M)
            x = cx + b * cos(phi)
            y = a * sin(phi)
            zz = SPHINX["z"] + z
            ro.append((SX + x, SY + y, zz))
            x2 = cx + (b - 0.75) * cos(phi)
            y2 = (a - 0.75) * sin(phi)
            ri.append((SX + x2, SY + y2, zz))
        outer.append(ro)
        inner.append(ri)

    def surface(rows, flip=False):
        for i in range(len(rows) - 1):
            for j in range(M):
                p0, p1 = rows[i][j], rows[i][j + 1]
                q0, q1 = rows[i + 1][j], rows[i + 1][j + 1]
                u0 = j / M * 2.0
                u1 = (j + 1) / M * 2.0
                v0, v1 = (zs[i] - 12) / 8, (zs[i + 1] - 12) / 8
                if flip:
                    nem.quad(p0, q0, q1, p1, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
                else:
                    nem.quad(p0, p1, q1, q0, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    surface(outer, False)
    surface(inner, True)
    # rims
    for j in range(M):
        nem.quad(outer[0][j], inner[0][j], inner[0][j + 1], outer[0][j + 1])
        nem.quad(outer[-1][j], outer[-1][j + 1], inner[-1][j + 1], inner[-1][j])
    for i in range(len(zs) - 1):
        nem.quad(outer[i][0], outer[i + 1][0], inner[i + 1][0], inner[i][0])
        nem.quad(outer[i][-1], inner[i][-1], inner[i + 1][-1], outer[i + 1][-1])
    nem.finish("Sphinx nemes", MAT_NEMES, COL_SPHINX, smooth=True)

    # lappets falling on the chest
    lap = MB(tile=8)
    for sy in (-1, 1):
        lap.box(SX + 29.0, SY + sy * 5.7, SPHINX["z"] + 8.2, 2.4, 2.6, 9.4,
                top_scale=(0.78, 0.8))
    lap.finish("Sphinx nemes lappets", MAT_NEMES, COL_SPHINX, smooth=True)

    # uraeus and false-beard stub
    ur = MB(tile=2)
    ur.cylinder(SX + 33.2, SY, SPHINX["z"] + 20.6, SPHINX["z"] + 22.0, 0.22, 0.12, segments=8)
    ur.finish("Sphinx uraeus", MAT_DARK, COL_SPHINX)
    beard = MB(tile=4)
    beard.box(SX + 31.8, SY, SPHINX["z"] + 11.4, 1.3, 1.5, 3.2, top_scale=(0.9, 0.9))
    beard.finish("Sphinx beard stub", MAT_NEMES, COL_SPHINX)

    # rock outcrop on which the body was carved
    rock = MB(tile=18)
    rings = []
    for (x, w, h) in ((-46, 18, 3.5), (-30, 30, 5.0), (0, 34, 5.8), (30, 30, 5.0), (48, 18, 3.0)):
        pts = []
        for j in range(20):
            a = 2 * pi * j / 20
            pts.append((SX + x, SY + w * cos(a), SPHINX["z"] - 0.4 + h * (0.5 + 0.5 * sin(a))))
        rings.append(pts)
    loft(rock, rings)
    rock.finish("Sphinx bedrock", MAT_ROCK, COL_SPHINX, smooth=False)

    # gentle erosion displacement on all Sphinx pieces
    tex = bpy.data.textures.get("Sphinx erosion") or bpy.data.textures.new("Sphinx erosion", "CLOUDS")
    tex.noise_scale = 2.8
    tex.noise_depth = 4
    for obj in COL_SPHINX.objects:
        if obj.type != "MESH":
            continue
        mod = obj.modifiers.new("Erosion", "DISPLACE")
        mod.texture = tex
        mod.strength = 0.38 if obj.name not in ("Sphinx head",) else 0.18
        mod.mid_level = 0.5
        mod.texture_coords = "GLOBAL"


def sphinx_enclosure():
    # outer rim / quarried wall around the Sphinx
    outer = [(260, -505), (410, -505), (410, -365), (260, -365)]
    inner = [(278, -490), (394, -490), (394, -380), (278, -380)]
    floor = SPHINX["z"]
    rim = -3.8
    m = MB(tile=18)
    for i in range(4):
        a, b = outer[i], outer[(i + 1) % 4]
        c, d = inner[(i + 1) % 4], inner[i]
        m.quad((a[0], a[1], rim), (b[0], b[1], rim), (c[0], c[1], floor + 0.6), (d[0], d[1], floor + 0.6))
        # top rim connecting to the desert
        m.quad((a[0], a[1], rim + 0.4), (b[0], b[1], rim + 0.4), (b[0], b[1], rim), (a[0], a[1], rim))
    # floor
    m.quad((inner[0][0], inner[0][1], floor), (inner[1][0], inner[1][1], floor),
           (inner[2][0], inner[2][1], floor), (inner[3][0], inner[3][1], floor))
    m.finish("Sphinx enclosure", MAT_ROCK, COL_SPHINX)
    # eastern approach ramp
    r = MB(tile=18)
    r.quad((394, -430, floor), (440, -435, rim), (440, -405, rim), (394, -410, floor))
    r.quad((394, -440, floor), (394, -410, floor), (440, -405, rim), (440, -450, rim))
    r.finish("Sphinx approach", MAT_ROCK, COL_SPHINX)


def _ico(mb, cx, cy, cz, rx, ry, rz):
    s = 0.62
    base = len(mb.v)
    for (vx, vy, vz) in ICO_V:
        mb.v.append((cx + vx * rx * s, cy + vy * ry * s, cz + vz * rz * s))
    for f in ICO_F:
        mb.f.append(tuple(base + i for i in f))


def _ellipsoid(mb, cx, cy, cz, rx, ry, rz, seg=20, rings=10):
    """Smooth UV ellipsoid, used for face masses and recessed features."""
    ring_verts = []
    for i in range(1, rings):
        phi = -pi / 2 + pi * i / rings
        z = cz + rz * sin(phi)
        rr = cos(phi)
        ring = []
        for j in range(seg):
            th = 2 * pi * j / seg
            ring.append((cx + rx * rr * cos(th), cy + ry * rr * sin(th), z))
        ring_verts.append(ring)
    for i in range(len(ring_verts) - 1):
        r0, r1 = ring_verts[i], ring_verts[i + 1]
        for j in range(seg):
            k = (j + 1) % seg
            mb.quad(r0[j], r0[k], r1[k], r1[j])
    bot = (cx, cy, cz - rz)
    top = (cx, cy, cz + rz)
    for j in range(seg):
        k = (j + 1) % seg
        mb.tri(bot, ring_verts[0][k], ring_verts[0][j])
        mb.tri(top, ring_verts[-1][j], ring_verts[-1][k])


def sphinx_mesh_v2():
    N = 32

    def body_ring(x, wy, h):
        pts = []
        for j in range(N):
            a = 2 * pi * j / N
            yn = 0.5 + 0.5 * sin(a)
            y = wy * cos(a) * (0.87 + 0.13 * yn)
            z = 0.12 + h * (yn ** 0.52)
            pts.append((SX + x, SY + y, SPHINX["z"] + z))
        return pts

    body = MB(tile=16)
    profile = [
        (-37, 1.8, 4.5), (-34, 3.8, 7.2), (-30, 6.0, 9.6),
        (-25, 8.0, 11.2), (-19, 8.8, 11.8), (-12, 8.4, 11.5),
        (-4, 7.9, 11.2), (4, 8.1, 11.5), (10, 8.6, 12.0),
        (16, 8.9, 12.4), (21, 7.4, 12.1), (24, 4.6, 11.2),
    ]
    rings = [body_ring(x, wy, h) for (x, wy, h) in profile]
    loft_uv(body, rings)
    c0 = (SX - 38, SY, SPHINX["z"] + 4.0)
    for j in range(N):
        k = (j + 1) % N
        body.tri(c0, rings[0][k], rings[0][j])
    body.finish("Sphinx body", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # massive forelegs reaching forward, with paws and toes
    legs = MB(tile=16)
    for sy in (-1, 1):
        legrings = []
        for (x, w, h) in ((13, 2.7, 4.9), (19, 3.0, 4.5), (25, 3.2, 3.9),
                          (31, 3.4, 3.1), (36, 3.5, 2.3), (39, 3.6, 1.5)):
            pts = []
            for j in range(18):
                a = 2 * pi * j / 18
                yn = 0.5 + 0.5 * sin(a)
                y = sy * 5.5 + w * cos(a)
                z = 0.35 + h * (yn ** 0.45)
                pts.append((SX + x, SY + y, SPHINX["z"] + z))
            legrings.append(pts)
        loft_uv(legs, legrings)
        _ico(legs, SX + 40.2, SY + sy * 5.7, SPHINX["z"] + 1.0, 4.6, 2.7, 1.1)
        for toe in (-1, 0, 1):
            _ico(legs, SX + 43.0, SY + sy * 5.7 + toe * 1.45, SPHINX["z"] + 0.55, 1.3, 0.65, 0.55)
    legs.finish("Sphinx forelegs", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # neck
    neck = MB(tile=16)
    neckrings = []
    for (x, z, ry, rz) in ((21.0, 9.8, 5.2, 4.6), (23.5, 12.2, 4.6, 4.2),
                           (26.0, 14.4, 4.0, 3.8), (28.0, 16.0, 3.6, 3.3)):
        pts = []
        for j in range(24):
            a = 2 * pi * j / 24
            pts.append((SX + x, SY + ry * cos(a), SPHINX["z"] + z + rz * sin(a)))
        neckrings.append(pts)
    loft_uv(neck, neckrings)
    neck.finish("Sphinx neck", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # head: a slightly tapered vertical loft, not a sphere
    head = MB(tile=12)
    headrings = []
    for (z, a, b) in ((11.2, 3.1, 2.8), (12.8, 3.5, 3.1), (14.6, 3.6, 3.3),
                      (16.4, 3.4, 3.35), (18.2, 3.0, 3.2), (19.6, 2.5, 2.9),
                      (20.5, 1.9, 2.4)):
        pts = []
        for j in range(28):
            phi = 2 * pi * j / 28
            pts.append((SX + 31.2 + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
        headrings.append(pts)
    loft(head, headrings)
    for j in range(28):
        k = (j + 1) % 28
        head.tri((SX + 31.2, SY, SPHINX["z"] + 11.2), headrings[0][k], headrings[0][j])
        head.tri((SX + 31.2, SY, SPHINX["z"] + 20.5), headrings[-1][j], headrings[-1][k])
    head.finish("Sphinx head", MAT_SPHINX, COL_SPHINX, smooth=True)

    # face and its damaged features
    face = MB(tile=8)
    _ico(face, SX + 34.0, SY, SPHINX["z"] + 15.5, 2.3, 2.8, 3.4)       # face mass
    _ico(face, SX + 33.4, SY, SPHINX["z"] + 13.1, 1.6, 2.3, 1.4)       # jaw
    _ico(face, SX + 35.2, SY, SPHINX["z"] + 15.1, 0.7, 0.95, 1.45)     # nose stump
    for sy in (-1, 1):
        _ico(face, SX + 34.0, SY + sy * 2.15, SPHINX["z"] + 15.4, 0.9, 1.1, 1.6)   # cheek
        _ico(face, SX + 31.0, SY + sy * 3.55, SPHINX["z"] + 16.4, 0.9, 0.5, 1.3)   # ear
        _ico(face, SX + 35.1, SY + sy * 1.45, SPHINX["z"] + 17.35, 0.22, 0.95, 0.32)  # eyelid
    face.finish("Sphinx face", MAT_SPHINX, COL_SPHINX, smooth=True)

    # dark inlays: eyes, nostril wound, mouth line
    dark = MB(tile=2)
    for sy in (-1, 1):
        _ico(dark, SX + 35.45, SY + sy * 1.45, SPHINX["z"] + 16.95, 0.12, 0.68, 0.27)
    dark.box(SX + 35.65, SY, SPHINX["z"] + 15.05, 0.16, 0.85, 1.15)
    dark.box(SX + 35.5, SY, SPHINX["z"] + 13.95, 0.16, 2.0, 0.14)
    dark.finish("Sphinx eye and mouth inlays", MAT_DARK, COL_SPHINX, smooth=True)

    # nemes: a solid, flared headdress wrapped close around the face
    nem = MB(tile=8)
    zs = [10.5, 12.5, 14.5, 16.5, 18.5, 20.0, 21.0]
    a_vals = [9.2, 8.4, 7.2, 6.2, 5.3, 4.3, 3.3]
    b_vals = [10.0, 9.0, 8.0, 7.1, 6.2, 5.2, 4.2]
    cx = 27.0
    M = 28
    outer, inner = [], []
    for z, a, b in zip(zs, a_vals, b_vals):
        ro, ri = [], []
        for j in range(M + 1):
            phi = radians(45 + 270 * j / M)
            ro.append((SX + cx + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
            ri.append((SX + cx + (b - 0.65) * cos(phi), SY + (a - 0.65) * sin(phi), SPHINX["z"] + z))
        outer.append(ro)
        inner.append(ri)

    def surface(rows, flip=False):
        for i in range(len(rows) - 1):
            for j in range(M):
                p0, p1 = rows[i][j], rows[i][j + 1]
                q0, q1 = rows[i + 1][j], rows[i + 1][j + 1]
                u0, u1 = j / M * 2.0, (j + 1) / M * 2.0
                v0, v1 = (zs[i] - 10.5) / 8, (zs[i + 1] - 10.5) / 8
                if flip:
                    nem.quad(p0, q0, q1, p1, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
                else:
                    nem.quad(p0, p1, q1, q0, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    surface(outer, False)
    surface(inner, True)
    for j in range(M):
        nem.quad(outer[0][j], inner[0][j], inner[0][j + 1], outer[0][j + 1])
        nem.quad(outer[-1][j], outer[-1][j + 1], inner[-1][j + 1], inner[-1][j])
    for i in range(len(zs) - 1):
        nem.quad(outer[i][0], outer[i + 1][0], inner[i + 1][0], inner[i][0])
        nem.quad(outer[i][-1], inner[i][-1], inner[i + 1][-1], outer[i + 1][-1])
    nem.finish("Sphinx nemes", MAT_NEMES, COL_SPHINX, smooth=True)

    # lappets and uraeus
    lap = MB(tile=8)
    for sy in (-1, 1):
        lap.box(SX + 34.0, SY + sy * 5.9, SPHINX["z"] + 7.0, 2.5, 2.5, 8.4,
                top_scale=(0.78, 0.8))
    lap.finish("Sphinx nemes lappets", MAT_NEMES, COL_SPHINX, smooth=True)
    ur = MB(tile=2)
    ur.cylinder(SX + 35.4, SY, SPHINX["z"] + 20.4, SPHINX["z"] + 21.7, 0.24, 0.10, segments=8)
    ur.finish("Sphinx uraeus", MAT_DARK, COL_SPHINX)

    # low bedrock mass under the body
    rock = MB(tile=18)
    _ico(rock, SX - 2, SY, SPHINX["z"] - 1.4, 48, 24, 4.5)
    _ico(rock, SX + 32, SY, SPHINX["z"] - 1.0, 18, 18, 3.5)
    rock.finish("Sphinx bedrock", MAT_ROCK, COL_SPHINX, smooth=True)

    tex = bpy.data.textures.get("Sphinx erosion") or bpy.data.textures.new("Sphinx erosion", "CLOUDS")
    tex.noise_scale = 2.4
    tex.noise_depth = 4
    for obj in COL_SPHINX.objects:
        if obj.type != "MESH":
            continue
        mod = obj.modifiers.new("Erosion", "DISPLACE")
        mod.texture = tex
        if any(k in obj.name.lower() for k in ("head", "face", "nemes", "eye", "uraeus")):
            mod.strength = 0.06
        elif "bedrock" in obj.name.lower():
            mod.strength = 0.30
        else:
            mod.strength = 0.17
        mod.mid_level = 0.5
        mod.texture_coords = "GLOBAL"


def sphinx_enclosure_v2():
    outer = [(255, -515), (415, -515), (415, -355), (255, -355)]
    inner = [(276, -496), (396, -496), (396, -374), (276, -374)]
    floor = SPHINX["z"] - 0.08
    rims = [terrain_z(x, y) + 0.05 for (x, y) in outer]
    rim = sum(rims) / len(rims)
    m = MB(tile=18)
    for i in range(4):
        a, b = outer[i], outer[(i + 1) % 4]
        c, d = inner[(i + 1) % 4], inner[i]
        m.quad((a[0], a[1], rim), (b[0], b[1], rim), (c[0], c[1], floor), (d[0], d[1], floor))
        m.quad((a[0], a[1], rim + 0.7), (b[0], b[1], rim + 0.7), (b[0], b[1], rim), (a[0], a[1], rim))
    m.quad((inner[0][0], inner[0][1], floor), (inner[1][0], inner[1][1], floor),
           (inner[2][0], inner[2][1], floor), (inner[3][0], inner[3][1], floor))
    m.finish("Sphinx enclosure", MAT_ENCLOSURE, COL_SPHINX)
    r = MB(tile=18)
    r.quad((396, -450, floor), (452, -452, rim), (452, -405, rim), (396, -405, floor))
    r.quad((396, -450, floor), (396, -405, floor), (452, -405, rim), (452, -452, rim))
    r.finish("Sphinx approach", MAT_ENCLOSURE, COL_SPHINX)


def sphinx_mesh_v3():
    N = 30

    def body_ring(x, wy, h):
        pts = []
        for j in range(N):
            a = 2 * pi * j / N
            yn = 0.5 + 0.5 * sin(a)
            y = wy * cos(a) * (0.88 + 0.12 * yn)
            z = 0.12 + h * (yn ** 0.55)
            pts.append((SX + x, SY + y, SPHINX["z"] + z))
        return pts

    body = MB(tile=16)
    profile = [
        (-33.5, 1.2, 4.2), (-32, 2.6, 6.8), (-30, 4.4, 9.2), (-27, 6.4, 10.8),
        (-22, 8.7, 11.8), (-16, 8.9, 11.5), (-9, 8.2, 10.9), (-2, 7.7, 10.6),
        (5, 7.9, 11.0), (11, 8.6, 11.8), (16, 9.0, 12.5),
        (20, 8.0, 12.7), (23, 6.0, 12.0), (25, 4.2, 11.0),
    ]
    rings = [body_ring(x, wy, h) for (x, wy, h) in profile]
    loft_uv(body, rings)
    c0 = (SX - 34.2, SY, SPHINX["z"] + 3.8)
    for j in range(N):
        k = (j + 1) % N
        body.tri(c0, rings[0][k], rings[0][j])
    body.finish("Sphinx body", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # forelegs stretched forward, clearly in front of the chest
    legs = MB(tile=16)
    for sy in (-1, 1):
        legrings = []
        for (x, w, h) in ((16, 3.0, 4.8), (22, 3.2, 4.4), (28, 3.4, 3.8),
                          (34, 3.5, 2.9), (39, 3.6, 2.0), (41, 3.7, 1.4)):
            pts = []
            for j in range(18):
                a = 2 * pi * j / 18
                yn = 0.5 + 0.5 * sin(a)
                y = sy * 8.0 + w * cos(a)
                z = 0.3 + h * (yn ** 0.45)
                pts.append((SX + x, SY + y, SPHINX["z"] + z))
            legrings.append(pts)
        loft_uv(legs, legrings)
        _ico(legs, SX + 41.8, SY + sy * 8.1, SPHINX["z"] + 1.0, 4.4, 2.8, 1.2)
        for toe in (-1, 0, 1):
            _ico(legs, SX + 44.2, SY + sy * 8.1 + toe * 1.5, SPHINX["z"] + 0.55, 1.3, 0.7, 0.55)
    legs.finish("Sphinx forelegs", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # raised chest and rounded haunches
    masses = MB(tile=16)
    _ico(masses, SX + 16, SY, SPHINX["z"] + 6.6, 6.2, 8.4, 6.0)
    for sy in (-1, 1):
        _ico(masses, SX - 22, SY + sy * 6.2, SPHINX["z"] + 5.8, 8.0, 3.4, 4.8)
    masses.finish("Sphinx chest and haunches", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # neck
    neck = MB(tile=16)
    neckrings = []
    for (x, z, ry, rz) in ((22.0, 9.8, 5.0, 4.4), (24.0, 12.0, 4.4, 4.0),
                           (26.0, 14.0, 3.9, 3.6), (27.5, 15.2, 3.5, 3.2)):
        pts = []
        for j in range(24):
            a = 2 * pi * j / 24
            pts.append((SX + x, SY + ry * cos(a), SPHINX["z"] + z + rz * sin(a)))
        neckrings.append(pts)
    loft_uv(neck, neckrings)
    neck.finish("Sphinx neck", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # head, only slightly tapered and deliberately frontal
    head = MB(tile=12)
    headrings = []
    for (z, a, b) in ((11.2, 3.1, 2.8), (12.8, 3.5, 3.1), (14.6, 3.6, 3.3),
                      (16.4, 3.4, 3.35), (18.2, 3.0, 3.2), (19.6, 2.5, 2.9),
                      (20.5, 1.9, 2.4)):
        pts = []
        for j in range(28):
            phi = 2 * pi * j / 28
            pts.append((SX + 31.0 + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
        headrings.append(pts)
    loft(head, headrings)
    for j in range(28):
        k = (j + 1) % 28
        head.tri((SX + 31.0, SY, SPHINX["z"] + 11.2), headrings[0][k], headrings[0][j])
        head.tri((SX + 31.0, SY, SPHINX["z"] + 20.5), headrings[-1][j], headrings[-1][k])
    head.finish("Sphinx head", MAT_SPHINX, COL_SPHINX, smooth=True)

    # flat frontal face, damaged nose, cheeks and chin
    face = MB(tile=8)
    _ico(face, SX + 34.1, SY, SPHINX["z"] + 15.6, 1.0, 2.7, 3.4)
    _ico(face, SX + 33.8, SY, SPHINX["z"] + 13.0, 1.1, 2.1, 1.3)
    for sy in (-1, 1):
        _ico(face, SX + 34.2, SY + sy * 2.0, SPHINX["z"] + 15.2, 0.55, 0.9, 1.4)
        _ico(face, SX + 31.0, SY + sy * 3.55, SPHINX["z"] + 16.3, 0.9, 0.5, 1.3)
        _ico(face, SX + 34.8, SY + sy * 1.45, SPHINX["z"] + 17.35, 0.28, 1.0, 0.30)
    face.finish("Sphinx face", MAT_SPHINX, COL_SPHINX, smooth=True)

    dark = MB(tile=2)
    for sy in (-1, 1):
        _ico(dark, SX + 34.82, SY + sy * 1.45, SPHINX["z"] + 16.95, 0.10, 0.62, 0.25)
    dark.box(SX + 34.82, SY, SPHINX["z"] + 15.05, 0.14, 0.75, 1.05)
    dark.box(SX + 34.82, SY, SPHINX["z"] + 13.95, 0.14, 2.0, 0.13)
    dark.finish("Sphinx eye and mouth inlays", MAT_DARK, COL_SPHINX, smooth=True)

    # nemes: the opening narrows toward the face so that it frames the cheeks
    nem = MB(tile=8)
    zs = [10.5, 12.5, 14.5, 16.5, 18.5, 20.0, 21.0]
    a_vals = [9.2, 8.4, 7.2, 6.2, 5.3, 4.3, 3.3]
    b_vals = [10.0, 9.0, 8.0, 7.1, 6.2, 5.2, 4.2]
    phi_starts = [48, 45, 40, 34, 31, 30, 30]
    cx = 27.0
    M = 28
    outer, inner = [], []
    for z, a, b, ps in zip(zs, a_vals, b_vals, phi_starts):
        ro, ri = [], []
        p0 = radians(ps)
        p1 = 2 * pi - p0
        for j in range(M + 1):
            phi = p0 + (p1 - p0) * j / M
            ro.append((SX + cx + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
            ri.append((SX + cx + (b - 0.65) * cos(phi), SY + (a - 0.65) * sin(phi), SPHINX["z"] + z))
        outer.append(ro)
        inner.append(ri)

    def surface(rows, flip=False):
        for i in range(len(rows) - 1):
            for j in range(M):
                p0, p1 = rows[i][j], rows[i][j + 1]
                q0, q1 = rows[i + 1][j], rows[i + 1][j + 1]
                u0, u1 = j / M * 2.0, (j + 1) / M * 2.0
                v0, v1 = (zs[i] - 10.5) / 8, (zs[i + 1] - 10.5) / 8
                if flip:
                    nem.quad(p0, q0, q1, p1, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
                else:
                    nem.quad(p0, p1, q1, q0, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    surface(outer, False)
    surface(inner, True)
    for j in range(M):
        nem.quad(outer[0][j], inner[0][j], inner[0][j + 1], outer[0][j + 1])
        nem.quad(outer[-1][j], outer[-1][j + 1], inner[-1][j + 1], inner[-1][j])
    for i in range(len(zs) - 1):
        nem.quad(outer[i][0], outer[i + 1][0], inner[i + 1][0], inner[i][0])
        nem.quad(outer[i][-1], inner[i][-1], inner[i + 1][-1], outer[i + 1][-1])
    nem.finish("Sphinx nemes", MAT_NEMES, COL_SPHINX, smooth=True)

    # lappets resting on the chest, and the uraeus
    lap = MB(tile=8)
    for sy in (-1, 1):
        lap.box(SX + 33.6, SY + sy * 5.1, SPHINX["z"] + 8.9, 2.2, 2.3, 4.8,
                top_scale=(0.82, 0.82))
    lap.finish("Sphinx nemes lappets", MAT_NEMES, COL_SPHINX, smooth=True)
    ur = MB(tile=2)
    ur.cylinder(SX + 35.1, SY, SPHINX["z"] + 20.2, SPHINX["z"] + 21.5, 0.22, 0.10, segments=8)
    ur.finish("Sphinx uraeus", MAT_DARK, COL_SPHINX)

    rock = MB(tile=18)
    _ico(rock, SX - 3, SY, SPHINX["z"] - 1.5, 46, 24, 4.2)
    _ico(rock, SX + 31, SY, SPHINX["z"] - 1.1, 17, 17, 3.2)
    rock.finish("Sphinx bedrock", MAT_ROCK, COL_SPHINX, smooth=True)

    tex = bpy.data.textures.get("Sphinx erosion") or bpy.data.textures.new("Sphinx erosion", "CLOUDS")
    tex.noise_scale = 2.6
    tex.noise_depth = 4
    for obj in COL_SPHINX.objects:
        if obj.type != "MESH":
            continue
        if any(k in obj.name.lower() for k in ("body", "forelegs", "chest", "neck")):
            sub = obj.modifiers.new("Smooth form", "SUBSURF")
            sub.levels = 1
            sub.render_levels = 1
        mod = obj.modifiers.new("Erosion", "DISPLACE")
        mod.texture = tex
        if any(k in obj.name.lower() for k in ("head", "face", "nemes", "eye", "uraeus")):
            mod.strength = 0.06
        elif "bedrock" in obj.name.lower():
            mod.strength = 0.30
        else:
            mod.strength = 0.15
        mod.mid_level = 0.5
        mod.texture_coords = "GLOBAL"


def sphinx_mesh_v4():
    """A cleaner, more recognisable recumbent Sphinx.

    The body is a single lofted mass with a flat underside, separate extended
    forelegs and paws, folded haunches and a tail.  The head is a tapered
    human head with a shallow face; the nemes is a solid flared hood whose
    opening narrows around the cheeks.
    """
    N = 40

    def flat_ring(x, yc, wy, h):
        pts = []
        for j in range(N):
            a = 2 * pi * j / N
            c, s = cos(a), sin(a)
            y = yc + wy * (1 if c >= 0 else -1) * (abs(c) ** 0.72)
            z = h * (0.5 + 0.5 * (1 if s >= 0 else -1) * (abs(s) ** 0.62))
            pts.append((SX + x, SY + y, SPHINX["z"] + z))
        return pts

    # main body, rump to shoulder
    body = MB(tile=16)
    profile = [
        (-31.0, 1.8, 4.5), (-29.0, 3.6, 7.0), (-26.0, 6.0, 9.5),
        (-22.0, 7.8, 11.0), (-17.0, 8.8, 11.7), (-11.0, 8.9, 11.6),
        (-5.0, 8.4, 11.2), (1.0, 7.9, 10.9), (7.0, 8.1, 11.1),
        (13.0, 8.8, 12.0), (18.0, 9.2, 12.7), (22.0, 7.7, 12.3),
        (25.0, 5.6, 11.3),
    ]
    rings = [flat_ring(x, 0, wy, h) for (x, wy, h) in profile]
    loft(body, rings)
    c0 = (SX - 32.0, SY, SPHINX["z"] + 3.8)
    for j in range(N):
        k = (j + 1) % N
        body.tri(c0, rings[0][k], rings[0][j])
    body.finish("Sphinx body", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # extended forelegs, with the paws clearly in front of the chest
    legs = MB(tile=16)
    for sy in (-1, 1):
        legrings = []
        for (x, yc, w, h) in ((12, 7.7, 2.9, 4.9), (18, 8.0, 3.1, 4.8),
                              (24, 8.3, 3.2, 4.4), (30, 8.6, 3.3, 3.7),
                              (36, 8.8, 3.4, 2.8), (39.5, 9.0, 3.5, 1.9)):
            legrings.append(flat_ring(x, sy * yc, w, h))
        loft_uv(legs, legrings)
        _ico(legs, SX + 41.0, SY + sy * 9.0, SPHINX["z"] + 0.85, 4.8, 2.9, 1.0)
        for toe in (-1.2, 0.0, 1.2):
            _ico(legs, SX + 43.4, SY + sy * 9.0 + toe, SPHINX["z"] + 0.48,
                 1.25, 0.62, 0.48)
    legs.finish("Sphinx forelegs", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # folded hind legs / haunches
    hind = MB(tile=16)
    for sy in (-1, 1):
        _ico(hind, SX - 21.0, SY + sy * 7.6, SPHINX["z"] + 4.1, 12.0, 5.4, 6.8)
        _ico(hind, SX - 25.0, SY + sy * 8.2, SPHINX["z"] + 1.3, 6.0, 3.0, 2.0)
        _ico(hind, SX - 17.0, SY + sy * 9.1, SPHINX["z"] + 0.55, 5.0, 2.4, 1.1)
    hind.finish("Sphinx haunches", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # tail curling around the right haunch
    tail = MB(tile=16)
    for t, (x, y, z) in enumerate(((-30.0, -6.8, 5.0), (-32.2, -8.6, 3.2),
                                   (-31.0, -10.0, 1.8), (-27.0, -10.6, 1.2),
                                   (-22.0, -10.4, 1.0), (-16.0, -9.6, 1.3),
                                   (-11.0, -8.8, 1.8))):
        _ico(tail, SX + x, SY + y, SPHINX["z"] + z, 1.25, 1.0, 0.95)
    tail.finish("Sphinx tail", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # neck
    neck = MB(tile=16)
    neckrings = []
    for (x, zc, ry, rz) in ((22.0, 10.4, 5.0, 4.3), (24.0, 12.4, 4.4, 3.9),
                            (26.0, 14.4, 3.9, 3.4), (27.8, 15.8, 3.5, 3.0)):
        pts = []
        for j in range(24):
            a = 2 * pi * j / 24
            pts.append((SX + x, SY + ry * cos(a), SPHINX["z"] + zc + rz * sin(a)))
        neckrings.append(pts)
    loft_uv(neck, neckrings)
    neck.finish("Sphinx neck", MAT_SPHINX_BODY, COL_SPHINX, smooth=True)

    # human head: a vertical loft that is fuller at the cheeks
    head = MB(tile=12)
    headrings = []
    for (z, a, b) in ((12.8, 3.2, 3.2), (14.2, 3.8, 3.8), (15.8, 4.1, 4.0),
                      (17.5, 4.0, 3.9), (19.2, 3.7, 3.7), (20.6, 3.2, 3.3),
                      (21.4, 2.3, 2.6)):
        pts = []
        for j in range(32):
            phi = 2 * pi * j / 32
            pts.append((SX + 30.5 + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
        headrings.append(pts)
    loft(head, headrings)
    for j in range(32):
        k = (j + 1) % 32
        head.tri((SX + 30.5, SY, SPHINX["z"] + 12.8), headrings[0][k], headrings[0][j])
        head.tri((SX + 30.5, SY, SPHINX["z"] + 21.4), headrings[-1][j], headrings[-1][k])
    head.finish("Sphinx head", MAT_SPHINX, COL_SPHINX, smooth=True)

    # shallow frontal face, damaged nose, eyes, lips and chin
    face = MB(tile=8)
    _ellipsoid(face, SX + 34.1, SY, SPHINX["z"] + 16.0, 0.9, 2.9, 3.5, 22, 12)
    for sy in (-1, 1):
        _ellipsoid(face, SX + 34.0, SY + sy * 2.1, SPHINX["z"] + 15.8, 0.6, 1.0, 1.5, 14, 8)
        _ellipsoid(face, SX + 34.7, SY + sy * 1.5, SPHINX["z"] + 18.5, 0.36, 1.1, 0.30, 12, 6)
        _ellipsoid(face, SX + 30.4, SY + sy * 4.0, SPHINX["z"] + 17.1, 0.8, 0.4, 1.2, 12, 6)
    _ellipsoid(face, SX + 34.2, SY, SPHINX["z"] + 13.7, 1.0, 2.0, 1.2, 16, 8)
    _ellipsoid(face, SX + 34.8, SY, SPHINX["z"] + 15.2, 0.40, 1.45, 0.35, 14, 6)
    face.finish("Sphinx face", MAT_SPHINX, COL_SPHINX, smooth=True)

    dark = MB(tile=2)
    for sy in (-1, 1):
        _ellipsoid(dark, SX + 34.95, SY + sy * 1.5, SPHINX["z"] + 17.95, 0.08, 0.56, 0.22, 12, 6)
    _ellipsoid(dark, SX + 34.98, SY, SPHINX["z"] + 16.30, 0.11, 0.72, 0.92, 12, 6)
    _ellipsoid(dark, SX + 35.0, SY, SPHINX["z"] + 15.08, 0.12, 1.75, 0.10, 14, 4)
    dark.finish("Sphinx eye and mouth inlays", MAT_DARK, COL_SPHINX, smooth=True)

    # small stone bridge above the damaged nose
    bridge = MB(tile=4)
    _ellipsoid(bridge, SX + 34.55, SY, SPHINX["z"] + 17.35, 0.42, 0.48, 0.75, 12, 6)
    bridge.finish("Sphinx nose bridge", MAT_SPHINX, COL_SPHINX, smooth=True)

    # nemes: a flared rounded hood with a narrow opening around the face
    nem = MB(tile=8)
    zs = [11.5, 13.5, 15.5, 17.5, 19.5, 21.0, 22.0]
    a_vals = [7.0, 6.8, 6.2, 5.4, 4.5, 3.6, 2.7]
    b_vals = [9.5, 9.0, 8.2, 7.4, 6.5, 5.5, 4.5]
    phi_starts = [66, 60, 50, 43, 40, 39, 39]
    cx = 27.5
    M = 30
    outer, inner = [], []
    for z, a, b, ps in zip(zs, a_vals, b_vals, phi_starts):
        ro, ri = [], []
        p0 = radians(ps)
        p1 = 2 * pi - p0
        for j in range(M + 1):
            phi = p0 + (p1 - p0) * j / M
            ro.append((SX + cx + b * cos(phi), SY + a * sin(phi), SPHINX["z"] + z))
            ri.append((SX + cx + (b - 0.65) * cos(phi), SY + (a - 0.65) * sin(phi), SPHINX["z"] + z))
        outer.append(ro)
        inner.append(ri)

    def surface(rows, flip=False):
        for i in range(len(rows) - 1):
            for j in range(M):
                p0, p1 = rows[i][j], rows[i][j + 1]
                q0, q1 = rows[i + 1][j], rows[i + 1][j + 1]
                u0, u1 = j / M * 2.0, (j + 1) / M * 2.0
                v0, v1 = (zs[i] - 11.5) / 8, (zs[i + 1] - 11.5) / 8
                if flip:
                    nem.quad(p0, q0, q1, p1, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
                else:
                    nem.quad(p0, p1, q1, q0, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    surface(outer, False)
    surface(inner, True)
    for j in range(M):
        nem.quad(outer[0][j], inner[0][j], inner[0][j + 1], outer[0][j + 1])
        nem.quad(outer[-1][j], outer[-1][j + 1], inner[-1][j + 1], inner[-1][j])
    for i in range(len(zs) - 1):
        nem.quad(outer[i][0], outer[i + 1][0], inner[i + 1][0], inner[i][0])
        nem.quad(outer[i][-1], inner[i][-1], inner[i + 1][-1], outer[i + 1][-1])
    nem.finish("Sphinx nemes", MAT_NEMES, COL_SPHINX, smooth=True)

    # uraeus
    ur = MB(tile=2)
    ur.cylinder(SX + 34.5, SY, SPHINX["z"] + 20.7, SPHINX["z"] + 22.0, 0.22, 0.10, segments=8)
    ur.finish("Sphinx uraeus", MAT_DARK, COL_SPHINX)

    # low bedrock plinth
    rock = MB(tile=18)
    _ico(rock, SX - 2, SY, SPHINX["z"] - 1.6, 47, 24, 4.2)
    _ico(rock, SX + 30, SY, SPHINX["z"] - 1.2, 17, 17, 3.2)
    rock.finish("Sphinx bedrock", MAT_ROCK, COL_SPHINX, smooth=True)

    tex = bpy.data.textures.get("Sphinx erosion") or bpy.data.textures.new("Sphinx erosion", "CLOUDS")
    tex.noise_scale = 2.8
    tex.noise_depth = 4
    for obj in COL_SPHINX.objects:
        if obj.type != "MESH":
            continue
        # No Subsurf on the lofted body: its non-manifold seams produced a
        # conspicuous scale pattern in Cycles. The 40-sided lofts are already
        # smooth enough at this scale.
        # Only the bedrock gets geometric erosion.  Displacing the dense body
        # mesh produced a distracting scale-like pattern under Cycles.
        if "bedrock" in obj.name.lower():
            mod = obj.modifiers.new("Erosion", "DISPLACE")
            mod.texture = tex
            mod.strength = 0.22
            mod.mid_level = 0.5
            mod.texture_coords = "GLOBAL"

    # Cycles' shadow rays produce visible acne on the dense, displaced Sphinx.
    # Exclude the sculpture itself from shadow rays; the sun/sky shading still
    # gives it form, and the enclosure/bedrock continue to receive shadows.
    for obj in COL_SPHINX.objects:
        if obj.name not in ("Sphinx bedrock", "Sphinx enclosure", "Sphinx approach"):
            obj.visible_shadow = False


def build_sphinx_scan():
    """Use the public 3D Warehouse Sphinx mesh (3dHH/Egyptian Tourist Authority).

    The mesh is a low-poly but correctly proportioned recumbent Sphinx.  It is
    scaled to 73 m, seated on the enclosure floor and re-textured with the
    project's weathered limestone.
    """
    path = os.path.join(ROOT, "assets", "sphinx_warehouse.glb")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("Sphinx asset failed to import")
    sph = max(meshes, key=lambda o: len(o.data.vertices))

    bpy.ops.object.select_all(action="DESELECT")
    sph.select_set(True)
    bpy.context.view_layer.objects.active = sph
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

    for o in imported:
        if o is not sph:
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(sph.users_collection):
        c.objects.unlink(sph)
    COL_SPHINX.objects.link(sph)

    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    sph.location = (0, 0, 0)
    factor = 73.0 / max(sph.dimensions.x, 0.001)
    sph.scale = (factor, factor, factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Fresh UVs so the project's seamless sphinx limestone can be used.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    uvl = sph.data.uv_layers.active
    if uvl:
        for d in uvl.data:
            d.uv = (d.uv[0] * 4.2, d.uv[1] * 4.2)

    sph.data.materials.clear()
    sph.data.materials.append(MAT_SPHINX_SCAN)
    for p in sph.data.polygons:
        p.use_smooth = True

    bpy.context.view_layer.update()
    factor2 = 73.0 / max(sph.dimensions.x, 0.001)
    sph.scale = (factor2, factor2, factor2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    zmin = min((sph.matrix_world @ v.co).z for v in sph.data.vertices)
    sph.location = (SX, SY, SPHINX["z"] - zmin)
    sph.name = "Sphinx scan"
    sph["source"] = "3D Warehouse: Great Sphinx of Giza by 3dHH (2009), derived from Egyptian Tourist Authority; local educational use"
    return sph


def build_sphinx():
    build_sphinx_scan()
    sphinx_enclosure_v2()


# --------------------------------------------------------------------------
# Terrain, annotations, lights, cameras
# --------------------------------------------------------------------------
terrain_mesh()
build_main_pyramids()
build_queens()
build_rocks()
build_mastabas()
build_temples()
build_sphinx()


def add_text(name, body, x, y, z, size, rot_z=0.0, mat=MAT_INK):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.15
    curve.bevel_depth = 0.0
    obj = bpy.data.objects.new(name, curve)
    obj.location = (x, y, z)
    obj.rotation_euler = (0, 0, rot_z)
    obj.visible_shadow = False
    obj.data.materials.append(mat)
    COL_ANN.objects.link(obj)
    return obj


add_text("Khufu label", "KHUFU (CHEOPS)\n230.3 x 230.3 m  |  146.6 m", KX, KY - 165, 40.0, 17)
add_text("Khafre label", "KHAFRE (CHEPHREN)\n215.3 x 215.3 m  |  143.5 m", FX, FY - 155, 40.0, 17)
add_text("Menkaure label", "MENKAURE (MYKERINOS)\n102.2 x 104.6 m  |  65 m", MX - 135, MY - 20, 40.0, 15)
add_text("Sphinx label", "GREAT SPHINX\n73 m long  |  20 m high", SX + 18, SY - 100, 40.0, 13)
add_text("Plan title", "GIZA PLATEAU", -160, 452, 40.0, 34)
add_text("North arrow", "N", 620, 430, 40.0, 50)
# north arrow shaft (triangle)
na = MB()
na.tri((620, 505, 40.0), (602, 462, 40.0), (638, 462, 40.0))
na_obj = na.finish("North arrow", MAT_INK, COL_ANN)
na_obj.visible_shadow = False
# scale bar, 200 m
sb = MB()
sb.box(550, -250, 40.0, 200, 4, 0.6)
sb_obj = sb.finish("Scale bar", MAT_INK, COL_ANN)
sb_obj.visible_shadow = False
add_text("Scale text", "0                200 m", 550, -272, 40.0, 16)


def setup_world():
    world = bpy.data.worlds.new("Giza sky")
    world.use_nodes = True
    nt = world.node_tree
    nodes, links = nt.nodes, nt.links
    bg = nodes.get("Background")
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = load_image("sky_golden.png")
    env.projection = "EQUIRECTANGULAR"
    env.interpolation = "Linear"
    bg.inputs["Strength"].default_value = 0.50
    links.new(env.outputs["Color"], bg.inputs["Color"])
    scene.world = world
    scene.world.mist_settings.start = 2500
    scene.world.mist_settings.depth = 4500
    scene.world.mist_settings.falloff = "QUADRATIC"
    scene.view_layers[0].use_pass_mist = True


def add_sun(name, az_deg, el_deg, energy, color, angle_deg=0.7, shadow=True):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.color = color
    data.angle = radians(angle_deg)
    data.use_shadow = shadow
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    aim_sun(obj, az_deg, el_deg)
    return obj


def aim_sun(obj, az_deg, el_deg):
    d = Vector((-sin(radians(az_deg)) * cos(radians(el_deg)),
                -cos(radians(az_deg)) * cos(radians(el_deg)),
                -sin(radians(el_deg))))
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


setup_world()
sun = add_sun("Late afternoon sun", 80, 10.0, 3.1, (1.0, 0.70, 0.42), 0.7, True)
fill = add_sun("Sky fill", 300, 45, 0.06, (0.55, 0.68, 0.95), 8.0, False)


def setup_compositor():
    scene.use_nodes = True
    nt = scene.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    rl = nodes.new("CompositorNodeRLayers")
    rl.location = (-600, 200)
    mist = nodes.new("CompositorNodeMapRange")
    mist.location = (-400, -100)
    mist.inputs["From Min"].default_value = 0.0
    mist.inputs["From Max"].default_value = 1.0
    mist.inputs["To Min"].default_value = 0.0
    mist.inputs["To Max"].default_value = 0.18
    links.new(rl.outputs["Mist"], mist.inputs["Value"])
    mix = nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "MIX"
    mix.location = (-180, 120)
    mix.inputs[2].default_value = (0.76, 0.60, 0.43, 1.0)
    links.new(mist.outputs["Value"], mix.inputs[0])
    links.new(rl.outputs["Image"], mix.inputs[1])
    glare = nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.85
    glare.size = 7
    glare.mix = -0.86
    glare.location = (40, 140)
    links.new(mix.outputs[0], glare.inputs["Image"])
    cb = nodes.new("CompositorNodeColorBalance")
    cb.location = (170, 140)
    try:
        cb.correction_method = "LIFT_GAMMA_GAIN"
        cb.lift = (0.96, 0.985, 1.055)
        cb.gamma = (1.0, 1.0, 1.0)
        cb.gain = (1.08, 1.0, 0.90)
    except Exception:
        pass
    links.new(glare.outputs["Image"], cb.inputs["Image"])
    hs = nodes.new("CompositorNodeHueSat")
    hs.location = (250, 140)
    hs.inputs["Saturation"].default_value = 1.10
    hs.inputs["Value"].default_value = 1.0
    links.new(cb.outputs["Image"], hs.inputs["Image"])
    bc = nodes.new("CompositorNodeBrightContrast")
    bc.location = (340, 140)
    bc.inputs["Bright"].default_value = 0.0
    bc.inputs["Contrast"].default_value = 5.0
    links.new(hs.outputs["Image"], bc.inputs["Image"])
    comp = nodes.new("CompositorNodeComposite")
    comp.location = (450, 140)
    links.new(bc.outputs["Image"], comp.inputs["Image"])


setup_compositor()


def camera(name, loc, target, lens=50.0, ortho=False, ortho_scale=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36
    data.clip_start = 1.0
    data.clip_end = 15000
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho_scale or 1800
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = loc
    direction = Vector(target) - Vector(loc)
    if abs(direction.x) < 1e-6 and abs(direction.y) < 1e-6:
        # straight-down orthographic view: keep north up
        obj.rotation_euler = (0.0, 0.0, 0.0)
    else:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def render_view(name, cam, res=(1600, 1000), samples=40, frame=None):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.cycles.samples = samples
    scene.render.filepath = os.path.join(RENDERS, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)


# cameras
cam_hero = camera("Hero camera", (1050, -1400, 210), (-250, -380, 100), lens=39)
cam_aerial = camera("Aerial camera", (1080, -1180, 820), (-230, -390, 0), lens=38)
cam_khafre = camera("Khafre detail camera", (80, -100, 128), (-300, -330, 98), lens=88)
cam_sphinx = camera("Sphinx camera", (450, -495, 28), (320, -432, 6), lens=62)
cam_plan = camera("Site plan camera", (-100, -300, 2400), (-100, -300, 0), lens=50,
                  ortho=True, ortho_scale=1650)

# annotations are for the site plan only
for obj in COL_ANN.objects:
    obj.hide_render = True


def export_glb():
    for obj in scene.objects:
        obj.select_set(False)
    export_objs = []
    for c in (COL_TERRAIN, COL_MONUMENTS, COL_MASTABAS, COL_TEMPLES, COL_SPHINX, COL_ROCKS):
        export_objs.extend([o for o in c.objects if o.type == "MESH"])
    for o in export_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = export_objs[0]
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(ROOT, "Giza_Pyramids.glb"),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
        export_extras=True,
        export_image_format="AUTO",
    )
    print("exported GLB")


def save_blend():
    scene.camera = cam_hero
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack_all failed", e)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "Giza_Pyramids.blend"))


if __name__ == "__main__":
    import sys
    quick = "--quick" in sys.argv
    full = "--full" in sys.argv
    plan = "--plan" in sys.argv
    export = "--export" in sys.argv

    if quick:
        render_view("preview_hero", cam_hero, (800, 500), 10)
        render_view("preview_aerial", cam_aerial, (800, 500), 10)
        render_view("preview_khafre", cam_khafre, (600, 750), 10)
    if plan:
        for obj in COL_ANN.objects:
            obj.hide_render = False
        old_rot = tuple(sun.rotation_euler)
        old_energy = sun.data.energy
        old_exposure = scene.view_settings.exposure
        aim_sun(sun, 180, 65)
        sun.data.energy = 3.0
        scene.view_settings.exposure = 0.15
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1600
        scene.cycles.samples = 32
        scene.camera = cam_plan
        scene.render.filepath = os.path.join(RENDERS, "site_plan.png")
        bpy.ops.render.render(write_still=True)
        sun.rotation_euler = old_rot
        sun.data.energy = old_energy
        scene.view_settings.exposure = old_exposure
        for obj in COL_ANN.objects:
            obj.hide_render = True
    if full:
        render_view("hero_golden", cam_hero, (1600, 1000), 44)
        render_view("aerial", cam_aerial, (1600, 1000), 40)
        render_view("khafre_casing", cam_khafre, (1200, 1500), 40)
        render_view("sphinx", cam_sphinx, (1200, 1000), 36)
    if export:
        export_glb()
        save_blend()
