# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

# All Operator


# core Blender properties are named with a bl_ prefix (so to avoid conflicts don't use this yourself )
# Once a class is loaded you can access it from bpy.types, using the bl_idname rather than the classes original name.
# a blender class can be executed by calling something like this:-
#bpy.types.MESH_OT_print3d_clean_holes.execute()   # NB doesn't work...
# see https://stackoverflow.com/questions/33903187/call-a-function-in-a-class-from-different-class/33903188


#unclear matching between checks and cleaners
#MESH_OT_print3d_check_intersections
#MESH_OT_print3d_check_thick
#MESH_OT_print3d_check_sharp
#MESH_OT_print3d_check_overhang

#class MESH_OT_print3d_clean_thin(Operator):
#class MESH_OT_print3d_clean_degenerate(Operator):
#class MESH_OT_print3d_clean_doubles(Operator):
#class MESH_OT_print3d_clean_loose(Operator):




import math
#import winsound
import traceback

import bpy
from bpy.types import Operator
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
)
import bmesh

from . import (
    mesh_helpers,
    report,
)


def clean_float(text):
    # strip trailing zeros: 0.000 -> 0.0
    index = text.rfind(".")
    if index != -1:
        index += 2
        head, tail = text[:index], text[index:]
        tail = tail.rstrip("0")
        text = head + tail
    return text


# ---------
# Mesh Info

class MESH_OT_print3d_info_volume(Operator):
    bl_idname = "mesh.print3d_info_volume"
    bl_label = "3D-Print Info Volume"
    bl_description = "Report the volume of the active mesh"

    def execute(self, context):
        scene = context.scene
        unit = scene.unit_settings
        scale = 1.0 if unit.system == 'NONE' else unit.scale_length
        obj = context.active_object

        bm = mesh_helpers.bmesh_copy_from_object(obj, apply_modifiers=True)
        volume = bm.calc_volume()
        bm.free()

        if unit.system == 'METRIC':
            volume_cm = volume * (scale ** 3.0) / (0.01 ** 3.0)
            volume_fmt = "{} cm".format(clean_float(f"{volume_cm:.4f}"))
        elif unit.system == 'IMPERIAL':
            volume_inch = volume * (scale ** 3.0) / (0.0254 ** 3.0)
            volume_fmt = '{} "'.format(clean_float(f"{volume_inch:.4f}"))
        else:
            volume_fmt = clean_float(f"{volume:.8f}")

        report.update((f"Volume: {volume_fmt}³", None))

        return {'FINISHED'}


class MESH_OT_print3d_info_area(Operator):
    bl_idname = "mesh.print3d_info_area"
    bl_label = "3D-Print Info Area"
    bl_description = "Report the surface area of the active mesh"

    def execute(self, context):
        scene = context.scene
        unit = scene.unit_settings
        scale = 1.0 if unit.system == 'NONE' else unit.scale_length
        obj = context.active_object

        bm = mesh_helpers.bmesh_copy_from_object(obj, apply_modifiers=True)
        area = mesh_helpers.bmesh_calc_area(bm)
        bm.free()

        if unit.system == 'METRIC':
            area_cm = area * (scale ** 2.0) / (0.01 ** 2.0)
            area_fmt = "{} cm".format(clean_float(f"{area_cm:.4f}"))
        elif unit.system == 'IMPERIAL':
            area_inch = area * (scale ** 2.0) / (0.0254 ** 2.0)
            area_fmt = '{} "'.format(clean_float(f"{area_inch:.4f}"))
        else:
            area_fmt = clean_float(f"{area:.8f}")

        report.update((f"Area: {area_fmt}²", None))

        return {'FINISHED'}


# ---------------
# Geometry Checks

def execute_check(self, context):
    obj = context.active_object

    info = []
    self.main_check(obj, info)
    report.update(*info)

    multiple_obj_warning(self, context)

    return {'FINISHED'}


def multiple_obj_warning(self, context):
    if len(context.selected_objects) > 1:
        self.report({"INFO"}, "Multiple selected objects. Only the active one will be evaluated")

def elem_count(context):
    bm = bmesh.from_edit_mesh(context.edit_object.data)
    return len(bm.verts), len(bm.edges), len(bm.faces)

def setup_environment():
    """set the mode as edit, select mode as vertices, and reveal hidden vertices"""
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.reveal()

