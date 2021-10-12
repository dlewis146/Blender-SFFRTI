bl_info = {
    "name" : "Blender RTI",
    "author" : "David A. Lewis",
    "version" : (0, 1, 0),
    "blender" : (2, 80, 0),
    "location" : "3D View > Tools > Blender RTI",
    "description" : "Addon for the digital simulation of RTI data collections",
    "warning" : "",
    "wiki_url" : "",
    "tracker_url" : "",
    "category" : "3D View"
}

import os
import bpy
from mathutils import Vector
import numpy as np

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )

from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )
from numpy import arange, subtract


### Scene Properties

class light(bpy.types.PropertyGroup):
    light = bpy.props.PointerProperty(name="Light object", 
                                      type = bpy.types.Object,
                                      description = "A light source")

class camera(bpy.types.PropertyGroup):
    camera = bpy.props.PointerProperty(name="Camera object", 
                                      type = bpy.types.Object,
                                      description = "A camera")

class lightSettings(PropertyGroup):

    lp_file_path : StringProperty(
        name="LP file path", 
        subtype="FILE_PATH",
        description="File path for light positions file (.lp)",
        default="",
        maxlen=1024
        )

    rti_parent : PointerProperty(
        name="RTI Parent",
        type=bpy.types.Object,
        description="Parent for RTI-related objects",
    )

    # light_object_list : bpy.props.CollectionProperty(type = light)
    light_list = []

class cameraSettings(PropertyGroup):

    focus_limits_auto : BoolProperty(
        name="Automatic focus positions", 
        description="Auto setting of camera position limts.",
        default=False,
    )

    camera_ortho : BoolProperty(
        name="Orthographic cameras", 
        description="Set camera view to orthographic.",
        default=False,
    )

    camera_type : bpy.props.EnumProperty(
        name = "Camera types",
        description = "Select a method for animating frames",
        items = [
            ('Moving', "Moving camera", "Set a single camera that moves to all desired positions"),
            ('Static', "Static cameras", "Set single camera that changes focus distance")
                ]
    )

    static_focus : FloatProperty(
        name="Static camera focus distance", 
        description="Focus distance for non-static camera placement",
        default=1.0,
    )

    camera_height : FloatProperty(
        name="Camera Height",
        description="Starting height for cameras (along Z-axis)",
        default=2.0,
    )

    num_z_pos : IntProperty(
        name="Number of Z positions", 
        description="Number of Z positions",
        default=1,
    )
   
    min_z_pos : FloatProperty(
        name="Lower focus position", 
        description="Lowest location to focus for SFF collection",
        default=2.0,
    )
    
    max_z_pos : FloatProperty(
        name="Upper focus position", 
        description="Highest location to focus for SFF collection",
        default=2.0,
    )

    main_object : PointerProperty(
        name="Object", 
        description="Object to use as focus for SFF collection.",
        type=bpy.types.Object,
    )

    aperture_size : FloatProperty(
        name="f/#",
        description="Aperture size, measured in f-stops",
    )

    sff_parent : PointerProperty(
        name="SFF Parent",
        type=bpy.types.Object,
        description="Parent for SFF-related objects",
    )

    # camera_object_list : bpy.props.CollectionProperty(type = camera)
    camera_list = []
    zPosList = []

class fileSettings(PropertyGroup):

    output_path : StringProperty(
        name="Output folder path",
        subtype="FILE_PATH",
        description="Folder path for outputting rendered frames.",
        default="",
        maxlen=1024
    )

    output_file_name : StringProperty(
        name="Output file name",
        description="File name to use when outputting image files for frames.",
        default="",
        maxlen=1024
    )

    csvOutputLines = []

### Operators

