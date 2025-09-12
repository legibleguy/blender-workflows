import bpy
import bmesh
from mathutils import Vector

def create_road_generator_node_group():
    """
    Creates a geometry node group for generating roads along curves with segmentation attributes.
    """
    # Create new geometry node group
    node_group = bpy.data.node_groups.new(name="Road Generator", type='GeometryNodeTree')
    
    # Clear default nodes
    node_group.nodes.clear()
    
    # Create input and output nodes
    group_input = node_group.nodes.new('NodeGroupInput')
    group_output = node_group.nodes.new('NodeGroupOutput')
    
    # Position nodes
    group_input.location = (-1000, 0)
    group_output.location = (1000, 0)
    
    # Create input sockets
    node_group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    node_group.interface.new_socket(name="Road Width", in_out='INPUT', socket_type='NodeSocketFloat')
    node_group.interface.new_socket(name="Resolution", in_out='INPUT', socket_type='NodeSocketInt')
    node_group.interface.new_socket(name="Segment Length", in_out='INPUT', socket_type='NodeSocketFloat')
    
    # Set default values
    road_width_socket = node_group.interface.items_tree["Road Width"]
    road_width_socket.default_value = 4.0
    road_width_socket.min_value = 0.1
    road_width_socket.max_value = 50.0
    
    resolution_socket = node_group.interface.items_tree["Resolution"]
    resolution_socket.default_value = 100
    resolution_socket.min_value = 10
    resolution_socket.max_value = 1000
    
    segment_length_socket = node_group.interface.items_tree["Segment Length"]
    segment_length_socket.default_value = 10.0
    segment_length_socket.min_value = 1.0
    segment_length_socket.max_value = 100.0
    
    # Create output socket
    node_group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    # Create nodes for the road generation pipeline
    
    # 1. Resample Curve
    resample_curve = node_group.nodes.new('GeometryNodeResampleCurve')
    resample_curve.location = (-800, 0)
    resample_curve.mode = 'COUNT'
    
    # 2. Create profile curve (rectangle cross-section)
    curve_line = node_group.nodes.new('GeometryNodeCurvePrimitiveLine')
    curve_line.location = (-800, -200)
    curve_line.mode = 'DIRECTION'
    
    # Set line direction and length
    curve_line.inputs['Direction'].default_value = (1, 0, 0)  # X direction
    
    # 3. Transform profile curve to set width
    transform_profile = node_group.nodes.new('GeometryNodeTransform')
    transform_profile.location = (-600, -200)
    
    # 4. Curve to Mesh
    curve_to_mesh = node_group.nodes.new('GeometryNodeCurveToMesh')
    curve_to_mesh.location = (-400, 0)
    
    # 5. Position node for distance calculation
    position = node_group.nodes.new('GeometryNodeInputPosition')
    position.location = (-200, -300)
    
    # 6. Index node for face indexing
    index = node_group.nodes.new('GeometryNodeInputIndex')
    index.location = (-200, -400)
    
    # 7. Math nodes for segment calculation
    math_divide = node_group.nodes.new('ShaderNodeMath')
    math_divide.location = (0, -300)
    math_divide.operation = 'DIVIDE'
    
    math_floor = node_group.nodes.new('ShaderNodeMath')
    math_floor.location = (200, -300)
    math_floor.operation = 'FLOOR'
    
    # 8. Store segment ID attribute
    store_segment_id = node_group.nodes.new('GeometryNodeStoreNamedAttribute')
    store_segment_id.location = (400, 0)
    store_segment_id.inputs['Name'].default_value = "segment_id"
    store_segment_id.domain = 'FACE'
    
    # 9. Curve parameter for normalized position along curve
    curve_parameter = node_group.nodes.new('GeometryNodeInputCurveParameter')
    curve_parameter.location = (-200, -500)
    
    # 10. Store curve parameter attribute
    store_curve_param = node_group.nodes.new('GeometryNodeStoreNamedAttribute')
    store_curve_param.location = (600, 0)
    store_curve_param.inputs['Name'].default_value = "curve_parameter"
    store_curve_param.domain = 'VERTEX'
    
    # 11. Calculate distance along curve using curve length
    curve_length = node_group.nodes.new('GeometryNodeCurveLength')
    curve_length.location = (-400, -500)
    
    # 12. Math multiply for distance calculation
    math_multiply = node_group.nodes.new('ShaderNodeMath')
    math_multiply.location = (0, -500)
    math_multiply.operation = 'MULTIPLY'
    
    # 13. Store distance attribute
    store_distance = node_group.nodes.new('GeometryNodeStoreNamedAttribute')
    store_distance.location = (800, 0)
    store_distance.inputs['Name'].default_value = "distance_along_curve"
    store_distance.domain = 'VERTEX'
    
    # 14. Vector math to get curve direction for banking (optional)
    curve_tangent = node_group.nodes.new('GeometryNodeInputTangent')
    curve_tangent.location = (-200, -600)
    
    # 15. Store tangent direction
    store_tangent = node_group.nodes.new('GeometryNodeStoreNamedAttribute')
    store_tangent.location = (1000, -200)
    store_tangent.inputs['Name'].default_value = "curve_tangent"
    store_tangent.domain = 'VERTEX'
    
    # Connect nodes
    links = node_group.links
    
    # Main pipeline
    links.new(group_input.outputs['Geometry'], resample_curve.inputs['Curve'])
    links.new(group_input.outputs['Resolution'], resample_curve.inputs['Count'])
    
    # Profile setup
    links.new(group_input.outputs['Road Width'], curve_line.inputs['Length'])
    links.new(curve_line.outputs['Curve'], curve_to_mesh.inputs['Profile Curve'])
    
    # Main curve to mesh
    links.new(resample_curve.outputs['Curve'], curve_to_mesh.inputs['Curve'])
    
    # Segment ID calculation (based on face index)
    links.new(index.outputs['Index'], math_divide.inputs[0])
    links.new(group_input.outputs['Segment Length'], math_divide.inputs[1])  # Faces per segment
    links.new(math_divide.outputs['Value'], math_floor.inputs['Value'])
    
    # Store segment ID
    links.new(curve_to_mesh.outputs['Mesh'], store_segment_id.inputs['Geometry'])
    links.new(math_floor.outputs['Value'], store_segment_id.inputs['Value'])
    
    # Store curve parameter
    links.new(store_segment_id.outputs['Geometry'], store_curve_param.inputs['Geometry'])
    links.new(curve_parameter.outputs['Factor'], store_curve_param.inputs['Value'])
    
    # Distance calculation
    links.new(resample_curve.outputs['Curve'], curve_length.inputs['Curve'])
    links.new(curve_parameter.outputs['Factor'], math_multiply.inputs[0])
    links.new(curve_length.outputs['Length'], math_multiply.inputs[1])
    
    # Store distance
    links.new(store_curve_param.outputs['Geometry'], store_distance.inputs['Geometry'])
    links.new(math_multiply.outputs['Value'], store_distance.inputs['Value'])
    
    # Store tangent for future use
    links.new(store_distance.outputs['Geometry'], store_tangent.inputs['Geometry'])
    links.new(curve_tangent.outputs['Tangent'], store_tangent.inputs['Value'])
    
    # Final output
    links.new(store_tangent.outputs['Geometry'], group_output.inputs['Geometry'])
    
    return node_group

