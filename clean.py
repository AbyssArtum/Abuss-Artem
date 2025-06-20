import os
import shutil

for root, dirs, files in os.walk("."):
    if "__pycache__" in dirs:
        shutil.rmtree(os.path.join(root, "__pycache__"))
print("✅ __pycache__ удалён во всех подпапках!")