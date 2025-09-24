"""
One-time script to save your geometry node setups as templates for the addon
Run this in Blender with your current scene that has the node groups
"""

import bpy
import os
from pathlib import Path

# Define the addon directory path
addon_dir = Path(r"F:\Stuff\blender-workflows\race-game\road_generator_addon")
templates_dir = addon_dir / "node_templates"

# Create templates directory if it doesn't exist
templates_dir.mkdir(exist_ok=True)

# Node groups to save
node_groups_to_save = ["road", "road_collision", "sidewalk", "sidewalk_collision"]

saved_count = 0
for group_name in node_groups_to_save:
    if group_name in bpy.data.node_groups:
        # Get the node group
        node_group = bpy.data.node_groups[group_name]
        
        # Mark with fake user to ensure it's saved
        node_group.use_fake_user = True
        
        # Define the file path
        filepath = templates_dir / f"{group_name}.blend"
        
        # Save to library file
        bpy.data.libraries.write(
            str(filepath),
            {node_group},
            path_remap='RELATIVE',
            fake_user=True
        )
        
        print(f"Saved '{group_name}' to {filepath}")
        saved_count += 1
    else:
        print(f"Warning: '{group_name}' not found in current file")

print(f"\nSaved {saved_count} node group templates to addon folder")
print(f"Templates location: {templates_dir}")
print("\nThese templates will now be bundled with your addon!")
print("Users can load them automatically when using the addon.")