def apply_road_generator_to_curve(curve_obj_name):
    """
    Apply the road generator node group to a curve object.
    """
    if curve_obj_name not in bpy.data.objects:
        print(f"Curve object '{curve_obj_name}' not found!")
        return None
    
    curve_obj = bpy.data.objects[curve_obj_name]
    
    # Ensure it's a curve object
    if curve_obj.type != 'CURVE':
        print(f"Object '{curve_obj_name}' is not a curve!")
        return None
    
    # Check if node group exists, create if not
    node_group_name = "Road Generator"
    if node_group_name not in bpy.data.node_groups:
        create_road_generator_node_group()
    
    # Add geometry nodes modifier
    modifier = curve_obj.modifiers.new(name="Road Generator", type='NODES')
    modifier.node_group = bpy.data.node_groups[node_group_name]
    
    # Set default values
    modifier["Input_2"] = 4.0    # Road Width
    modifier["Input_3"] = 100    # Resolution
    modifier["Input_4"] = 10.0   # Segment Length
    
    return modifier

def separate_road_segments(road_obj_name):
    """
    Separate the generated road into individual segment objects.
    """
    if road_obj_name not in bpy.data.objects:
        print(f"Road object '{road_obj_name}' not found!")
        return
    
    road_obj = bpy.data.objects[road_obj_name]
    mesh = road_obj.data
    
    # Check if segment attribute exists
    if "segment_id" not in mesh.attributes:
        print("No segment_id attribute found! Make sure the road was generated with the Road Generator node group.")
        return
    
    # Get segment attribute
    segment_attr = mesh.attributes["segment_id"]
    
    # Get unique segment IDs
    segment_ids = set()
    for i in range(len(segment_attr.data)):
        segment_ids.add(int(segment_attr.data[i].value))
    
    print(f"Found {len(segment_ids)} road segments")
    
    # Create collection for road segments
    collection_name = f"{road_obj_name}_Segments"
    if collection_name in bpy.data.collections:
        bpy.data.collections.remove(bpy.data.collections[collection_name])
    
    segment_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(segment_collection)
    
    # Create separate objects for each segment
    for segment_id in sorted(segment_ids):
        # Duplicate the original object
        new_obj = road_obj.copy()
        new_obj.data = mesh.copy()
        new_obj.name = f"{road_obj_name}_Segment_{segment_id:03d}"
        
        # Link to segment collection
        segment_collection.objects.link(new_obj)
        
        # Use bmesh to remove faces not in this segment
        bm = bmesh.new()
        bm.from_mesh(new_obj.data)
        
        # Get face segment attributes
        bm.faces.ensure_lookup_table()
        faces_to_remove = []
        
        for face in bm.faces:
            face_segment_id = int(segment_attr.data[face.index].value)
            if face_segment_id != segment_id:
                faces_to_remove.append(face)
        
        # Remove faces from other segments
        for face in faces_to_remove:
            if face.is_valid:
                bm.faces.remove(face)
        
        # Update mesh
        bm.to_mesh(new_obj.data)
        bm.free()
        
        # Clean up loose vertices
        new_obj.data.update()
    
    print(f"Created {len(segment_ids)} road segment objects in collection '{collection_name}'")

