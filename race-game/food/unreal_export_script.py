import bpy
import os
from mathutils import Vector

def create_unreal_export_collection():
    """Create or get the 'Unreal Export' collection"""
    collection_name = "Unreal Export"
    
    # Check if collection already exists
    if collection_name in bpy.data.collections:
        unreal_collection = bpy.data.collections[collection_name]
        # Clear existing objects from the collection
        for obj in unreal_collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        # Create new collection
        unreal_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(unreal_collection)
    
    return unreal_collection

def reset_origin_to_geometry_center(obj):
    """Reset object origin to geometry center"""
    # Make sure object is selected and active
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # Set origin to geometry center
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

def move_object_to_scene_center(obj):
    """Move object to the center of the scene (0, 0, 0)"""
    obj.location = Vector((0.0, 0.0, 0.0))

def duplicate_and_process_objects():
    """Main function to duplicate objects and process them"""
    # Get the main collection
    main_collection = bpy.data.collections.get("Collection")
    if not main_collection:
        print("Error: 'Collection' not found in the scene")
        return []
    
    # Create or get the Unreal Export collection
    unreal_collection = create_unreal_export_collection()
    
    # Store original objects to avoid processing duplicates
    original_objects = list(main_collection.objects)
    processed_objects = []
    
    for obj in original_objects:
        # Only process mesh objects
        if obj.type == 'MESH':
            # Duplicate the object
            obj_copy = obj.copy()
            obj_copy.data = obj.data.copy()
            
            # Clean the original name and create SM_ prefixed name
            original_name = obj.name
            # Remove any .001, .002, etc. suffixes that Blender might have added
            if '.' in original_name and original_name.split('.')[-1].isdigit():
                clean_name = '.'.join(original_name.split('.')[:-1])
            else:
                clean_name = original_name
            
            # Set the new name with SM_ prefix
            new_name = f"SM_{clean_name}"
            obj_copy.name = new_name
            
            # Add to Unreal Export collection
            unreal_collection.objects.link(obj_copy)
            
            # Deselect all objects first
            bpy.ops.object.select_all(action='DESELECT')
            
            # Reset origin to geometry center
            reset_origin_to_geometry_center(obj_copy)
            
            # Move to scene center
            move_object_to_scene_center(obj_copy)
            
            processed_objects.append(obj_copy)
            print(f"Processed object: {original_name} -> {obj_copy.name}")
    
    return processed_objects

def export_objects_as_fbx(objects, export_path):
    """Export each object as individual FBX file"""
    if not objects:
        print("No objects to export")
        return
    
    # Create export directory if it doesn't exist
    os.makedirs(export_path, exist_ok=True)
    
    # Store current selection
    original_selection = bpy.context.selected_objects.copy()
    original_active = bpy.context.view_layer.objects.active
    
    for obj in objects:
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select only the current object
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        
        # Generate filename with SM_ prefix
        filename = f"SM_{obj.name}.fbx"
        filepath = os.path.join(export_path, filename)
        
        # Export FBX
        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                use_active_collection=False,
                global_scale=1.0,
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
                add_leaf_bones=True,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=False,
                armature_nodetype='NULL',
                bake_anim=True,
                bake_anim_use_all_bones=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=1.0,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=True,
                use_metadata=True
            )
            print(f"Exported: {filename}")
        except Exception as e:
            print(f"Error exporting {filename}: {str(e)}")
    
    # Restore original selection
    bpy.ops.object.select_all(action='DESELECT')
    for obj in original_selection:
        if obj.name in bpy.data.objects:
            bpy.data.objects[obj.name].select_set(True)
    
    if original_active and original_active.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = bpy.data.objects[original_active.name]

def main():
    """Main execution function"""
    print("Starting Unreal Export process...")
    
    # Get the directory where the blend file is located
    blend_filepath = bpy.data.filepath
    if blend_filepath:
        export_directory = os.path.join(os.path.dirname(blend_filepath), "UnrealExports")
    else:
        # If blend file is not saved, use a default directory
        export_directory = "/tmp/UnrealExports"
    
    print(f"Export directory: {export_directory}")
    
    # Process objects
    processed_objects = duplicate_and_process_objects()
    
    if processed_objects:
        print(f"Successfully processed {len(processed_objects)} objects")
        
        # Export as FBX files
        export_objects_as_fbx(processed_objects, export_directory)
        
        print("Export process completed!")
    else:
        print("No mesh objects found in 'Collection' to process")

# Run the script
if __name__ == "__main__":
    main()
