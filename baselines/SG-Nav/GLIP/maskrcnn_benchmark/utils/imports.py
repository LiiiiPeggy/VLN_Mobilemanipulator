# ################################
# VLN adapt: torch._six removed in PyTorch 2.x — always use importlib
# ################################
import importlib
import importlib.util
import sys


def import_file(module_name, file_path, make_importable=False):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if make_importable:
        sys.modules[module_name] = module
    return module
# ################################
