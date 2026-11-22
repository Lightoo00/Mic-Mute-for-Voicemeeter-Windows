# Mic Mute for Voicemeeter & Windows

Version: 6.1.1  
Repository: https://github.com/Lightoo00/Mic-Mute-for-Voicemeeter-Windows

This project is based on the supplied complete MicHUD v6.0 source. The original HUD,
10 shapes, 20 wave styles, color/size settings, Voicemeeter and Windows Audio support,
and hotkey behavior are retained.

## Build a Windows release
1. Install Python 3.11 on Windows.
2. Run `build-windows.bat`.
3. The ZIP package will be created in this folder.

## Publish updates
1. Create a GitHub repository named `Mic-Mute-for-Voicemeeter-Windows` under `Lightoo00`.
2. Upload/push all project files.
3. Push a version tag, for example: `git tag v6.1.0` then `git push origin v6.1.0`.
4. GitHub Actions builds both EXEs and attaches the ZIP to a GitHub Release.

The app checks the latest GitHub Release. Automatic replacement is available in the
packaged EXE when the matching `MicMuteUpdater.exe` is beside the main EXE.

## Settings compatibility
The existing `%APPDATA%\MicHUD.json` settings file is intentionally preserved so
existing user preferences remain available.


## Version 6.1.1
- Refreshed microphone HUD artwork.
- Added a custom microphone application icon to the Windows EXE.
- Preserved the existing HUD layouts, waveform styles, settings, and hotkeys.
