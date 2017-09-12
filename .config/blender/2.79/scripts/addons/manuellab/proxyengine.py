#ManuelbastioniLAB - Copyright (C) 2016 Manuel Bastioni
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import algorithms
import os, json, time
import mathutils
import logging
import bpy
lab_logger = logging.getLogger('manuelbastionilab_logger')

def error_msg(path):
    lab_logger.error("Database file not found or corrupted: {0}".format(algorithms.simple_path(path)))

def get_boundary_verts(blender_object):
    obj = blender_object
    polygons_dict = {}
    for polyg in obj.data.polygons:
        for i in polyg.vertices:
            if str(i) not in polygons_dict:
                indices = [n for n in polyg.vertices if n != i]
                polygons_dict[str(i)] = indices
            else:
                for vert_id in polyg.vertices:
                    if vert_id != i and vert_id not in polygons_dict[str(i)]:
                        polygons_dict[str(i)].append(vert_id)

    return polygons_dict

def load_forma_database(data_path):
    lab_logger.info("Loading forma from {0}".format(algorithms.simple_path(data_path)))
    if os.path.isfile(data_path):
        database_file = open(data_path, "r")
        try:
            forma_data = json.load(database_file)
        except:
            lab_logger.error("Error decoding {0}".format(algorithms.simple_path(data_path)))
            database_file.close()
            return None
        database_file.close()
        return forma_data
    else:
        error_msg(data_path)
        return None

def save_forma_database(blender_object, filepath):
    lab_logger.info("Saving forma in {0}".format(algorithms.simple_path(filepath)))
    time1 = time.time()
    obj = blender_object
    forma_data = []
    for polyg in obj.data.polygons:
        polygon_data = [polyg.index]
        factors = algorithms.polygon_forma(obj, polyg)
        polygon_data += factors
        forma_data.append(polygon_data)

    database_file = open(filepath, 'w')
    json.dump(forma_data, database_file)
    database_file.close()
    lab_logger.info("Forma of obj {0} saved in {1} secs".format(obj, time.time()-time1))

def calculate_finishing_morph(blender_object, boundary_verts, morph_forma_data, threshold=0.25):
    obj = blender_object
    for m_data in morph_forma_data:
        polyg = obj.data.polygons[int(m_data[0])]
        orig_factors = [float(n) for n in m_data[1:]]
        new_factors = algorithms.polygon_forma(obj, polyg)
        deformations = []
        for idx in range(len(new_factors)):
            deformations.append(abs(new_factors[idx]-orig_factors[idx]))
        max_deform = max(deformations)/2.0

        if max_deform > threshold:
            for idx in polyg.vertices:
                b_verts = boundary_verts[str(idx)]
                average = mathutils.Vector((0, 0, 0))

                for vidx in b_verts:
                    coords = mathutils.Vector(obj.data.vertices[vidx].co)
                    average += coords

                average = average/len(b_verts)
                obj.data.vertices[idx].co = obj.data.vertices[idx].co*(1.0 - max_deform) + average*max_deform

#def find_best_polygon(self, vert, polygons):
    #for polyg in polygons:
        #if polyg.normal.dot(vert.normal) > 0:
            #return polyg
    #return polygons[0]

def average_basis_matrix(vec0, vec1, vec2, invert=False, normalize=True):

    if normalize:
        vec0.normalize()
        vec1.normalize()
        vec2.normalize()

    mtx = mathutils.Matrix((
        (vec0[0], vec1[0], vec2[0]),
        (vec0[1], vec1[1], vec2[1]),
        (vec0[2], vec1[2], vec2[2]),
        ))
    if invert:
        try:
            mtx.invert() #TODO: use invert_safe
            return mtx
        except:            
            return None
    else:
        return mtx


def save_proxy_database(body, proxy, filepath):

    lab_logger.info("Saving proxy data in {0}".format(algorithms.simple_path(filepath)))
    search_tree = mathutils.kdtree.KDTree(len(body.data.polygons))

    for face in body.data.polygons:
        search_tree.insert(face.center, face.index)
    search_tree.balance()

    proxy_data = []
    for vert in proxy.data.vertices:
        closer_polygons = search_tree.find_n(vert.co, 1)

        p_index = closer_polygons[0][1]
        polygon = body.data.polygons[p_index]

        vec0 = polygon.normal.copy()
        vec1 = polygon.center-body.data.vertices[polygon.vertices[0]].co
        vec2 = vec0.cross(vec1)

        delta_vector = vert.co-polygon.center
        mtx = average_basis_matrix(vec0, vec1, vec2, invert=True)
        if mtx:
            d_vect = mtx*delta_vector
            proxy_data.append([
                int(p_index),
                round(float(d_vect[0]), 4),
                round(float(d_vect[1]), 4),
                round(float(d_vect[2]), 4)])

        else:
            proxy_data.append([int(p_index), 0, 0, 0])

    file_proxy = open(filepath, 'w')
    json.dump(proxy_data, file_proxy)
    file_proxy.close()

