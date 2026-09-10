import importlib
import os
import pkgutil

import tools


def discover_tools():
    discovered = []
    package_dir = os.path.dirname(tools.__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        module = importlib.import_module(f"tools.{module_name}")

        if hasattr(module, "TOOL_NAME") and hasattr(module, "run"):
            discovered.append({
                "name": module.TOOL_NAME,
                "description": module.TOOL_DESCRIPTION,
                "input_schema": module.INPUT_SCHEMA,
                "module": module,
            })

    return discovered