class CreateLights(Operator):
    bl_label = "Create RTI system"
    bl_idname = "rti.create_rti"

    def execute(self, context):
        scene = context.scene
        rtitool = scene.rti_tool

        if not os.path.isfile(rtitool.lp_file_path):
            self.report({"ERROR"})

        # Delete pre-existing lights
        # DeleteLights()

        # Create parent to hold all the lights
        rti_parent = bpy.data.objects.new(name = "rti_parent", object_data = None)

        # Link to scene
        scene.collection.objects.link(rti_parent)

        # Link to properties
        rtitool.rti_parent = rti_parent

        # Read in .lp data
        try:
            file = open(rtitool.lp_file_path)
        except RuntimeError as ex:
            error_report = "\n".join(ex.args)
            print("Caught error:", error_report)
            return {'ERROR'}

        rows = file.readlines()
        file.close()

        # Parse for number of lights
        numLights = int(rows[0].split()[0])

        # Create default light data
        lightData = bpy.data.lights.new(name="RTI_light", type="SUN")

        # Run through .lp file and create all lights
        for idx in range(1, numLights + 1):
            cols = rows[idx].split()
            x = float(cols[1])
            y = float(cols[2])
            z = float(cols[3])

            # Create light
            current_light = bpy.data.objects.new(name="Light_{0}".format(idx), object_data=lightData)
            # current_light = bpy.data.objects.new(name="Lamp_{0}".format(idx), object_data=bpy.data.lights.new(name="RTI_light", type="SUN"))
            
            # Re-position light
            current_light.location = (x, y, z)

            # Link light to scene
            scene.collection.objects.link(current_light)   
            
            current_light.rotation_mode = 'QUATERNION'
            current_light.rotation_quaternion = Vector((x,y,z)).to_track_quat('Z','Y')

            # Link light to rti_parent
            current_light.parent = rti_parent

            # Add light name to stored list for easier file creation later
            rtitool.light_list.append(current_light.name)

        return {"FINISHED"}            


class CreateSingleCamera(Operator):
    bl_idname = "rti.create_single_camera"
    bl_label = "Create single camera for RTI-only system"


    def execute(self, context):
        scene = context.scene

        # Create single camera at default height (w/o DoF)
        camera_data = bpy.data.cameras.new("Camera")
        camera_data.dof.use_dof = False
        camera_object = bpy.data.objects.new("Camera", camera_data)
        
        # Link camera to current scene
        scene.collection.objects.link(camera_object)
        
        # Set parent to RTI parent
        camera_object.parent = scene.rti_tool.rti_parent

        # Move camera to default location
        camera_object.location = (0,0,2)

        # Add camera ID to SFF camera list for animation creation
        scene.sff_tool.camera_list.append(camera_object.name)


        return {'FINISHED'}


class DeleteLights(Operator):
    bl_label="Delete RTI system"
    bl_idname = "rti.delete_rti"

    def execute(self, context):
        scene = context.scene
        rtitool = scene.rti_tool

        # Iterate through all lights in bpy.data.lights and remove them
        for current_light in bpy.data.lights:
            bpy.data.lights.remove(current_light)

        # Empty list of light IDs
        rtitool.light_list.clear()

        # Deselect any currently selected objects
        try:
            bpy.ops.object.select_all(action='DESELECT')
            # bpy.context.active_object.select_set(False)
        except:
            pass

        try: 
            # Source: https://blender.stackexchange.com/questions/44653/delete-parent-object-hierarchy-in-code
            names = set()

            def get_child_names(obj):

                for child in obj.children:
                    names.add(child.name)
                    if child.children:
                        get_child_names(child)

            get_child_names(rtitool.rti_parent)

            [bpy.data.objects[n].select_set(True) for n in names]
            rtitool.rti_parent.select_set(True)

            # Remove animation from child objects
            # for child_name in names:
            #     bpy.data.objects[child_name].animation.data.clear()

            # Delete rti_parent object
            bpy.ops.object.delete()

            # Remove rti_parent reference from properties
            rtitool.rti_parent = None

        except:
            pass

        return {'FINISHED'}


