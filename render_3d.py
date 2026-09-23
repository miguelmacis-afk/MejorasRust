import sys
import os
import bpy

# Obtener los argumentos pasados tras '--'
args = sys.argv[sys.argv.index("--") + 1:]
obj_path = args[0]
output_png = args[1]

# Limpiar cualquier objeto existente en Blender
bpy.ops.wm.read_factory_settings(use_empty=True)

# Importar el archivo .obj
try:
    bpy.ops.wm.obj_import(filepath=obj_path)
except AttributeError:
    bpy.ops.import_scene.obj(filepath=obj_path)

# Buscar los objetos 3D importados
imported_objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']

if imported_objs:
    # Crear Cámara y Luz tipo Sol
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))

    # Enfocar la cámara hacia el centro del objeto
    cam.location = (3, -3, 2)
    constraint = cam.constraints.new(type='TRACK_TO')
    constraint.target = imported_objs[0]
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

# Configurar calidad y tamaño de la imagen de salida (512x512)
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = output_png
scene.render.resolution_x = 512
scene.render.resolution_y = 512

# Generar la imagen
bpy.ops.render.render(write_still=True)
