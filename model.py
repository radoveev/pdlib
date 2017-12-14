# -*- coding: utf-8 -*-
"""Paperdoll state module.

Copyright (C) 2017 Radomir Matveev GPL 3.0+
"""

# --------------------------------------------------------------------------- #
# Import libraries
# --------------------------------------------------------------------------- #
import logging
import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from decimal import Decimal
from collections import OrderedDict
import pdb
trace = pdb.set_trace

import svglib
from svglib import round_decimal
import simplesignals as sisi


# --------------------------------------------------------------------------- #
# Define classes
# --------------------------------------------------------------------------- #
class MBase(object):
    """Base class for models, which handle state and data structures.
    """
    def __init__(self):
        pass


class MDial(MBase):
    """Controls one or more animation states.

     #TODO feature proposal: dial
     A dial is a layer of abstraction between animation states and the GUI.
     Each dial has a specified range of integer values, usually from 1 to 100
     and is controlled by the user via a slider. When the dial values changes
     by one the states of the animations effected by that dial are modified.
     The change in dial values does not have to translate 1:1 to the change
     in animation state.
     <dial name="boobs" start="1" end="100">
         <animation name="" weight="1"/>
     </dial>
     """
    def __init__(self, name, minimum=1, maximum=100):
        MBase.__init__(self)
        self.name = name
        self.minimum = minimum
        self.maximum = maximum
        self.animations = {}
        self.ignore_state_change = False
        # connect simple signals
        sisi.connect(self.on__state_changed, signal="state changed",
                     channel="editor")

    @property
    def value(self):
        """Returns the value of the dial based on stored animation values."""
        # the whole range of the dial is split between the animations
        # according to their weight
        # each segment is filled according to animation progress
        dialrange = self.maximum - self.minimum
        dialval = 0.0
        weightsum = sum([animdata["weight"] for animdata
                         in self.animations.values()])
        for animname, animdata in self.animations.items():
            animstate = editor.state[animname]
            # calculate the porting of slider value this animation represents
            animportion = dialrange * animdata["weight"] / weightsum
            # calculate animation progress
            progress = ((animstate - animdata["minimum"]) /
                        (animdata["maximum"] - animdata["minimum"]))
            # adjust slider value
            dialval += animportion * progress
        return round(dialval)

#    def animation_state(self, name):
#        """Returns the last known state for this animation."""

    def add_animation(self, name, minimum, initial, maximum):
        # calculate weight
        animrange = maximum - minimum
        dialrange = self.maximum - self.minimum
        weight = animrange / dialrange
        self.animations[name] = {"weight": weight, "value": initial,
                                 "minimum": minimum, "maximum": maximum}

#    def has_animation(self, name):
#        """Returns True if this dial influences the state of this animation."""
#        return name in self.animations

    def update_animation_value(self, name, dialchange=0, animchange=0):
        """If a state changed we need to update the animation value."""
        if dialchange is 0 and animchange is 0:
            raise ValueError("Do not update the animation value if neither " +
                             "the dial state nor the animation state changed.")
        animdata = self.animations[name]
        # calculate the new value of this animation
        if dialchange is not 0:
            animval = (dialchange * animdata["weight"]) + animdata["value"]
        else:
            animval = animchange + animdata["value"]
        # limit the value and store it
        animval = max(animval, animdata["minimum"])
        animval = min(animval, animdata["maximum"])
        animdata["value"] = animval
        return animval

    def change_value(self, newval):
        """This changes the value of the dial to the specified number."""
        oldval = self.value
        # limit the value change
        newval = max(newval, self.minimum)
        newval = min(newval, self.maximum)
        if oldval == newval:
            return oldval
        # update the animations
        statechange = newval - oldval
        for animname, animdata in self.animations.items():
            animval = self.update_animation_value(animname,
                                                  dialchange=statechange)
            # check if the new value is different from the current state
            oldstate = editor.state[animname]
            newstate = round(animval)  # round to int
            if oldstate != newstate:
#                sisi.disconnect(self.on__state_changed, signal="state changed",
#                     channel="editor")
                self.ignore_state_change = True
                sisi.send(signal="set state", channel="editor", sender=self,
                          data={"field": animname, "value": newstate})
                self.ignore_state_change = False
#                sisi.connect(self.on__state_changed, signal="state changed",
#                     channel="editor")
                # update the view
                sisi.send(signal="update dial state", sender=self,
                          data=newstate)
        return newval

    def on__state_changed(self, sender, data):
        if self.ignore_state_change is True:
            return
        animname = data["field"]
        if animname not in self.animations:
            return
        newstate = data["new"]
        oldstate = data["old"]
        # update the internal animation value
        self.update_animation_value(animname, animchange=newstate - oldstate)
        # calculate new value of slider based on change in animation value
        # and send it to the view
        sisi.send(signal="update dial state", sender=self, data=self.value)


class MPaperdollEditor(MBase):
    """Represents the state of the paperdoll editor application.
    """
    def __init__(self):
        MBase.__init__(self)
        self.state = {}
        # TODO: xmllayers and xmlbones should be unused; refactor and remove
        self.xmllayers = []  # the <layer> elements from doll description files
        self.xmlbones = []  # the <bone> elements from doll description files
        self.xmlitems = []  # the <item> elements from doll description files
        self.dollgeometry = {}  # the geometry that was drawn last
        self.modified_styles = {}
        self.dollfiles = {}
        self.connectivity = {}
        self.geometry = {}
        self.animations = {}
        self.dials = {}
        self.wardrobe = MInventory("wardrobe")
        self.drawn_character = None  # the model of the currently drawn char
        # connect simple signals
        sisi.autoconnect_signals(self, channels={"add item": "wardrobe"})

