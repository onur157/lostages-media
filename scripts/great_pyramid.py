import bpy, math, random, sys
random.seed(7)
out = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'; cy.samples = 8; cy.use_denoising = True
cy.max_bounces = 3; cy.diffuse_bounces = 2; cy.glossy_bounces = 1; cy.transmission_bounces = 0
cy.use_adaptive_sampling = True
sc.render.use_persistent_data = True
sc.render.resolution_x, sc.render.resolution_y = 540, 960
sc.render.fps = 12
FR = 240
sc.frame_start, sc.frame_end = 1, FR
sc.view_settings.view_transform = 'AgX'
sc.view_settings.exposure = -1.3
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass

def mat(name, rgb, rough=0.85, metal=0.0, noise=True):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if noise:
        n = nt.nodes.new("ShaderNodeTexNoise"); n.inputs["Scale"].default_value = 6
        r = nt.nodes.new("ShaderNodeValToRGB")
        r.color_ramp.elements[0].color = (rgb[0]*0.8, rgb[1]*0.78, rgb[2]*0.75, 1)
        r.color_ramp.elements[1].color = (*rgb, 1)
        nt.links.new(n.outputs["Fac"], r.inputs["Fac"]); nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*rgb, 1)
    return m

stone = mat("stone", (0.80, 0.63, 0.40))
casing = mat("casing", (0.84, 0.76, 0.62), rough=0.55)
gold = mat("gold", (1.0, 0.76, 0.33), rough=0.25, metal=1.0, noise=False)
sandm = mat("sand", (0.86, 0.69, 0.45), rough=0.95)

# desert ground with soft dunes
bpy.ops.mesh.primitive_plane_add(size=3000)
g = bpy.context.object; g.data.materials.append(sandm)
mod = g.modifiers.new("sub", 'SUBSURF'); mod.subdivision_type = 'SIMPLE'; mod.levels = 7; mod.render_levels = 7
tex = bpy.data.textures.new("dune", 'CLOUDS'); tex.noise_scale = 25
d = g.modifiers.new("disp", 'DISPLACE'); d.texture = tex; d.strength = 3.0; d.mid_level = 0.6

L = 12                # steps
S = 1.0               # block width
H = 0.64              # block height (gives ~52 deg slope, close to the real pyramid)
blocks = []
for lv in range(L):
    n = L - lv
    for i in range(n):
        for j in range(n):
            blocks.append((lv, (i - (n - 1) / 2) * S, (j - (n - 1) / 2) * S))
total = len(blocks)
BUILD_END = 150
for k, (lv, x, y) in enumerate(blocks):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0))
    o = bpy.context.object; o.scale = (S * 0.97, S * 0.97, H * 0.97)
    o.data.materials.append(stone)
    o.rotation_euler[2] = random.uniform(-0.02, 0.02)
    z = H / 2 + lv * H
    start = 2 + int(k / total * (BUILD_END - 14)) + random.randint(0, 3)
    o.location = (x, y, z + 2.5); o.keyframe_insert("location", frame=start)
    o.hide_render = True; o.keyframe_insert("hide_render", frame=start - 1)
    o.hide_render = False; o.keyframe_insert("hide_render", frame=start)
    o.location = (x, y, z); o.keyframe_insert("location", frame=start + 8)

# smooth limestone casing rising through the steps
top = L * H
apex = (L + 1) * H
r = (L * S / 2 + 0.5 * S) * math.sqrt(2) * 1.01
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=r, radius2=0, depth=apex * 1.01, location=(0, 0, 0))
c = bpy.context.object; c.rotation_euler[2] = math.radians(45); c.data.materials.append(casing)
c.location = (0, 0, apex / 2 - apex - 0.3); c.keyframe_insert("location", frame=BUILD_END)
c.location = (0, 0, apex / 2 * 1.01); c.keyframe_insert("location", frame=BUILD_END + 45)

# golden capstone
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.9, radius2=0, depth=0.85, location=(0, 0, (L + 1) * H + 6))
cap = bpy.context.object; cap.rotation_euler[2] = math.radians(45); cap.data.materials.append(gold)
cap.keyframe_insert("location", frame=BUILD_END + 50)
cap.hide_render = True; cap.keyframe_insert("hide_render", frame=1)
cap.hide_render = False; cap.keyframe_insert("hide_render", frame=BUILD_END + 50)
cap.location = (0, 0, apex * 1.01 - 0.25); cap.keyframe_insert("location", frame=BUILD_END + 70)

# camera: slow orbit, rising to an aerial view
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 30
tgt = bpy.data.objects.new("t", None); sc.collection.objects.link(tgt)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
for f in range(1, FR + 1, 6):
    p = f / FR
    a = 0.5 + p * 2.2
    rad = 24 - p * 4
    cam.location = (rad * math.cos(a), rad * math.sin(a), 3.5 + p * 9)
    cam.keyframe_insert("location", frame=f)
    tgt.location = (0, 0, 1.5 + p * 2.5); tgt.keyframe_insert("location", frame=f)

# warm low sun + sky
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(62), 0, math.radians(-40)))
sun = bpy.context.object.data; sun.energy = 3.0; sun.color = (1.0, 0.80, 0.58); sun.angle = math.radians(1.5)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes["Background"]
try:
    sky = nt.nodes.new("ShaderNodeTexSky")
    try: sky.sun_elevation = math.radians(22); sky.sun_rotation = math.radians(-40)
    except Exception: pass
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.18
    print("SKY", sky.sky_type)
except Exception as e:
    print("SKYFAIL", e); bg.inputs["Color"].default_value = (0.35, 0.5, 0.75, 1)
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
sc.render.filepath = out + "/f_"
if "--still" in sys.argv:
    for f in (60, 140, 230):
        sc.frame_set(f); sc.render.filepath = out + f"/still_{f}.jpg"; bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
