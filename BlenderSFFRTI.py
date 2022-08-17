bl_info = {
    "name" : "Blender SFF-RTI",
    "author" : "David A. Lewis",
    "version" : (1, 1, 0),
    "blender" : (3, 0, 0),
    "location" : "3D View > Tools > Blender RTI",
    "description" : "Addon for the digital simulation of RTI and SFF data collections",
    "warning" : "",
    "wiki_url" : "",
    "tracker_url" : "",
    "category" : "3D View"
}

import os
import bpy
from mathutils import Vector
import numpy as np
import math
import csv

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

    dome_radius : FloatProperty(
        name="RTI dome radius",
        description="Radius of RTI dome [m]",
        default=1
    )

    # light_object_list : bpy.props.CollectionProperty(type = light)
    light_list = []

class cameraSettings(PropertyGroup):

    focus_limits_type : bpy.props.EnumProperty(
        name = "Focus limit methods",
        description = "Select a method for choosing SFF depth levels",
        items = [
            ('Auto', "Automatic focus limits", "Sets focus limits based on highest and lowest vertices of selected object."),
            ('Manual', "Manual focus limits", "Allows for setting of focus limits manually."),
            ('Tasked', "Tasked SFF w/ CSV", "Reads a given CSV for depth levels to image at.")
                ]
    )


    camera_type : bpy.props.EnumProperty(
        name = "Camera types",
        description = "Select a method for animating frames",
        items = [
            ('Moving', "Moving camera", "Set a single camera that moves to all desired positions"),
            ('Static', "Static camera", "Set single camera that changes focus distance")
                ]
    )

    static_focus : FloatProperty(
        name="Static camera focus distance", 
        description="Focus distance for non-static camera placement",
        default=1.0,
    )

    camera_height : FloatProperty(
        name="Static camera height",
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
        name="Aperture size (f/#)",
        description="Aperture size, measured in f-stops",
    )

    sff_parent : PointerProperty(
        name="SFF Parent",
        type=bpy.types.Object,
        description="Parent for SFF-related objects",
    )

    tasked_file_path : StringProperty(
        name="Tasked SFF file path", 
        subtype="FILE_PATH",
        description="File path for CSV which describes depth levels for a tasked SFF acquisition (.csv)",
        default="",
        maxlen=1024
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

    # output_file_name : StringProperty(
    #     name="Output file name",
    #     description="File name to use when outputting image files for frames.",
    #     default="",
    #     maxlen=1024
    # )

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
        # NOTE: Using SUN light source for ease of lighting right now since it doesn't implement the Inverse-Square Law for falloff of light intensity
        lightData = bpy.data.lights.new(name="RTI_light", type="SUN")

        # Run through .lp file and create all lights
        for idx in range(1, numLights + 1):
            cols = rows[idx].split()
            x = float(cols[1])
            y = float(cols[2])
            z = float(cols[3])

            r, long, lat = Cartesian2Polar3D(x,y,z)
            r = rtitool.dome_radius
            x, y, z = Polar2Cartesian3D(r,long,lat)

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

        if len(scene.sff_tool.camera_list) != 0:
            self.report({'ERROR'}, "Cameras already exist in scene.")
            return {'FINISHED'}

        # Create single camera at default height (w/o DoF)
        camera_data = bpy.data.cameras.new("Camera")
        camera_data.dof.use_dof = False
        camera_object = bpy.data.objects.new("Camera", camera_data)
        
        # Link camera to current scene
        scene.collection.objects.link(camera_object)
        
        # Set parent to RTI parent
        camera_object.parent = scene.rti_tool.rti_parent

        # Move camera to default location at top of dome
        camera_object.location = (0,0,scene.rti_tool.dome_radius)
        # camera_object.location = (0,0,2)

        # Add camera ID to SFF camera list for animation creation
        scene.sff_tool.camera_list.append(camera_object.name)

        # NOTE: First clearing zPosList to make sure that previous SFF collections aren't being stored still. This would create a false understanding of the number of positions
        scene.sff_tool.zPosList.clear()

        # Add default Z-position to zPosList
        scene.sff_tool.zPosList.append(scene.rti_tool.dome_radius)
        # scene.sff_tool.zPosList.append(2)

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

            # Remove single camera from list if present
            if len(scene.sff_tool.zPosList) == 1:
                scene.sff_tool.zPosList.clear()
                scene.sff_tool.camera_list.clear()


            # if len(scene.sff_tool.camera_list)

        except:
            self.report({'ERROR'}, "Broke inside child name getting")

        return {'FINISHED'}


class CreateCameras(Operator):
    bl_idname = "sff.create_sff"
    bl_label = "Create SFF system"
    
    def execute(self, context):
        scene = context.scene
        sfftool = scene.sff_tool

        # Create parent to hold the system
        sff_parent = bpy.data.objects.new(name = "sff_parent", object_data = None)

        # Link to scene
        scene.collection.objects.link(sff_parent)

        # Link to properties
        sfftool.sff_parent = sff_parent

        f = DefineFocusLimits(context)

        # Add all zPos to sfftool.zPosList
        ## NOTE: Seems to require appending to persist outside of this method
        [sfftool.zPosList.append(i) for i in f]

        # Instantiate camera object
        camera_data = bpy.data.cameras.new("Camera")

        camera_data.dof.use_dof = True

        # Set camera type to orthographic if box is checked
        # if sfftool.camera_ortho:
        #     camera_data.type = 'ORTHO'

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
            # Set camera so that first sF[0])
            camera_object.location = (0, 0, f[0])

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

        if len(scene.rti_tool.light_list) != 0:
            self.report({'ERROR'}, "Lights already exist in scene.")
            return {'FINISHED'}

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
            cam.animation_data_clear()
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

            # Clear zPosList
            sfftool.zPosList.clear()

            # NOTE: IF single light exists, assume it's created for SFF and clear it from the stored light list
            if len(scene.rti_tool.light_list) == 1:
                scene.rti_tool.light_list.clear()

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
        # scene.file_tool.csvOutputLines = []
        scene.file_tool.csvOutputLines.clear()

        # Create CSV header
        csvHeader = "image,x_lamp,y_lamp,z_lamp,z_cam,aperture_fstop,lens"
        scene.file_tool.csvOutputLines.append(csvHeader)

        # Clear previous animations
        scene.animation_data_clear()
        for o in scene.objects:
            o.animation_data_clear()

        # Recompute SFF camera positions if currently stored num_z_pos is different than length of stored position list 
        # if scene.sff_tool.num_z_pos != len(scene.sff_tool.zPosList):
        #     f = DefineFocusLimits(context)

        #     # Clear sfftool.zPosList
        #     scene.sff_tool.zPosList.clear()

        #     # Add all zPos to sfftool.zPosList
        #     ## NOTE: Seems to require appending to have persistency outside of this method
        #     [scene.sff_tool.zPosList.append(i) for i in f]


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

            # aperture_size = ComputeApertureSize(context)
            # camera.data.dof.aperture_fstop = ComputeApertureSize(context)

            # Move camera to desired location
            if scene.sff_tool.camera_type == 'Moving':
                # Move camera to current in zPosList
                camera.location = (0, 0, (scene.sff_tool.static_focus + scene.sff_tool.zPosList[camIdx]) )

            elif scene.sff_tool.camera_type == 'Static':
                # Change camera focus distance to current in zPosList
                camera.data.dof.focus_distance = (scene.sff_tool.camera_height - scene.sff_tool.zPosList[camIdx])
            
            # mark = scene.timeline_markers.new(camera.name, frame=currentFrame)
            # mark.camera = camera

            for lightIdx in range(0, len(scene.rti_tool.light_list)):

                light = scene.objects[scene.rti_tool.light_list[lightIdx]]

                # currentFrame based on SyntheticRTI
                currentFrame = (camIdx * numLights) + lightIdx + 1
                # currentFrame = (numCams * numLights) + (camIdx * numLights) + lightIdx + 1

                # Adapted from SyntheticRTI. Make sure light is hidden in previous and next frames.

                ## TEMP: Fix always hidden light in SFF by not hiding lights if only one exists. This might be an issue with how we're iterating across the lights...
                if len(scene.rti_tool.light_list) > 1:

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

                # Insert keyframes to animate camera movement at current frame IF MOVING IS SELECTED
                if scene.sff_tool.camera_type == 'Moving':
                    camera.keyframe_insert(data_path="location", frame=currentFrame)
                    camera.keyframe_insert(data_path="location", frame=currentFrame)
                
                # Insert keyframes to animate camera focus length at current frame IF STATIC IS SELECTED
                if scene.sff_tool.camera_type == 'Static':
                    camera.data.dof.keyframe_insert(data_path="focus_distance", frame=currentFrame)


                outputFrameNumber = str(currentFrame).zfill(len(str(numCams*numLights)))

                csvNewLine = ""

                # Create line for output CSV

                # If static camera, set 'z_cam' column to be camera focus distance
                if scene.sff_tool.camera_type == "Static":
                    csvNewLine = "-{0},{1},{2},{3},{4},{5},{6}".format(outputFrameNumber, light.location[0], light.location[1], light.location[2], camera.data.dof.focus_distance, camera.data.dof.aperture_fstop, camera.data.lens)
                    print("Keyframe created for static camera focused at (0,0,{0}) and light at ({1}, {2}, {3})".format(camera.data.dof.focus_distance-scene.sff_tool.camera_height, light.location[0], light.location[1], light.location[2]))

                # If moving camera, set 'z_cam' column to be new camera location
                elif scene.sff_tool.camera_type == "Moving":
                    csvNewLine = "-{0},{1},{2},{3},{4},{5},{6}".format(outputFrameNumber, light.location[0], light.location[1], light.location[2], camera.location[2], camera.data.dof.aperture_fstop, camera.data.lens)
                    print("Keyframe created for dynamic camera at (0,0,{0}) and light at ({1}, {2}, {3})".format(camera.location[2], light.location[0], light.location[1], light.location[2]))


                scene.file_tool.csvOutputLines.append(csvNewLine)


                lightCount += 1

            camCount += 1
            lightCount = 0
        
        # Set maximum number of frames to render (-1 for the header)
        scene.frame_end = len(scene.file_tool.csvOutputLines)-1


        return {'FINISHED'}


class SetRender(Operator):
    bl_idname = "files.set_render"
    bl_label = "Set render settings"

    def execute(self, context):
        scene = context.scene
        
        # Make sure compositing and nodes are enabled so that we can generate depth and normal images with render passes
        if not scene.render.use_compositing:
            scene.render.use_compositing = True
        if not scene.use_nodes:
            scene.use_nodes = True

        # Remove all existing nodes to create new ones
        try:
            for node in scene.node_tree.nodes:
                scene.node_tree.nodes.remove(node)
        except:
            pass

        outputPath = scene.file_tool.output_path

        # Error handling
        if outputPath == "":
            self.report({'ERROR'}, "Output file path not set.")
            return {'CANCELLED'}

        # Get total numbers of frames
        numLights = len(scene.rti_tool.light_list)
        numCams = len(scene.sff_tool.camera_list)

        # Get number of spaces with which to zero-pad
        numSpaces = len(str(numCams*numLights))

        # Set filepath as well as format for iterated filenames
        scene.render.filepath = "{0}/Renders/Image-{1}".format(outputPath,"#"*numSpaces)
        
        # Make sure Cycles is set as render engine
        scene.render.engine = 'CYCLES'

        # Image output settings
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.color_depth = "8"

        # Set color management to linear (?)
        scene.display_settings.display_device = 'None'

        # Disable overwriting of output images by default
        scene.render.use_overwrite = False

        # Set render passes
        current_render_layer = scene.view_layers['ViewLayer']
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

        # Create nodes for Render Layers, map range, normalization, and output files
        ## NOTE: Positioning of nodes isn't considered as it's not important for background processes.
        render_layers_node = scene.node_tree.nodes.new(type="CompositorNodeRLayers")
        # normalize_node = scene.node_tree.nodes.new(type="CompositorNodeNormalize")
        output_node_z = scene.node_tree.nodes.new(type="CompositorNodeOutputFile")
        output_node_normal = scene.node_tree.nodes.new(type="CompositorNodeOutputFile")

        if scene.sff_tool.focus_limits_type != "Auto":
            # Set map range node settings
            map_range_node = scene.node_tree.nodes.new(type="CompositorNodeMapRange")
            map_range_node.use_clamp = True
            map_range_node.inputs[2].default_value = scene.sff_tool.camera_height
            # map_range_node.inputs[1].default_value = (scene.sff_tool.camera_height - np.max(scene.sff_tool.zPosList))
            map_range_node.inputs[1].default_value = (scene.sff_tool.camera_height - scene.sff_tool.max_z_pos)

            # Link nodes together
            scene.node_tree.links.new(render_layers_node.outputs['Depth'], map_range_node.inputs['Value'])
            scene.node_tree.links.new(map_range_node.outputs['Value'], output_node_z.inputs['Image'])

        elif scene.sff_tool.focus_limits_type == "Auto":
            normalize_node = scene.node_tree.nodes.new(type="CompositorNodeNormalize")

            # Link nodes together
            scene.node_tree.links.new(render_layers_node.outputs['Depth'], normalize_node.inputs['Value'])
            scene.node_tree.links.new(normalize_node.outputs['Value'], output_node_z.inputs['Image'])

        # Set normal node output
        scene.node_tree.links.new(render_layers_node.outputs['Normal'], output_node_normal.inputs['Image'])

        # Set output filepaths
        output_node_z.base_path = scene.file_tool.output_path + "/Depth/"
        output_node_normal.base_path = scene.file_tool.output_path + "/Normal/"

        return {'FINISHED'}

        
class CreateCSV(Operator):
    bl_idname = "files.create_csv"
    # bl_label = "Create CSV file"
    bl_label = "Create CSV and text files"

    @classmethod
    def poll(cls, context):
        return len(context.scene.file_tool.csvOutputLines) != 0

    def execute(self, context):
        scene = context.scene

        outputPath = scene.file_tool.output_path

        # Error handling
        if outputPath == "":
            self.report({'ERROR'}, "Output file path not set.")
            return {'CANCELLED'}

        # Create file
        filePath = bpy.path.abspath(outputPath + "/Image" + ".csv")
        file = open(filePath, 'w')

        # Write header
        file.write(scene.file_tool.csvOutputLines[0])
        file.write('\n')

        # Iterate through the remaining lines, writing desired filename and respective line
        for line in scene.file_tool.csvOutputLines[1:]:
            file.write("Image" + line)
            file.write('\n')
        file.close()

        # Write out camera distance and aperture size from sff_tool into 
        # space-delimited text file
        filePath = bpy.path.abspath(outputPath + "/Camera Settings" + ".txt")
        file = open(filePath, 'w')
        file.write("distance ")
        file.write(str(context.scene.sff_tool.camera_height))
        file.write('\n')
        file.write("aperture ")
        file.write(str(context.scene.sff_tool.aperture_size))
        file.close()

        return {'FINISHED'}


### Helper functions

def DefineFocusLimits(context):
    """
    Function to compute list of Z-axis positions for SFF camera
    """

    scene = context.scene
    sfftool = scene.sff_tool

    f = []
    if sfftool.focus_limits_type == "Auto":
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

    elif sfftool.focus_limits_type == "Tasked":

        # Check to make sure that CSV exists
        if not os.path.isfile(sfftool.tasked_file_path):
            self.report({"ERROR"})

        # Read in .csv data
        filename = open(sfftool.tasked_file_path, 'r')
        depthData = csv.DictReader(filename)

        ## NOTE: Subtracting camera height from distances

        # Iterate through CSV file and get desired depth levels
        for col in depthData:
            # f.append(sfftool.camera_height - float(col["Depth"]))
            f.append(float(col["Depth"]))

        # Sort stored depth levels
        f = sorted(f)

    elif sfftool.focus_limits_type == "Manual":
        f = np.linspace(start=sfftool.min_z_pos, stop=sfftool.max_z_pos, num=sfftool.num_z_pos, endpoint=True)

    return f


def ComputeApertureSize(context):
    """
    Used to compute an appropriate aperture size for the desired number of Z positions in the given space
    """

    scene = context.scene
    sfftool = scene.sff_tool

    camera_data = scene.objects[sfftool.camera_list[0]].data

    # Get camera focal length
    # NOTE: Assuming one camera right now
    f = camera_data.lens / 1000
    
    # Get object distance for computing DoF
    s = (sfftool.camera_height - sfftool.zPosList[0]) / 1000

    # NOTE: From dof_utils Blender plugin
    # Calculate Circle of confusion (diameter limit based on d/1500) 
    # https://en.wikipedia.org/wiki/Circle_of_confusion#Circle_of_confusion_diameter_limit_based_on_d.2F1500
    c = math.sqrt(camera_data.sensor_width**2 + camera_data.sensor_height**2) / 1500      


    D = np.sqrt( (sfftool.zPosList[1] - sfftool.zPosList[0])**2 )

    print(D)

    # D = (np.max(sfftool.zPosList) - np.min(sfftool.zPosList)) / len(sfftool.zPosList)
    # D = (sfftool.max_z_pos - sfftool.min_z_pos) / sfftool.num_z_pos

    # H = (-np.sqrt( (2*f*s - 2*(s**s)) - 4*D*(-D*(f**f) + 2*D*f*s - D*(s**s)) ) - 2*f*s + 2*(s**s)) / (2*D)
    H = (-np.sqrt( (D*D + s*s) * (f-s)**2 ) - f*s+(s*s) ) / D
    
    print(H)

    N = ((f*f) / (c*f - c * H))

    print(N)

    # N = np.abs(((-np.sqrt(c**2 * f**4 * (targetDoF**2 + s**2) * (f-s)**2)) + (c * f**2 * s) - (c * f**2 * s**2)) / (c**2 * targetDoF * (f-s)**2))

    return N


def Cartesian2Polar3D(x, y, z):
    """
    Takes X, Y, and Z coordinates as input and converts them to a polar
    coordinate system

    Source: https://stackoverflow.com/questions/10868135/cartesian-to-polar-3d-coordinates

    """

    r = math.sqrt(x*x + y*y + z*z)

    longitude = math.acos(x / math.sqrt(x*x + y*y)) * (-1 if y < 0 else 1)

    latitude = math.acos(z / r)

    return r, longitude, latitude


def Polar2Cartesian3D(r, longitude, latitude):
    """
    Takes, r, longitude, and latitude coordinates in a polar coordinate
    system and converts them to a 3D cartesian coordinate system

    Source: https://stackoverflow.com/questions/10868135/cartesian-to-polar-3d-coordinates
    """

    x = r * math.sin(latitude) * math.cos(longitude)
    y = r * math.sin(latitude) * math.sin(longitude)
    z = r * math.cos(latitude)

    return x, y, z


### Panel in Object Mode

class MainPanel(Panel):
    """
    Panel to contain all control sub-panels
    """
    bl_label = "SFF-RTI Control"
    bl_idname = "VIEW3D_PT_sffrti_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SFF-RTI"
    # bl_options = {"HEADER_LAYOUT_EXPAND"}

    def draw(self,context):
        layout = self.layout
        scene = context.scene


class RTIPanel(Panel):
    """
    Create tool panel for handling RTI data collection
    """

    bl_idname = "VIEW3D_PT_rti_subpanel"
    bl_parent_id = "VIEW3D_PT_sffrti_main"
    bl_label = "RTI Control"  
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SFF-RTI"
    bl_options = {"DEFAULT_CLOSED"}

    # Hide panel when not in proper context
    # @classmethod
    # def poll(self, context):
    #     return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.rti_tool

        layout.label(text="Light settings")
        layout.prop(mytool, "lp_file_path")
        layout.prop(mytool, "dome_radius")

        layout.label(text="RTI system creation")
        row = layout.row(align = True)
        row.operator("rti.create_rti")
        row.operator("rti.delete_rti")

        if len(scene.sff_tool.camera_list) == 0:
            layout.operator("rti.create_single_camera")

        # layout.prop(scene.file_tool, "output_path")
        # layout.prop(scene.file_tool, "output_file_name")

        # layout.operator("sffrti.set_animation")
        # layout.operator("files.set_render")
        # layout.operator("files.create_csv")


        layout.separator()


class SFFPanel(Panel):
    """
    Create tool panel for handling SFF data collection
    """

    bl_idname = "VIEW3D_PT_sff_subpanel"
    bl_parent_id = "VIEW3D_PT_sffrti_main"
    bl_label = "SFF Control"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SFF"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sfftool = scene.sff_tool

        # row1 = layout.row(align = True)
        # row.prop(sfftool, "camera_ortho")

        layout.label(text="SFF acquisition settings")
        layout.prop(sfftool, "focus_limits_type")
        layout.prop(sfftool, "main_object")
        layout.prop(sfftool, "num_z_pos")

        layout.separator()

        layout.label(text="Camera parameters")
        layout.prop(sfftool, "camera_type")
        layout.prop(sfftool, "aperture_size")

        if sfftool.camera_type == "Static":
            layout.prop(sfftool, "camera_height")
            layout.prop(sfftool, "static_focus")


        if sfftool.focus_limits_type == "Manual":

            layout.separator()

            layout.label(text="Manual Z position settings")
            layout.prop(sfftool, "min_z_pos")
            layout.prop(sfftool, "max_z_pos")

        if sfftool.focus_limits_type == "Tasked":

            layout.separator()
            layout.prop(sfftool, "tasked_file_path")

        layout.separator()

        layout.label(text="SFF system creation")

        row2 = layout.row(align = True)
        row2.operator("sff.create_sff")
        row2.operator("sff.delete_sff")

        if len(scene.rti_tool.light_list) == 0:
            layout.operator("sff.create_single_light")

        # layout.operator("sffrti.set_animation")

        # layout.prop(scene.file_tool, "output_path")
        # # layout.prop(scene.file_tool, "output_file_name")

        # # row
        # layout.operator("files.set_render")
        # layout.operator("files.create_csv")

        layout.separator()

class OutputPanel(Panel):
    """
    Create tool panel for handling output and render options
    """

    bl_idname = "VIEW3D_PT_output_subpanel"
    bl_parent_id = "VIEW3D_PT_sffrti_main"
    bl_label = "Output Control"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SFF-RTI Output"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        filetool = scene.file_tool

        layout.operator("sffrti.set_animation")

        layout.prop(scene.file_tool, "output_path")

        layout.operator("files.set_render")
        layout.operator("files.create_csv")

        layout.separator()
    

### Registration

classes = (light, camera, lightSettings, cameraSettings, fileSettings, CreateLights, CreateSingleCamera, DeleteLights, CreateCameras, CreateSingleLight, DeleteCameras, SetAnimation, SetRender, CreateCSV, MainPanel, RTIPanel, SFFPanel, OutputPanel)

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