class MESH_OT_print3d_check_solid(Operator):
    bl_idname = "mesh.print3d_check_solid"
    bl_label = "3D-Print Check Solid"
    bl_description = "Check for solid geometry. Must have valid inside/outside (every edge is linked to exactly 2 faces) and correct normals (all directed outside of solid)"

    @staticmethod
    def main_check(obj, info):
        import array

        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=False, triangulate=False)

        edges_non_manifold = array.array('i', (i for i, ele in enumerate(bm.edges) if not ele.is_manifold))
        edges_non_contig = array.array(
            'i',
            (i for i, ele in enumerate(bm.edges) if ele.is_manifold and (not ele.is_contiguous)),
        )

        info.append((f"Non Manifold Edge: {len(edges_non_manifold)}", (bmesh.types.BMEdge, edges_non_manifold), MESH_OT_print3d_clean_non_manifold))
        info.append((f"Bad Contig. Edges: {len(edges_non_contig)}", (bmesh.types.BMEdge, edges_non_contig), MESH_OT_print3d_clean_non_manifold))

        bm.free()

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_intersections(Operator):
    bl_idname = "mesh.print3d_check_intersect"
    bl_label = "3D-Print Check Intersections"
    bl_description = "Check geometry for self intersections"

    @staticmethod
    def main_check(obj, info):
        faces_intersect = mesh_helpers.bmesh_check_self_intersect_object(obj)
        info.append((f"Intersect Face: {len(faces_intersect)}", (bmesh.types.BMFace, faces_intersect), MESH_OT_print3d_clean_distorted))

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_degenerate(Operator):
    bl_idname = "mesh.print3d_check_degenerate"
    bl_label = "3D-Print Check Degenerate"
    bl_description = (
        "Check for minimum component size ('degenerate geometry') that may not print properly "
        "(zero/small area faces, zero/small length edges, TODO: include doubles (=very close vertices))"
    )

    @staticmethod
    def main_check(obj, info):
        import array

        scene = bpy.context.scene
        print_3d = scene.print_3d
        threshold = print_3d.threshold_zero

        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=False, triangulate=False)

        faces_zero = array.array('i', (i for i, ele in enumerate(bm.faces) if ele.calc_area() <= threshold))
        edges_zero = array.array('i', (i for i, ele in enumerate(bm.edges) if ele.calc_length() <= threshold))

        info.append((f"Zero Area Faces: {len(faces_zero)}", (bmesh.types.BMFace, faces_zero), MESH_OT_print3d_clean_degenerate))
        info.append((f"Zero Length Edges: {len(edges_zero)}", (bmesh.types.BMEdge, edges_zero), MESH_OT_print3d_clean_degenerate))

        bm.free()

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_distorted(Operator):
    bl_idname = "mesh.print3d_check_distort"
    bl_label = "3D-Print Check Distorted Faces"
    bl_description = "Check for non-flat faces"

    @staticmethod
    def main_check(obj, info):
        import array

        scene = bpy.context.scene
        print_3d = scene.print_3d
        angle_distort = print_3d.angle_distort

        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=True, triangulate=False)
        bm.normal_update()

        faces_distort = array.array(
            'i',
            (i for i, ele in enumerate(bm.faces) if mesh_helpers.face_is_distorted(ele, angle_distort))
        )

        info.append((f"Non-Flat Faces: {len(faces_distort)}", (bmesh.types.BMFace, faces_distort), MESH_OT_print3d_clean_distorted))

        bm.free()

    def execute(self, context):
        return execute_check(self, context)




class MESH_OT_print3d_check_disconnected(Operator):
    bl_idname = "mesh.print3d_check_disconnected"
    bl_label = "3D-Print Check for Disconnected Components"
    bl_description = "Check for Islands and Orphans - ie disconnected small parts of the total object"

    @staticmethod
    def main_check(obj, info):

        self.report({'INFO'}, "SORRY NO SEARCH FOR DISCONNECTED COMPONENTS CODED YET")
        # ideally use the meshlab filter "select small disconnected components" to save extra coding

    def execute(self, context):
        return execute_check(self, context)