def load_proxy_database(body, proxy, filepath):

    lab_logger.info("Loading proxy from {0}".format(algorithms.simple_path(filepath)))

    if os.path.isfile(filepath):
        database_file = open(filepath, "r")
        try:
            fitting_data = json.load(database_file)
        except:
            lab_logger.error("Error decoding {0}".format(algorithms.simple_path(filepath)))
            database_file.close()
            return
        database_file.close()
    else:
        error_msg(filepath)
        return


    for proxy_index, m_data in enumerate(fitting_data):
        p_index = m_data[0]
        delta0 = m_data[1]
        delta1 = m_data[2]
        delta2 = m_data[3]

        proxy_vert = proxy.data.vertices[proxy_index]
        polygon = body.polygons[p_index]

        vec0 = polygon.normal.copy()
        vec1 = polygon.center-body.vertices[polygon.vertices[0]].co
        vec2 = vec0.cross(vec1)

        d_vect = mathutils.Vector((delta0, delta1, delta2))
        mtx = average_basis_matrix(vec0, vec1, vec2)
        if mtx:
            delta_vector = mtx*d_vect
        proxy_vert.co = polygon.center+delta_vector


def validate_proxy_save(human_obj):
    proxy_obj = bpy.context.active_object    
    origin_dist = proxy_obj.location - human_obj.location
    
    if proxy_obj == human_obj:
        proxy_status = "Please select the proxy mesh"
        lab_logger.warning(proxy_status)
        return proxy_status
    
    if origin_dist.length > 0.0001:
        proxy_status = "Please fix obj origin: the origin of proxy must be the same of the humanoid"
        lab_logger.warning(proxy_status)
        return proxy_status

    if proxy_obj.type != 'MESH':
        proxy_status = "{0} cannot be used as proxy mesh".format(proxy_obj.name)
        lab_logger.warning(proxy_status)
        return proxy_status

    for modf in proxy_obj.modifiers:
        if modf.type == 'ARMATURE':
            if modf.show_viewport == True:
                proxy_status = "Please disable the armature modifier in {0} before calibrating".format(proxy_obj.name)
                lab_logger.warning(proxy_status) 
                return proxy_status   

    if proxy_obj.scale != human_obj.scale:
        proxy_status = "Please fix the scale of {0}. It must be the same of human [1,1,1]".format(proxy_obj.name)
        lab_logger.warning(proxy_status)
        return proxy_status

    return "OK"


def validate_proxy_load(human_obj):
    
    for modf in human_obj.modifiers:
        if modf.type == 'SUBSURF':
            if modf.show_viewport == True:
                proxy_status = "Please disable the subdivision modifier in {0} before proxy fitting".format(human_obj.name)
                lab_logger.warning(proxy_status)    
                return proxy_status
                
    return "OK"
                
    


def validate_proxy_select(human_obj):
    proxy_obj = bpy.context.active_object   

    if proxy_obj == human_obj:
        proxy_status = "Please select the proxy mesh"
        lab_logger.warning(proxy_status)
        return proxy_status

    if proxy_obj.type != 'MESH':
        proxy_status = "{0} cannot be used as proxy mesh".format(proxy_obj.name)
        lab_logger.warning(proxy_status)
        return proxy_status
        
    return "OK"
    
def move_proxy_origin_to_human_origin(human_obj):
    scn = bpy.context.scene
    proxy_obj = bpy.context.active_object    
    
    if proxy_obj.location != human_obj.location:
        scn.cursor_location = human_obj.location
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        lab_logger.info("Origin of {0} moved to origin of {1}".format(proxy_obj.name,human_obj.name))
        
def apply_proxy_transformations(human_obj):    
    proxy_obj = bpy.context.active_object    
    if proxy_obj.scale != human_obj.scale:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        lab_logger.info("Applied transformation to {0}".format(proxy_obj.name))
        
def disable_modifiers(human_obj):    
    proxy_obj = bpy.context.active_object    
    
    for modf in proxy_obj.modifiers:
        if modf.type == 'ARMATURE':
            modf.show_viewport = False
            lab_logger.info("Disabled armature in {0}".format(proxy_obj.name))
            
    for modf in human_obj.modifiers:
        if modf.type == 'SUBSURF':
            modf.show_viewport = False
            lab_logger.info("Disabled armature in {0}".format(human_obj.name))
            
   