def create_example_curve():
    """
    Create an example curve for testing the road generator.
    """
    # Create a new curve
    curve_data = bpy.data.curves.new(name="Race_Track", type='CURVE')
    curve_data.dimensions = '3D'
    
    # Create a spline
    spline = curve_data.splines.new(type='NURBS')
    spline.points.add(7)  # Add more points (total will be 8)
    
    # Define track points (a simple racing circuit)
    track_points = [
        (0, 0, 0, 1),
        (10, 0, 0, 1),
        (20, 5, 0, 1),
        (25, 15, 2, 1),   # Banking
        (20, 25, 0, 1),
        (5, 30, 0, 1),
        (-5, 20, 0, 1),
        (-2, 5, 0, 1)
    ]
    
    # Set point coordinates
    for i, point in enumerate(track_points):
        spline.points[i].co = point
    
    # Make it cyclic for a closed track
    spline.use_cyclic_u = True
    
    # Create object
    curve_obj = bpy.data.objects.new("Race_Track", curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)
    
    return curve_obj

# Main execution function
def main():
    """
    Main function to demonstrate the road generator.
    """
    print("Creating Road Generator Geometry Node Group...")
    
    # Create the node group
    node_group = create_road_generator_node_group()
    print(f"Created node group: {node_group.name}")
    
    # Create example curve if none exists
    if "Race_Track" not in bpy.data.objects:
        curve_obj = create_example_curve()
        print(f"Created example curve: {curve_obj.name}")
    else:
        curve_obj = bpy.data.objects["Race_Track"]
    
    # Apply road generator to curve
    modifier = apply_road_generator_to_curve("Race_Track")
    if modifier:
        print(f"Applied road generator modifier to {curve_obj.name}")
        print("You can now adjust the Road Width, Resolution, and Segment Length in the modifier properties")
        print("To separate into segments, run: separate_road_segments('Race_Track')")
    
if __name__ == "__main__":
    main()
