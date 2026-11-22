<img src="assets/icon.svg" width="64" height="64" alt="">

# Mic-Mute-for-Voicemeeter-Windows

A floating HUD that mutes your microphone in Voicemeeter or Windows Audio with one key,
one click, or one tap on the widget.

- 10 HUD shapes · 20 live visualisers · 8 colour palettes · 3 sizes
- Antialiased rendering (Pillow, 3× supersampled) — no pixelated edges
- Voicemeeter Remote API **or** Windows Audio (pycaw)
- Built-in updater: installed copies update themselves from GitHub Releases

## Run from source

```bat
py -m pip install -r requirements.txt
py main.py
```

## Build the EXE

```bat
build-windows.bat
```

## Publish a release (one button)

Double-click **`publish.bat`**, press Enter to accept the suggested version, and it will:

1. bump `APP_VERSION` in `main.py` (and the ZIP name in `build-windows.bat`)
2. commit and push to GitHub
3. create and push the `v<version>` tag

GitHub Actions then builds both EXEs and publishes `Mic-Mute-Windows-v<version>.zip`
to Releases automatically. Installed users get it on their next launch — the app checks
for a newer release at most once every 6 hours and installs it when accepted
(Settings → *Install updates automatically on launch*).

First run only: if the folder has no remote yet, `publish.bat` asks for the repository URL
and adds it as `origin`. Git for Windows is required.

The script also protects you:

* it syncs with GitHub first, so a folder whose history is unrelated to the repo (for
example a repo created by uploading files on github.com) is rebased instead of rejected
* a rejected push is retried after a rebase once, then rolled back — the version number,
commit and tag are undone, so a failed run publishes nothing and never inflates the version
* a full log is written to `%TEMP%\michud-publish.log`, and after a successful tag push the
script waits until the release ZIP is really live on GitHub

If GitHub asks for a login the first time, sign in in the window that opens. Without a
stored credential the push fails with `could not read Username`; run
`git credential-manager configure` once (or use a Personal Access Token as the password).