#    @property
#    def frames(self):
#        """Returns the animation frames corresponding to the current state."""
#        frames = []
#        for name in sorted(self.animations):
#            frames.append(self.animation_frame(name))
#        return frames
#
##    def animation_state(self, name):
##        """Returns the current state of the specified animation."""
##        return self.state[name]
#
#    def animation_frame(self, name, state=None):
#        """Return the current frame of this animation.
#
#        If a state is given the frame corresponding to that state is returned.
#        """
#        anim = self.animations[name]
#        if state is None:
#            state = self.state[name]
#        if isinstance(anim, svglib.CombinedAnimation):
#            frame = anim.get_frame(state, self.state.copy())
#        else:
#            frame = anim.get_frame(state)
#        return frame

    def parse_ressources(self, dolldir):
        """Parses the dollfiles at the specified path.
        """
        # parse paperdoll ressource files
        for descfilepath in dolldir.glob("*.xml"):
            descfile = svglib.DescriptionFile(descfilepath)
            # parse paperdoll description file
            descfile.load_connectivity()
            descfile.load_geometry()
            descfile.load_animations()
            # store paperdoll description file
            descfilename = descfile.path.name
            assert descfilename not in self.dollfiles, descfilename
            self.dollfiles[descfilename] = descfile
        for content in ("connectivity", "geometry", "animations"):
            for filename in sorted(self.dollfiles):
                descfile = self.dollfiles[filename]
                self.load_content(descfile, content)
        for filename in sorted(self.dollfiles):
            self.load_doll_file(self.dollfiles[filename])
        # initialize animation state
        for animname in self.animations:
            self.state[animname] = 40
        # parse available items (requires initialized animation states)
        for xmlitem in self.xmlitems:
            self.wardrobe.add_item(MItem.from_xml(xmlitem))

    def load_content(self, file, attribute):
        source = getattr(file, attribute)
        target = getattr(self, attribute)
        for name, data in source.items():
            if name in target:
                log.warning("%s '%s' from %s was ignored because" +
                            "it already exists.", attribute.capitalize(),
                            name, file.path.name)
            else:
                target[name] = data

    def load_doll_file(self, descfile):
        # load layers
        log.info("Load XML layer descriptions")
        xmllayers = descfile.tree.find("layers")
        if xmllayers is None:
            log.warning("No layer description found in %s",
                        descfile.path.name)
        else:
            self.xmllayers.extend(list(xmllayers))
        # load drawing order
        log.info("Load XML drawing order descriptions")
        xmlbones = descfile.tree.find("drawingorder")
        if xmlbones is None:
            log.warning("No drawing order description found in %s",
                        descfile.path.name)
        else:
            self.xmlbones.extend(list(xmlbones))
        # load items
        log.info("Load XML item descriptions")
        xmlitems = descfile.tree.findall("item")
        if xmlitems is None:
            log.warning("No item description found in %s",
                        descfile.path.name)
        else:
            self.xmlitems.extend(xmlitems)
        # load dials
        log.info("Load dials")
        xmldials = descfile.tree.find("dials")
        if xmldials is None:
            log.warning("No dial description found in %s",
                        descfile.path.name)
        else:
            for xmlelem in xmldials:
                name = xmlelem.get("name", None)
                if name in self.dials:
                    dial = self.dials[name]
                else:
                    minimum = int(xmlelem.get("min", None))
                    maximum = int(xmlelem.get("max", None))
                    dial = MDial(name, minimum=minimum, maximum=maximum)
                    self.dials[name] = dial
                # add animations to dial
                for xmlanim in xmlelem:
                    animname = xmlanim.get("name", None)
                    animmin = int(xmlanim.get("min", None))
                    animinit = int(xmlanim.get("init", None))
                    animmax = int(xmlanim.get("max", None))
                    dial.add_animation(animname, animmin, animinit, animmax)
        return descfile

    def get_geometry(self, geomid):
        geomelem = self.geometry.get(geomid, None)
        if geomelem is None:
            geomelem = self.dollgeometry[geomid]
        delta = getattr(geomelem, "delta", None)
        if delta is not None:
            targetid = delta.trgtelem.connectivity
            targetelem = self.get_geometry(targetid)
            geomelem = delta.conform(geomid, targetelem)
        return geomelem

    def print_geometry(self):
        print()
        for label, elem in self.descfile.geometry.items():
            if isinstance(elem, svglib.SvgPath):
                print(elem.prettystring(), "\n")
            else:
                for path in elem:
                    if path.elemid.endswith("_l"):
                        print(path.prettystring(), "\n")
        print()

    def set_dial(self, name, value):
        dial = self.dials[name]
        dial.change_value(value)

    # TODO remove
    def trace_outline(self, geomelem, elemid, start=0, end=-1):
        """Creates a line along geomelem.

        elemid is the element id of the newly created line
        start is the command index where the line should start
        end is the command index where the line should end.
        """
        return svglib.SvgPath.from_path(geomelem, elemid, start, end)

    def transform_skeleton(self, svgdoc):
        """Apply current scale, translations and rotations to skeleton.

        This method assumes that all elements in svgdoc have the scale and
        position they have in the SVG data files.
        """
        # TODO read this from the svg data file
        bonegroupmap = {"shoulder_bone_l": "g_bone_shoulder_l",
                        "upper_arm_bone_l": "g_bone_arm_l",
                        "lower_arm_bone_l": "g_bone_lower_arm_l",
                        "thigh_bone_l": "g_bone_leg_l",
                        "shin_bone_l": "g_bone_lower_leg_l"}
        pelvisbone = svgdoc.idmap["g_bone_pelvis"]
        boneidmap = pelvisbone.idmap.copy()
        # determine "local" bone transformations
        bonelist = ("shoulder_bone_l", "upper_arm_bone_l",
                    "lower_arm_bone_l", "hand_bone_l",
                    "thigh_bone_l", "foot_bone_l")
        skeletondesc = self.dollfiles["skeleton.xml"]
        for bonename in bonelist:
            bone = boneidmap[bonename]
            # find the transformation to create the rotated bone
            animname = "rotate_" + bone.elemid
            anim = skeletondesc.animations[animname]
            animstate = self.state[animname]
            tfcmd = anim.get_command(animstate)
            # create the rotated bone
            rotbone = bone.copy()
            rotbone.transform(tfcmd)
            # determine the operations to transform bone into rotbone
            transforms = bone.transform_operations(rotbone)
            scale, translation, angle, rotcenter = transforms
            # apply transformations to bone or bone group
            bonegroupname = bonegroupmap.get(bonename, None)
            if bonegroupname is None:
                tfbone = bone
            else:
                tfbone = svgdoc.idmap[bonegroupname]
            tfbone.rotate(angle, rotcenter.x, rotcenter.y)
            tfbone.translate(translation.x, translation.y)
            tfbone.scale(scale, scale)

        # determine "global" bone transformations
        bonetransforms = {}
        basepelvisbone = skeletondesc.get_geometry("g_bone_pelvis")
        baseboneidmap = basepelvisbone.idmap.copy()
        bonenames = [bone.elemid for bone in pelvisbone.iterate()
                     if isinstance(bone, svglib.SvgGeometryElement)]
        for bonename in bonenames:
            bone = boneidmap[bonename]
            basebone = baseboneidmap[bonename]
            # determine transformations to get from base position directly
            # to the transformed position of this bone
            transforms = basebone.transform_operations(bone)
            scale, translation, angle, rotcenter = transforms
            # store bone transformations
            bonetflist = [("rotate", angle, rotcenter.x, rotcenter.y),
                          ("translate", translation.x, translation.y),
                          ("scale", scale, scale)]
            bonetransforms[bonename] = bonetflist

        # map all geometry elements to their associated bone
        meatmap = {}
        for elem in [el for el in svgdoc.iterate(ignore={"g_bone_pelvis"})
                     if isinstance(el, svglib.SvgGeometryElement)]:
            if elem.boneid is None:
                log.warning("No bone specified for %s", elem.elemid)
                continue
            try:
                meatmap[elem.boneid].append(elem.elemid)
            except KeyError:
                meatmap[elem.boneid] = [elem.elemid]

        # transform all geometry elements associated with each bone
        for bonename in bonetransforms:
            elemids = meatmap.get(bonename, None)
            if elemids is None:
                continue
            elemtransforms = bonetransforms[bonename]
            for elemid in elemids:
                elem = svgdoc.idmap.get(elemid, None)
                if elem is None:
                    log.warning("No geometry element found to transform" +
                                " based on bone %s", bonename)
                    continue
                for tf in elemtransforms:
                    operation = tf[0]
                    parameters = tf[1:]
                    method = getattr(elem, operation)
                    method(*parameters)
        return svgdoc

    # TODO refactor so we create just one connector (exactly when we need it)
    def connect_parts(self, svgdoc):
        """Create connectors between all doll parts."""
        log.info("Connecting doll parts...")
        connectors = {}
        for xmllayer in self.xmllayers:
            layername = xmllayer.get("name", None)