class print3d_check_resin_traps(Operator):
    bl_idname = "mesh.print3d_check_unfilled_islands"
    bl_label = "3D-Print Check for internal but incompletely cured spots"
    bl_description = "Check for internal but incompletely cured spots which will not be able to drain externally"

    @staticmethod
    def main_check(obj, info):

        self.report({'INFO'}, "SORRY NO SEARCH FOR RESIN ISLANDS CODED YET")
        # ideally use the meshlab filter "select small disconnected components" to save extra coding

#        import array

#        scene = bpy.context.scene
#        print_3d = scene.print_3d
#        angle_distort = print_3d.angle_distort

#        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=True, triangulate=False)
#        bm.normal_update()

#        faces_distort = array.array(
#            'i',
#            (i for i, ele in enumerate(bm.faces) if mesh_helpers.face_is_distorted(ele, angle_distort))
#        )

#        info.append((f"Non-Flat Faces: {len(faces_distort)}", (bmesh.types.BMFace, faces_distort), MESH_OT_print3d_clean_distorted))

#        bm.free()

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_clean_notdefined(Operator):
    bl_idname = "mesh.print3d_clean_notdefined"
    bl_label = "3D-Print No Defined Cleaner"
    bl_description = "Placeholder when cleaner class not available"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # TODO
        # This needs to search for faces which have no backing (ie are a single face thick)
        # also for any areas which are too thin for the resolution of the printer
        #print("")
        #bpy.context.window_manager.popup_menu("CLEAN THIN", title="Action", icon='ERROR')
        self.report({'INFO'}, "SORRY NO AUTOMATIC CLEANER AVAILABLE")
        #The color depends on the type enum: INFO gets green, WARNING light red, and ERROR dark red. I don't see reference to any direct output to Info window, other than this method.


        #winsound.Beep(2500, 1000)

        return {'FINISHED'}


class MESH_OT_print3d_check_thick(Operator):
    bl_idname = "mesh.print3d_check_thick"
    bl_label = "3D-Print Check Thickness"
    bl_description = (
        "Check geometry is above the minimum thickness preference "
        " = identify features which are too thin for robust real-world performance"
        "(relies on correct normals)"
    )

    @staticmethod
    def main_check(obj, info):
        scene = bpy.context.scene
        print_3d = scene.print_3d

        faces_error = mesh_helpers.bmesh_check_thick_object(obj, print_3d.thickness_min)
        info.append((f"Thin Faces: {len(faces_error)}", (bmesh.types.BMFace, faces_error), MESH_OT_print3d_clean_notdefined))

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_sharp(Operator):
    bl_idname = "mesh.print3d_check_sharp"
    bl_label = "3D-Print Check Sharp"
    bl_description = "Check edges are below the sharpness preference"

    @staticmethod
    def main_check(obj, info):
        scene = bpy.context.scene
        print_3d = scene.print_3d
        angle_sharp = print_3d.angle_sharp

        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=True, triangulate=False)
        bm.normal_update()

        edges_sharp = [
            ele.index for ele in bm.edges
            if ele.is_manifold and ele.calc_face_angle_signed() > angle_sharp
        ]

        info.append((f"Sharp Edge: {len(edges_sharp)}", (bmesh.types.BMEdge, edges_sharp), MESH_OT_print3d_clean_notdefined))
        bm.free()

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_overhang(Operator):
    bl_idname = "mesh.print3d_check_overhang"
    bl_label = "3D-Print Check Overhang"
    bl_description = "Check faces don't overhang past a certain angle"

    @staticmethod
    def main_check(obj, info):
        from mathutils import Vector

        scene = bpy.context.scene
        print_3d = scene.print_3d
        angle_overhang = (math.pi / 2.0) - print_3d.angle_overhang

        if angle_overhang == math.pi:
            info.append(("Skipping Overhang", ()))
            return

        bm = mesh_helpers.bmesh_copy_from_object(obj, transform=True, triangulate=False)
        bm.normal_update()

        z_down = Vector((0, 0, -1.0))
        z_down_angle = z_down.angle

        # 4.0 ignores zero area faces
        faces_overhang = [
            ele.index for ele in bm.faces
            if z_down_angle(ele.normal, 4.0) < angle_overhang
        ]

        info.append((f"Overhang Face: {len(faces_overhang)}", (bmesh.types.BMFace, faces_overhang), MESH_OT_print3d_clean_notdefined))
        bm.free()

    def execute(self, context):
        return execute_check(self, context)


