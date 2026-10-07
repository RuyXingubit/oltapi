import sys
import os
sys.path.append(os.getcwd())
from app.drivers.registry import DriverRegistry
# Need to import the drivers to trigger the decorators!
import app.drivers.factory
print("Fiberhome:", DriverRegistry.list_supported_models("fiberhome"))
print("VSOL:", DriverRegistry.list_supported_models("vsol"))
