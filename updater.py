"""
Small Windows updater helper.
Arguments: target_exe, release_zip_url, app_name

Handles both release layouts:
  * single-file build   -> the package holds one EXE, only that file is replaced
  * folder (onedir) build -> the package holds EXE + _internal, the whole tree is replaced
A package whose layout does not match the installed one is rejected instead of
leaving a half-broken install behind.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

LOG = os.path.join(tempfile.gettempdir(), "micmute-update.log")


def log(message):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(message) + "\n")
    except Exception:
        pass


def alert(title, message):
    log(title + ": " + message)
    if os.environ.get("MICMUTE_QUIET") == "1":
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass


def is_folder_build(folder):
    return os.path.isdir(os.path.join(folder, "_internal"))


def copy_tree(src_root, dst_root, skip_paths):
    """Copy every file from src_root over dst_root, tolerating locked files."""
    for root, _dirs, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        target_dir = dst_root if rel == "." else os.path.join(dst_root, rel)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception:
            continue
        for name in files:
            src = os.path.join(root, name)
            dst = os.path.join(target_dir, name)
            if os.path.abspath(dst).lower() in skip_paths:
                continue
            tmp = dst + ".new"
            try:
                shutil.copy2(src, tmp)
                os.replace(tmp, dst)
            except PermissionError:
                # running executables cannot be overwritten: move them aside first
                old = dst + ".old"
                try:
                    if os.path.exists(old):
                        os.remove(old)
                    os.replace(dst, old)
                    os.replace(tmp, dst)
                    log("replaced locked file " + dst)
                except Exception as exc:
                    log("could not replace " + dst + " -> " + str(exc))
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
            except Exception as exc:
                log("copy failed " + dst + " -> " + str(exc))


def main():
    if len(sys.argv) < 4:
        return 2
    target, url, app_name = sys.argv[1:4]
    target = os.path.abspath(target)
    folder = os.path.dirname(target)
    folder_build = is_folder_build(folder)
    log("---- update start: target=%s folder_build=%s url=%s" % (target, folder_build, url))
    time.sleep(1.5)  # let the main application exit

    tmp = tempfile.mkdtemp(prefix="micmute-update-")
    try:
        archive = os.path.join(tmp, "release.zip")
        request = urllib.request.Request(url, headers={"User-Agent": app_name})
        with urllib.request.urlopen(request, timeout=180) as response, open(archive, "wb") as fh:
            shutil.copyfileobj(response, fh)
        unpacked = os.path.join(tmp, "unpacked")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(unpacked)

        wanted = os.path.basename(target).lower()
        new_exe = None
        for root, _dirs, files in os.walk(unpacked):
            for name in files:
                if name.lower() == wanted:
                    new_exe = os.path.join(root, name)
                    break
            if new_exe:
                break
        if not new_exe:
            raise RuntimeError("The downloaded package does not contain the application EXE.")

        package_root = os.path.dirname(new_exe)
        package_folder_build = is_folder_build(package_root)
        if package_folder_build != folder_build:
            raise RuntimeError(
                "This update package does not match the installed layout.\n\n"
                "Installed: " + ("folder build" if folder_build else "single file") + "\n"
                "Package:   " + ("folder build" if package_folder_build else "single file") + "\n\n"
                "Nothing was changed. Download the right ZIP from the releases page.")

        if package_folder_build:
            skip = {os.path.abspath(sys.executable).lower()}
            copy_tree(package_root, folder, skip)
        else:
            replacement = target + ".new"
            shutil.copy2(new_exe, replacement)
            os.replace(replacement, target)

        log("update applied, launching " + target)
        if os.environ.get("MICMUTE_NO_LAUNCH") != "1":
            subprocess.Popen([target], cwd=folder)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        alert("Mic Mute updater", str(exc))
        raise
