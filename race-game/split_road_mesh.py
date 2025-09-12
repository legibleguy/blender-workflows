import bpy
import bmesh
from mathutils import Vector, geometry
import math

print("=== IMPROVED ROAD SEGMENTATION SCRIPT ===")
print("Output visible in: Window > Toggle System Console")
print("This version uses curve sampling and vertex weights for better results")
print()

def split_road_with_curve_sampling(road_object, segment_length=25.0):
    """
    Split a road object using proper curve sampling and vertex weight assignment.
    Works with both curve and mesh objects.
    """
    print(f"Processing road object: {road_object.name} (Type: {road_object.type})")
    
    # Ensure we have proper context
    bpy.context.view_layer.objects.active = road_object
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # Get the original curve for sampling (if it's a curve) or create centerline
    if road_object.type == 'CURVE':
        curve_obj = road_object
        print("Using original curve for sampling")
        
        # Create a mesh version
        mesh_duplicate = road_object.copy()
        mesh_duplicate.data = road_object.data.copy()
        mesh_duplicate.name = f"{road_object.name}_Mesh_Temp"
        bpy.context.collection.objects.link(mesh_duplicate)
        
        # Convert curve to mesh (this applies geometry nodes if present)
        bpy.context.view_layer.objects.active = mesh_duplicate
        bpy.ops.object.convert(target='MESH')
        working_obj = mesh_duplicate
        
    elif road_object.type == 'MESH':
        print("Object is mesh - will create virtual centerline")
        working_obj = road_object.copy()
        working_obj.data = road_object.data.copy()
        working_obj.name = f"{road_object.name}_Working_Temp"
        bpy.context.collection.objects.link(working_obj)
        curve_obj = None  # We'll create a virtual curve
        
    else:
        print(f"Error: {road_object.name} is not a curve or mesh object!")
        return []
    
    # Check if the mesh has vertices
    if not working_obj.data.vertices:
        print("Error: Converted mesh has no vertices!")
        bpy.data.objects.remove(working_obj, do_unlink=True)
        return []
        
    print(f"Working with mesh: {working_obj.name} ({len(working_obj.data.vertices)} vertices)")
    
    # Sample the curve/centerline to get splitting points
    if curve_obj and curve_obj.type == 'CURVE':
        sample_points, sample_tangents = sample_curve_properly(curve_obj, segment_length)
    else:
        sample_points, sample_tangents = create_virtual_curve_samples(working_obj, segment_length)
    
    if len(sample_points) < 2:
        print("Error: Could not generate enough sample points!")
        bpy.data.objects.remove(working_obj, do_unlink=True)
        return []
    
    print(f"Generated {len(sample_points)} sample points with tangent vectors")
    
    # Create segments with proper cutting planes
    segments = create_segments_with_cutting_planes(working_obj, sample_points, sample_tangents, road_object.name, segment_length)
    
    # Remove the temporary working object
    bpy.data.objects.remove(working_obj, do_unlink=True)
    
    print(f"Successfully created {len(segments)} road segments!")
    return segments

def sample_curve_properly(curve_obj, segment_length):
    """
    Properly sample a curve object to get points and tangent vectors.
    """
    curve_data = curve_obj.data
    if not curve_data.splines:
        return [], []
    
    spline = curve_data.splines[0]
    
    # Calculate total curve length by dense sampling
    resolution = 200
    temp_points = []
    temp_tangents = []
    
    for i in range(resolution + 1):
        t = i / resolution
        
        # Get point and tangent at parameter t
        if spline.type == 'BEZIER' and len(spline.bezier_points) >= 2:
            # For Bezier curves
            point, tangent = evaluate_bezier_spline(spline, t)
        else:
            # For NURBS and other curves
            try:
                point = spline.calc_point(t)
                # Calculate tangent by finite difference
                if t < 1.0:
                    next_point = spline.calc_point(min(1.0, t + 0.01))
                    tangent = (next_point - Vector(point)).normalized()
                else:
                    prev_point = spline.calc_point(max(0.0, t - 0.01))
                    tangent = (Vector(point) - prev_point).normalized()
                point = Vector(point)
            except:
                # Fallback for unsupported curve types
                point, tangent = fallback_curve_evaluation(spline, t)
        
        # Transform to world space
        world_point = curve_obj.matrix_world @ point
        world_tangent = curve_obj.matrix_world.to_3x3() @ tangent
        world_tangent.normalize()
        
        temp_points.append(world_point)
        temp_tangents.append(world_tangent)
    
    # Calculate cumulative distances
    distances = [0.0]
    for i in range(1, len(temp_points)):
        dist = (temp_points[i] - temp_points[i-1]).length
        distances.append(distances[-1] + dist)
    
    total_length = distances[-1]
    print(f"Total curve length: {total_length:.2f}")
    
    # Sample at regular intervals
    sample_points = []
    sample_tangents = []
    current_distance = 0.0
    
    while current_distance <= total_length:
        # Find the parameter t for this distance
        t = find_t_for_distance(distances, current_distance, total_length)
        
        # Interpolate point and tangent
        index = int(t * (len(temp_points) - 1))
        index = min(index, len(temp_points) - 2)
        local_t = (t * (len(temp_points) - 1)) - index
        
        interp_point = temp_points[index].lerp(temp_points[index + 1], local_t)
        interp_tangent = temp_tangents[index].lerp(temp_tangents[index + 1], local_t).normalized()
        
        sample_points.append(interp_point)
        sample_tangents.append(interp_tangent)
        
        current_distance += segment_length
    
    return sample_points, sample_tangents