#            print("Connect parts on layer", layername)
            for xmlconnect in xmllayer.findall("connect"):
                connpath = self.draw_connector(xmlconnect, svgdoc)[0]
                # TODO there can only be one connect element per layer
                # TODO add outlines to connectors
                connectors[layername] = connpath
        return connectors

#    def animate_geometry(self):
#        """Calculate animated geometry elements based on current state.
#
#        Returns a mapping of animation names to lists of animated
#        geometry elements.
#        """
#        # calculate the geometry elements that should be drawn from the
#        # current animation frames
#        animationelems = {}
#        for xmllayer in self.xmllayers:
#            for xmlanim in xmllayer.findall("animation"):
#                anim = self.animations[xmlanim.get("name")]
#                subelems = self.draw_animation(xmlanim)
#                for elem in subelems:
#                    elid = elem.elemid
#                    assert elid not in self.dollgeometry, elid
#                    self.dollgeometry[elid] = elem
#                    try:
#                        animationelems[anim.name].append(elem)
#                    except KeyError:
#                        animationelems[anim.name] = [elem]
#        return animationelems

    # TODO create and transform skeleton before creating other doll parts

    # TODO when modifying the group structure of elements, transforms
    # TODO and styles from removed parent groups should be applied to children
    def draw(self, width=600, height=800, viewbox="-300 0 600 800"):
        """Returns a SVG drawing in a string."""
        self.dollgeometry = {}

#        # calculate the geometry elements that should be drawn from the
#        # current animation frames
#        animationelems = self.animate_geometry()
#
#        # add outlines
#        for xmllayer in self.xmllayers:
#            for xmloutline in xmllayer.findall("trace_outline"):
#                elem = self.draw_outline(xmloutline)[0]
#                assert elem.elemid not in self.dollgeometry
#                self.dollgeometry[elem.elemid] = elem

        # set the default z offset of clothing tiers
        tier2zoff = {"hair": -22, "shadows": -2,
            "body": 0, "skin": 2, "details": 2,
            "underwear": 6,
            "clothes": 12, "overclothes": 30,
            "skeleton": 1000}

        # assemble the z stack
        zstack = ZStack()
        for xmlbone in self.xmlbones:
            # map clothing tier names to lists of geometry elements
            bonemap = self.parse_bone_description(xmlbone)
            # get the z level of this bone (most bones have 0)
            bonez = ZStack.zbones.get(xmlbone.get("name"), 0)
            for tiername, tierelems in bonemap.items():
                # determine the z level of this tier
                tierz = tier2zoff[tiername] + bonez
                # add the geometry elements on this tier to the z stack
                tierelems = [elem for elem in tierelems if elem is not None]
                zstack.add(tierz, tierelems)
                # adjust the style of the elements
                for elem in tierelems:
                    if elem.elemid.startswith("line_"):
                        elem.style = linestyle.copy()
                    elif elem.elemid.startswith("shadow_"):
                        elem.style = shadowstyle.copy()
                    elif elem.elemid in {
                            "eye_lower_l", "eye_upper_l", "eye_lid_l",
                            "eye_lower_r", "eye_upper_r", "eye_lid_r"
                            }:
                        elem.style = bodystyle.copy()
                    elif tiername == "body":
                        elem.style = bodystyle.copy()
                    # adjust style as specified by the user
                    #TODO replace this hack by implementing style propagation
                    if elem.elemid in self.modified_styles:
                        elem.style = self.modified_styles[elem.elemid]

        for item in self.drawn_character.inventory:
            zstack.add_zstack(self.draw_item(item))

        # add geometry elements to svg document in draw order
        svgelem = svglib.SvgDocument()
        svgelem.elemid = "paperdoll1"
        svgelem.width = width
        svgelem.height = height
        svgelem.viewbox = viewbox
        for zlevel, elements in zstack.items():
            # create layer element
            layerelem = svglib.SvgGroup()
            layername = "Layer %i" % zlevel
            layerelem.elemid = "layer%i" % zlevel
            layerelem.xmlattrib = {"inkscape:label": layername,
                                   "inkscape:groupmode": "layer"}
            # adjust style as specified by the user
            #TODO replace this hack by implementing style propagation
            if layerelem.elemid in self.modified_styles:
                layerelem.style = self.modified_styles[layerelem.elemid]
            svgelem.append(layerelem)
            # add elements to layer
            for elem in elements:
                layerelem.append(elem)

