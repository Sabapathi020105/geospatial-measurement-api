import os
import sys
import urllib.request
import zipfile

url = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/MinGit-2.44.0-64-bit.zip"
dest_zip = "mingit.zip"
dest_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mingit"))

print(f"Downloading MinGit to {dest_zip}...")
try:
    urllib.request.urlretrieve(url, dest_zip)
    print(f"Extracting to {dest_dir}...")
    with zipfile.ZipFile(dest_zip, "r") as zf:
        zf.extractall(dest_dir)
    if os.path.exists(dest_zip):
        os.remove(dest_zip)
    git_cmd = os.path.join(dest_dir, "cmd", "git.exe")
    print(f"MinGit ready: {git_cmd}")
    os.system(f'"{git_cmd}" --version')
except Exception as e:
    print(f"Error downloading MinGit: {e}")
