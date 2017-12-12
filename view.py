# -*- coding: utf-8 -*-
"""Paperdoll GUI module.

Copyright (C) 2017 Radomir Matveev GPL 3.0+
"""


# --------------------------------------------------------------------------- #
# Import libraries
# --------------------------------------------------------------------------- #
import logging

import xml.etree.ElementTree as ET
from PyQt5 import QtWidgets, QtGui, QtCore, QtSvg, QtWebEngineWidgets
from PyQt5.QtCore import Qt

import svglib
import simplesignals as sisi


# --------------------------------------------------------------------------- #
# Define classes
# --------------------------------------------------------------------------- #
class DrawSchedule(QtCore.QObject):
    """Initiates a redraw when no state change has happened for some time.
    """
    def __init__(self, delay=10, parent=None):
        QtCore.QObject.__init__(self, parent=parent)
        # the time in milliseconds we wait for state changes
        # before we start a redraw
        self.delay = delay
        # the number of changes that occurred
        self.changecount = 0
        # set draw mode ("direct", "delayed" or "off")
        self._mode = "delayed"
        # connect simple signals
        sisi.connect(self.on__state_changed, signal="state changed",
                     channel="editor")

    @property
    def mode(self):
        """Return the drawing mode."""
        return self._mode

    @mode.setter
    def mode(self, value):
        sisi.disconnect(self.on__state_changed, signal="state changed",
                        channel="editor")
        if value == "delayed":
            self.on__state_changed = self._delayed_redraw
        elif value == "direct":
            self.on__state_changed = self._direct_redraw
        elif value == "off":
            self.on__state_changed = self._no_redraw
        else:
            raise ValueError("Drawing mode must be either 'direct', " +
                             "'delayed' or 'off'")
        self.changecount = 0
        log.info("Set paperdoll drawing mode to '%s'", value)
        self._mode = value
        sisi.connect(self.on__state_changed, signal="state changed",
                     channel="editor")

    @QtCore.pyqtSlot()
    def attempt_redraw(self):
        """Start a redraw if changeid is the id of the last state change."""
        # the delay for the first change is up, so we update the changecount
        self.changecount -= 1
        # has the time delay for all changes passed?
        if self.changecount is 0:
            self._direct_redraw()

    def _delayed_redraw(self):
#        print("delayed redraw")
        # remember that a change occurred
        self.changecount += 1
        # each time the state is changed we start waiting again
        QtCore.QTimer.singleShot(self.delay, self.attempt_redraw)

    def _direct_redraw(self):
#        print("direct redraw")
        sisi.send(signal="draw doll")

    def _no_redraw(self):
#        print("no redraw")
        pass

    on__state_changed = _delayed_redraw


class VBase(object):
    """Base class for views, which are classes displaying data in a widget.
    """
    def __init__(self):
        pass


class VWidget(VBase, QtWidgets.QWidget):
    """Base class for views acting like a QWidget.
    """
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        VBase.__init__(self)


class VInventory(VWidget):
    """Displays the items a paperdoll wears.
    """
    def __init__(self):
        VWidget.__init__(self)
        self.charid = None
        self.itemmap = {}
        self.btnmap = {}
        # create layout
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        # connect signals
        sisi.autoconnect_signals(self)
#        sisi.connect(self, "item added", channel=self.charid)

    def setCharacter(self, charid):
        self.charid = charid

    @QtCore.pyqtSlot()
    def on_remove_item(self):
        removebtn = self.sender()
        item = self.itemmap[removebtn]
        sisi.send("remove item", channel=self.charid, item=item)

    def on__item_added(self, sender, channel, item):
        if channel == self.charid:
#            label = QtWidgets.QLabel(item.name)
            removebtn = QtWidgets.QPushButton("Remove")
            removebtn.clicked.connect(self.on_remove_item)
#            hbox = QtWidgets.QHBoxLayout()
#            hbox.addWidget(label)
#            hbox.addWidget(removebtn)
#            self.layout().addRow(hbox)
            self.layout().addRow(item.name, removebtn)
            self.itemmap[removebtn] = item
            self.btnmap[item.itemid] = removebtn

    def on__item_removed(self, channel, item):
        if channel == self.charid:
            removebtn = self.btnmap.pop(item.itemid)
            self.itemmap.pop(removebtn)
            self.layout().removeRow(removebtn)