#        for xmllayer in self.xmllayers:
#            # create layer element
#            layerelem = svglib.SvgGroup()
#            layername = xmllayer.get("name")
#            layerelem.elemid = "layer_" + layername.lower()
#            layerelem.xmlattrib = {"inkscape:label": layername,
#                                   "inkscape:groupmode": "layer"}
#            svgelem.append(layerelem)
#            # add geometry elements
#            for xmldesc in xmllayer:
#                if xmldesc.tag == "animation":
#                    elemlist = animationelems[xmldesc.get("name")]
#                    for unified_elem in elemlist:
#                        layerelem.append(unified_elem)
#                elif xmldesc.tag == "trace_outline":
#                    unified_elem = self.dollgeometry[xmldesc.get("id")]
#                    layerelem.append(unified_elem)
#                elif xmldesc.tag == "connect":
#                    pass
#                else:
#                    if xmldesc.tag == "conform":
#                        geomid = xmldesc.get("geometry")
#                    else:
#                        geomid = xmldesc.get("id")
#                    group = self.get_geometry(geomid)
#                    # create a copy of the group
#                    groupelem = group.copy()
#                    layerelem.append(groupelem)
#                    # add all geometry elements to the new group
#                    # TODO this should probably loop over groupelem, not group
#                    # TODO why do conforming paths break if we loop over groupelem?
#                    for elem in group.iterate():
##                    for elem in groupelem.iterate():
#                        if isinstance(elem, svglib.SvgGeometryElement):
#                            # adjust conforming paths
#                            delta = getattr(elem, "delta", None)
#                            if delta is not None:
#                                targetid = elem.delta.trgtelem.connectivity
#                                targetelem = self.get_geometry(targetid)
##                                targetelem = svgelem.idmap[targetid]
#                                elem.conform_to(targetelem)
#        # TODO replace current drawing mechanism with the z stack
#        layerelem = svglib.SvgGroup()
#        layername = "zstack"
#        layerelem.elemid = "layer_" + layername.lower()
#        layerelem.xmlattrib = {"inkscape:label": layername,
#                               "inkscape:groupmode": "layer"}
#        svgelem.append(layerelem)
#        for zlvl in zstack:
#            print("draw zlvl", zlvl)
#            for elem in zstack[zlvl]:
#                layerelem.append(elem)

        # TODO check if we add defs from all data files, not just basedoll.svg
        # add defs to svg document
        xmldefselem = ET.Element("defs", {"id": "defs_paperdoll1"})
        descfile = self.dollfiles["basedoll.xml"]
        datafile = descfile.svgfile
        datasvgelem = datafile.tree.getroot()
        datadefselem = datasvgelem.find(datafile.svgns("defs"))
        for filterelem in datadefselem.findall(datafile.svgns("filter")):
            xmldefselem.append(copy.deepcopy(filterelem))
        for radialelem in datadefselem.findall(
                datafile.svgns("radialGradient")):
            xmldefselem.append(copy.deepcopy(radialelem))
        for linearelem in datadefselem.findall(
                datafile.svgns("linearGradient")):
            xmldefselem.append(copy.deepcopy(linearelem))
        svgelem.defs = xmldefselem

        # replace all H and V commands in geometry elements with L
        for subelem in svgelem.iterate():
            if isinstance(subelem, svglib.SvgGeometryElement):
                for cmd in subelem.commands:
                    if cmd.commandletter in "HV":
                        cmd.commandletter = "L"
                    elif cmd.commandletter in "hv":
                        cmd.commandletter = "l"

#        # transform skeleton
#        svgelem = self.transform_skeleton(svgelem)

        # add connectors between doll parts
        connectors = self.connect_parts(svgelem)
        for layerelem in svgelem:
            layername = layerelem.xmlattrib["inkscape:label"]
            if layername in connectors:
                layerelem.append(connectors[layername])
                # TODO move connectors to correct layers

        # round coordinates of all geometry elements
        for elem in [el for el in svgelem.iterate()
                     if isinstance(el, svglib.SvgGeometryElement)]:
            for cmd in elem.commands:
                for point in cmd.parameters:
                    point.x = round_decimal(point.x, 3)
                    point.y = round_decimal(point.y, 3)

        # add labels to nodes
