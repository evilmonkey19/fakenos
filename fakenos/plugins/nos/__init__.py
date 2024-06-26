"""
This module is the point of entry for all NOS plugins.
It imports all the NOS plugins and loads them into a dictionary.

The NOS plugins are loaded first, using the .py modules and
then the .yaml files in the platforms directory for those which are left.

With .py modules we can have functionality, while using YAML is only
intended for quick development of new NOS plugins.
"""

import glob
import os

from fakenos.core.nos import Nos

from . import cisco_ios
from . import arista_eos

nos_plugins = {}
nos_plugins_modules = {"cisco_ios": cisco_ios, "arista_eos": arista_eos}

current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)
platforms_directory = os.path.join(current_directory, "platforms")
yaml_files = glob.glob(os.path.join(platforms_directory, "*.yaml"))

# load NOS from YAML files
for file in yaml_files:
    nos_instance = Nos()
    nos_instance.from_file(file)
    nos_plugins[nos_instance.name] = nos_instance

# load NOS from python modules updating the NOS
for plugin_name, plugin_module in nos_plugins_modules.items():
    if plugin_name in nos_plugins:
        nos_instance = nos_plugins[plugin_name]
    else:
        nos_instance = Nos()
    nos_instance.from_module(plugin_module)
    nos_plugins[nos_instance.name] = nos_instance
    