class VWardrobe(VWidget):
    """Displays the items a paperdoll wears.
    """
    def __init__(self):
        VWidget.__init__(self)
        self.addbtn = QtWidgets.QPushButton("Add", self)
        self.itemlist = QtWidgets.QComboBox(self)
        self.itemmap = {}
        self.model = None
        # create layout
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.itemlist)
        layout.addWidget(self.addbtn)
        self.setLayout(layout)
        # connect signals
        self.addbtn.clicked.connect(self.on_add_item)
        sisi.autoconnect_signals(self, channels={"item added": "wardrobe"})

    def setModel(self, model):
        self.model = model
        for item in model:
            self.on__item_added(item)

    @QtCore.pyqtSlot()
    def on_add_item(self):
#        removebtn = self.sender()
#        item = self.itemmap[removebtn]
#        sisi.send("remove item", channel=self.charid, item=item)
        itemname = self.itemlist.currentText()
        item = self.itemmap[itemname]
        sisi.send("add item", channel="wardrobe", item=item)

    def on__item_added(self, item):
        print("item added", item)
        self.itemlist.addItem(item.name)
        self.itemmap[item.name] = item


class VPaperDoll(VWidget):
    """Displays a paperdoll composed of layered SVG paths.
    """
    def __init__(self, parent=None):
        VWidget.__init__(self, parent=parent)
        self.webview = QScrollingWebView()
#        self.lastpos = None
        # create layout
        self.setMinimumWidth(50)
        self.setMinimumHeight(50)
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.webview)
        self.setLayout(vbox)

    def render(self, doll):
        """Displays a doll given as bytes or svglib SVG document."""
        if isinstance(doll, bytes):
            self.render_str(doll)
        else:
            self.render_svgdoc(doll)

    def render_svgdoc(self, svgdoc):
        """Displays the doll from the SVG document in svglib format."""
        # create an element tree from the svg document
        xmlsvgelem = svgdoc.to_xml()
        # create bytes from xml object
        self.render_str(ET.tostring(xmlsvgelem))

    def render_str(self, xml):
        # update paperdoll webview
        self.webview.setContent(xml, "image/svg+xml")


class VDial(VWidget):
    """Controls one or more animation states.

     #TODO feature proposal: dial
     A dial is a layer of abstraction between animation states and the GUI.
     Each dial has a specified range of integer values, usually from 1 to 100
     and is controlled by the user via a slider. When the dial values changes
     by one the states of the animations effected by that dial are modified.
     The change in dial values does not have to translate 1:1 to the change
     in animation state.
     <dial name="boobs" start="1" end="100">
         <animation name="" min="1" init="30" max="100"/>
     </dial>
     """
    def __init__(self, model):
        VWidget.__init__(self)
        self.model = model
        self.label = QtWidgets.QLabel(self.model.name)
        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.lineedit = QtWidgets.QLineEdit()
        # configure widgets
        self.slider.setMinimum(self.model.minimum)
        self.slider.setMaximum(self.model.maximum)
        intval = QtGui.QIntValidator(self.model.minimum, self.model.maximum)
        self.lineedit.setValidator(intval)
#        self.slider.setTracking(False)
        # create layout
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.label)
        hbox.addWidget(self.slider)
        hbox.addWidget(self.lineedit)
        self.setLayout(hbox)
        # connect Qt signals
        self.slider.valueChanged.connect(self.on_slider_valueChanged)
        self.lineedit.editingFinished.connect(self.on_lineedit_editingFinished)
        # connect simple signals
        sisi.connect(self.on__update_dial_state, signal="update dial state",
                     sender=self.model)
#
#    @property
#    def minimum(self):
#        return self.slider.minimum()
#
#    @property
#    def maximum(self):
#        return self.slider.maximum()

    @QtCore.pyqtSlot(int)
    def on_slider_valueChanged(self, newval):
        newval = self.model.change_value(newval)
        self.on__update_dial_state(self, newval)  # update the dial GUI

    @QtCore.pyqtSlot()
    def on_lineedit_editingFinished(self):
        newval = int(self.lineedit.text())
        newval = self.model.change_value(newval)
        self.on__update_dial_state(self, newval)  # update the dial GUI

    def on__update_dial_state(self, sender, data):
        self.slider.valueChanged.disconnect(self.on_slider_valueChanged)
        self.slider.setValue(data)
        self.slider.valueChanged.connect(self.on_slider_valueChanged)
        self.lineedit.setText(str(data))