#            # determine how many commands need labels
#            cmdcount = len(elem.commands)
#            if isinstance(elem, SvgPath):
#                closed = elem.is_closed()
#                circular = elem.is_circular()
#                if closed and circular:
#                    # if the second last point actually closes the path and the
#                    # path has a Z command nevertheless, the last two commands
#                    # do not get a label
#                    cmdcount -= 2
#                elif closed or circular:
#                    # the close path command does not get a label
#                    # the last point of a circular path is identical to its first
#                    # point; therefore, the last command does not get a label
#                    cmdcount -= 1
#            if (isinstance(geomobj, svglib.SvgPath) and
#                geomobj.elemid in {"line_boob_l"}):
#                for cmd in geomobj.commands:
#                    if cmd.nodeid is not None:
#                        pos = cmd.endpoint()
#                        xmltext = ET.Element("text")
#                        xmltext.set("x", str(pos.x + 2))
#                        xmltext.set("y", str(pos.y))
#                        xmltext.text = cmd.nodeid
#                        xmllayerelem.append(xmltext)
        # create element tree from svg document


#        # add geometry elements to list in draw order
#        completelayers = []
#        for layer in self.layers:
#            # add geometry elements that are not part of animations
#            for content in layer["content"]:
#                contenttag = content.get("tag", None)
#                if "animation" in content:
#                    elemlist = animationelems[content["animation"]]
#                    for unified_elem in elemlist:
#                        layerdata = {"name": layer["name"],
#                                     "geometry": unified_elem}
#                        completelayers.append(layerdata)
#                elif contenttag == "trace_outline":
#                    unified_elem = self.dollgeometry[content["id"]]
#                    layerdata = {"name": layer["name"],
#                                 "geometry": unified_elem}
#                    completelayers.append(layerdata)
#                else:
#                    group = self.get_geometry(content["geometry"])
#                    for elem in group.iterate():
#                        # reload elem so conforming paths can adjust
#                        delta = getattr(elem, "delta", None)
#                        if delta is not None:
#                            elem = self.get_geometry(elem.elemid)
#                        layerdata = {"name": layer["name"],
#                                     "geometry": elem}
#                        completelayers.append(layerdata)
#            # add animated geometry elements
#            completelayers.extend(layermap.get(layer["name"], []))

#        # prepare svg element
#        datafile = self.descfile.svgfile
#        datasvgelem = datafile.tree.getroot()
#        xmlsvgelem = ET.Element("svg")
#        xmlsvgelem.set("id", "paperdoll1")
#        xmlsvgelem.set("width", str(width))
#        xmlsvgelem.set("height", str(height))
#        xmlsvgelem.set("viewBox", viewbox)
#        # define name spaces
#        for prefix, uri in datafile.svgnamespaces.items():
#            if prefix == "svg":
#                ET.register_namespace("", uri)
#            else:
#                ET.register_namespace(prefix, uri)
#        xmlsvgelem.set("xmlns:svg", "http://www.w3.org/2000/svg")
##        print("attribs")
##        for key, val in datasvgelem.attrib.items():
##            print(key, val)
#        # add defs
#        xmldefselem = ET.Element("defs", {"id": "defs_paperdoll1"})
#        datadefselem = datasvgelem.find(datafile.svgns("defs"))
#        for filterelem in datadefselem.findall(datafile.svgns("filter")):
#            xmldefselem.append(copy.deepcopy(filterelem))
#        for radialelem in datadefselem.findall(
#                datafile.svgns("radialGradient")):
#            xmldefselem.append(copy.deepcopy(radialelem))
#        for linearelem in datadefselem.findall(
#                datafile.svgns("linearGradient")):
#            xmldefselem.append(copy.deepcopy(linearelem))
#        xmlsvgelem.append(xmldefselem)
#        # prepare layers
#        layerelems = {}
#        layerorder = []
#        for layer in completelayers:
#            layername = layer["name"]
#            # fetch layer element
#            xmllayerelem = layerelems.get(layername, None)
#            if xmllayerelem is None:
#                # create layer element
#                xmlattrib = {"inkscape:label": layername,
#                             "inkscape:groupmode": "layer",
#                             "id": "layer_%s" % layername.lower()}
#                xmllayerelem = ET.Element("g", attrib=xmlattrib)
#                layerelems[layername] = xmllayerelem
#                layerorder.append(layername)
#            # adjust style of geometry element
#            geomobj = layer["geometry"]
#            if geomobj.elemid.startswith("line_"):
#                geomobj.style = linestyle
#            elif geomobj.elemid.startswith("shadow_"):
#                geomobj.style = shadowstyle
#            elif geomobj.elemid.startswith("outline_"):
#                geomobj.style = outlinestyle
#            elif geomobj.elemid in {"eye_lower_l", "eye_upper_l", "eye_lid_l",
#                                    "eye_lower_r", "eye_upper_r", "eye_lid_r"}:
#                geomobj.style = bodystyle
#            elif layername in {"face", "arms", "legs", "boobs", "torso"}:
#                geomobj.style = bodystyle
##            if layername in {"boobs", "torso"}:
##                geomobj.style = torsostyle
#            # make invisible elements visible
#            if hasattr(geomobj, "style"):
#                if "display:none;" in geomobj.style:
#                    geomobj.style = geomobj.style.replace("display:none;", "")
#                elif "display:none" in geomobj.style:
#                    geomobj.style = geomobj.style.replace("display:none", "")
#            # add geometry element to layer
#            xmlgeomelem = geomobj.to_xml()
#            xmllayerelem.append(xmlgeomelem)
#        # add layers
#        for layername in layerorder:
#            xmllayerelem = layerelems[layername]
#            xmlsvgelem.append(xmllayerelem)
        return svgelem

    def parse_bone_description(self, xmlbone):
        """Parses the XML description of a bone and returns a bonemap.

        A bonemap is a dict mapping clothing tier names to lists of geometry
        elements.
        """
#        print("bone:", xmlbone.get("name"))
        bonemap = {}
        for xmltier in xmlbone.findall("tier"):
            tiername = xmltier.get("name")
            assert tiername is not None
            assert tiername not in bonemap
            tierelems = []
            for xmldesc in xmltier:
                if xmldesc.tag == "connect":
                    continue  # connectors are handled in self.draw
                elemlist = self.parse_drawing_description(xmldesc)
                tierelems.extend(elemlist)
            bonemap[tiername] = tierelems
        return bonemap