class CreateCameras(Operator):
    bl_idname = "sff.create_sff"
    bl_label = "Create SFF system"
    
    def execute(self, context):
        scene = context.scene
        sfftool = scene.sff_tool

        # Delete all pre-existing cameras
        # DeleteCameras()

        # Create parent to hold all the cameras
        sff_parent = bpy.data.objects.new(name = "sff_parent", object_data = None)

        # Link to scene
        scene.collection.objects.link(sff_parent)

        # Link to properties
        sfftool.sff_parent = sff_parent

        f = []
        if sfftool.focus_limits_auto:
            # Get min and max vertex Z positions and use to create f


            obj = sfftool.main_object # Selected object for SFF
            mw = obj.matrix_world # Selected object's world matrix

            minZ = 9999
            maxZ = 0

            if len(obj.children) >= 1:
                
                # If the selected object has children, iterate through them, transforming their vertex coordinates into world coordinates, then find the minimum and maximum amongst them.
                for child in obj.children:

                    glob_vertex_coordinates = [mw @ v.co for v in child.data.vertices] # Global coordinates of vertices

                    # Find lowest Z value amongst the object's verts
                    minZCurr = min([co.z for co in glob_vertex_coordinates])

                    # Find highest Z value amongst the object's verts
                    maxZCurr = max([co.z for co in glob_vertex_coordinates])

                    if minZCurr < minZ:
                        minZ = minZCurr
                    
                    if maxZCurr > maxZ:
                        maxZ = maxZCurr

            else:
                # In case there aren't any children, just iterate through all object vertices and find the min and max.

                glob_vertex_coordinates = [mw @ v.co for v in obj.data.vertices] # Global coordinates of vertices

                # Find lowest Z value amongst the object's verts
                minZCurr = min([co.z for co in glob_vertex_coordinates])

                # Find highest Z value amongst the object's verts
                maxZCurr = max([co.z for co in glob_vertex_coordinates])

                if minZCurr < minZ:
                    minZ = minZCurr
                
                if maxZCurr > maxZ:
                    maxZ = maxZCurr

            f = np.linspace(start=minZ, stop=maxZ, num=sfftool.num_z_pos, endpoint=True) 


        elif sfftool.focus_limits_auto is False:        
            f = np.linspace(start=sfftool.min_z_pos, stop=sfftool.max_z_pos, num=sfftool.num_z_pos, endpoint=True)

        # Add all zPos to sfftool.zPosList
        ## NOTE: Seems to require appending to have persistency outside of this method
        [sfftool.zPosList.append(i) for i in f]

        # Instantiate camera object
        camera_data = bpy.data.cameras.new("Camera")

        camera_data.dof.use_dof = True

        # Set camera type to orthographic if box is checked
        if sfftool.camera_ortho:
            camera_data.type = 'ORTHO'

        # Set aperture size
        camera_data.dof.aperture_fstop = sfftool.aperture_size

        if sfftool.camera_type == 'Moving':
            # Set static focus distance
            camera_data.dof.focus_distance = sfftool.static_focus

        elif sfftool.camera_type == 'Static':
            # Set depth of field focus distance for first position
            camera_data.dof.focus_distance = (sfftool.camera_height - f[0])

        # Create camera object from camera_data
        camera_object = bpy.data.objects.new("Camera", camera_data)

        # Link camera with current scene
        scene.collection.objects.link(camera_object)

        # Set parent to sff_parent
        camera_object.parent = sff_parent

        # Move camera to desired location
        if sfftool.camera_type == 'Moving':
            # Set camera so that first sampled focus point is at "focus distance" from camera 
            camera_object.location = (0, 0, sfftool.static_focus+f[0])
        
        elif sfftool.camera_type == 'Static':
            # Set camera to given height
            camera_object.location = (0, 0, sfftool.camera_height)

        # Add camera ID to stored list
        sfftool.camera_list.append(camera_object.name)

        return {'FINISHED'}


class CreateSingleLight(Operator):
    bl_idname = "sff.create_single_light"
    bl_label = "Create single light for SFF-only system"
    
    def execute(self, context):
        scene = context.scene

        # Create single light at (0,0,camera_height)
        lightData = bpy.data.lights.new(name="Light", type="SUN")
        light = bpy.data.objects.new(name="Light", object_data=lightData)

        # Reposition light
        light.location = (0, 0, scene.sff_tool.camera_height)

        # Link light to scene
        scene.collection.objects.link(light)

        # Link light to sff_parent
        light.parent = scene.sff_tool.sff_parent

        # Add light ID to RTI light list for animation creation
        scene.rti_tool.light_list.append(light.name)

        return {'FINISHED'}


