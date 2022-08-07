#====================== BEGIN GPL LICENSE BLOCK ======================
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
#======================= END GPL LICENSE BLOCK ========================

from mathutils import *
from bpy.props import *
import bpy
import bmesh
import math
from mathutils.bvhtree import BVHTree

# Version history
# 1.0.0 - 2021-07-15: Original version. 
# 1.0.1 - 2021-12-03: Fixed bug that kept showing up in console when no object was selected.
# 1.0.2 - 2022-04-28: Added a comment about bl_options = {"REGISTER", "UNDO"}
# 1.0.3 - 2022-06-22: Moved the add-on to a "Modeling" tab (it used to be in "Animation", which makes no sense).
# 1.0.4 - 2022-08-07: Misc formatting cleanup before uploading to GitHub.

###############################################################################
SCRIPT_NAME = 'shrinkwrap_without_touching'

# This Blender add-on creates (and possibly applies) a Shrinkwrap modifier at
# the lowest possible setting so that it doesn't touch the object it's
# shrinkwrapped around.
# To use this, select the object that needs the shrinkwrap and fill in the
# parameters in the add-on.
###############################################################################

bl_info = {
    "name": "Shrinkwrap without Touching",
    "author": "Jeff Boller",
    "version": (1, 0, 4),
    "blender": (2, 93, 0),
    "location": "View3D > Properties > Modeling",
    "description": "Creates (and possibly applies) a Shrinkwrap modifier at the lowest possible setting so that it doesn't touch the object it's shrinkwrapped around.",
    "wiki_url": "https://github.com/sundriftproductions/blenderaddon-shrinkwrap-without-touching/wiki",
    "tracker_url": "https://github.com/sundriftproductions/blenderaddon-shrinkwrap-without-touching",
    "category": "3D View"}

def select_name( name = "", extend = True ):
    if extend == False:
        bpy.ops.object.select_all(action='DESELECT')
    ob = bpy.data.objects.get(name)
    ob.select_set(state=True)
    bpy.context.view_layer.objects.active = ob

class SHRINKWRAPWITHOUTTOUCHING_PT_CreateShrinkwrapModifier(bpy.types.Operator):
    bl_idname = "swt.create_shrinkwrap_modifier"
    bl_label = "Create Shrinkwrap Modifier"
    bl_options = {"REGISTER", "UNDO"}  # Required for when we do a bpy.ops.ed.undo_push(), otherwise Blender will crash when you try to undo the action in this class.

    def create_shrinkwrap_modifier(self, offset):
        bpy.ops.object.modifier_add(type='SHRINKWRAP')
        index = len(bpy.context.active_object.modifiers) - 1
        bpy.context.active_object.modifiers[index].wrap_method = 'NEAREST_SURFACEPOINT'
        bpy.context.active_object.modifiers[index].wrap_mode = 'OUTSIDE_SURFACE'
        bpy.context.active_object.modifiers[index].target = bpy.data.objects[
            bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.target_name]
        if len(bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.vertex_group_name) > 0:
            bpy.context.active_object.modifiers[index].vertex_group = bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.vertex_group_name
            bpy.context.active_object.modifiers[index].invert_vertex_group = bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.invert_group_influence
        bpy.context.active_object.modifiers[index].offset = offset
        return index

    def intersection_check(self, obj_list):
        objectsTouching = False
        # check every object for intersection with every other object
        for obj_now in obj_list:
            for obj_next in obj_list:
                print()
                if obj_now == obj_next:
                    continue

                # create bmesh objects
                bm1 = bmesh.new()
                bm2 = bmesh.new()

                # fill bmesh data from objects
                bm1.from_mesh(bpy.context.scene.objects[obj_now].data)
                bm2.from_mesh(bpy.context.scene.objects[obj_next].data)

                # fixed it here:
                bm1.transform(bpy.context.scene.objects[obj_now].matrix_world)
                bm2.transform(bpy.context.scene.objects[obj_next].matrix_world)

                # make BVH tree from BMesh of objects
                obj_now_BVHtree = BVHTree.FromBMesh(bm1)
                obj_next_BVHtree = BVHTree.FromBMesh(bm2)

                # get intersecting pairs
                inter = obj_now_BVHtree.overlap(obj_next_BVHtree)

                # if list is empty, no objects are touching
                if inter != []:
                    objectsTouching = True

        return objectsTouching

    def execute(self, context):
        self.report({'INFO'}, '**********************************')
        self.report({'INFO'}, SCRIPT_NAME + ' - START')

        mode = bpy.context.active_object.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        offset = 0

        obj_list = [bpy.context.active_object.name, bpy.data.objects[bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.target_name].name]

        iterations = 0
        foundGoodOffset = False

        while iterations < 20:
            iterations += 1

            index = self.create_shrinkwrap_modifier(offset)

            bpy.ops.ed.undo_push() # Manually record that when we do an undo, we want to go back to this exact state.
            bpy.ops.object.modifier_apply(modifier=bpy.context.active_object.modifiers[index].name, report=True)

            if not self.intersection_check(obj_list):
                foundGoodOffset = True
                self.report({'INFO'}, 'NOT intersecting -- found good offset: ' + str(offset))
                bpy.ops.ed.undo()
                break
            else:
                offset += 0.01
                self.report({'INFO'}, 'Intersecting -- going to try with offset ' + str(offset))
                bpy.ops.ed.undo()

        if foundGoodOffset:
            index = self.create_shrinkwrap_modifier(offset)
            if bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences.apply_shrinkwrap:
                bpy.ops.ed.undo_push()  # Manually record that when we do an undo, we want to go back to this exact state.
                bpy.ops.object.modifier_apply(modifier=bpy.context.active_object.modifiers[index].name, report=True)
        else:
            self.report({'ERROR'}, 'Could not find good offset.')

        # Go back to whatever mode we were in.
        bpy.ops.object.mode_set(mode=mode)

        self.report({'INFO'}, SCRIPT_NAME + ' - END')
        self.report({'INFO'}, '**********************************')
        self.report({'INFO'}, 'Done running script ' + SCRIPT_NAME)

        return {'FINISHED'}