#    def parse_item_description(self, xmlitem):
#        """Parses the XML description of an item and returns a model.
#
#        A bonemap is a dict mapping clothing tier names to lists of geometry
#        elements.
#        """
#        zlevel = xmlitem.get("zlevel", None)
#        item = MItem(xmlitem.get("id"), xmlitem.get("slot"), zlevel=zlevel)
#        for xmldesc in xmlitem:
#            bone = xmldesc.get("bone")
#            ztier = xmldesc.get("ztier", "base")
#            drawelems = self.parse_drawing_description(xmldesc)
#            item.add_drawn_elements(drawelems, bone, ztier)
#        return item

    def parse_drawing_description(self, xmldesc):
        """Parses the XML description how to draw a geometry element."""
#        print("parse drawing description:", xmldesc.tag)
        drawelems = None
        if xmldesc.tag == "animation":
            drawelems = self.draw_animation(xmldesc)
        elif xmldesc.tag == "trace_outline":
            drawelems = self.draw_outline(xmldesc)
        else:
            drawelems = self.draw_geometry(xmldesc)
        # TODO add all elements to self.dollgeometry?
        if xmldesc.tag in {"animation", "trace_outline"}:
            for elem in drawelems:
                elid = elem.elemid
                if elid in self.dollgeometry:
                    dollelem = self.dollgeometry[elid]
                    # this is probably quite expensive and could be optimized
                    # however, we do this only once at startup, so we might
                    # get away with it
                    if dollelem.to_string() != elem.to_string():
                        log.debug(dollelem.to_xml())
                        log.debug(elem.to_xml())
                        msg = "Svg element id not unique: '%s'" % elid
                        raise ValueError(msg)
                else:
                    self.dollgeometry[elid] = elem
        return drawelems

    def draw_geometry(self, xmlgeom):
        """Creates regular and conforming geometry elements for drawing."""
        if xmlgeom.tag == "geometry":
            geomid = xmlgeom.get("id")
        elif xmlgeom.tag == "conform":
            geomid = xmlgeom.get("geometry")
        else:
            raise ValueError("Unknown draw order tag: %s" % xmlgeom.tag)
#        print("draw geometry:", geomid)
        elem = self.get_geometry(geomid)
        if isinstance(elem, svglib.SvgGroup):
            elemlist = list(elem.iterate())
        else:
            elemlist = [elem]
        # add all geometry elements to the new elem
        for subelem in elemlist:
            if isinstance(subelem, svglib.SvgGeometryElement):
                # adjust conforming paths
                delta = getattr(subelem, "delta", None)
                if delta is not None:
                    targetid = subelem.delta.trgtelem.connectivity
                    targetelem = self.get_geometry(targetid)
#                        targetelem = svgelem.idmap[targetid]
                    subelem.conform_to(targetelem)
        # return a copy of the elem
        return [elem.copy()]

    def draw_animation(self, xmlanim):
        """Creates geometry elements for drawing from an animation."""
        anim = self.animations[xmlanim.get("name")]
        animstate = self.state[anim.name]
        # TODO should the two names always be identical? assert?
        if isinstance(anim, svglib.CombinedAnimation):
            frame = anim.get_frame(animstate, self.state.copy())
        else:
            frame = anim.get_frame(animstate)
        # add geometry elements that should be drawn to the doll
        subelems = []
        if isinstance(frame, svglib.SvgGroup):
            for subelem in frame.iterate():
                subelems.append(subelem)
        else:
            subelems.append(frame)
        return subelems

    def draw_outline(self, xmloutline):
        """Draws lines along geometry elements and returns the lines."""
        base_geometry_id = xmloutline.get("base_geometry")
        base_geometry = self.get_geometry(base_geometry_id)
        # elemid is the element id of the newly created line
        elemid = xmloutline.get("id")
        # start is the command index where the line should start
        start = int(xmloutline.get("start"))
        # end is the command index where the line should end
        end = int(xmloutline.get("end"))
        elem = svglib.SvgPath.from_path(base_geometry, elemid, start, end)
        return [elem]

    def draw_connector(self, xmlconnect, svgdoc):
        """Draw a connector between two geometry elements."""
        # iterate over XML descriptions of doll part connectors
        xmlconnectiter = iter(xmlconnect)
        xmlstartnode = next(xmlconnectiter)
        assert xmlstartnode.tag == "node"
        layerconnectors = []
        conntype = None
        for xmlelem in xmlconnectiter:
            if xmlelem.tag != "node":
                conntype = xmlelem.tag
            else:
                assert conntype is not None
                startelemid = xmlstartnode.get("geometry")
                startnodeid = xmlstartnode.get("id")
                endelemid = xmlelem.get("geometry")
                endnodeid = xmlelem.get("id")
                elem = connect_nodes(svgdoc, startelemid, startnodeid,
                                     endelemid, endnodeid)
                layerconnectors.append(elem)
                xmlstartnode = xmlelem
                conntype = None
        # merge all connector paths into one path
        connpath = layerconnectors.pop(0)
        for path in layerconnectors:
            connpath = connpath.join(path)
        # update attributes of connpath
        connpath.elemid = "connect_%s_to_%s" % (startelemid, endelemid)
        endelem = svgdoc.idmap[endelemid]
        connpath.style = endelem.style.copy()
        connpath.style["stroke-width"] = "0"
        return [connpath]

    def draw_item(self, item):
        """Create a zstack of drawable elements from an item model."""
        zstack = ZStack()
        for xmldesc in item.drawdesc:
            bone = xmldesc.get("bone")
            ztier = xmldesc.get("ztier", "base")
            drawelems = self.parse_drawing_description(xmldesc)
            # add itemid and item slot to element attributes
            for elem in drawelems:
                elem.xmlattrib["item"] = item.itemid
                elem.xmlattrib["slot"] = item.slot
            # get the z level of this bone (most bones have 0)
            bonez = ZStack.zbones.get(bone, 0)
            # determine the slot z level
            zleveldef = xmldesc.get("zlevel", None)
            if zleveldef is None:
                itemz = item.zlevel
            else:
                itemz = MItem.parse_zlevel(zleveldef)
            # determine the z offset of this tier
            tierz = ZStack.ztiers[ztier]
            # determine the z level for the drawn elements
            zlevel = bonez + itemz + tierz
            # add the geometry elements on this tier to the z stack
            drawelems = [elem for elem in drawelems if elem is not None]
            zstack.add(zlevel, drawelems)
            # adjust the style of the elements
            for elem in drawelems:
                if elem.elemid.startswith("line_"):
                    elem.style = linestyle.copy()
                elif elem.elemid.startswith("shadow_"):
                    elem.style = shadowstyle.copy()
                elif elem.elemid in {
                        "eye_lower_l", "eye_upper_l", "eye_lid_l",
                        "eye_lower_r", "eye_upper_r", "eye_lid_r"
                        }:
                    elem.style = bodystyle.copy()
                elif ztier == "body":
                    elem.style = bodystyle.copy()
                # adjust style as specified by the user
                # TODO replace this hack by implementing style propagation
                if elem.elemid in editor.modified_styles:
                    elem.style = editor.modified_styles[elem.elemid]
        return zstack

    def save_to_file(self, filepath):
        """Write the current state of the paperdoll to a SVG file."""
        log.info("Write paperdoll to: %s", filepath)
        # draw the paperdoll
        svgdoc = self.draw(width=200, height=800, viewbox="0 0 200 800")
        # rename all elements so we can filter them out if the exported
        # file was used as template for new art
        prefix = "pdcexp_"
        svgdoc.elemid = prefix + svgdoc.elemid
        for elem in svgdoc.iterate():
            elem.elemid = prefix + elem.elemid
        # create an element tree from the svg document
        xmlsvgelem = svgdoc.to_xml()
        # create bytes from xml object
        xml = ET.tostring(xmlsvgelem)
        # save xml to file
        dollpath = Path(filepath)
        with dollpath.open("w") as f:
            f.write(xml.decode("utf-8"))

    def on__set_state(self, data):
        animname = data["field"]
        new = data["value"]
        old = self.state[animname]
        #TODO limit change
        # ignore if operation doesn't change anything
        if old == new:
            return
        # update internal state
        self.state[animname] = new
        # inform the world about state change
        data = {"field": animname, "old": old, "new": new}
        sisi.send(signal="state changed", channel="editor", data=data)

    def on__draw_doll(self):
        sisi.send(signal="doll drawn", data=self.draw())

    def on__export_doll(self, data):
        self.save_to_file(data["path"])

    def on__set_style(self, data):
        self.modified_styles[data["elemid"]] = data["style"]

    def on__change_character(self, char):
        self.drawn_character = char

    def on__item_removed(self, sender, item):
        inventory = getattr(self.drawn_character, "inventory", None)
        if sender is inventory:
            sisi.send(signal="draw doll")

    def on__add_item(self, item):
        if self.drawn_character.inventory.has_free_slot(item.slot):
            self.drawn_character.inventory.add_item(item)
            sisi.send(signal="draw doll")
        else:
            log.warning("Inventory has no free '%s' slot for %s",
                        item.slot, item)


