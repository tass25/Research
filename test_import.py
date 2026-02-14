import sys
import os

print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    print("Attempting to import data package...")
    import data
    print(f"data package: {data}")
    print(f"data package file: {data.__file__}")

    print("Attempting to import data.simulation_trace...")
    import data.simulation_trace
    print(f"data.simulation_trace: {data.simulation_trace}")
    
    from data.simulation_trace import SimulationTrace
    print(f"SimulationTrace: {SimulationTrace}")
    
    print("Import successful!")

except Exception as e:
    print(f"Caught exception: {e}")
    import traceback
    traceback.print_exc()