class DuplicateCyclePreferencesPanel(bpy.types.AddonPreferences):
    bl_idname = __module__
    target_name: bpy.props.StringProperty(name='Target', default='', description='Target mesh to shrink to')
    vertex_group_name: bpy.props.StringProperty(name='Vertex Group', default='', description='Vertex group name')
    invert_group_influence: bpy.props.BoolProperty(name='', description="Invert vertex group influence", default=False)
    apply_shrinkwrap: bpy.props.BoolProperty(name = "Apply Shrinkwrap", description = "After the modifier is created, apply it immediately", default = True)

    def draw(self, context):
        self.layout.label(text="Current values")

class SHRINKWRAPWITHOUTTOUCHING_PT_Main(bpy.types.Panel):
    bl_idname = "SHRINKWRAPWITHOUTTOUCHING_PT_Main"
    bl_label = "Shrinkwrap without Touching"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Modeling"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.label(text="Object that will get Shrinkwrap modifier:")
        row = self.layout.row(align=True)
        name = '(none)'

        try:
            name = str(bpy.context.active_object.name)
        except:
            pass

        row.label(text=name)

        row = self.layout.row(align=True)
        row.prop_search(bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences, "target_name", bpy.data, "objects", icon='OBJECT_DATA')

        row = self.layout.row(align=True)

        try:
            row.prop_search(bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences, "vertex_group_name", bpy.context.active_object, "vertex_groups", icon='GROUP_VERTEX')
        except:
            pass

        row.prop(bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences, "invert_group_influence", icon='ARROW_LEFTRIGHT')

        row = self.layout.row(align=True)
        row.prop(bpy.context.preferences.addons['shrinkwrap_without_touching'].preferences, "apply_shrinkwrap")

        row = self.layout.row(align=True)
        row = self.layout.row(align=True)
        self.layout.operator("swt.create_shrinkwrap_modifier",icon='MOD_SHRINKWRAP')

def register():
    bpy.utils.register_class(SHRINKWRAPWITHOUTTOUCHING_PT_Main)
    bpy.utils.register_class(DuplicateCyclePreferencesPanel)
    bpy.utils.register_class(SHRINKWRAPWITHOUTTOUCHING_PT_CreateShrinkwrapModifier)

def unregister():
    bpy.utils.unregister_class(SHRINKWRAPWITHOUTTOUCHING_PT_CreateShrinkwrapModifier)
    bpy.utils.unregister_class(DuplicateCyclePreferencesPanel)
    bpy.utils.unregister_class(SHRINKWRAPWITHOUTTOUCHING_PT_Main)

if __name__ == "__main__":
    register()
