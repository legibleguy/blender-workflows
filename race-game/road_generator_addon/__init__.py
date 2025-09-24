"""
Road Generator Addon for Blender
Automates road generation workflow with splitting, collision generation, and export
"""

bl_info = {
    "name": "Road Generator",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Road Generator",
    "description": "Generate and export road segments with collision for game engines",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

import bpy
from bpy.props import (
    IntProperty, 
    FloatProperty, 
    StringProperty, 
    BoolProperty,
    EnumProperty,
    PointerProperty
)
from bpy.types import (
    Panel,
    PropertyGroup,
    Operator,
    AddonPreferences
)

# Import operator modules
from . import road_split_operator
from . import collision_gen_operator
from . import export_operator
from . import node_loader
from . import utils


class RoadGeneratorPreferences(AddonPreferences):
    bl_idname = __name__

    default_export_path: StringProperty(
        name="Default Export Path",
        description="Default path for exporting FBX files",
        subtype='DIR_PATH',
        default="//"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "default_export_path")


class RoadGeneratorSettings(PropertyGroup):
    """Property group for addon settings"""
    
    # Road splitting settings
    num_divisions: IntProperty(
        name="Number of Divisions",
        description="Number of road segments to create",
        default=10,
        min=1,
        max=100
    )
    
    len_attr_name: StringProperty(
        name="Length Attribute",
        description="Name of the vertex float attribute for length",
        default="Len"
    )
    
    # Smart UV unwrap settings
    enable_smart_uv: BoolProperty(
        name="Enable Smart UV",
        description="Create Smart UV unwrap for each segment",
        default=True
    )
    
    smart_uv_angle_limit: FloatProperty(
        name="Angle Limit",
        description="Maximum angle between faces for Smart UV grouping",
        default=66.0,
        min=1.0,
        max=89.0,
        subtype='ANGLE'
    )
    
    smart_uv_island_margin: FloatProperty(
        name="Island Margin",
        description="Space between UV islands",
        default=0.02,
        min=0.0,
        max=1.0
    )
    
    smart_uv_area_weight: FloatProperty(
        name="Area Weight",
        description="Weight factor for face areas",
        default=0.0,
        min=0.0,
        max=1.0
    )
    
    # Collision generation settings
    solidify_thickness: FloatProperty(
        name="Collision Thickness",
        description="Thickness of solidify modifier for collision",
        default=0.05,
        min=0.001,
        max=10.0
    )
    
    collision_prefix: StringProperty(
        name="Collision Prefix",
        description="Prefix for collision objects (Unreal uses UCX)",
        default="UCX"
    )
    
    separate_collision_boxes: BoolProperty(
        name="Separate Collision Boxes",
        description="Separate each collision box into individual objects",
        default=True
    )
    
    # Export settings
    export_path: StringProperty(
        name="Export Path",
        description="Path for exporting FBX files",
        subtype='DIR_PATH',
        default="//"
    )
    
    export_scale: FloatProperty(
        name="Export Scale",
        description="Scale factor for FBX export",
        default=1.0,
        min=0.001,
        max=1000.0
    )
    
    # Node template settings
    road_node_group: StringProperty(
        name="Road Node Group",
        description="Name of the geometry node group for roads",
        default="road"
    )
    
    collision_node_group: StringProperty(
        name="Collision Node Group",
        description="Name of the geometry node group for collision",
        default="road_collision"
    )


class MESH_OT_generate_complete_road(Operator):
    """Generate complete road with collision from selected curve"""
    bl_idname = "mesh.generate_complete_road"
    bl_label = "Generate Complete Road"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'CURVE'
    
    def execute(self, context):
        settings = context.scene.road_generator_settings
        original_curve = context.active_object
        
        # Step 1: Split the road
        bpy.ops.mesh.split_road()
        
        # Step 2: Create collision curve
        # Duplicate the original curve
        bpy.context.view_layer.objects.active = original_curve
        original_curve.select_set(True)
        bpy.ops.object.duplicate()
        collision_curve = context.active_object
        collision_curve.name = f"UCX_{original_curve.name}"
        
        # Apply collision node group if available
        if settings.collision_node_group in bpy.data.node_groups:
            utils.apply_geometry_nodes(collision_curve, settings.collision_node_group)
        
        # Step 3: Generate collision objects
        bpy.ops.mesh.generate_collision()
        
        self.report({'INFO'}, "Road and collision generated successfully")
        return {'FINISHED'}


class MESH_OT_load_node_templates(Operator):
    """Load geometry node templates from addon"""
    bl_idname = "mesh.load_road_node_templates"
    bl_label = "Load Node Templates"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        loaded = node_loader.load_node_templates()
        if loaded:
            self.report({'INFO'}, f"Loaded {len(loaded)} node templates")
        else:
            self.report({'WARNING'}, "No node templates loaded")
        return {'FINISHED'}


class MESH_OT_cleanup_road_segments(Operator):
    """Remove all road segments and collision objects"""
    bl_idname = "mesh.cleanup_road_segments"
    bl_label = "Cleanup Segments"
    bl_description = "Remove all road segments and UCX collision objects from the scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.road_generator_settings
        prefix = settings.collision_prefix
        
        objects_to_remove = []
        segment_count = 0
        collision_count = 0
        
        # Find all objects to remove
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                # Check if it's a collision object
                if obj.name.startswith(prefix + "_"):
                    objects_to_remove.append(obj)
                    collision_count += 1
                # Check if it's a road segment
                elif "_seg" in obj.name:
                    parts = obj.name.rsplit("_seg", 1)
                    if len(parts) == 2:
                        try:
                            int(parts[1])  # Verify it ends with a number
                            objects_to_remove.append(obj)
                            segment_count += 1
                        except ValueError:
                            pass
        
        # Remove all found objects
        for obj in objects_to_remove:
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Clean up orphaned mesh data
        removed_meshes = 0
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
                removed_meshes += 1
        
        self.report({'INFO'}, f"Removed {segment_count} segments and {collision_count} collision objects")
        if removed_meshes > 0:
            self.report({'INFO'}, f"Cleaned up {removed_meshes} unused mesh data blocks")
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Show confirmation dialog
        return context.window_manager.invoke_confirm(self, event)


class VIEW3D_PT_road_generator(Panel):
    """Main panel for Road Generator addon"""
    bl_label = "Road Generator"
    bl_idname = "VIEW3D_PT_road_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Road Gen"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.road_generator_settings
        
        # Node Templates section
        box = layout.box()
        box.label(text="Node Templates", icon='NODETREE')
        box.operator("mesh.load_road_node_templates", icon='IMPORT')
        
        # Generation section
        box = layout.box()
        box.label(text="Road Generation", icon='MESH_DATA')
        
        col = box.column(align=True)
        col.prop(settings, "num_divisions")
        col.prop(settings, "len_attr_name")
        
        col.separator()
        col.prop(settings, "road_node_group")
        col.prop(settings, "collision_node_group")
        
        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("mesh.generate_complete_road", icon='AUTO')
        
        # Individual operations
        box = layout.box()
        box.label(text="Individual Operations", icon='MODIFIER')
        
        col = box.column(align=True)
        col.operator("mesh.split_road", icon='MESH_GRID')
        col.operator("mesh.generate_collision", icon='PHYSICS')
        
        # UV Settings
        box = layout.box()
        box.label(text="UV Settings", icon='UV')
        col = box.column(align=True)
        col.prop(settings, "enable_smart_uv")
        
        if settings.enable_smart_uv:
            col.separator()
            col.prop(settings, "smart_uv_angle_limit")
            col.prop(settings, "smart_uv_island_margin")
            col.prop(settings, "smart_uv_area_weight")
        
        # Collision settings
        box = layout.box()
        box.label(text="Collision Settings", icon='PHYSICS')
        col = box.column(align=True)
        col.prop(settings, "solidify_thickness")
        col.prop(settings, "collision_prefix")
        col.prop(settings, "separate_collision_boxes")
        
        # Export section
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        
        col = box.column(align=True)
        col.prop(settings, "export_path")
        col.prop(settings, "export_scale")
        
        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("mesh.export_road_segments", text="Export All Segments", icon='EXPORT')
        
        # Cleanup section
        box = layout.box()
        box.label(text="Cleanup", icon='TRASH')
        
        row = box.row()
        row.scale_y = 1.2
        row.operator("mesh.cleanup_road_segments", text="Remove All Segments", icon='CANCEL')
        row.alert = True  # Make the button appear in red/alert color


classes = [
    RoadGeneratorPreferences,
    RoadGeneratorSettings,
    MESH_OT_generate_complete_road,
    MESH_OT_load_node_templates,
    MESH_OT_cleanup_road_segments,
    VIEW3D_PT_road_generator,
]

def register():
    # Register classes
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register operator modules
    road_split_operator.register()
    collision_gen_operator.register()
    export_operator.register()
    
    # Add property group to scene
    bpy.types.Scene.road_generator_settings = PointerProperty(type=RoadGeneratorSettings)
    
    print("Road Generator Addon registered")

def unregister():
    # Unregister operator modules
    export_operator.unregister()
    collision_gen_operator.unregister()
    road_split_operator.unregister()
    
    # Remove property group from scene
    del bpy.types.Scene.road_generator_settings
    
    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    print("Road Generator Addon unregistered")

if __name__ == "__main__":
    register()
