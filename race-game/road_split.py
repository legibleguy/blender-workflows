import bpy
import bmesh

# Parameters
num_divisions = 10  # number of road segments
len_attr_name = "Len"  # name of the custom vertex float attribute

def split_road_by_len(obj, num_divisions, len_attr_name):
    # Duplicate the object with modifiers applied
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)

    # Create new mesh object
    new_obj = bpy.data.objects.new(obj.name + "_segmented", mesh_from_eval)
    bpy.context.collection.objects.link(new_obj)

    # Get bmesh for processing
    bm = bmesh.new()
    bm.from_mesh(new_obj.data)

    # Ensure vertex attributes exist
    layer = bm.verts.layers.float.get(len_attr_name)
    if layer is None:
        print(f"ERROR: Vertex attribute '{len_attr_name}' not found.")
        bm.free()
        return None

    # Find min/max length to normalize
    len_values = [v[layer] for v in bm.verts]
    min_len, max_len = min(len_values), max(len_values)
    span = max_len - min_len if max_len > min_len else 1.0

    # Assign each vertex to a segment index
    vert_to_segment = {}
    for v in bm.verts:
        t = (v[layer] - min_len) / span
        seg = min(int(t * num_divisions), num_divisions - 1)
        vert_to_segment[v.index] = seg

    # For each face, assign it to the lowest-index segment among its vertices
    face_to_segment = {}
    for f in bm.faces:
        segs = [vert_to_segment[v.index] for v in f.verts]
        face_to_segment[f.index] = min(segs)

    # Duplicate faces into separate objects by segment
    for seg in range(num_divisions):
        bm_seg = bmesh.new()
        vmap = {}

        for f in bm.faces:
            if face_to_segment[f.index] == seg:
                verts = []
                for v in f.verts:
                    if v not in vmap:
                        vmap[v] = bm_seg.verts.new(v.co)
                    verts.append(vmap[v])
                try:
                    bm_seg.faces.new(verts)
                except ValueError:
                    # face already exists
                    pass

        if len(bm_seg.faces) > 0:
            new_mesh = bpy.data.meshes.new(f"{obj.name}_seg{seg}")
            bm_seg.to_mesh(new_mesh)
            seg_obj = bpy.data.objects.new(f"{obj.name}_seg{seg}", new_mesh)
            bpy.context.collection.objects.link(seg_obj)

        bm_seg.free()

    bm.free()
    
    # Delete the intermediate _segmented object as it's no longer needed
    bpy.data.objects.remove(new_obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_from_eval, do_unlink=True)
    
    return None


# Run the function on the active object
active_obj = bpy.context.active_object
if active_obj and active_obj.type == "CURVE":
    split_road_by_len(active_obj, num_divisions, len_attr_name)
else:
    print("Please select a curve object.")
