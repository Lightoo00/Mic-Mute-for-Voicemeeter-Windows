"""
Small Windows updater helper.
Arguments: target_exe, release_zip_url, app_name
"""
import os, sys, time, urllib.request, tempfile, zipfile, subprocess, shutil

def main():
    if len(sys.argv) < 4:
        return 2
    target, url, app_name = sys.argv[1:4]
    target = os.path.abspath(target)
    folder = os.path.dirname(target)
    time.sleep(1.5)  # allow the main application to exit
    tmp = tempfile.mkdtemp(prefix="micmute-update-")
    try:
        archive = os.path.join(tmp, "release.zip")
        req = urllib.request.Request(url, headers={"User-Agent": app_name})
        with urllib.request.urlopen(req, timeout=90) as r, open(archive, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(archive) as z:
            z.extractall(os.path.join(tmp, "unpacked"))
        unpacked = os.path.join(tmp, "unpacked")
        new_exe = None
        for root, dirs, files in os.walk(unpacked):
            for name in files:
                if name.lower() == os.path.basename(target).lower():
                    new_exe = os.path.join(root, name)
                    break
            if new_exe:
                break
        if not new_exe:
            raise RuntimeError("The downloaded package does not contain the application EXE.")
        replacement = target + ".new"
        shutil.copy2(new_exe, replacement)
        os.replace(replacement, target)
        subprocess.Popen([target], cwd=folder)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Mic Mute updater", str(e))
        except Exception:
            pass
        raise
