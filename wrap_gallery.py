import os
import subprocess

def create_executable(script_name):
    # Install PyInstaller if not already installed
    subprocess.call(['pip', 'install', 'pyinstaller'])

    # Create the executable
    subprocess.call(['pyinstaller', '--onefile', script_name])

    # Locate the executable
    dist_path = os.path.join(os.getcwd(), 'dist', os.path.splitext(script_name)[0])
    print(f"Executable created at: {dist_path}")

if __name__ == "__main__":
    script_name = 'gallery.py'  # Replace with your script name
    create_executable(script_name)
