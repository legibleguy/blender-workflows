"""
Node loader module for loading geometry node templates
"""

import bpy
import os
from pathlib import Path


def get_addon_path():
    """Get the addon directory path"""
    return Path(__file__).parent


def load_node_templates():
    """Load geometry node templates from the addon's node_templates directory"""
    addon_path = get_addon_path()
    templates_dir = addon_path / "node_templates"
    
    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}")
        return []
    
    loaded_groups = []
    
    # List of expected node group files
    node_files = ["road.blend", "road_collision.blend", "sidewalks.blend", "sidewalks_collision.blend", "guardrails_collision.blend", "guardrails.blend"]
    
    for node_file in node_files:
        filepath = templates_dir / node_file
        
        if not filepath.exists():
            print(f"Template file not found: {filepath}")
            continue
        
        # Extract the node group name from filename
        group_name = node_file.replace(".blend", "")
        
        # Check if the node group already exists
        if group_name in bpy.data.node_groups:
            print(f"Node group '{group_name}' already exists, skipping...")
            continue
        
        # Load the node group from the file
        with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
            # Load all node groups from the file
            data_to.node_groups = data_from.node_groups
        
        # Check if the node group was loaded
        if group_name in bpy.data.node_groups:
            loaded_groups.append(group_name)
            print(f"Loaded node group: {group_name}")
        else:
            print(f"Failed to load node group: {group_name}")
    
    return loaded_groups


def ensure_node_groups_loaded():
    """Ensure required node groups are loaded"""
    required_groups = ["road", "road_collision"]
    missing_groups = []
    
    for group_name in required_groups:
        if group_name not in bpy.data.node_groups:
            missing_groups.append(group_name)
    
    if missing_groups:
        print(f"Missing node groups: {missing_groups}")
        loaded = load_node_templates()
        return len(loaded) > 0
    
    return True


def apply_geometry_nodes_to_curve(curve_obj, node_group_name):
    """Apply a geometry node modifier to a curve object"""
    if curve_obj.type != 'CURVE':
        print(f"Object {curve_obj.name} is not a curve")
        return False
    
    if node_group_name not in bpy.data.node_groups:
        print(f"Node group '{node_group_name}' not found")
        return False
    
    # Check if the object already has a geometry nodes modifier
    for modifier in curve_obj.modifiers:
        if modifier.type == 'NODES':
            # Update existing modifier
            modifier.node_group = bpy.data.node_groups[node_group_name]
            print(f"Updated existing geometry nodes modifier on {curve_obj.name}")
            return True
    
    # Add new geometry nodes modifier
    geo_modifier = curve_obj.modifiers.new(name="GeometryNodes", type='NODES')
    geo_modifier.node_group = bpy.data.node_groups[node_group_name]
    print(f"Added geometry nodes modifier to {curve_obj.name}")
    
    return True


def save_node_template(node_group_name, output_dir=None):
    """Save a node group as a template file"""
    if node_group_name not in bpy.data.node_groups:
        print(f"Node group '{node_group_name}' not found")
        return False
    
    if output_dir is None:
        addon_path = get_addon_path()
        output_dir = addon_path / "node_templates"
    
    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the node group
    node_group = bpy.data.node_groups[node_group_name]
    
    # Mark with fake user to ensure it's saved
    node_group.use_fake_user = True
    
    # Define the file path
    filepath = output_dir / f"{node_group_name}.blend"
    
    # Save to library file
    bpy.data.libraries.write(
        str(filepath),
        {node_group},
        path_remap='RELATIVE',
        fake_user=True
    )
    
    print(f"Saved '{node_group_name}' to {filepath}")
    return True
