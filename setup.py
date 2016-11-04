#!/usr/bin/env python

import os
from distutils.core import setup
from distutils.dir_util import copy_tree
import py2exe

import lxml

##############

class Target(object):
    """ A simple class that holds information on our executable file. """
    def __init__(self, **kw):
        """ Default class constructor. Update as you need. """
        self.__dict__.update(kw)

#############

distDir = "setup"

lxmlPath = os.path.join( distDir, "lxml")
copy_tree(lxml.__path__[ 0], lxmlPath )


includes = ['lxml']
excludes = []
 
packages = ['app', 'app.connectors', 'app.engines', 'app.ui']

dll_excludes = []

data_files = [("./",["config.txt","phantomjs.exe"],), ("storage",["storage/app.db"],), ("images", \
                    ["images/monkey_on_16x16.png"],
             )]
icon_resources   = []
bitmap_resources = []
other_resources  = []


App_Target = Target(
    # what to build
    script = "gui.pyw",
    uac_info = "requireAdministrator", 
    icon_resources = icon_resources,
    bitmap_resources = bitmap_resources,
    other_resources = other_resources,
    dest_base = "app",
    version = "0.1.0",
    company_name = "My Company",
    copyright = "My Company",
    name = "GUI",
    )

""" 
setup(
    data_files = data_files,
    windows=[{"script":"gui.pyw"}],
    options={"py2exe": {"includes":["sip"]}}
)
"""

setup(
    data_files = data_files,
    options = {"py2exe": {"compressed":  0,
                          "optimize": 1,
                          "includes": includes,
                          "excludes": excludes,
                          "packages": packages,
                          "dll_excludes": dll_excludes,
                          "bundle_files": 3,
                          "dist_dir": distDir,
                          "xref": False,
                          "skip_archive": True,
                          "ascii": False,
                          "custom_boot_script": '',
                         }
              },

    zipfile = r'library.zip',
    console = [],
    windows = [App_Target],
    service = [],
    com_server = [],
    ctypes_com_server = []
    )
