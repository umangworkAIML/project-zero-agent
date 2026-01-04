import os
import sys
os.system(f"{sys.executable} -m ensurepip --user")
os.system(f"{sys.executable} -m pip install --upgrade pip --user")
os.system(f"{sys.executable} -m pip install pyfiglet --user")