class MESH_OT_print3d_check_all(Operator):
    bl_idname = "mesh.print3d_check_all"
    bl_label = "3D-Print Check All"
    bl_description = "Run all checks"

    check_cls = (
        MESH_OT_print3d_check_solid,
        MESH_OT_print3d_check_intersections,
        MESH_OT_print3d_check_degenerate,
        MESH_OT_print3d_check_distorted,
        MESH_OT_print3d_check_thick,
        MESH_OT_print3d_check_sharp,
        MESH_OT_print3d_check_overhang,
    )

    def execute(self, context):
        obj = context.active_object

        info = []
        for cls in self.check_cls:
            cls.main_check(obj, info)

        report.update(*info)

        multiple_obj_warning(self, context)

        return {'FINISHED'}




class MESH_OT_print3d_clean_notdefined(Operator):
    bl_idname = "mesh.print3d_clean_notdefined"
    bl_label = "3D-Print No Defined Cleaner"
    bl_description = "Placeholder when cleaner class not available"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # TODO
        # This needs to search for faces which have no backing (ie are a single face thick)
        # also for any areas which are too thin for the resolution of the printer
        #print("")
        #bpy.context.window_manager.popup_menu("CLEAN THIN", title="Action", icon='ERROR')
        self.report({'INFO'}, "SORRY NO AUTOMATIC CLEANER AVAILABLE")
        #The color depends on the type enum: INFO gets green, WARNING light red, and ERROR dark red. I don't see reference to any direct output to Info window, other than this method.


        #winsound.Beep(2500, 1000)

        return {'FINISHED'}


class MESH_OT_print3d_clean_distorted(Operator):
    bl_idname = "mesh.print3d_clean_distorted"
    bl_label = "3D-Print Clean Distorted"
    bl_description = "Triangulate distorted faces"
    bl_options = {'REGISTER', 'UNDO'}

    angle: FloatProperty(
        name="Angle",
        description="Limit for checking distorted faces",
        subtype='ANGLE',
        default=math.radians(45.0),
        min=0.0,
        max=math.radians(180.0),
    )

    def execute(self, context):
        obj = context.active_object
        bm = mesh_helpers.bmesh_from_object(obj)
        bm.normal_update()
        elems_triangulate = [ele for ele in bm.faces if mesh_helpers.face_is_distorted(ele, self.angle)]

        if elems_triangulate:
            bmesh.ops.triangulate(bm, faces=elems_triangulate)
            mesh_helpers.bmesh_to_object(obj, bm)

        self.report({'INFO'}, f"Triangulated {len(elems_triangulate)} faces")

        return {'FINISHED'}

    def invoke(self, context, event):
        print_3d = context.scene.print_3d
        self.angle = print_3d.angle_distort

        return self.execute(context)