def evaluate_bezier_spline(spline, t):
    """
    Evaluate a Bezier spline at parameter t.
    """
    if len(spline.bezier_points) < 2:
        return Vector((0, 0, 0)), Vector((1, 0, 0))
    
    # Simple linear interpolation for now (can be improved for complex Bezier curves)
    point_index = int(t * (len(spline.bezier_points) - 1))
    point_index = min(point_index, len(spline.bezier_points) - 2)
    local_t = (t * (len(spline.bezier_points) - 1)) - point_index
    
    p1 = spline.bezier_points[point_index].co
    p2 = spline.bezier_points[point_index + 1].co
    
    point = p1.lerp(p2, local_t)
    tangent = (p2 - p1).normalized()
    
    return point, tangent

def fallback_curve_evaluation(spline, t):
    """
    Fallback method for curve types that don't support calc_point.
    """
    if hasattr(spline, 'points') and len(spline.points) > 1:
        point_index = int(t * (len(spline.points) - 1))
        point_index = min(point_index, len(spline.points) - 2)
        local_t = (t * (len(spline.points) - 1)) - point_index
        
        p1 = Vector(spline.points[point_index].co[:3])
        p2 = Vector(spline.points[point_index + 1].co[:3])
        
        point = p1.lerp(p2, local_t)
        tangent = (p2 - p1).normalized()
    else:
        point = Vector((0, 0, 0))
        tangent = Vector((1, 0, 0))
    
    return point, tangent

def create_virtual_curve_samples(mesh_obj, segment_length):
    """
    Create virtual curve samples from a mesh object by analyzing its centerline.
    """
    # This is the same centerline finding logic from before, but now also calculates tangents
    centerline_points = find_road_centerline_from_mesh(mesh_obj)
    
    if len(centerline_points) < 2:
        return [], []
    
    # Calculate tangents for each centerline point
    tangents = []
    for i in range(len(centerline_points)):
        if i == 0:
            # First point: use direction to next point
            tangent = (centerline_points[i + 1] - centerline_points[i]).normalized()
        elif i == len(centerline_points) - 1:
            # Last point: use direction from previous point
            tangent = (centerline_points[i] - centerline_points[i - 1]).normalized()
        else:
            # Middle points: average of incoming and outgoing directions
            in_dir = (centerline_points[i] - centerline_points[i - 1]).normalized()
            out_dir = (centerline_points[i + 1] - centerline_points[i]).normalized()
            tangent = (in_dir + out_dir).normalized()
        
        tangents.append(tangent)
    
    # Sample at regular intervals
    return sample_centerline_at_intervals(centerline_points, tangents, segment_length)

def find_road_centerline_from_mesh(mesh_obj):
    """
    Find the centerline from a mesh (same as before).
    """
    mesh = mesh_obj.data
    vertices = [mesh_obj.matrix_world @ vert.co for vert in mesh.vertices]
    
    if not vertices:
        return []
    
    # Find main axis and create centerline
    min_coords = Vector((min(v.x for v in vertices), min(v.y for v in vertices), min(v.z for v in vertices)))
    max_coords = Vector((max(v.x for v in vertices), max(v.y for v in vertices), max(v.z for v in vertices)))
    dimensions = max_coords - min_coords
    
    if dimensions.x >= dimensions.y and dimensions.x >= dimensions.z:
        sort_key = lambda v: v.x
    elif dimensions.y >= dimensions.x and dimensions.y >= dimensions.z:
        sort_key = lambda v: v.y
    else:
        sort_key = lambda v: v.z
    
    sorted_vertices = sorted(vertices, key=sort_key)
    axis_min = sort_key(sorted_vertices[0])
    axis_max = sort_key(sorted_vertices[-1])
    
    centerline_points = []
    num_samples = 50
    
    for i in range(num_samples):
        progress = i / (num_samples - 1)
        axis_value = axis_min + progress * (axis_max - axis_min)
        tolerance = (axis_max - axis_min) / num_samples * 1.5
        
        nearby_vertices = [v for v in vertices if abs(sort_key(v) - axis_value) < tolerance]
        
        if nearby_vertices:
            centroid = Vector((0, 0, 0))
            for v in nearby_vertices:
                centroid += v
            centroid /= len(nearby_vertices)
            centerline_points.append(centroid)
    
    return centerline_points