class ZStack(object):
    """The z stack maps z levels to the svg elements drawn at that level.

    keys must be integers
    levels must be lists of svglib.SvgElement instances

    The zlevel of the bone is the most basic zlevel adjustment. It determines
    the z levels of whole body parts relative to each other. The head is drawn
    on top of the body. Are the arms in front of or behind the body.

    The zlevel of the item slots describes the layers of clothing on that
    body part.

    The z tiers are used to make overlapping clothes easier and modify the
    zlevel of parts of an item only slightly.
    """

#        # set the default z offset of clothing tiers
#        tier2zoff = {"hair": -10, "shadows": -2,
#            "body": 0, "skin": 2, "details": 2,
#            "underwear": 6,
#            "clothes": 12, "overclothes": 30,
#            "skeleton": 1000}
    ztiers = {"back_hair": -22,
              "shadow": -2,
              "base": 0,
              "skin": 2, "detail": 2
              }

    zbones = {"skull": 10,
              "boob_bone_l": 10, "boob_bone_r": 10,
              "nipple_bone_l": 120, "nipple_bone_r": 120,
              "upper_arm_bone_l": -10, "upper_arm_bone_r": -10,
              "lower_arm_bone_l": 100, "lower_arm_bone_r": 100,
              "hand_bone_l": 100, "hand_bone_r": 100}

    def __init__(self):
        self.zmap = {}
        self.idmap = {}

    def __getitem__(self, zlevel):
        return self.zmap[zlevel]

    def __iter__(self):
        return iter(sorted(self.zmap))

    def add(self, zlevel, elemlist):
        if not isinstance(zlevel, int):
            raise TypeError("Not an int: %s" % repr(zlevel))
        for elem in elemlist:
            if not isinstance(elem, svglib.SvgElement):
                raise TypeError("Not a geometry element: %s" % repr(elem))
            if elem.elemid in self.idmap:
                raise ValueError("Duplicate element id: %s" % elem.elemid)
            self.idmap[elem.elemid] = elem
        zlevel_elemlist = self.zmap.setdefault(zlevel, [])
        zlevel_elemlist.extend(elemlist)

    def add_zstack(self, other):
        """Merge this zstack with the other zstack."""
        for zlevel, elemlist in other.zmap.items():
            self.add(zlevel, elemlist)

    def items(self):
        return [(zlevel, self.zmap[zlevel]) for zlevel in self]


class MCharacter(MBase):
    """A character.
    """
    def __init__(self, charid):
        MBase.__init__(self)
        self.charid = charid
        self.inventory = MInventory(self.charid)


