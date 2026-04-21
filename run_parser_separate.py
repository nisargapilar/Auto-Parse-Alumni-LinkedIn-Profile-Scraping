
import os
import subprocess
import sys
print(f"Parser running in separate process PID: {os.getpid()}")
print("Starting parse_linkedin_02.py...")
try:
    result = subprocess.run([sys.executable, "parse_linkedin_02.py", "saved_profiles"], 
                          capture_output=True, text=True, timeout=300)
    print("Parser stdout:")
    print(result.stdout)
    if result.stderr:
        print("Parser stderr:")
        print(result.stderr)
    print(f"Parser return code: {result.returncode}")
except Exception as e:
    print(f"Parser error: {e}")