class VSliders(VWidget):
    """The sliders controlling animation settings."""
    def __init__(self):
        VWidget.__init__(self)
        self.sliders = {}
        self.lastval = {}
        # create layout
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        # connect simple signals
        sisi.connect(self.on__set_state, signal="set state", channel="editor")

    def add_slider(self, aniname, value=50):
        slider = QtWidgets.QSlider(Qt.Horizontal)
        slidername = aniname + "_slider"
        # configure widgets
        slider.setObjectName(slidername)
#        self.slider.setTracking(False)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(value)
        self.lastval[slidername] = value
        # connect Qt signals
        slider.valueChanged.connect(self.on_slider_valueChanged)
        # add to layout
        self.sliders[slidername] = slider
        self.layout().addRow(aniname, self.sliders[slidername])
        return slider

    @QtCore.pyqtSlot(int)
    def on_slider_valueChanged(self, sliderval):
        slidername = self.sender().objectName()
        slider = self.sliders[slidername]
        slider.setValue(self.lastval[slidername])

    def on__set_state(self, sender, data):
        if sender is not self:
            aniname = data["field"]
            value = data["value"]
            slidername = aniname + "_slider"
            slider = self.sliders[slidername]
            self.lastval[slidername] = value
            slider.setValue(value)


# define window classes
class VBaseWindow(VBase, QtWidgets.QMainWindow):
    """Base class for top-level windows, views based on QMainWindow.
    """
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        VBase.__init__(self)
        # create widgets
        self.toolbar = QtWidgets.QToolBar()
        # create actions
        self.quit = self.toolbar.addAction("quit")
        # connect Qt signals
        self.quit.triggered.connect(self.on_quit_triggered)
        # create layout
        self.toolbar.addSeparator()
#        self.toolbar.setOrientation(QtNS.Vertical)
        self.addToolBar(Qt.RightToolBarArea, self.toolbar)

    def resizeToScreen(self, width=0.8, height=0.8):
        """Resizes the window to a fraction of the screen size."""
        # get the size of the primary screen and resize main window
        desktop = QtWidgets.QDesktopWidget()
        freespace = desktop.availableGeometry(desktop.primaryScreen())
        freewidth, freeheigth = (freespace.width(), freespace.height())
        self.resize(int(freewidth * width), int(freeheigth * height))

    def centerOnScreen(self):
        """Centers the window on the screen."""
        desktop = QtWidgets.QDesktopWidget()
        screen = desktop.screenGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def hideToolbar(self):
        action = self.toolbar.toggleViewAction()
        action.setChecked(True)
        action.trigger()

    def showToolbar(self, toolbar):
        action = self.toolbar.toggleViewAction()
        action.setChecked(False)
        action.trigger()

    @QtCore.pyqtSlot()
    def on_quit_triggered(self):
        log.info("Closing all windows")
        app.closeAllWindows()


