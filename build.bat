# Create directory for build output if it doesn't exist
if not exist build (
    mkdir build
)
"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -c extension build --source-dir=./src --output-dir=./build 