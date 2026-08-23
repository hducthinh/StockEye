@echo off
echo Building auto_setup.py...
pyinstaller --onefile auto_setup.py

echo Building main.py...
pyinstaller --onefile main.py

echo Build complete! The executable files are in the 'dist' folder.
echo You will need to copy the 'engine' folder, 'templates' folder, and 'config.json' to the 'dist' folder for the app to work correctly.