class VEditorWindow(VBaseWindow):
    """The main window of the paperdoll editor application.
    """
    def __init__(self, model):
        VBaseWindow.__init__(self)
        self.model = model
        self.svgdoc = None  # the SVG document of the currently displayed doll
        self.dials = []
        # create widgets
        self.central = QtWidgets.QWidget()
        self.doll = VPaperDoll()
        self.sliders = VSliders()
        self.objectlist = QtWidgets.QTreeView()
        self.inventory = VInventory()
        self.wardrobe = VWardrobe()
        # create actions
        self.exportsvg = self.toolbar.addAction("export")
        # configure widgets
        self.setWindowTitle("Paperdoll editor {}".format(version))
        self.objectlist.setHeaderHidden(True)
        self.objectlist.setIndentation(20)
        self.wardrobe.setModel(self.model.wardrobe)
        # create animation controls
        diallist = [(d.name, d) for d in self.model.dials.values()]
        for dialname, dialmodel in sorted(diallist):
            self.dials.append(VDial(dialmodel))
        animation_names = [(a.name, a) for a in self.model.animations.values()]
        for aniname, ani in sorted(animation_names):
            self.sliders.add_slider(aniname, ani.default_state)
        # connect Qt signals
        self.exportsvg.triggered.connect(self.on_exportsvg_triggered)
        self.objectlist.clicked.connect(self.on_objectlist_clicked)
        # create layout
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.doll, stretch=5)
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.objectlist)
        vbox.addWidget(self.inventory)
        vbox.addWidget(self.wardrobe)
        hbox.addLayout(vbox)
        dialbox = QtWidgets.QVBoxLayout()
        for dialview in self.dials:
            dialbox.addWidget(dialview)
        dialbox.addStretch()
        hbox.addLayout(dialbox)
        hbox.addWidget(self.sliders)
        self.central.setLayout(hbox)
        self.setCentralWidget(self.central)
        # connect simple signals
        sisi.autoconnect_signals(self)

    @QtCore.pyqtSlot()
    def on_exportsvg_triggered(self):
        # ask user where we should save the svg file
        path, filetypefilter = QtWidgets.QFileDialog.getSaveFileName(self,
            "Export paperdoll SVG file", "./paperdoll.svg",
            "SVG Files (*.svg)")
        if path:
            # ask model to save the doll to disk
            sisi.send(signal="export doll", data={"path": path})

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_objectlist_clicked(self, idx):
        model = self.objectlist.model()
        # fetch all SVG element ids whose visibility should be changed
        elemids = model.elemids(idx)
        visibility = None
        for elemid in elemids:
            elem = self.svgdoc.idmap[elemid]
            if elem.style is None:
                elem.style = svglib.Style("display:inline")
            # set visibility
            if visibility is None:
                # toggle visibility
                if elem.style.visible is True:
                    elem.style.visible = False
                else:
                    elem.style.visible = True
                visibility = elem.style.visible
            else:
                elem.style.visible = visibility
            data = {"elemid": elem.elemid, "style": elem.style}
            sisi.send(signal="set style", data=data)
        sisi.send(signal="draw doll")
        #TODO fix making lines invisible (their style does not have "display")

    def on__doll_drawn(self, data):
        # update current model
        self.svgdoc = data
        # update object list
#        model = self.objectlist.model()
#        if model is None:
#            model = QSvgElementAttributeModel("slot")
#            self.objectlist.setModel(model)
#        else:
#            model.update(self.svgdoc)
        model = QSvgElementAttributeModel("slot")
        model.update(self.svgdoc)
        self.objectlist.setModel(model)
        self.doll.render(self.svgdoc)

    def on__change_character(self, char):
        self.inventory.setCharacter(char.charid)


# define application class
class Application(QtWidgets.QApplication):
    """This class will have only one instance."""
    def __init__(self, *args, **kwargs):
        QtWidgets.QApplication.__init__(self, *args, **kwargs)
        # connect Qt signals
        self.aboutToQuit.connect(self.on_aboutToQuit)

    @QtCore.pyqtSlot()
    def on_aboutToQuit(self):
        log.info("Quitting now")


# define new widgets
class QFixedSvgWidget(QtSvg.QSvgWidget):
    """A QSvgWidget that preserves aspect ratio.
    """
    def __init__(self, *args, **kwargs):
        QtSvg.QSvgWidget.__init__(self, *args, **kwargs)

    def paintEvent(self, paint_event):
        svgsize = self.renderer().defaultSize()
        svgsize.scale(self.size(), Qt.KeepAspectRatio)
        rect = QtCore.QRectF(0, 0, svgsize.width(), svgsize.height())
        self.renderer().render(QtGui.QPainter(self), rect)


class QSvgDocumentModel(QtGui.QStandardItemModel):
    """A model for a Qt tree view based on a SvgDocument.
    """
    def __init__(self, svgdoc, *args, **kwargs):
        QtGui.QStandardItemModel.__init__(self, *args, **kwargs)
#        self.setColumnCount(2)
        self.itemmap = {}  # maps element ids to Qt items
        self.modified_style = {}

#    @property
#    def elemidmap(self):
#        return {v: k for k, v in self.itemmap.items()}

    def update(self, svgdoc):
        root = self.invisibleRootItem()
        self.updateTree(svgdoc, root)

    def updateTree(self, elem, parentItem):
        for child in elem:
            if child.elemid in self.itemmap:
                item = self.itemmap[child.elemid]
                #TODO implement updating the model
            else:
                item = QtGui.QStandardItem(child.elemid)
                assert child.elemid not in self.itemmap
                self.itemmap[child.elemid] = item
                parentItem.appendRow(item)
