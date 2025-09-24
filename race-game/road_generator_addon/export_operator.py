"""
Export operator for road segments with collision
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty


class MESH_OT_export_road_segments(Operator):
    """Export all road segments, each with its collision objects in a single FBX file"""
    bl_idname = "mesh.export_road_segments"
    bl_label = "Export Road Segments"
    bl_description = "Export each road segment with its UCX collision objects as a single FBX file"
    bl_options = {'REGISTER', 'UNDO'}
    
    def get_road_segments(self, context):
        """Find all road segments in the scene"""
        segments = {}
        settings = context.scene.road_generator_settings
        prefix = settings.collision_prefix
        
        for obj in bpy.data.objects:
            # Skip collision objects (UCX prefix)
            if obj.name.startswith(prefix + "_"):
                continue
                
            # Check if it's a road segment (ends with _seg<number>)
            if "_seg" in obj.name and obj.type == 'MESH':
                # Extract base name and segment number
                parts = obj.name.rsplit("_seg", 1)
                if len(parts) == 2:
                    base_name = parts[0]
                    try:
                        seg_num = int(parts[1])
                        if base_name not in segments:
                            segments[base_name] = {}
                        if seg_num not in segments[base_name]:
                            segments[base_name][seg_num] = {
                                'mesh': None,
                                'collisions': []
                            }
                        segments[base_name][seg_num]['mesh'] = obj
                    except ValueError:
                        continue
        
        return segments
    
    def get_collision_objects(self, context, road_base_name, seg_num):
        """Find collision objects for a specific road segment"""
        settings = context.scene.road_generator_settings
        prefix = settings.collision_prefix
        collision_objects = []
        
        # Look for collision objects with matching pattern
        search_patterns = [
            f"{prefix}_{road_base_name}_seg{seg_num}_",  # For separated collision boxes
            f"{prefix}_{road_base_name}_seg{seg_num}"     # For non-separated collision
        ]
        
        for obj in bpy.data.objects:
            for pattern in search_patterns:
                if obj.name.startswith(pattern) and obj.type == 'MESH':
                    collision_objects.append(obj)
                    break
        
        return collision_objects
    
    def export_segment_with_collision(self, segment_obj, collision_objs, export_path, export_scale):
        """Export a road segment with its collision objects in a single FBX file"""
        # Store current selection
        original_selection = bpy.context.selected_objects.copy()
        original_active = bpy.context.view_layer.objects.active
        
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select the segment and ALL its collision objects together
        segment_obj.select_set(True)
        for col_obj in collision_objs:
            col_obj.select_set(True)
        
        bpy.context.view_layer.objects.active = segment_obj
        
        # Generate filename using just the segment name
        filename = f"{segment_obj.name}.fbx"
        filepath = os.path.join(export_path, filename)
        
        # Export FBX
        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                use_active_collection=False,
                global_scale=export_scale,
                apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_NONE',
                bake_space_transform=False,
                object_types={'MESH'},
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=True,
                mesh_smooth_type='OFF',
                use_subsurf=False,
                use_mesh_edges=False,
                use_tspace=False,
                use_custom_props=False,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=False,
                armature_nodetype='NULL',
                bake_anim=False,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=False,
                use_metadata=True
            )
            print(f"Exported: {filename} (1 segment + {len(collision_objs)} collision objects in single FBX)")
            return True
        except Exception as e:
            print(f"Error exporting {filename}: {str(e)}")
            return False
        finally:
            # Restore original selection
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                if obj.name in bpy.data.objects:
                    bpy.data.objects[obj.name].select_set(True)
            
            if original_active and original_active.name in bpy.data.objects:
                bpy.context.view_layer.objects.active = bpy.data.objects[original_active.name]
    
    def execute(self, context):
        settings = context.scene.road_generator_settings
        
        # Get export path
        export_path = bpy.path.abspath(settings.export_path)
        if not export_path or export_path == "//":
            # Use blend file directory if not specified
            blend_filepath = bpy.data.filepath
            if blend_filepath:
                export_path = os.path.join(os.path.dirname(blend_filepath), "RoadExports")
            else:
                self.report({'ERROR'}, "Please save the blend file or specify an export path")
                return {'CANCELLED'}
        
        # Create export directory if it doesn't exist
        os.makedirs(export_path, exist_ok=True)
        
        # Find all road segments
        segments = self.get_road_segments(context)
        
        if not segments:
            self.report({'ERROR'}, "No road segments found to export")
            return {'CANCELLED'}
        
        exported_count = 0
        total_segments = sum(len(segs) for segs in segments.values())
        
        # Export each segment with its collision
        for road_base_name, road_segments in segments.items():
            for seg_num, seg_data in sorted(road_segments.items()):
                if seg_data['mesh']:
                    # Find collision objects for this segment
                    collision_objs = self.get_collision_objects(context, road_base_name, seg_num)
                    
                    # Export the segment with collision
                    if self.export_segment_with_collision(
                        seg_data['mesh'], 
                        collision_objs, 
                        export_path,
                        settings.export_scale
                    ):
                        exported_count += 1
        
        self.report({'INFO'}, f"Exported {exported_count} FBX files to {export_path}")
        self.report({'INFO'}, f"Each FBX contains one segment with all its collision objects")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(MESH_OT_export_road_segments)

def unregister():
    bpy.utils.unregister_class(MESH_OT_export_road_segments)