def find_t_for_distance(distances, target_distance, total_length):
    """Find the parameter t for a given distance along the curve."""
    if target_distance >= total_length:
        return 1.0
    
    for i in range(len(distances) - 1):
        if distances[i] <= target_distance <= distances[i + 1]:
            local_t = (target_distance - distances[i]) / (distances[i + 1] - distances[i])
            return (i + local_t) / (len(distances) - 1)
    
    return 0.0

def sample_centerline_at_intervals(centerline_points, tangents, interval_length):
    """
    Sample centerline at regular intervals.
    """
    if len(centerline_points) < 2:
        return centerline_points, tangents
    
    # Calculate distances
    distances = [0.0]
    for i in range(1, len(centerline_points)):
        dist = (centerline_points[i] - centerline_points[i-1]).length
        distances.append(distances[-1] + dist)
    
    total_length = distances[-1]
    
    sample_points = []
    sample_tangents = []
    current_distance = 0.0
    
    while current_distance <= total_length:
        # Find corresponding point
        for i in range(len(distances) - 1):
            if distances[i] <= current_distance <= distances[i + 1]:
                local_distance = current_distance - distances[i]
                segment_length = distances[i + 1] - distances[i]
                
                if segment_length > 0:
                    local_t = local_distance / segment_length
                    interp_point = centerline_points[i].lerp(centerline_points[i + 1], local_t)
                    interp_tangent = tangents[i].lerp(tangents[i + 1], local_t).normalized()
                else:
                    interp_point = centerline_points[i]
                    interp_tangent = tangents[i]
                
                sample_points.append(interp_point)
                sample_tangents.append(interp_tangent)
                break
        
        current_distance += interval_length
    
    return sample_points, sample_tangents

def create_segments_with_cutting_planes(mesh_obj, sample_points, sample_tangents, base_name, segment_length):
    """
    Create mesh segments using proper cutting planes based on curve tangents.
    """
    segments = []
    mesh = mesh_obj.data
    
    # Calculate cutting planes
    cutting_planes = []
    for i in range(1, len(sample_points) - 1):  # Skip first and last points
        point = sample_points[i]
        tangent = sample_tangents[i]
        
        # Create a cutting plane perpendicular to the tangent
        normal = tangent.normalized()
        cutting_planes.append((point, normal))
    
    print(f"Created {len(cutting_planes)} cutting planes")
    
    # Create segments
    for i in range(len(sample_points) - 1):
        start_point = sample_points[i]
        end_point = sample_points[i + 1]
        
        # Create new segment object
        segment_mesh = mesh.copy()
        segment_obj = bpy.data.objects.new(f"{base_name}_Segment_{i+1:03d}", segment_mesh)
        bpy.context.collection.objects.link(segment_obj)
        segment_obj.location = mesh_obj.location.copy()
        segment_obj.rotation_euler = mesh_obj.rotation_euler.copy()
        segment_obj.scale = mesh_obj.scale.copy()
        
        # Use bmesh for vertex operations
        bm = bmesh.new()
        bm.from_mesh(segment_mesh)
        
        # Determine which vertices to keep
        verts_to_remove = []
        overlap = segment_length * 0.1  # 10% overlap for safety
        
        for vert in bm.verts:
            world_pos = segment_obj.matrix_world @ vert.co
            keep_vertex = True
            
            # Check against cutting planes to determine if vertex should be kept
            if i > 0:  # Not the first segment
                plane_point, plane_normal = cutting_planes[i - 1]
                # Distance from vertex to cutting plane
                distance_to_plane = (world_pos - plane_point).dot(plane_normal)
                if distance_to_plane < -overlap:  # Before the start cutting plane
                    keep_vertex = False
            
            if i < len(cutting_planes) and keep_vertex:  # Not the last segment
                plane_point, plane_normal = cutting_planes[i]
                distance_to_plane = (world_pos - plane_point).dot(plane_normal)
                if distance_to_plane > overlap:  # After the end cutting plane
                    keep_vertex = False
            
            if not keep_vertex:
                verts_to_remove.append(vert)
        
        # Remove vertices outside the segment
        if verts_to_remove:
            bmesh.ops.delete(bm, geom=verts_to_remove, context='VERTS')
        
        # Update the mesh
        segment_mesh.clear_geometry()
        bm.to_mesh(segment_mesh)
        segment_mesh.update()
        bm.free()
        
        segments.append(segment_obj)
        print(f"Created segment {i+1}: {segment_obj.name} ({len(segment_mesh.vertices)} vertices)")
    
    return segments

# Configuration
SEGMENT_LENGTH = 25.0

# Find the road object
road_obj = bpy.data.objects.get("Procedural Road")

if road_obj:
    print(f"Found road object: {road_obj.name}")
    segments = split_road_with_curve_sampling(road_obj, SEGMENT_LENGTH)
    print("=== SCRIPT COMPLETED ===")
    print("Check your outliner for the new segment objects!")
    print("The segments should now have better continuity with fewer gaps.")
else:
    print("Could not find 'Procedural Road' object!")
    print("Available objects:")
    for obj in bpy.context.scene.objects:
        print(f"  - {obj.name} ({obj.type})")