class MInventory(MBase):
    """The inventory of a character.
    """
    def __init__(self, charid):
        MBase.__init__(self)
        self.charid = charid  # the id of the character who owns the inventory
        self.items = OrderedDict()
        sisi.autoconnect_signals(self, channels={"remove item": self.charid})

    def __iter__(self):
        return iter(self.items.values())

    def __contains__(self, item):
        itemid = getattr(item, "itemid", None)
        if itemid in self.items:
            return True
        return False

    def __getitem__(self, key):
        return self.items[key]

    def __str__(self):
        return "<MInventory of '%s'>" % self.charid

    def has_free_slot(self, slot):
        """Return True if this model has a free item slot."""
        for item in self:
            if item.slot == slot:
                return False
        return True

    def add_item(self, item):
        self.items[item.itemid] = item
        sisi.send("item added", sender=self, channel=self.charid, item=item)

    def remove_item(self, itemid):
        return self.items.pop(itemid)

    def on__remove_item(self, item):
        self.remove_item(item.itemid)
        sisi.send("item removed", sender=self, channel=self.charid, item=item)


class MItem(MBase):
    """A clothing item or body part of a paper doll.
    """

    itemslots = {"body": 0,
                 "bra": 6, "shirt": 12, "jacket": 30,
                 "panties": 6, "pants": 16,
                 "stockings": 6, "shoes": 12}

    @classmethod
    def parse_zlevel(cls, zlvldef):
        """Calculates a zlevel from a zlevel definition string."""
        if "+" in zlvldef:
            slot, mod = [s.strip() for s in zlvldef.split("+")]
            mod = int(mod)
        elif "-" in zlvldef:
            slot, mod = [s.strip() for s in zlvldef.split("-")]
            mod = int(mod) * -1
        else:
            slot = zlvldef
            mod = 0
        try:
            itemz = cls.itemslots[slot]
        except KeyError as exc:
            msg = "No z offset defined for item slot '%s'" % slot
            raise KeyError(msg) from exc
        return itemz + mod

    @classmethod
    def from_xml(cls, xmlitem):
        """Parses the XML description of an item and returns its model."""
        tagselem = xmlitem.find("tags")
        if tagselem is not None:
            xmlitem.remove(tagselem)
            tags = MTagSet.from_xml(tagselem)
        else:
            tags = MTagSet()
        zlevel = xmlitem.get("zlevel", None)
        return cls(xmlitem.get("id"), xmlitem.get("slot"), zlevel=zlevel,
                   drawdesc=list(xmlitem), tags=tags)

    def __init__(self, itemid, slot, zlevel=None, drawdesc=None, tags=None):
        MBase.__init__(self)
        self.itemid = itemid
        self.name = "Item '%s'" % itemid
        if slot not in self.itemslots:
            log.warning("Unknown slot '%s' defined for %s", slot, self)
        self.slot = slot
        # the positioning of the item on the z axis
        if zlevel is None:
            self.zlevel = self.itemslots[slot]
        else:
            self.zlevel = self.parse_zlevel(zlevel)
        # XML elems describing how to draw the item
        self.drawdesc = [] if drawdesc is None else drawdesc
        # key words describing the item
        self.tags = MTagSet() if tags is None else tags
        # modify tags based on item attributes
        self.tags.add("%s slot" % self.slot)

    def __str__(self):
        return "<MItem object '%s' in %s>" % (self.itemid, self.slot)


class MTagSet(MBase):
    """A set of tags describing something.
    """
    @classmethod
    def from_xml(cls, xmlitem):
        """Parses the XML description of a tagset and returns its model."""
        return cls([tag.strip() for tag in xmlitem.text.split(",")])

    def __init__(self, tags=None):
        MBase.__init__(self)
        self.tags = set() if tags is None else set(tags)

    def __str__(self):
        return "<MTagSet %s>" % str(self.tags)

    def __contains__(self, val):
        return val in self.tags

    def add(self, val):
        self.tags.add(val)


# --------------------------------------------------------------------------- #
# Define functions
# --------------------------------------------------------------------------- #
def connect_nodes(svgdoc, startelemid, startnodeid, endelemid, endnodeid):
    """Connects one node to another node on a different element."""
    bp1 = svgdoc.idmap[startelemid]
    bp2 = svgdoc.idmap[endelemid]
    assert bp1.boneid is not None, "%s is not associated with a bone" % bp1
    assert bp2.boneid is not None, "%s is not associated with a bone" % bp2
    bone1 = svglib.Bone(svgdoc.idmap[bp1.boneid])
    bone2 = svglib.Bone(svgdoc.idmap[bp2.boneid])
    startpoint = bp1.nodemap[startnodeid].endpoint()
    endpoint = bp2.nodemap[endnodeid].endpoint()
    line1 = bone1.line.new_intercept(startpoint)
    line2 = bone2.line.new_intercept(endpoint)
    return bp1.connect_by_arc(bp2, startnodeid, endnodeid, line1, line2)


# --------------------------------------------------------------------------- #
# Declare module globals
# --------------------------------------------------------------------------- #
log = logging.getLogger(__name__)
linestyle = svglib.Style("fill:none;stroke:#000000;stroke-width:0.58405101;" +
             "stroke-linecap:butt;stroke-linejoin:miter;" +
             "stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1")
shadowstyle = svglib.Style("display:inline;fill:none;stroke:#000000;stroke-width:7;" +
       "stroke-linecap:butt;stroke-linejoin:miter;stroke-miterlimit:4;" +
       "stroke-dasharray:none;stroke-opacity:1;filter:url(#filter6343)")
torsostyle = svglib.Style("display:inline;fill:#eac6b6;fill-opacity:1;" +
              "fill-rule:evenodd;stroke:#000000;stroke-width:0.37795276;" +
              "stroke-linecap:butt;stroke-linejoin:miter;stroke-opacity:1;" +
              "stroke-miterlimit:4;stroke-dasharray:none;")
bodystyle = svglib.Style("display:inline;fill:#eac6b6;fill-opacity:1;" +
             "fill-rule:evenodd;stroke:none;")
editor = None  # the main model of this application; set in __init__.py