#                idx = item.index()
#                parent = self.itemFromIndex(idx.parent())
#                print("add item", child.elemid, "at", idx.row(), idx.column(), parent==parentItem)
#                # add visibility item
#                visitem = QtGui.QStandardItem("v")
#                self.setItem(item.index().row(), 1, visitem)
            if isinstance(child, svglib.SvgGroup):
                self.updateTree(child, item)

#    def toggleVisibility(self, item):
#        elemid = item.text()
#        elem = self.svgdoc.idmap[elemid]
##        opacity = elem.style.get("opacity", "1")
##        print("style before", str(elem.style))
##        for key in ("opacity", "fill-opacity", "stroke-opacity"):
##            if key in elem.style:
##                if elem.style[key] == "0":
##                    elstyle[key] = "1"
##                elif elem.style[key] == "1":
##                    elstyle[key] = "0"
#        if elem.style is not None:
#            if elem.style.visible is not None:
#                if elem.style.visible is True:
#                    elem.style.visible = False
#                else:
#                    elem.style.visible = True
#        # if elem has subelements, change their visibility too
#        if isinstance(elem, svglib.SvgGroup):
#            if elem.style is None:
#                groupvis = False
#                elem.style = svglib.Style("display:none")
#            else:
#                groupvis = elem.style.visible
#            for subelem in elem.iterate():
#                if subelem.style is not None:
#                    subelem.style.visible = groupvis
##        print("style after", str(elem.style), type(elem.style))
#        self.modified_style[elem.elemid] = elem.style
#        #TODO modify the model via signals, do not store state here


class QSvgElementAttributeModel(QtGui.QStandardItemModel):
    """A model for a Qt tree view based on a SvgDocument.
    """
    def __init__(self, attrname, *args, **kwargs):
        QtGui.QStandardItemModel.__init__(self, *args, **kwargs)
        self.attrname = attrname
        self.itemmap = {}  # maps attribute values to Qt items
        self.modified_style = {}

    def update(self, svgdoc):
        root = self.invisibleRootItem()
        for elem in svgdoc.iterate():
            val = elem.xmlattrib.get(self.attrname, None)
            if val is not None:
                if val not in self.itemmap:
                    parentItem = QtGui.QStandardItem(val)
                    root.appendRow(parentItem)
                    self.itemmap[val] = parentItem
                parentItem = self.itemmap[val]
                item = QtGui.QStandardItem(elem.elemid)
                parentItem.appendRow(item)

    def elemids(self, idx):
        """Returns all SVG element ids below this model index."""
        item = self.itemFromIndex(idx)
        elemids = []
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                child = item.child(row, col)
                if child is not None:
                    elemids.append(child.text())
        return elemids


class QScrollingWebView(QtWebEngineWidgets.QWebEngineView):
    def __init__(self, *args, **kwargs):
        QtWebEngineWidgets.QWebEngineView.__init__(self, *args, **kwargs)

    def wheelEvent(self, event):
        angledelta = event.angleDelta().y()
        pos = event.pos()
        evx, evy = pos.x(), pos.y()
#        if angledelta > 0:
#            scrollstep = 10
#        else:
#            scrollstep = -10
        page = self.page()
        if event.modifiers() == Qt.ControlModifier:
            zoom = self.zoomFactor()
            if angledelta > 0:
                zoom = min(zoom + 0.125, 5.0)
            else:
                zoom = max(zoom - 0.125, 0.25)
            self.setZoomFactor(zoom)
            page.runJavaScript("window.scrollTo(%s, %s);" % (evx, evy))
#        elif event.modifiers() == Qt.ShiftModifier:
#            page.runJavaScript("window.scrollBy(%s, 0);" % scrollstep)
#        else:
#            page.runJavaScript("window.scrollBy(0, %s);" % scrollstep)
        event.accept()


# --------------------------------------------------------------------------- #
# Declare module globals
# --------------------------------------------------------------------------- #
log = logging.getLogger(__name__)
draw_schedule = DrawSchedule()
version = None  # the application version; set in __init__.py
app = None  # the QApplication instance of this application; set in __init__.py
gui = None  # the main window of this application; set in __init__.py
