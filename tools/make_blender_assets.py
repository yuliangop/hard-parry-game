from __future__ import annotations

import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "generated_blender"
OUT.mkdir(parents=True, exist_ok=True)


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def mat(name: str, color: tuple[float, float, float, float]):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    return material


def cube(name: str, loc, scale, material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def sphere(name: str, loc, scale, material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    return obj


def make_humanoid(name: str, body_color, accent_color, loc=(0, 0, 0)) -> None:
    body = mat(f"{name}_body", body_color)
    accent = mat(f"{name}_accent", accent_color)
    skin = mat(f"{name}_skin", (0.78, 0.58, 0.43, 1))
    cube(f"{name}_torso", (loc[0], loc[1], loc[2] + 1.25), (0.55, 0.34, 1.0), body)
    sphere(f"{name}_head", (loc[0], loc[1], loc[2] + 2.05), (0.33, 0.30, 0.36), skin)
    cube(f"{name}_sword", (loc[0] + 0.58, loc[1], loc[2] + 1.25), (0.08, 0.08, 1.35), accent).rotation_euler[1] = math.radians(18)
    cube(f"{name}_left_arm", (loc[0] - 0.42, loc[1], loc[2] + 1.25), (0.18, 0.18, 0.78), body)
    cube(f"{name}_right_arm", (loc[0] + 0.42, loc[1], loc[2] + 1.25), (0.18, 0.18, 0.78), body)
    cube(f"{name}_left_leg", (loc[0] - 0.18, loc[1], loc[2] + 0.45), (0.18, 0.18, 0.85), body)
    cube(f"{name}_right_leg", (loc[0] + 0.18, loc[1], loc[2] + 0.45), (0.18, 0.18, 0.85), body)


def make_beast(name: str, body_color, accent_color, loc=(0, 0, 0)) -> None:
    body = mat(f"{name}_body", body_color)
    accent = mat(f"{name}_accent", accent_color)
    sphere(f"{name}_body", (loc[0], loc[1], loc[2] + 0.75), (0.65, 0.42, 0.38), body)
    sphere(f"{name}_head", (loc[0] + 0.58, loc[1], loc[2] + 1.03), (0.34, 0.28, 0.30), body)
    cube(f"{name}_ear_l", (loc[0] + 0.58, loc[1] - 0.22, loc[2] + 1.34), (0.12, 0.08, 0.35), accent)
    cube(f"{name}_ear_r", (loc[0] + 0.58, loc[1] + 0.22, loc[2] + 1.34), (0.12, 0.08, 0.35), accent)
    for i, y in enumerate([-0.28, -0.08, 0.12, 0.32]):
        cube(f"{name}_leg_{i}", (loc[0] - 0.2, loc[1] + y, loc[2] + 0.28), (0.16, 0.12, 0.5), body)


def make_arena() -> None:
    floor = mat("cold_stone", (0.25, 0.30, 0.27, 1))
    wall = mat("old_wall", (0.45, 0.42, 0.35, 1))
    gold = mat("shrine_gold", (0.95, 0.72, 0.22, 1))
    cube("arena_floor", (0, 0, -0.04), (22, 18, 0.08), floor)
    for x, y, sx, sy in [(-5, -3, 4, 0.4), (3, -4, 0.4, 5), (7, 3, 5, 0.4), (-7, 4, 3, 0.5)]:
        cube("broken_wall", (x, y, 0.45), (sx, sy, 0.9), wall)
    for x, y in [(-6, 5), (2, 5), (7, -5)]:
        cube("shrine", (x, y, 0.45), (0.5, 0.5, 0.9), gold)


def export(name: str) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(OUT / f"{name}.glb"), export_format="GLB")


def main() -> None:
    clear()
    make_arena()
    make_humanoid("hero", (0.78, 0.80, 0.82, 1), (0.25, 0.78, 0.95, 1), (-4, 0, 0))
    make_humanoid("boss_ma", (0.22, 0.18, 0.16, 1), (0.95, 0.75, 0.22, 1), (-1.5, 0, 0))
    make_beast("boss_cat", (0.85, 0.55, 0.22, 1), (0.95, 0.8, 0.4, 1), (1.4, 0, 0))
    make_beast("boss_wolf", (0.12, 0.13, 0.14, 1), (0.9, 0.42, 0.16, 1), (4.0, 0, 0))
    export("hard_parry_models")


if __name__ == "__main__":
    main()