class MESH_OT_print3d_clean_non_manifold(Operator):
    bl_idname = "mesh.print3d_clean_non_manifold"
    bl_label = "3D-Print Clean Non-Manifold"
    bl_description = "Cleanup problems, like holes, non-manifold vertices and inverted normals"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Merge Distance",
        description="Minimum distance between elements to merge",
        default=0.0001,
    )
    sides: IntProperty(
        name="Sides",
        description="Number of sides in hole required to fill (zero fills all holes)",
        default=0,
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()
        bm_key_orig = elem_count(context)

        self.delete_loose()
        self.delete_interior()
        self.remove_doubles(self.threshold)
        self.dissolve_degenerate(self.threshold)
        self.fix_non_manifold(context, self.sides)  # may take a while
        self.make_normals_consistently_outwards()

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        verts = bm_key[0] - bm_key_orig[0]
        edges = bm_key[1] - bm_key_orig[1]
        faces = bm_key[2] - bm_key_orig[2]

        self.report({'INFO'}, f"Modified: {verts:+} vertices, {edges:+} edges, {faces:+} faces")

        return {'FINISHED'}

#    @staticmethod
#    def elem_count(context):
#        bm = bmesh.from_edit_mesh(context.edit_object.data)
#        return len(bm.verts), len(bm.edges), len(bm.faces)

#    @staticmethod
#    def setup_environment():
#        """set the mode as edit, select mode as vertices, and reveal hidden vertices"""
#        bpy.ops.object.mode_set(mode='EDIT')
#        bpy.ops.mesh.select_mode(type='VERT')
#        bpy.ops.mesh.reveal()

    @staticmethod
    def remove_doubles(threshold):
        """remove duplicate vertices"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)

    @staticmethod
    def delete_loose():
        """delete loose vertices/edges/faces"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=True)

    @staticmethod
    def delete_interior():
        """delete interior faces"""
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_interior_faces()
        bpy.ops.mesh.delete(type='FACE')

    @staticmethod
    def dissolve_degenerate(threshold):
        """dissolve zero area faces and zero length edges"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.dissolve_degenerate(threshold=threshold)

    @staticmethod
    def make_normals_consistently_outwards():
        """have all normals face outwards"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent()

    @classmethod
    def fix_non_manifold(cls, context, sides):
        """naive iterate-until-no-more approach for fixing manifolds"""
        total_non_manifold = cls.count_non_manifold_verts(context)

        if not total_non_manifold:
            return

        bm_states = set()
        bm_key = cls.elem_count(context)
        bm_states.add(bm_key)

        while True:
            cls.fill_non_manifold(sides)
            cls.delete_newly_generated_non_manifold_verts()

            bm_key = cls.elem_count(context)
            if bm_key in bm_states:
                break
            else:
                bm_states.add(bm_key)

    @staticmethod
    def select_non_manifold_verts(
        use_wire=False,
        use_boundary=False,
        use_multi_face=False,
        use_non_contiguous=False,
        use_verts=False,
    ):
        """select non-manifold vertices"""
        bpy.ops.mesh.select_non_manifold(
            extend=False,
            use_wire=use_wire,
            use_boundary=use_boundary,
            use_multi_face=use_multi_face,
            use_non_contiguous=use_non_contiguous,
            use_verts=use_verts,
        )

    @classmethod
    def count_non_manifold_verts(cls, context):
        """return a set of coordinates of non-manifold vertices"""
        cls.select_non_manifold_verts(use_wire=True, use_boundary=True, use_verts=True)

        bm = bmesh.from_edit_mesh(context.edit_object.data)
        return sum((1 for v in bm.verts if v.select))

    @classmethod
    def fill_non_manifold(cls, sides):
        """fill in any remnant non-manifolds"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.fill_holes(sides=sides)

    @classmethod
    def delete_newly_generated_non_manifold_verts(cls):
        """delete any newly generated vertices from the filling repair"""
        cls.select_non_manifold_verts(use_wire=True, use_verts=True)
        bpy.ops.mesh.delete(type='VERT')


class MESH_OT_print3d_clean_thin(Operator):
    bl_idname = "mesh.print3d_clean_thin"
    bl_label = "3D-Print Clean Thin"
    bl_description = "Ensure minimum thickness"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # TODO
        # This needs to search for faces which have no backing (ie are a single face thick)
        # also for any areas which are too thin for the resolution of the printer
        #print("")
        #bpy.context.window_manager.popup_menu("CLEAN THIN", title="Action", icon='ERROR')
        self.report({'INFO'}, "CLEAN THIN")
        #The color depends on the type enum: INFO gets green, WARNING light red, and ERROR dark red. I don't see reference to any direct output to Info window, other than this method.


        #winsound.Beep(2500, 1000)

        return {'FINISHED'}


class MESH_OT_print3d_clean_degenerate(Operator):
    bl_idname = "mesh.print3d_clean_degenerate"
    bl_label = "Degenerate Dissolve"
    bl_description = "Dissolve zero area faces and zero length edges"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Merge Distance",
        description="Minimum distance between elements to merge",
        default=0.0001,
        step=1
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.dissolve_degenerate(self.threshold)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def dissolve_degenerate(threshold):
        """dissolve zero area faces and zero length edges"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.dissolve_degenerate(threshold=threshold)


class MESH_OT_print3d_clean_doubles(Operator):
    bl_idname = "mesh.print3d_clean_doubles"
    bl_label = "Remove Doubles"
    bl_description = "Remove duplicate vertices"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: FloatProperty(
        name="Merge Distance",
        description="Minimum distance between elements to merge",
        default=0.01,
        step=1
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.remove_doubles(self.threshold)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def remove_doubles(threshold):
        """select all vertices and remove duplicated ones"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=threshold)



class MESH_OT_print3d_clean_loose(Operator):
    bl_idname = "mesh.print3d_clean_loose"
    bl_label = "Delete Loose"
    bl_description = "Delete unconnected ('loose') vertices, edges or faces"
    bl_options = {'REGISTER', 'UNDO'}

    use_verts: BoolProperty(
        name="Vertices",
        description="Remove loose vertices",
        default=True
    )

    use_edges: BoolProperty(
        name="Edges",
        description="Remove loose edges",
        default=True
    )

    use_faces: BoolProperty(
        name="Faces",
        description="Remove loose faces",
        default=True
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.delete_loose(self.use_verts, self.use_edges, self.use_faces)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def delete_loose(use_verts, use_edges, use_faces):
        #"""delete loose vertices, edges or faces"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete_loose(use_verts=use_verts, use_edges=use_edges, use_faces=use_faces)



class MESH_OT_print3d_clean_non_planars(Operator):
    bl_idname = "mesh.print3d_clean_non_planars"
    bl_label = "Split Non Planar Faces"
    bl_description = "Split non-planar faces that exceed the angle threshold"
    bl_options = {'REGISTER', 'UNDO'}

    angle_threshold: FloatProperty(
        name="Max Angle",
        description="Angle limit",
        default=0.174533,
        subtype="ANGLE",
        unit="ROTATION",
        step=10
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.clean_non_planars(self.angle_threshold)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def clean_non_planars(angle_limit):
        #"""split non-planar faces that exceed the angle threshold"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vert_connect_nonplanar(angle_limit=angle_limit)
        # bpy.ops.ui.reports_to_textblock()


class MESH_OT_print3d_clean_concaves(Operator):
    bl_idname = "mesh.print3d_clean_concaves"
    bl_label = "Split Concave Faces"
    bl_description = "Make all faces convex"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.clean_concaves()

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def clean_concaves():
        #"""make all faces convex"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vert_connect_concave()


class MESH_OT_print3d_clean_triangulates(Operator):
    bl_idname = "mesh.print3d_clean_triangulates"
    bl_label = "Triangulate Faces"
    bl_description = "Triangulate selected faces"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        bpy.ops.mesh.quads_convert_to_tris()

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}



class MESH_OT_print3d_clean_holes(Operator):
    bl_idname = "mesh.print3d_clean_holes"
    bl_label = "Fill Holes"
    bl_description = "Fill in holes (boundary edge loops)"
    bl_options = {'REGISTER', 'UNDO'}

    sides: IntProperty(
        name="Sides",
        description="Number of sides in hole required to fill (zero fills all holes)",
        default=4,
        step=1
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.fill_holes(self.sides)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def fill_holes(sides):
        #"""fill in holes (boundary edge loops)"""
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.fill_holes(sides=sides)



class MESH_OT_print3d_clean_limited(Operator):
    bl_idname = "mesh.print3d_clean_limited"
    bl_label = "Limited Dissolve"
    bl_description = "Dissolve selected edges and verts, limited by the angle of surrounding geometry"
    bl_options = {'REGISTER', 'UNDO'}

    angle_threshold: FloatProperty(
        name="Max Angle",
        description="Angle limit",
        default=0.0872665,
        subtype="ANGLE",
        unit="ROTATION",
        step=10
    )

    use_boundaries: BoolProperty(
        name="All Boundaries",
        description="Dissolve all vertices in between face boundaries",
        default=False
    )

    def execute(self, context):
        context = bpy.context
        self.context = context
        mode_orig = context.mode

        setup_environment()

        bm_key_orig = elem_count(context)

        self.limited_dissolve(self.angle_threshold, self.use_boundaries)

        bm_key = elem_count(context)

        if mode_orig != 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        self.report(
            {'INFO'},
            "Modified Verts:%+d, Edges:%+d, Faces:%+d" %
            (bm_key[0] - bm_key_orig[0],
             bm_key[1] - bm_key_orig[1],
             bm_key[2] - bm_key_orig[2]
            ))

        return {'FINISHED'}

    @staticmethod
    def limited_dissolve(angle, use_boundaries):
        #"""dissolve selected edges and verts, limited by the angle of surrounding geometry"""
        bpy.ops.mesh.dissolve_limited(angle_limit=angle, use_dissolve_boundaries=use_boundaries, delimit={'NORMAL'})




'''
# ------------------------------------
# Make Solid from selected objects

class MESH_OT_print3d_merge_selected_into_single_solid(Operator):
    """Combine selected objects into one"""
    bl_idname = "object.make_solid"
    bl_label = "Make Solid"
    bl_options = {'REGISTER', 'UNDO'}

    mode: 'UNION'

    def execute(self, context):
        active = context.view_layer.objects.active
        selected = context.selected_objects

        if active is None or len(selected) < 2:
            self.report({'WARNING'}, "Select at least 2 objects")
            return {'CANCELLED'}
        else:
            #mesh_helpers.prepare_meshes()
            #mesh_helpers.make_solid_batch()
            #mesh_helpers.is_manifold(self)

        return {'FINISHED'}        

'''
# -------------
# Select Report
# ... helper function for info UI

class MESH_OT_print3d_select_report(Operator):
    bl_idname = "mesh.print3d_select_report"
    bl_label = "3D-Print Select Report"
    bl_description = "Select the data associated with this report"
    bl_options = {'INTERNAL'}

    index: IntProperty()

    _type_to_mode = {
        bmesh.types.BMVert: 'VERT',
        bmesh.types.BMEdge: 'EDGE',
        bmesh.types.BMFace: 'FACE',
    }

    _type_to_attr = {
        bmesh.types.BMVert: "verts",
        bmesh.types.BMEdge: "edges",
        bmesh.types.BMFace: "faces",
    }

    def execute(self, context):
        obj = context.edit_object
        info = report.info()
        _text, data, cls = info[self.index]
        bm_type, bm_array = data

        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type=self._type_to_mode[bm_type])

        bm = bmesh.from_edit_mesh(obj.data)
        elems = getattr(bm, MESH_OT_print3d_select_report._type_to_attr[bm_type])[:]

        try:
            for i in bm_array:
                elems[i].select_set(True)
        except:
            # possible arrays are out of sync
            self.report({'WARNING'}, "Report is out of date, re-run check")

        return {'FINISHED'}

class MESH_OT_print3d_trigger_clean(Operator):
    bl_idname = "mesh.print3d_trigger_clean"
    bl_label = "3D-Print Trigger Clean"
    bl_description = "Fix the issues associated with this report"
    bl_options = {'INTERNAL'}

    index: IntProperty()


    use_export_texture: BoolProperty(
        name="Copy Textures",
        description="Copy textures on export to the output path",
        default=False,
    )
    use_apply_scale: BoolProperty(
        name="Apply Scale",
        description="Apply scene scale setting on export",
        default=False,
    )
    export_path: StringProperty(
        name="Export Directory",
        description="Path to directory where the files are created",
        default="//",
        maxlen=1024,
        subtype="DIR_PATH",
    )
    thickness_min: FloatProperty(
        name="Thickness",
        description="Minimum thickness",
        subtype='DISTANCE',
        default=0.001,  # 1mm
        min=0.0,
        max=10.0,
    )
    threshold_zero: FloatProperty(
        name="Threshold",
        description="Limit for checking zero area/length",
        default=0.01,
        precision=5,
        min=0.0,
        max=0.2,
    )
    angle_distort: FloatProperty(
        name="Angle",
        description="Limit for checking distorted faces",
        subtype='ANGLE',
        default=math.radians(45.0),
        min=0.0,
        max=math.radians(180.0),
    )
    angle_sharp: FloatProperty(
        name="Angle",
        subtype='ANGLE',
        default=math.radians(160.0),
        min=0.0,
        max=math.radians(180.0),
    )
    angle_overhang: FloatProperty(
        name="Angle",
        subtype='ANGLE',
        default=math.radians(45.0),
        min=0.0,
        max=math.radians(90.0),
    )

    _type_to_mode = {
        bmesh.types.BMVert: 'VERT',
        bmesh.types.BMEdge: 'EDGE',
        bmesh.types.BMFace: 'FACE',
    }

    _type_to_attr = {
        bmesh.types.BMVert: "verts",
        bmesh.types.BMEdge: "edges",
        bmesh.types.BMFace: "faces",
    }

    def execute(self, context):
        obj = context.edit_object
        info = report.info()
        _text, data, cls = info[self.index]
        bm_type, bm_array = data

        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type=self._type_to_mode[bm_type])

        bm = bmesh.from_edit_mesh(obj.data)
        elems = getattr(bm, MESH_OT_print3d_select_report._type_to_attr[bm_type])[:]



        try:
            for i in bm_array:
                elems[i].select_set(True)
            try:
                cls.execute(self, context)
            #except Exception as e:
            except:
                #self.report({'WARNING'}, )
                error_message = traceback.format_exc()
                self.report({'WARNING'}, "Unable to trigger cleaner function: " + error_message)

        except:
            # possible arrays are out of sync
            self.report({'WARNING'}, "Report is out of date, re-run check")

        return {'FINISHED'}







# -----------
# Scale to...

def _scale(scale, report=None, report_suffix=""):
    if scale != 1.0:
        bpy.ops.transform.resize(value=(scale,) * 3)
    if report is not None:
        scale_fmt = clean_float(f"{scale:.6f}")
        report({'INFO'}, f"Scaled by {scale_fmt}{report_suffix}")


class MESH_OT_print3d_scale_to_volume(Operator):
    bl_idname = "mesh.print3d_scale_to_volume"
    bl_label = "Scale to Volume"
    bl_description = "Scale edit-mesh or selected-objects to a set volume"
    bl_options = {'REGISTER', 'UNDO'}

    volume_init: FloatProperty(
        options={'HIDDEN'},
    )
    volume: FloatProperty(
        name="Volume",
        unit='VOLUME',
        min=0.0,
        max=100000.0,
    )

    def execute(self, context):
        scale = math.pow(self.volume, 1 / 3) / math.pow(self.volume_init, 1 / 3)
        scale_fmt = clean_float(f"{scale:.6f}")
        self.report({'INFO'}, f"Scaled by {scale_fmt}")
        _scale(scale, self.report)
        return {'FINISHED'}

    def invoke(self, context, event):

        def calc_volume(obj):
            bm = mesh_helpers.bmesh_copy_from_object(obj, apply_modifiers=True)
            volume = bm.calc_volume(signed=True)
            bm.free()
            return volume

        if context.mode == 'EDIT_MESH':
            volume = calc_volume(context.edit_object)
        else:
            volume = sum(calc_volume(obj) for obj in context.selected_editable_objects if obj.type == 'MESH')

        if volume == 0.0:
            self.report({'WARNING'}, "Object has zero volume")
            return {'CANCELLED'}

        self.volume_init = self.volume = abs(volume)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class MESH_OT_print3d_scale_to_bounds(Operator):
    bl_idname = "mesh.print3d_scale_to_bounds"
    bl_label = "Scale to Bounds"
    bl_description = "Scale edit-mesh or selected-objects to fit within a maximum length"
    bl_options = {'REGISTER', 'UNDO'}

    length_init: FloatProperty(
        options={'HIDDEN'},
    )
    axis_init: IntProperty(
        options={'HIDDEN'},
    )
    length: FloatProperty(
        name="Length Limit",
        unit='LENGTH',
        min=0.0,
        max=100000.0,
    )

    def execute(self, context):
        scale = self.length / self.length_init
        axis = "XYZ"[self.axis_init]
        _scale(scale, report=self.report, report_suffix=f", Clamping {axis}-Axis")
        return {'FINISHED'}

    def invoke(self, context, event):
        from mathutils import Vector

        def calc_length(vecs):
            return max(((max(v[i] for v in vecs) - min(v[i] for v in vecs)), i) for i in range(3))

        if context.mode == 'EDIT_MESH':
            length, axis = calc_length(
                [Vector(v) @ obj.matrix_world for obj in [context.edit_object] for v in obj.bound_box]
            )
        else:
            length, axis = calc_length(
                [
                    Vector(v) @ obj.matrix_world for obj in context.selected_editable_objects
                    if obj.type == 'MESH'
                    for v in obj.bound_box
                ]
            )

        if length == 0.0:
            self.report({'WARNING'}, "Object has zero bounds")
            return {'CANCELLED'}

        self.length_init = self.length = length
        self.axis_init = axis

        wm = context.window_manager
        return wm.invoke_props_dialog(self)


# ------
# Export

class MESH_OT_print3d_export(Operator):
    bl_idname = "mesh.print3d_export"
    bl_label = "3D-Print Export"
    bl_description = "Export selected objects using 3D-Print settings"

    def execute(self, context):
        from . import export

        ret = export.write_mesh(context, self.report)

        if ret:
            return {'FINISHED'}

        return {'CANCELLED'}