class DeleteCameras(Operator):
    bl_idname = "sff.delete_sff"
    bl_label = "Delete SFF system"
    
    def execute(self, context):
        scene = context.scene
        sfftool = scene.sff_tool

        # Iterate through all cameras in bpy.data.cameras and remove them
        for cam in bpy.data.cameras:
            bpy.data.cameras.remove(cam)

        # Empty list of camera IDs
        sfftool.camera_list.clear()

        # Deselect any currently selected objects
        try:
            bpy.ops.object.select_all(action='DESELECT')
            # bpy.context.active_object.select_set(False)
        except:
            pass

        try:
            # Source: https://blender.stackexchange.com/questions/44653/delete-parent-object-hierarchy-in-code
            names = set()

            def get_child_names(obj):

                for child in obj.children:
                    names.add(child.name)
                    if child.children:
                        get_child_names(child)

                # return names

            get_child_names(sfftool.sff_parent)

            [bpy.data.objects[n].select_set(True) for n in names]
            sfftool.sff_parent.select_set(True)

            # Remove animation from child objects
            # for child_name in names:
            #     bpy.data.objects[child_name].animation.data.clear()

            # Delete sff_parent object
            bpy.ops.object.delete()

            # Remove sff_parent reference from properties
            sfftool.sff_parent = None

        except:
            self.report({'ERROR'}, "Broke inside child name getting")

        return {'FINISHED'}


class SetAnimation(Operator):
    bl_idname = "sffrti.set_animation"
    bl_label = "Create animation for data collection"

    def execute(self, context):

        scene = context.scene
        
        # Set renderer to Cycles
        scene.render.engine = 'CYCLES'

        # Get total numbers of frames
        numLights = len(scene.rti_tool.light_list)
        numCams = len(scene.sff_tool.camera_list)

        # Check to make sure lights and cameras both exist for the animation to be set.
        if numLights < 1:
            self.report({'ERROR'}, "There aren't any lights connected to the scene.")
            return {'CANCELLED'}
        if numCams < 1:
            self.report({'ERROR'}, "There aren't any cameras connected to the scene.")
            return {'CANCELLED'}

        #Clear previously stored CSV lines to start anew
        scene.file_tool.csvOutputLines = []

        # Create CSV header
        csvHeader = "image,x_lamp,y_lamp,z_lamp,z_cam,aperture_fstop,lens"
        scene.file_tool.csvOutputLines.append(csvHeader)

        # Clear previous animations
        try:
            for lightName in scene.rti_tool.light_list:
                scene.objects[lightName].animation_data_clear()
            for cameraName in scene.sff_tool.camera_list:
                scene.objects[cameraName].animation_data_clear()
        except KeyError:
            # Something wasn't deleted correctly and therefore wasn't deleted from a list
            pass

        # Clear timeline markers
        scene.timeline_markers.clear()
        
        camCount = 0
        lightCount = 0

        # Iterate through all permutations of cameras and lights and create keyframes for animation
        for camIdx in range(0, len(scene.sff_tool.zPosList)):
        # for camIdx in range(0, len(scene.sff_tool.camera_list)):

            ## TODO: Change to just saving and selecting single camera instead of list
            camera = scene.objects[scene.sff_tool.camera_list[0]]
            # camera = scene.objects[scene.sff_tool.camera_list[camIdx]]

            # currentFrame based on SyntheticRTI
            currentFrame = (camIdx * numLights) + 1
            # currentFrame = (numCams * numLights) + (camIdx * numLights) + 1

            # Move camera to desired location
            if scene.sff_tool.camera_type == 'Moving':
                # Move camera to current in zPosList
                camera.location = (0, 0, (scene.sff_tool.static_focus + scene.sff_tool.zPosList[camIdx]) )

            elif scene.sff_tool.camera_type == 'Static':
                # Change camera focus distance to current in zPosList
                camera.data.dof.focus_distance = (scene.sff_tool.camera_height - scene.sff_tool.zPosList[camIdx])
            
            mark = scene.timeline_markers.new(camera.name, frame=currentFrame)
            mark.camera = camera

            for lightIdx in range(0, len(scene.rti_tool.light_list)):

                light = scene.objects[scene.rti_tool.light_list[lightIdx]]

                # currentFrame based on SyntheticRTI
                currentFrame = (camIdx * numLights) + lightIdx + 1
                # currentFrame = (numCams * numLights) + (camIdx * numLights) + lightIdx + 1

                # Adapted from SyntheticRTI. Make sure light is hidden in previous and next frames.

                light.hide_viewport = True
                light.hide_render = True
                light.hide_set(True)

                light.keyframe_insert(data_path="hide_render", frame=currentFrame-1)
                light.keyframe_insert(data_path="hide_viewport", frame = currentFrame-1)
                light.keyframe_insert(data_path="hide_render", frame=currentFrame+1)
                light.keyframe_insert(data_path="hide_viewport", frame=currentFrame+1)

                # Make light visible in current frame.

                light.hide_viewport = False
                light.hide_render = False
                light.hide_set(False)

                light.keyframe_insert(data_path="hide_render", frame=currentFrame)
                light.keyframe_insert(data_path="hide_viewport", frame=currentFrame)

                # Insert keyframes to animate camera at current frame
                camera.keyframe_insert(data_path="location", frame=currentFrame)
                camera.keyframe_insert(data_path="location", frame=currentFrame)

                outputFrameNumber = str(currentFrame).zfill(len(str(numCams*numLights)))

                # Create line for output CSV
                csvNewLine = "-{0},{1},{2},{3},{4},{5},{6}".format(outputFrameNumber, light.location[0], light.location[1], light.location[2], camera.data.dof.focus_distance, camera.data.dof.aperture_fstop, camera.data.lens)

                scene.file_tool.csvOutputLines.append(csvNewLine)

                lightCount += 1

            camCount += 1
            lightCount = 0
        
        return {'FINISHED'}


