#!/usr/bin/env python3
"""Inventory an already loaded .blend in Blender; never save or repair it.

blender --background --factory-startup --disable-autoexec model.blend \
    --python-exit-code 1 --python inspect_blend.py -- --output new-report.json

The optional report is created exclusively. No output path prints JSON to stdout.
This is source-data inspection, not export, appearance, or runtime validation.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from datetime import datetime, timezone

import bpy


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def driver_count(owner):
    animation = getattr(owner, "animation_data", None)
    return len(animation.drivers) if animation else 0


def constraints(owner):
    return [
        {"name": item.name, "type": item.type, "muted": item.mute,
         "influence": item.influence}
        for item in owner.constraints
    ]


def mesh_record(obj):
    mesh = obj.data
    armatures = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE"]
    deform_names = {
        bone.name
        for modifier in armatures if modifier.object
        for bone in modifier.object.data.bones if bone.use_deform
    }
    deform_indices = {group.index for group in obj.vertex_groups if group.name in deform_names}
    weights = None
    if armatures:
        unweighted = 0
        non_unit_sum = 0
        maximum_influences = 0
        for vertex in mesh.vertices:
            active = [group.weight for group in vertex.groups
                      if group.group in deform_indices and group.weight > 1e-8]
            maximum_influences = max(maximum_influences, len(active))
            if not active:
                unweighted += 1
            elif not math.isclose(math.fsum(active), 1.0, rel_tol=0.0, abs_tol=1e-4):
                non_unit_sum += 1
        weights = {
            "vertices_without_positive_deform_weight": unweighted,
            "weighted_vertices_with_non_unit_sum": non_unit_sum,
            "maximum_positive_deform_influences": maximum_influences,
            "scope": "source vertex groups for all referenced deform bones; not evaluated skinning",
        }

    keys = mesh.shape_keys
    shape_keys = []
    if keys:
        for key in keys.key_blocks:
            reference = key.relative_key if keys.use_relative else keys.reference_key
            changed = sum(
                (point.co - reference.data[index].co).length_squared > 1e-12
                for index, point in enumerate(key.data)
            ) if reference else None
            shape_keys.append({
                "name": key.name, "value": key.value,
                "slider_min": key.slider_min, "slider_max": key.slider_max,
                "relative_key": reference.name if reference else None,
                "changed_vertices_vs_reference": changed,
            })

    return {
        "name": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent_type,
        "parent_bone": obj.parent_bone or None,
        "dimensions_at_inspection": list(obj.dimensions),
        "scale": list(obj.scale),
        "source_vertices": len(mesh.vertices),
        "source_polygons": len(mesh.polygons),
        "source_triangles_estimate": sum(max(0, len(face.vertices) - 2) for face in mesh.polygons),
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
        "modifiers": [{"name": item.name, "type": item.type,
                       "viewport": item.show_viewport, "render": item.show_render}
                      for item in obj.modifiers],
        "armature_modifiers": [{"name": item.name,
                                "object": item.object.name if item.object else None,
                                "vertex_groups": item.use_vertex_groups,
                                "bone_envelopes": item.use_bone_envelopes}
                               for item in armatures],
        "weights": weights,
        "shape_keys_relative": keys.use_relative if keys else None,
        "shape_keys": shape_keys,
        "drivers": {"object": driver_count(obj), "mesh": driver_count(mesh),
                    "shape_keys": driver_count(keys) if keys else 0},
        "constraints": constraints(obj),
    }


def armature_record(obj):
    return {
        "name": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "scale": list(obj.scale),
        "pose_position": obj.data.pose_position,
        "bones": [{"name": bone.name,
                   "parent": bone.parent.name if bone.parent else None,
                   "deform": bone.use_deform,
                   "head_local": list(bone.head_local), "tail_local": list(bone.tail_local)}
                  for bone in obj.data.bones],
        "pose_constraints": [{"bone": bone.name, "constraints": constraints(bone)}
                             for bone in obj.pose.bones if bone.constraints],
        "drivers": {"object": driver_count(obj), "armature": driver_count(obj.data)},
    }


def image_record(item):
    packed = bool(item.packed_file) or bool(getattr(item, "packed_files", ()))
    resolved = bpy.path.abspath(item.filepath, library=item.library) if item.filepath else None
    single_file = item.source == "FILE"
    exists = Path(resolved).is_file() if single_file and resolved else None
    return {
        "name": item.name, "users": item.users, "source": item.source,
        "filepath": item.filepath or None, "resolved_path": resolved,
        "packed": packed, "single_file_exists": exists,
        "missing_single_file": single_file and not packed and (exists is not True),
        "size": list(item.size), "color_space": item.colorspace_settings.name,
        "requires_manual_dependency_check": item.source in {"TILED", "SEQUENCE", "MOVIE"},
    }


def inspect():
    if not bpy.data.filepath or not Path(bpy.data.filepath).is_file():
        raise RuntimeError("Load an existing saved .blend before running this inspector.")
    source = Path(bpy.data.filepath).resolve()
    scene = bpy.context.scene
    objects = sorted(scene.objects, key=lambda obj: obj.name)
    camera = scene.camera
    return {
        "schema_version": 1,
        "kind": "blender-source-inspection",
        "inspected_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(source), "source_sha256": sha256_file(source),
        "in_memory_data_is_dirty": bool(bpy.data.is_dirty),
        "blender_version": bpy.app.version_string,
        "scene": {
            "name": scene.name, "render_engine": scene.render.engine,
            "unit_system": scene.unit_settings.system,
            "unit_scale": scene.unit_settings.scale_length,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "resolution_percentage": scene.render.resolution_percentage,
            "color_management": {"display_device": scene.display_settings.display_device,
                                 "view_transform": scene.view_settings.view_transform,
                                 "look": scene.view_settings.look,
                                 "exposure": scene.view_settings.exposure,
                                 "gamma": scene.view_settings.gamma},
            "camera": {"name": camera.name, "projection": camera.data.type,
                       "ortho_scale": camera.data.ortho_scale, "lens": camera.data.lens}
                      if camera else None,
        },
        "objects": [{"name": obj.name, "type": obj.type} for obj in objects],
        "meshes": [mesh_record(obj) for obj in objects if obj.type == "MESH"],
        "armatures": [armature_record(obj) for obj in objects if obj.type == "ARMATURE"],
        "materials": [{"name": item.name, "users": item.users, "use_nodes": item.use_nodes,
                       "node_types": sorted({node.bl_idname for node in item.node_tree.nodes})
                       if item.use_nodes and item.node_tree else []}
                      for item in sorted(bpy.data.materials, key=lambda item: item.name)],
        "images": [image_record(item) for item in sorted(bpy.data.images, key=lambda item: item.name)],
        "libraries": [{"name": item.name, "filepath": item.filepath,
                       "resolved_path": bpy.path.abspath(item.filepath, library=item.parent),
                       "exists": Path(bpy.path.abspath(item.filepath, library=item.parent)).is_file()}
                      for item in bpy.data.libraries],
        "limitations": [
            "Source-data inventory only; no appearance, deformation, export or engine verdict.",
            "The fingerprint identifies the saved file; the inventory describes the current in-memory scene.",
            "Scene meshes may include objects outside the intended export collection.",
            "Source triangle estimates exclude modifiers and exporter changes.",
            "External cache, plugin and multi-file image dependencies need additional inspection.",
            "Auto-execution is controlled by the Blender invocation; disabled drivers may affect evaluation.",
        ],
    }


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON report path; parent directory must exist.")
    options = parser.parse_args(args)
    if options.output and options.output.exists():
        raise FileExistsError(f"Refusing to overwrite report: {options.output}")
    report = inspect()
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if options.output:
        with options.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
        print(f"Source inspection written to {options.output.resolve()}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
