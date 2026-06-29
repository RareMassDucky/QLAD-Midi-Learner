@echo off
echo Building QLAD-Midi-Learner...

:: Run the PyInstaller command
py -3.12 -m PyInstaller --noconsole --onefile --icon="src/app_icon.ico" --add-data "src/app_icon.ico;." -n "QLAD_Midi_Learner" --hidden-import="mido.backends.rtmidi" --collect-all mido src/midi_learner.py

:: Check if the build was successful, then delete the extra folders
if exist "build" rmdir /s /q "build"
if exist "QLAD_Midi_Learner.spec" del "QLAD_Midi_Learner.spec"

echo Build complete! 'dist' folder updated and cleanup finished.
pause