class SetRender(Operator):
    bl_idname = "files.set_render"
    bl_label = "Set render settings"

    def execute(self, context):
        scene = context.scene
        
        # Remove all existing nodes to create new ones
        for node in scene.node_tree.nodes:
            scene.node_tree.nodes.remove(node)

        outputPath = scene.file_tool.output_path
        fileName = scene.file_tool.output_file_name

        # Error handling
        if outputPath == "":
            self.report({'ERROR'}, "Output file path not set.")
            return {'CANCELLED'}
        if fileName == "":
            self.report({'ERROR'}, "Output file name not set.")
            return {'CANCELLED'}

        # Get total numbers of frames
        numLights = len(scene.rti_tool.light_list)
        numCams = len(scene.sff_tool.camera_list)

        # Get number of spaces with which to zero-pad
        numSpaces = len(str(numCams*numLights))

        # Filename created to match SyntheticRTI as parsing functions are already written for that format
        scene.render.filepath = "{0}/PNG/{1}-{2}".format(outputPath, fileName,"#"*numSpaces)

        
        # Make sure Cycles is set as render engine
        scene.render.engine = 'CYCLES'

        # Image output settings
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.color_depth = "16"

        # Make sure compositing and nodes are enabled so that we can generate depth and normal images with render passes
        if not scene.render.use_compositing:
            scene.render.use_compositing = True
        if not scene.use_nodes:
            scene.use_nodes = True

        # Set color management to linear (?)
        scene.display_settings.display_device = 'None'

        # Disable overwriting of output images
        scene.render.use_overwrite = False

        # Set render passes
        current_render_layer = scene.view_layers['View Layer']
        # current_render_layer = scene.view_layers.active
        current_render_layer.use_pass_combined = True
        current_render_layer.use_pass_z = True
        current_render_layer.use_pass_normal = True
        current_render_layer.use_pass_shadow = True
        current_render_layer.use_pass_diffuse_direct = True
        current_render_layer.use_pass_diffuse_indirect = True
        current_render_layer.use_pass_diffuse_color = True
        current_render_layer.use_pass_glossy_direct = True
        current_render_layer.use_pass_glossy_indirect = True
        current_render_layer.use_pass_glossy_color = True

        # Create nodes for Render Layers, normalization, and output files
        ## NOTE: Positioning of nodes isn't considered as it's not important for background processes.
        render_layers_node = scene.node_tree.nodes.new(type="CompositorNodeRLayers")
        normalize_node = scene.node_tree.nodes.new(type="CompositorNodeNormalize")
        output_node_z = scene.node_tree.nodes.new(type="CompositorNodeOutputFile")
        output_node_normal = scene.node_tree.nodes.new(type="CompositorNodeOutputFile")

        # Link nodes together
        scene.node_tree.links.new(render_layers_node.outputs['Depth'], normalize_node.inputs['Value'])
        scene.node_tree.links.new(normalize_node.outputs['Value'], output_node_z.inputs['Image'])
        
        scene.node_tree.links.new(render_layers_node.outputs['Normal'], output_node_normal.inputs['Image'])

        # Set output filepaths
        output_node_z.base_path = scene.file_tool.output_path + "/Depth/"
        output_node_normal.base_path = scene.file_tool.output_path + "/Normal/"

        return {'FINISHED'}

        
