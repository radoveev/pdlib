# -*- coding: utf-8 -*-
"""Paperdoll library package.

Displays and manipulates paperdolls. This package should be importable
by other PyQt applications.

Copyright (C) 2017 Radomir Matveev GPL 3.0+

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""

__version__ = "0.2.0"

# --------------------------------------------------------------------------- #
# Import libraries
# --------------------------------------------------------------------------- #
import logging
import os
import sys
from pathlib import Path

# add the current working directory to the python path
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

import simplesignals as sisi


# --------------------------------------------------------------------------- #
# Declare package globals
# --------------------------------------------------------------------------- #
from paperdoll import model
from paperdoll import view
log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Define functions
# --------------------------------------------------------------------------- #
def main():
    # set up logging
    logging.basicConfig(level=logging.WARNING)
    log.info("")
    log.info("")
    log.info("Paperdoll editor")
    log.info("")
    log.info("cwd %s", os.getcwd())
    # initialize signalling
    sisi.add_signals("add item",
                     "change character",
                     "doll drawn", "draw doll", "export doll",
                     "item added", "item removed", "remove item",
                     "set state", "set style", "state changed",
                     "update dial state")
    sisi.add_channels("editor")
    # create editor model
    model.editor = model.MPaperdollEditor()
    # parse paperdoll ressource files
    dolldir = Path("../paperdoll/dollfiles").resolve()
    assert dolldir.exists()
    model.editor.parse_ressources(dolldir)
    # create Qt GUI
    view.version = __version__
    view.app = view.Application(sys.argv)
    view.gui = view.VEditorWindow(model.editor)
    # display the gui
    log.info("Show main window")
    view.gui.resizeToScreen(width=0.8, height=0.8)
    view.gui.centerOnScreen()
    view.gui.show()
    # define initial state and draw the doll
    char = model.MCharacter("drawn character")
    sisi.send(signal="change character", char=char)
    char.inventory.add_item(model.editor.wardrobe["uniform_jacket"])
    char.inventory.add_item(model.editor.wardrobe["uniform_shirt"])
    char.inventory.add_item(model.editor.wardrobe["uniform_skirt"])
    char.inventory.add_item(model.editor.wardrobe["uniform_socks"])
    char.inventory.add_item(model.editor.wardrobe["uniform_shoes"])
    char.inventory.add_item(model.editor.wardrobe["basic_bra"])
    char.inventory.add_item(model.editor.wardrobe["basic_panties"])
#    for item in model.editor.wardrobe:
#        # TODO: do not add all items
#        char.inventory.add_item(item)
    for dial in model.editor.dials.values():
        dial.change_value(dial.value + 1)
        dial.change_value(dial.value - 1)
    sisi.send(signal="draw doll")
#    print_state()
    # show GUI with Qt
    sys.exit(view.app.exec_())

def print_state():
    print("editor state:")
    for animname, animstate in sorted(model.editor.state.items()):
        print("  ", animname, animstate)
    print("\nview state:")
    for slidername, slider in sorted(view.gui.sliders.sliders.items()):
        print("  ", slidername, slider.value())
