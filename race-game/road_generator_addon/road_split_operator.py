"""
Road splitting operator for dividing roads into segments
"""

import bpy
import bmesh
from bpy.types import Operator


def _smart_uv_unwrap(obj, angle_limit=66.0, island_margin=0.02, area_weight=0.0):
    """Create a new UV map and run Smart UV Project on the given mesh object.
    - Always creates a new UV layer (never overrides existing)
    - Runs the unwrap on that newly created layer
    - Restores previous active object and mode afterwards
    """
    if not obj or obj.type != 'MESH':
        return False

    # Ensure object is in the view layer and selectable
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    prev_mode = bpy.context.mode

    # Create a new UV map and make it active
    uv_layer = obj.data.uv_layers.new(name="UVMap")  # Blender auto-uniques names
    obj.data.uv_layers.active = uv_layer
    obj.data.uv_layers.active_index = len(obj.data.uv_layers) - 1

    # Make object active and in Edit mode
    for o in view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj

    try:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(
            angle_limit=angle_limit, 
            island_margin=island_margin, 
            area_weight=area_weight,
            correct_aspect=True
        )
    except TypeError as e:
        # Fallback for compatibility with different Blender versions
        print(f"Smart UV Project parameter error: {e}")
        print("Attempting with minimal parameters...")
        bpy.ops.uv.smart_project(angle_limit=angle_limit)
    finally:
        # Return to object mode and restore previous active
        bpy.ops.object.mode_set(mode='OBJECT')
        if prev_active is not None and prev_active != obj:
            for o in view_layer.objects:
                o.select_set(False)
            prev_active.select_set(True)
            view_layer.objects.active = prev_active
        else:
            # Keep current as active if there was none before
            pass

    return True


class MESH_OT_split_road(Operator):
    """Split road mesh into segments based on length attribute"""
    bl_idname = "mesh.split_road"
    bl_label = "Split Road"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'CURVE'
    
    def split_road_by_len(self, obj, num_divisions, len_attr_name):
        """Split road mesh based on length attribute"""
        
        # Get settings for Smart UV
        settings = bpy.context.scene.road_generator_settings
        
        # Duplicate the object with modifiers applied
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        mesh_from_eval = bpy.data.meshes.new_from_object(obj_eval)
        
        # Create new mesh object
        new_obj = bpy.data.objects.new(obj.name + "_segmented", mesh_from_eval)
        bpy.context.collection.objects.link(new_obj)

        # Immediately create a Smart UV unwrap on the combined road mesh (new UV map) if enabled
        if settings.enable_smart_uv:
            _smart_uv_unwrap(
                new_obj,
                angle_limit=settings.smart_uv_angle_limit,
                island_margin=settings.smart_uv_island_margin,
                area_weight=settings.smart_uv_area_weight
            )
        
        # Get bmesh for processing
        bm = bmesh.new()
        bm.from_mesh(new_obj.data)
        
        # Store existing UV layer information
        existing_uv_layers = []
        for uv_layer in new_obj.data.uv_layers:
            existing_uv_layers.append(uv_layer.name)
        
        # Get UV layers from bmesh for copying later
        bm_uv_layers = {}
        for uv_name in existing_uv_layers:
            uv_layer = bm.loops.layers.uv.get(uv_name)
            if uv_layer:
                bm_uv_layers[uv_name] = uv_layer
        
        # Ensure vertex attributes exist
        layer = bm.verts.layers.float.get(len_attr_name)
        if layer is None:
            print(f"ERROR: Vertex attribute '{len_attr_name}' not found.")
            bm.free()
            bpy.data.objects.remove(new_obj, do_unlink=True)
            bpy.data.meshes.remove(mesh_from_eval, do_unlink=True)
            return False
        
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
        created_segments = []
        for seg in range(num_divisions):
            bm_seg = bmesh.new()
            vmap = {}
            
            # Create UV layers in segment bmesh to match original
            seg_uv_layers = {}
            for uv_name, source_uv_layer in bm_uv_layers.items():
                seg_uv_layer = bm_seg.loops.layers.uv.new(uv_name)
                seg_uv_layers[uv_name] = seg_uv_layer
            
            # Map to track loop correspondence for UV copying
            face_map = {}  # Maps original face to new face
            
            for f in bm.faces:
                if face_to_segment[f.index] == seg:
                    verts = []
                    for v in f.verts:
                        if v not in vmap:
                            vmap[v] = bm_seg.verts.new(v.co)
                        verts.append(vmap[v])
                    try:
                        new_face = bm_seg.faces.new(verts)
                        face_map[f] = new_face
                        
                        # Copy UV data for each UV layer
                        for uv_name, source_uv_layer in bm_uv_layers.items():
                            seg_uv_layer = seg_uv_layers[uv_name]
                            # Copy UV coordinates for each loop
                            for i, loop in enumerate(f.loops):
                                source_uv = loop[source_uv_layer].uv
                                new_face.loops[i][seg_uv_layer].uv = source_uv.copy()
                                
                    except ValueError:
                        # face already exists
                        pass
            
            if len(bm_seg.faces) > 0:
                new_mesh = bpy.data.meshes.new(f"{obj.name}_seg{seg}")
                bm_seg.to_mesh(new_mesh)
                seg_obj = bpy.data.objects.new(f"{obj.name}_seg{seg}", new_mesh)
                bpy.context.collection.objects.link(seg_obj)
                
                # Smart UV unwrap each segment on its own new map if enabled
                if settings.enable_smart_uv:
                    _smart_uv_unwrap(
                        seg_obj,
                        angle_limit=settings.smart_uv_angle_limit,
                        island_margin=settings.smart_uv_island_margin,
                        area_weight=settings.smart_uv_area_weight
                    )
                
                created_segments.append(seg_obj)
            
            bm_seg.free()
        
        bm.free()
        
        # Delete the intermediate _segmented object as it's no longer needed
        bpy.data.objects.remove(new_obj, do_unlink=True)
        bpy.data.meshes.remove(mesh_from_eval, do_unlink=True)
        
        return True
    
    def execute(self, context):
        settings = context.scene.road_generator_settings
        active_obj = context.active_object
        
        if active_obj and active_obj.type == "CURVE":
            success = self.split_road_by_len(
                active_obj, 
                settings.num_divisions, 
                settings.len_attr_name
            )
            
            if success:
                self.report({'INFO'}, f"Road split into {settings.num_divisions} segments")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Failed to split road. Check if '{settings.len_attr_name}' attribute exists")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Please select a curve object")
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(MESH_OT_split_road)

def unregister():
    bpy.utils.unregister_class(MESH_OT_split_road)
