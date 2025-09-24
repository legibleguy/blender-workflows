"""
Utility functions for the Road Generator addon
"""

import bpy
from pathlib import Path


def apply_geometry_nodes(obj, node_group_name):
    """Apply a geometry nodes modifier to an object"""
    if node_group_name not in bpy.data.node_groups:
        print(f"Node group '{node_group_name}' not found")
        return False
    
    # Check if the object already has a geometry nodes modifier
    for modifier in obj.modifiers:
        if modifier.type == 'NODES':
            # Update existing modifier
            modifier.node_group = bpy.data.node_groups[node_group_name]
            return True
    
    # Add new geometry nodes modifier
    geo_modifier = obj.modifiers.new(name="GeometryNodes", type='NODES')
    geo_modifier.node_group = bpy.data.node_groups[node_group_name]
    
    return True


def get_selected_curves():
    """Get all selected curve objects"""
    return [obj for obj in bpy.context.selected_objects if obj.type == 'CURVE']


def get_road_segments_in_scene():
    """Get all road segment objects in the scene"""
    segments = []
    for obj in bpy.data.objects:
        if "_seg" in obj.name and obj.type == 'MESH':
            # Check if it matches the pattern *_seg<number>
            parts = obj.name.rsplit("_seg", 1)
            if len(parts) == 2:
                try:
                    seg_num = int(parts[1])
                    segments.append((obj, parts[0], seg_num))
                except ValueError:
                    continue
    
    # Sort by base name and segment number
    segments.sort(key=lambda x: (x[1], x[2]))
    return segments


def get_collision_objects_for_segment(segment_name, collision_prefix="UCX"):
    """Get collision objects for a specific segment"""
    collision_objects = []
    
    # Extract base name and segment number
    if "_seg" not in segment_name:
        return collision_objects
    
    parts = segment_name.rsplit("_seg", 1)
    if len(parts) != 2:
        return collision_objects
    
    base_name = parts[0]
    try:
        seg_num = int(parts[1])
    except ValueError:
        return collision_objects
    
    # Look for collision objects with matching pattern
    search_patterns = [
        f"{collision_prefix}_{base_name}_seg{seg_num}_",  # For separated collision boxes
        f"{collision_prefix}_{base_name}_seg{seg_num}"     # For non-separated collision
    ]
    
    for obj in bpy.data.objects:
        for pattern in search_patterns:
            if obj.name.startswith(pattern) and obj.type == 'MESH':
                collision_objects.append(obj)
                break
    
    return collision_objects


def ensure_collection_exists(collection_name):
    """Ensure a collection exists in the scene"""
    if collection_name in bpy.data.collections:
        return bpy.data.collections[collection_name]
    
    # Create new collection
    new_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(new_collection)
    return new_collection


def move_objects_to_collection(objects, collection_name):
    """Move objects to a specific collection"""
    collection = ensure_collection_exists(collection_name)
    
    for obj in objects:
        # Remove from all collections first
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        
        # Add to target collection
        collection.objects.link(obj)


def organize_road_objects():
    """Organize road objects into collections"""
    # Create collections
    road_collection = ensure_collection_exists("Road_Segments")
    collision_collection = ensure_collection_exists("Road_Collisions")
    
    # Move road segments
    road_segments = []
    collision_objects = []
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            # Check if it's a collision object
            if obj.name.startswith("UCX_"):
                collision_objects.append(obj)
            # Check if it's a road segment
            elif "_seg" in obj.name:
                parts = obj.name.rsplit("_seg", 1)
                if len(parts) == 2:
                    try:
                        int(parts[1])  # Verify it ends with a number
                        road_segments.append(obj)
                    except ValueError:
                        pass
    
    # Move objects to appropriate collections
    if road_segments:
        move_objects_to_collection(road_segments, "Road_Segments")
        print(f"Moved {len(road_segments)} road segments to 'Road_Segments' collection")
    
    if collision_objects:
        move_objects_to_collection(collision_objects, "Road_Collisions")
        print(f"Moved {len(collision_objects)} collision objects to 'Road_Collisions' collection")


def cleanup_empty_meshes():
    """Clean up empty mesh data blocks"""
    removed_count = 0
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
            removed_count += 1
    
    if removed_count > 0:
        print(f"Removed {removed_count} unused mesh data blocks")
    
    return removed_count


def get_addon_version():
    """Get the addon version"""
    bl_info = {
        "version": (1, 0, 0)
    }
    
    # Try to get version from __init__.py
    addon_path = Path(__file__).parent
    init_file = addon_path / "__init__.py"
    
    if init_file.exists():
        with open(init_file, 'r') as f:
            content = f.read()
            # Simple parsing for bl_info
            if '"version":' in content:
                import re
                match = re.search(r'"version":\s*\(([^)]+)\)', content)
                if match:
                    version_str = match.group(1)
                    version_parts = [int(x.strip()) for x in version_str.split(',')]
                    return tuple(version_parts)
    
    return bl_info["version"]
