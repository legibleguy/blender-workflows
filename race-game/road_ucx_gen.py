import bpy
import bmesh

# USER PARAMETERS
num_divisions = 10  # how many sections based on Len
len_attr_name = "Len"  # name of the custom float attribute on verts
solidify_thickness = 0.05  # adjust thickness of solidify (collision box depth)
collision_obj_prefix = "UCX"  # prefix for Unreal collision meshes
separate_collision_boxes = True  # whether to separate each box into individual objects

def separate_loose_parts(obj, base_name):
    """
    Separate all loose (disconnected) parts of a mesh object into individual objects.
    Returns a list of the new objects created.
    """
    # Select the object and make it active
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # Enter edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Select all
    bpy.ops.mesh.select_all(action='SELECT')
    
    # Separate by loose parts
    bpy.ops.mesh.separate(type='LOOSE')
    
    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Get all selected objects (the separated parts)
    separated_objects = [o for o in bpy.context.selected_objects]
    
    # Just give them temporary names for now - the main function will handle final naming
    for i, sep_obj in enumerate(separated_objects):
        sep_obj.name = f"{base_name}_{i:03d}"
    
    return separated_objects

def create_ucx_collision_sections(curve_obj, num_divisions, len_attr_name, thickness, prefix):
    """
    For the given curve object (with the “collision version” node graph applied),
    create collision boxes per section using Len attribute.
    """
    # Ensure we have a curve
    if curve_obj.type != 'CURVE':
        print("Select a curve object")
        return

    # Duplicate the curve, with modifiers applied (especially the geometry nodes & solidify)
    deps = bpy.context.evaluated_depsgraph_get()
    obj_eval = curve_obj.evaluated_get(deps)
    mesh_data = bpy.data.meshes.new_from_object(obj_eval, preserve_all_data_layers=True)

    # New mesh object
    mesh_name = curve_obj.name + "_collision_mesh"
    temp_mesh_obj = bpy.data.objects.new(mesh_name, mesh_data)
    bpy.context.collection.objects.link(temp_mesh_obj)

    # Apply a solidify modifier on the mesh object
    # Actually: since we've already converted via new_from_object, modifiers are baked;
    # but if solidify is still a modifier, we can add and apply
    solid_mod = temp_mesh_obj.modifiers.new(name="UCX_Solidify", type='SOLIDIFY')
    solid_mod.thickness = thickness
    solid_mod.offset =  1.0 # center the solidification; adjust as needed
    # Apply the solidify
    bpy.context.view_layer.objects.active = temp_mesh_obj
    bpy.ops.object.modifier_apply(modifier=solid_mod.name)

    # Convert to mesh if not already (should be already)
    if temp_mesh_obj.type != 'MESH':
        bpy.context.view_layer.objects.active = temp_mesh_obj
        bpy.ops.object.convert(target='MESH')

    # Create bmesh
    bm = bmesh.new()
    bm.from_mesh(temp_mesh_obj.data)

    # Get Len attribute from vertices
    layer = bm.verts.layers.float.get(len_attr_name)
    if layer is None:
        print(f"ERROR: Vertex attribute '{len_attr_name}' not found in mesh.")
        bm.free()
        return

    # Find min/max Len
    len_vals = [v[layer] for v in bm.verts]
    if not len_vals:
        print("No verts found?")
        bm.free()
        return
    min_len = min(len_vals)
    max_len = max(len_vals)
    span = max_len - min_len if max_len > min_len else 1.0

    # Map each vertex to a segment
    vert_to_segment = {}
    for v in bm.verts:
        t = (v[layer] - min_len) / span
        seg = min(int(t * num_divisions), num_divisions - 1)
        vert_to_segment[v.index] = seg

    # For each face, decide which segment it belongs to (lowest of its vertices)
    face_to_segment = {}
    for f in bm.faces:
        segs = [vert_to_segment[v.index] for v in f.verts]
        face_to_segment[f.index] = min(segs)

    # Now, for each segment, make a separate object out of the faces
    created_segments = []  # Keep track of created segment objects
    
    for seg in range(num_divisions):
        # Create new bmesh for this segment
        bm_seg = bmesh.new()
        vmap = {}  # map from original vert index to new vert

        for f in bm.faces:
            if face_to_segment[f.index] == seg:
                # copy verts
                new_verts = []
                for v in f.verts:
                    if v.index not in vmap:
                        v_new = bm_seg.verts.new(v.co)
                        vmap[v.index] = v_new
                    new_verts.append(vmap[v.index])
                try:
                    bm_seg.faces.new(new_verts)
                except ValueError:
                    # face might already exist, skip
                    pass

        if len(bm_seg.faces) == 0:
            bm_seg.free()
            continue

        # Create mesh data and object
        # Create a temporary name first
        temp_obj_name = f"temp_seg_{seg}"
        
        # Create mesh with a different internal name to avoid conflicts
        mesh_name = f"{temp_obj_name}_mesh"
        coll_mesh = bpy.data.meshes.new(mesh_name)
        bm_seg.to_mesh(coll_mesh)
        coll_obj = bpy.data.objects.new(temp_obj_name, coll_mesh)
        bpy.context.collection.objects.link(coll_obj)
        
        created_segments.append(coll_obj)

        bm_seg.free()
    
    # Now separate each segment's loose parts if requested
    if separate_collision_boxes:
        total_collision_objects = 0
        
        # Process each segment and separate its loose parts
        for seg_idx, seg_obj in enumerate(created_segments):
            # Use a temporary base name for separation
            temp_base = f"temp_seg{seg_idx}"
            
            # Separate loose parts and get the resulting objects
            separated_parts = separate_loose_parts(seg_obj, temp_base)
            
            # Now rename objects for this segment with proper naming
            if curve_obj.name.startswith(prefix + "_"):
                base_name = f"{curve_obj.name}_seg{seg_idx}"
            else:
                base_name = f"{prefix}_{curve_obj.name}_seg{seg_idx}"
            
            for i, collision_obj in enumerate(separated_parts):
                collision_obj.name = f"{base_name}_{i:02d}"
                collision_obj.display_type = 'WIRE'
            
            total_collision_objects += len(separated_parts)
        
        print(f"Created {total_collision_objects} individual collision objects from {len(created_segments)} segments")
    else:
        # If not separating, just rename the segment objects with proper naming
        for i, seg_obj in enumerate(created_segments):
            if curve_obj.name.startswith(prefix + "_"):
                seg_obj.name = f"{curve_obj.name}_seg{i}"
            else:
                seg_obj.name = f"{prefix}_{curve_obj.name}_seg{i}"
            seg_obj.display_type = 'WIRE'

    # Clean up the temporary mesh object and its data if desired
    # Optionally delete temp_mesh_obj
    bpy.data.objects.remove(temp_mesh_obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_data, do_unlink=True)

    bm.free()


# Run script on active object
active = bpy.context.active_object
if active:
    create_ucx_collision_sections(active, num_divisions, len_attr_name, solidify_thickness, collision_obj_prefix)
else:
    print("No active object selected.")