class CreateCSV(Operator):
    bl_idname = "files.create_csv"
    bl_label = "Create CSV file"

    @classmethod
    def poll(cls, context):
        return len(context.scene.file_tool.csvOutputLines) != 0

    def execute(self, context):
        scene = context.scene

        outputPath = scene.file_tool.output_path
        fileName = scene.file_tool.output_file_name

        # Error handling
        if outputPath == "":
            self.report({'ERROR'}, "Output file path not set.")
            return {'CANCELLED'}
        if fileName == "":
            self.report({'ERROR'}, "Output file name not set.")
            return {'CANCELLED'}

        # Create file
        filePath = bpy.path.abspath(outputPath + '/' + fileName + ".csv")
        file = open(filePath, 'w')

        # Write header
        file.write(scene.file_tool.csvOutputLines[0])

        # Iterate through the remaining lines, writing desired filename and respective line
        for line in scene.file_tool.csvOutputLines[1:]:
            file.write(fileName + line)
            file.write('\n')
        file.close()

        return {'FINISHED'}


### Panel in Object Mode

class RTIPanel(Panel):
    """
    Create tool panel for handling RTI data collection
    """

    bl_label = "RTI Control"
    bl_idname = "VIEW3D_PT_rti_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RTI"

    # Hide panel when not in proper context
    # @classmethod
    # def poll(self, context):
    #     return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.rti_tool

        layout.prop(mytool, "lp_file_path")

        row = layout.row(align = True)
        row.operator("rti.create_rti")
        row.operator("rti.delete_rti")

        layout.operator("rti.create_single_camera")

        layout.prop(scene.file_tool, "output_path")
        layout.prop(scene.file_tool, "output_file_name")

        layout.operator("sffrti.set_animation")
        layout.operator("files.set_render")
        layout.operator("files.create_csv")


        layout.separator()


class SFFPanel(Panel):
    """
    Create tool panel for handling SFF data collection
    """

    bl_label = "SFF Control"
    bl_idname = "VIEW3D_PT_sff_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SFF"

    # Hide panel when not in proper context
    # @classmethod
    # def poll(self, context):
    #     return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sfftool = scene.sff_tool

        row = layout.row(align = True)
        row.prop(sfftool, "camera_ortho")
        row.prop(sfftool, "focus_limits_auto")

        layout.prop(sfftool, "camera_type")

        layout.prop(sfftool, "main_object")

        layout.prop(sfftool, "static_focus")

        layout.prop(sfftool, "camera_height")

        layout.prop(sfftool, "num_z_pos")
        layout.prop(sfftool, "aperture_size")

        row = layout.row(align = True)
        row.operator("sff.create_sff")
        row.operator("sff.delete_sff")

        layout.operator("sff.create_single_light")

        layout.operator("sffrti.set_animation")

        layout.prop(scene.file_tool, "output_path")
        layout.prop(scene.file_tool, "output_file_name")

        layout.operator("files.set_render")
        layout.operator("files.create_csv")

        layout.separator()


### Registration

classes = (light, camera, lightSettings, cameraSettings, fileSettings, CreateLights, CreateSingleCamera, DeleteLights, CreateCameras, CreateSingleLight, DeleteCameras, SetAnimation, SetRender, CreateCSV, RTIPanel, SFFPanel)

def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.rti_tool = PointerProperty(type=lightSettings)
    bpy.types.Scene.sff_tool = PointerProperty(type=cameraSettings)
    bpy.types.Scene.file_tool = PointerProperty(type=fileSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.rti_tool
    del bpy.types.Scene.sff_tool


if __name__ == "__main__":
    register()