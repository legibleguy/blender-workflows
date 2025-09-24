# Road Generator Addon for Blender

A comprehensive Blender addon for generating, splitting, and exporting road segments with collision geometry for game engines.

## Features

- **Road Splitting**: Automatically split road meshes into manageable segments based on a length attribute
- **Collision Generation**: Generate UCX collision objects for Unreal Engine compatibility
- **Batch Export**: Export all road segments with their collision objects as FBX files
- **Node Templates**: Built-in geometry node templates for road and collision generation
- **Organized Workflow**: Automated organization of road and collision objects into collections

## Installation

1. Download or clone the `road_generator_addon` folder
2. In Blender, go to Edit → Preferences → Add-ons
3. Click "Install..." and select the addon folder or zip file
4. Enable the "Road Generator" addon from the list
5. The addon panel will appear in the 3D Viewport sidebar under the "Road Gen" tab

## Setup

### First Time Setup

1. Open your Blender project with the road geometry node groups
2. Run the included `save_node_templates.py` script to save your node groups:
   - This will save "road" and "road_collision" node groups to the addon's templates folder
   - These templates will be bundled with the addon for future use

### Loading Node Templates

1. In any new project, click "Load Node Templates" in the addon panel
2. This will load the saved geometry node groups into your project

## Usage

### Complete Workflow

1. **Create a Curve**: Draw a curve object that represents your road path
2. **Load Templates**: Click "Load Node Templates" if not already loaded
3. **Apply Road Geometry**: The addon will apply the "road" geometry node group to your curve
4. **Generate Complete Road**: 
   - Select your curve object
   - Click "Generate Complete Road" button
   - This will:
     - Split the road into segments
     - Create a duplicate curve with collision geometry
     - Generate UCX collision objects

### Individual Operations

#### Split Road
- Select a curve with road geometry nodes applied
- Adjust "Number of Divisions" to control segment count
- Click "Split Road" to create individual segment objects

#### Generate Collision
- Select a curve with collision geometry nodes applied (usually named "UCX_[original_name]")
- Adjust collision settings:
  - **Collision Thickness**: Solidify modifier thickness
  - **Collision Prefix**: Prefix for collision objects (default: UCX)
  - **Separate Collision Boxes**: Split collision into individual objects
- Click "Generate Collision"

### Export

#### Export Settings
- **Export Path**: Directory for FBX files
- **Export Scale**: Scale factor for export (default: 1.0)

#### Export Options
- **Export Road Segments**: Export all segments with their collision
- **Export All Roads**: Opens a file browser to select export location

## Settings

### Road Generation
- **Number of Divisions**: Number of segments to create (1-100)
- **Length Attribute**: Vertex attribute name for length-based splitting (default: "Len")
- **Road Node Group**: Name of geometry node group for roads (default: "road")
- **Collision Node Group**: Name of geometry node group for collision (default: "road_collision")

### Collision Settings
- **Collision Thickness**: Thickness of solidify modifier (0.001-10.0)
- **Collision Prefix**: Prefix for collision objects (default: "UCX" for Unreal)
- **Separate Collision Boxes**: Create individual collision objects per segment

### Export Settings
- **Export Path**: Default directory for exports
- **Export Scale**: Global scale for FBX export

## File Structure

```
road_generator_addon/
├── __init__.py               # Main addon initialization
├── road_split_operator.py    # Road splitting functionality
├── collision_gen_operator.py # Collision generation
├── export_operator.py        # FBX export functionality
├── node_loader.py           # Node template loading
├── utils.py                 # Utility functions
├── node_templates/          # Stored geometry node templates
│   ├── road.blend          # Road generation nodes
│   └── road_collision.blend # Collision generation nodes
└── README.md               # This file
```

## Tips

1. **Curve Setup**: Ensure your curve has proper resolution for smooth roads
2. **Length Attribute**: The geometry nodes should create a "Len" attribute on vertices for proper splitting
3. **Collections**: The addon automatically organizes segments and collision into separate collections
4. **Naming Convention**: 
   - Road segments: `[curve_name]_seg[number]`
   - Collision objects: `UCX_[curve_name]_seg[number]_[part]`

## Troubleshooting

- **"Vertex attribute 'Len' not found"**: Ensure your geometry nodes create a vertex float attribute named "Len"
- **No collision generated**: Check that the collision curve has the proper geometry node group applied
- **Export fails**: Ensure you have saved the .blend file or specified an export path

## Version

1.0.0 - Initial release

## License

Free to use and modify for your projects.
