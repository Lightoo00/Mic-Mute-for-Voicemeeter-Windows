"""
Mic Mute for Voicemeeter & Windows v6.1.0
MicHUD v6.0 - واجهة عائمة احترافية متطورة
✅ يدعم Voicemeeter Banana + كل مايكات Windows
✅ 20 موجة جديدة مبتكرة + أيقونة مايك محسّنة
✅ معاينة حية + تأثيرات بصرية متقدمة
"""
import ctypes
import json
import math
import os
import struct
import sys
import time
import threading
import urllib.request
import urllib.error
import subprocess
import tempfile
import zipfile
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

try:
    import winreg
except ImportError:
    print("هذا البرنامج يعمل على Windows فقط.")
    sys.exit(1)

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

# ---------------------------------------------------------------------------
# الإعدادات
# ---------------------------------------------------------------------------
APP_NAME = "Mic Mute for Voicemeeter & Windows"
APP_VERSION = "6.1.1"
GITHUB_REPO = "Lightoo00/Mic-Mute-for-Voicemeeter-Windows"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CONFIG_PATH = os.path.join(os.environ.get("APPDATA", "."), "MicHUD.json")


def resource_path(relative_path):
    """Resolve bundled assets in development and PyInstaller one-file builds."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

DEFAULTS = {
    "hotkey": "t",
    "mode": "voicemeeter",
    "strip": 0,
    "device_id": "",
    "opacity": 0.95,
    "topmost": True,
    "wave_style": 0,
    "hud_shape": 0,
    "hud_size": "medium",
    "colors": {
        "accent": "#64e6c0",
        "glow": "#c0ffed",
        "background": "#101923",
        "text": "#e7edf5",
    },
    "x": 100,
    "y": 100,
}

WAVE_NAMES = [
    "01 · Crystal Waves", "02 · Neon Flow", "03 · Particle Storm",
    "04 · Aurora Borealis", "05 · Digital Rain", "06 · Plasma Field",
    "07 · Quantum Dots", "08 · Liquid Metal", "09 · Electric Storm",
    "10 · Holographic", "11 · Cosmic Dust", "12 · Fire Waves",
    "13 · Ice Crystals", "14 · Sound Spectrum", "15 · Wave Rider",
    "16 · Neon Grid", "17 · Pulse Matrix", "18 · Star Field",
    "19 · Energy Flow", "20 · Final Frontier",
]

HUD_SHAPES = [
    ("01 · Capsule", (248, 56)),
    ("02 · Studio Rack", (316, 70)),
    ("03 · Micro Strip", (190, 42)),
    ("04 · Vertical Totem", (80, 160)),
    ("05 · Audio Orb", (100, 100)),
    ("06 · Split Modules", (286, 64)),
    ("07 · Glass Rail", (328, 48)),
    ("08 · Radar Dial", (124, 124)),
    ("09 · Minimal Line", (264, 38)),
    ("10 · Console Stack", (236, 84)),
]

SIZE_FACTORS = {"small": 0.82, "medium": 1.0, "large": 1.25}
SIZE_LABELS = {"Small · 82%": "small", "Medium · 100%": "medium", "Large · 125%": "large"}

PALETTES = {
    "Aurora Mint": {"accent": "#64e6c0", "glow": "#c0ffed", "background": "#101923", "text": "#e7edf5"},
    "Arctic Blue": {"accent": "#72c7ff", "glow": "#c7eaff", "background": "#101a28", "text": "#e8f3ff"},
    "Violet Pulse": {"accent": "#b69aff", "glow": "#e0d5ff", "background": "#191526", "text": "#f0eaff"},
    "Amber Studio": {"accent": "#ffbd70", "glow": "#ffe0b6", "background": "#211a14", "text": "#fff0df"},
    "Crimson Signal": {"accent": "#ff718b", "glow": "#ffc2ce", "background": "#21151c", "text": "#ffedf1"},
    "Cyber Lime": {"accent": "#c6ee64", "glow": "#edffb7", "background": "#171e14", "text": "#f2f8e8"},
    "Ice Rose": {"accent": "#f18bc8", "glow": "#ffd0ec", "background": "#211722", "text": "#ffeff8"},
    "Pure Mono": {"accent": "#dce6ef", "glow": "#ffffff", "background": "#151a20", "text": "#f4f7fb"},
}


def load_config():
    cfg = dict(DEFAULTS)
    cfg["colors"] = dict(DEFAULTS["colors"])
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            cfg.update(saved)
            if isinstance(saved.get("colors"), dict):
                cfg["colors"].update(saved["colors"])
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Voicemeeter Remote API
# ---------------------------------------------------------------------------
class Voicemeeter:
    def __init__(self):
        self.dll = None
        self.logged_in = False
        self._last_try = 0.0

    def _find_dir(self):
        key_path = r"VB:Voicemeeter {17359A74-1236-5467}"
        for root in (
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ):
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root + "\\" + key_path)
                us = winreg.QueryValueEx(k, "UninstallString")[0]
                return os.path.dirname(us.strip('"'))
            except OSError:
                continue
        return r"C:\Program Files (x86)\VB\Voicemeeter"

    def _load_dll(self):
        is64 = struct.calcsize("P") * 8 == 64
        name = "VoicemeeterRemote64.dll" if is64 else "VoicemeeterRemote.dll"
        self.vm_dir = self._find_dir()
        path = os.path.join(self.vm_dir, name)
        d = ctypes.WinDLL(path)
        d.VBVMR_Login.restype = ctypes.c_long
        d.VBVMR_Logout.restype = ctypes.c_long
        d.VBVMR_RunVoicemeeter.argtypes = [ctypes.c_long]
        d.VBVMR_IsParametersDirty.restype = ctypes.c_long
        d.VBVMR_GetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_float)]
        d.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
        d.VBVMR_GetLevel.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.POINTER(ctypes.c_float)]
        self.dll = d

    def connect(self):
        now = time.time()
        if self.logged_in:
            return True
        if now - self._last_try < 2.0:
            return False
        self._last_try = now
        try:
            if self.dll is None:
                self._load_dll()
            res = self.dll.VBVMR_Login()
            if res == 1:
                self.dll.VBVMR_RunVoicemeeter(2)
                time.sleep(1.5)
                res = self.dll.VBVMR_Login()
            self.logged_in = res >= 0
        except Exception:
            self.logged_in = False
        return self.logged_in

    def close(self):
        if self.dll and self.logged_in:
            try:
                self.dll.VBVMR_Logout()
            except Exception:
                pass
        self.logged_in = False

    def get_mute(self, strip):
        if not self.connect():
            return None
        try:
            self.dll.VBVMR_IsParametersDirty()
            v = ctypes.c_float()
            r = self.dll.VBVMR_GetParameterFloat(f"Strip[{strip}].Mute".encode(), ctypes.byref(v))
            if r != 0:
                self.logged_in = False
                return None
            return v.value > 0.5
        except Exception:
            self.logged_in = False
            return None

    def set_mute(self, strip, mute):
        if not self.connect():
            return False
        try:
            r = self.dll.VBVMR_SetParameterFloat(
                f"Strip[{strip}].Mute".encode(), ctypes.c_float(1.0 if mute else 0.0)
            )
            return r == 0
        except Exception:
            self.logged_in = False
            return False

    def get_level(self, strip):
        if not self.logged_in:
            return 0.0
        try:
            best = 0.0
            for ch in (strip * 2, strip * 2 + 1):
                v = ctypes.c_float()
                if self.dll.VBVMR_GetLevel(0, ch, ctypes.byref(v)) == 0:
                    best = max(best, v.value)
            return best
        except Exception:
            return 0.0


# ---------------------------------------------------------------------------
# Windows Audio (pycaw) - مع دعم قائمة المايكات
# ---------------------------------------------------------------------------
class WindowsAudio:
    def __init__(self):
        self.volume = None
        self.device_id = ""
        self.devices = []
        self._refresh_devices()
        self._refresh()

    def _refresh_devices(self):
        """يجلب قائمة بكل المايكات المتاحة"""
        if not PYCAW_AVAILABLE:
            self.devices = []
            return
        try:
            devices = AudioUtilities.GetAllDevices()
            self.devices = []
            for d in devices:
                if hasattr(d, 'dataFlow') and str(d.dataFlow) == '1':
                    self.devices.append({
                        'id': d.id,
                        'name': d.FriendlyName,
                        'device': d
                    })
        except Exception as e:
            print(f"Error getting devices: {e}")
            self.devices = []

    def get_devices_list(self):
        """يرجع قائمة بأسماء المايكات"""
        return [d['name'] for d in self.devices]

    def set_device(self, device_id):
        """يضبط المايك المختار"""
        self.device_id = device_id
        self._refresh()

    def _refresh(self):
        """يحدث اتصال المايك الحالي"""
        if not PYCAW_AVAILABLE:
            return
        try:
            if self.device_id:
                for d in self.devices:
                    if d['id'] == self.device_id:
                        interface = d['device'].Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                        self.volume = interface.QueryInterface(IAudioEndpointVolume)
                        return
            mic = AudioUtilities.GetMicrophone()
            if mic:
                interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.volume = interface.QueryInterface(IAudioEndpointVolume)
        except Exception:
            self.volume = None

    def get_mute(self):
        if not PYCAW_AVAILABLE or not self.volume:
            self._refresh()
            if not self.volume:
                return None
        try:
            return bool(self.volume.GetMute())
        except Exception:
            self._refresh()
            return None

    def set_mute(self, mute):
        if not PYCAW_AVAILABLE or not self.volume:
            self._refresh()
            if not self.volume:
                return False
        try:
            self.volume.SetMute(1 if mute else 0, None)
            return True
        except Exception:
            return False

    def get_level(self):
        if not PYCAW_AVAILABLE:
            return 0.0
        try:
            mic = AudioUtilities.GetMicrophone()
            if mic and hasattr(mic, 'AudioMeterInformation'):
                return mic.AudioMeterInformation.MasterValue
            return 0.0
        except Exception:
            return 0.0

    def close(self):
        self.volume = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return f"#{int(max(0,min(255,r))):02x}{int(max(0,min(255,g))):02x}{int(max(0,min(255,b))):02x}"


def blend_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex(r1 + (r2-r1)*t, g1 + (g2-g1)*t, b1 + (b2-b1)*t)


def noise(x, seed=0):
    return (math.sin(x * 12.9898 + seed * 78.233) * 43758.5453) % 1.0


# ---------------------------------------------------------------------------
# الواجهة الرئيسية
# ---------------------------------------------------------------------------
TRANSPARENT = "#010101"
RED = "#ff7185"
GRAY = "#8a96a8"
MUTED_TEXT = "#8793a5"


class MicHUD:
    def __init__(self):
        self.cfg = load_config()
        self.mode = self.cfg.get("mode", "voicemeeter")
        if self.mode == "voicemeeter":
            self.audio = Voicemeeter()
        else:
            self.audio = WindowsAudio()
            self.audio.set_device(self.cfg.get("device_id", ""))

        self.muted = False
        self.connected = False
        self.level = 0.0
        self.phase = 0.0
        self.hotkey_handle = None
        self.hotkey_hook_handle = None
        self._hotkey_down = False
        self._native_hook = None
        self._native_hook_proc = None
        self._native_vk = 0
        self._press = None
        self._moved = False
        self._frame = 0
        self._toggle_req = False
        self.settings_win = None

        self.colors = dict(DEFAULTS["colors"])
        self.colors.update(self.cfg.get("colors", {}))
        self.cfg["colors"] = self.colors

        self.hud_shape = max(0, min(len(HUD_SHAPES) - 1, int(self.cfg.get("hud_shape", 0))))
        self.hud_size = self.cfg.get("hud_size", "medium")
        if self.hud_size not in SIZE_FACTORS:
            self.hud_size = "medium"
        self.scale = SIZE_FACTORS[self.hud_size]
        self._set_dimensions()

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        try:
            self.root.iconbitmap(resource_path(os.path.join("assets", "mic-mute.ico")))
        except (tk.TclError, OSError):
            pass
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", bool(self.cfg["topmost"]))
        self.root.attributes("-alpha", float(self.cfg["opacity"]))
        self.root.config(bg=TRANSPARENT)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.root.geometry(f"{self.W}x{self.H}+{self.cfg['x']}+{self.cfg['y']}")

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg=TRANSPARENT,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Settings", command=self.open_settings)
        self.menu.add_command(label="Check for Updates", command=self.check_for_updates)
        self.menu.add_command(label="Toggle Mute", command=self.toggle)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.quit)

        self.register_hotkey()
        self.sync_state()
        self.animate()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _fetch_latest_release(self):
        request = urllib.request.Request(
            RELEASE_API,
            headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def check_for_updates(self):
        """Check GitHub Releases without blocking the HUD."""
        def worker():
            try:
                release = self._fetch_latest_release()
                latest = str(release.get("tag_name", "")).lstrip("vV")
                current_parts = tuple(int(x) for x in APP_VERSION.split("."))
                latest_parts = tuple(int(x) for x in latest.split(".")[:3])
                latest_parts = (latest_parts + (0, 0, 0))[:3]
                current_parts = (current_parts + (0, 0, 0))[:3]
                if latest_parts <= current_parts:
                    self.root.after(0, lambda: messagebox.showinfo(
                        APP_NAME, f"You are using the latest version ({APP_VERSION})."
                    ))
                    return
                assets = release.get("assets", [])
                asset = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
                if not asset:
                    self.root.after(0, lambda: messagebox.showwarning(
                        APP_NAME, "A new version is available, but its ZIP update package was not found."
                    ))
                    return
                self.root.after(0, lambda: self._offer_update(release, asset))
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): messagebox.showerror(
                    APP_NAME, "Could not check for updates. Check your internet connection and GitHub repository.\\n\\n" + err
                ))
        threading.Thread(target=worker, daemon=True).start()

    def _offer_update(self, release, asset):
        version = str(release.get("tag_name", "new version"))
        notes = str(release.get("body", "")).strip()
        if not messagebox.askyesno(
            APP_NAME,
            f"Version {version} is available.\\nCurrent version: {APP_VERSION}\\n\\n"
            + (notes[:1200] + "\\n\\n" if notes else "")
            + "Download and install it now? The app will restart."
        ):
            return
        try:
            if getattr(sys, "frozen", False):
                app_path = sys.executable
            else:
                messagebox.showinfo(
                    APP_NAME,
                    "Automatic replacement works in the installed EXE. You are currently running the Python source."
                )
                return
            helper = os.path.join(os.path.dirname(app_path), "MicMuteUpdater.exe")
            if not os.path.isfile(helper):
                messagebox.showerror(
                    APP_NAME,
                    "The updater helper is missing. Install the complete release package, including MicMuteUpdater.exe."
                )
                return
            subprocess.Popen([
                helper, app_path, asset["browser_download_url"], APP_NAME
            ], close_fds=True)
            self.quit()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not start the updater:\\n{exc}")

    def register_hotkey(self):
        try:
            if self._native_hook:
                ctypes.windll.user32.UnhookWindowsHookEx(self._native_hook)
                self._native_hook = None
        except Exception:
            pass
        try:
            if self.hotkey_handle is not None and keyboard is not None:
                keyboard.remove_hotkey(self.hotkey_handle)
        except Exception:
            pass
        self.hotkey_handle = None
        self._hotkey_down = False

        key = str(self.cfg.get("hotkey", "t")).strip().lower() or "t"

        if len(key) == 1 and key.isascii() and key.isalnum():
            self._native_vk = ord(key.upper())
            self._install_native_key_hook()
            return

        if keyboard is not None:
            try:
                self.hotkey_handle = keyboard.add_hotkey(
                    key,
                    lambda: setattr(self, "_toggle_req", True),
                    suppress=False,
                    trigger_on_release=False,
                )
            except Exception as e:
                print("Hotkey error:", e)

    def _install_native_key_hook(self):
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_uint), ("scanCode", ctypes.c_uint),
                ("flags", ctypes.c_uint), ("time", ctypes.c_uint),
                ("dwExtraInfo", ctypes.c_size_t),
            ]
        LRESULT = ctypes.c_ssize_t
        WPARAM = ctypes.c_size_t
        LPARAM = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM, LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.UnhookWindowsHookEx.restype = ctypes.c_bool
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p

        def hook_proc(n_code, w_param, l_param):
            if n_code >= 0:
                try:
                    info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if info.vkCode == self._native_vk:
                        if w_param in (0x0100, 0x0104):
                            if not self._hotkey_down:
                                self._hotkey_down = True
                                self._toggle_req = True
                        elif w_param in (0x0101, 0x0105):
                            self._hotkey_down = False
                except Exception:
                    pass
            return user32.CallNextHookEx(self._native_hook, n_code, w_param, l_param)

        self._native_hook_proc = HOOKPROC(hook_proc)
        module = kernel32.GetModuleHandleW(None)
        self._native_hook = user32.SetWindowsHookExW(13, self._native_hook_proc, module, 0)

    def toggle(self):
        new_state = not self.muted
        if self.mode == "voicemeeter":
            if self.audio.set_mute(self.cfg["strip"], new_state):
                self.muted = new_state
        else:
            if self.audio.set_mute(new_state):
                self.muted = new_state
        self.draw()

    def sync_state(self):
        if self.mode == "voicemeeter":
            m = self.audio.get_mute(self.cfg["strip"])
        else:
            m = self.audio.get_mute()
        if m is None:
            self.connected = False
        else:
            self.connected = True
            self.muted = m
        self.root.after(150, self.sync_state)

    def on_press(self, e):
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def on_drag(self, e):
        if not self._press:
            return
        dx, dy = e.x_root - self._press[0], e.y_root - self._press[1]
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{self._press[2] + dx}+{self._press[3] + dy}")

    def on_release(self, e):
        if self._moved:
            self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
            save_config(self.cfg)
        else:
            self.toggle()
        self._press = None

    def on_right_click(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    @staticmethod
    def rrect(c, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return c.create_polygon(pts, smooth=True, **kw)

    def _glow_line(self, c, pts, color, glow_color, width=2.0, layers=3):
        for i in range(layers, 0, -1):
            w = width + i * 2.5
            alpha_color = blend_color(glow_color, color, i / layers)
            c.create_line(*pts, fill=alpha_color, width=w, smooth=True, splinesteps=16, capstyle=tk.ROUND)
        c.create_line(*pts, fill=color, width=width, smooth=True, splinesteps=16, capstyle=tk.ROUND)

    def _glow_dot(self, c, x, y, r, color, glow_color, layers=3):
        for i in range(layers, 0, -1):
            expand = i * 1.5
            alpha_color = blend_color(glow_color, color, i / layers)
            c.create_oval(x - r - expand, y - r - expand, x + r + expand, y + r + expand,
                          fill=alpha_color, outline="")
        c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

    def _gradient_bar(self, c, x, y1, y2, w, color_top, color_bottom, steps=8):
        h = y2 - y1
        if h < 1:
            return
        step_h = h / steps
        for i in range(steps):
            t = i / max(1, steps - 1)
            color = blend_color(color_top, color_bottom, t)
            cy = y1 + i * step_h
            c.create_rectangle(x - w/2, cy, x + w/2, cy + step_h + 0.5,
                               fill=color, outline="")

    def _set_dimensions(self):
        base_w, base_h = HUD_SHAPES[self.hud_shape][1]
        self.W = max(1, int(round(base_w * self.scale)))
        self.H = max(1, int(round(base_h * self.scale)))

    def _u(self, value):
        return value * self.scale

    def _palette(self):
        return {
            "accent": self.colors.get("accent", "#64e6c0"),
            "glow": self.colors.get("glow", "#c0ffed"),
            "background": self.colors.get("background", "#101923"),
            "text": self.colors.get("text", "#e7edf5"),
            "muted": "#526174",
            "edge": "#2c3d50",
        }

    def draw_wave(self, canvas, style, x1, x2, mid, amp, phase, level,
                  accent, glow=None, quiet=None):
        style = max(0, min(19, int(style or 0)))
        gain = max(0.0, min(1.0, float(level or 0.0)))
        glow = glow or "#c0ffed"
        quiet = quiet or "#526174"
        dim = "#2b3a49"
        width = max(1.0, x2 - x1)
        active = gain > 0.025
        cx = (x1 + x2) / 2

        canvas.create_line(x1, mid, x2, mid, fill="#1e2d3d", width=1, dash=(1, 6))

        if style == 0:
            for layer in range(3):
                pts = []
                for i in range(100):
                    t = i / 99
                    v = math.sin(t * math.tau * 2.0 + phase * 0.8 + layer * 0.5)
                    env = 0.2 + 0.8 * (math.sin(math.pi * t) ** 0.7)
                    y = mid - v * amp * gain * env * (1 - layer * 0.2)
                    pts.extend((x1 + width * t, y))
                if active:
                    color = blend_color(accent, glow, layer / 3)
                    canvas.create_line(*pts, fill=color, width=2.5 - layer * 0.5,
                                       smooth=True, splinesteps=16)

        elif style == 1:
            for i in range(50):
                t = (i / 50 + phase * 0.02) % 1
                x = x1 + t * width
                h = amp * gain * (0.3 + 0.7 * abs(math.sin(i * 0.5 + phase * 0.6)))
                w = 2 + gain * 3
                self._glow_dot(canvas, x, mid - h, w, accent, glow, layers=3)
                self._glow_dot(canvas, x, mid + h * 0.5, w * 0.7, glow, accent, layers=2)

        elif style == 2:
            for i in range(60):
                t = (i / 60 + phase * 0.015) % 1
                x = x1 + t * width
                spread = amp * gain * 1.2
                y = mid + math.sin(i * 1.7 + phase * 0.8) * spread
                r = 0.8 + gain * 1.5 * noise(i + phase, seed=3)
                if active:
                    self._glow_dot(canvas, x, y, r,
                                   glow if i % 7 == 0 else accent,
                                   accent, layers=2)

        elif style == 3:
            for ribbon in range(5):
                pts = []
                offset = ribbon * 0.3
                for i in range(80):
                    t = i / 79
                    v = math.sin(t * math.tau * 1.5 + phase * 0.6 + offset)
                    env = 0.3 + 0.7 * (math.sin(math.pi * t) ** 0.8)
                    x = x1 + width * t
                    y = mid + v * amp * gain * env * 0.5 + (ribbon - 2) * 3
                    pts.extend((x, y))
                if active:
                    color = blend_color(accent, glow, ribbon / 5)
                    canvas.create_line(*pts, fill=color, width=2, smooth=True)

        elif style == 4:
            for col in range(30):
                x = x1 + col * width / 30
                for row in range(8):
                    t = (row / 8 + phase * 0.03 + col * 0.1) % 1
                    y = mid - amp * gain * t * 2
                    r = 1.5 * (1 - t) * gain
                    if active and r > 0.5:
                        alpha = 1 - t
                        color = blend_color(glow, accent, alpha)
                        canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="")

        elif style == 5:
            for i in range(40):
                t = i / 40
                x = x1 + t * width
                for j in range(3):
                    angle = phase * 0.5 + i * 0.3 + j * 2
                    r = amp * gain * (0.3 + 0.7 * abs(math.sin(angle)))
                    y = mid + math.cos(angle) * r * 0.5
                    size = 2 + gain * 2 * noise(i + j, seed=6)
                    if active:
                        self._glow_dot(canvas, x, y, size, accent, glow, layers=2)

        elif style == 6:
            for i in range(50):
                t = (i / 50 + phase * 0.01) % 1
                x = x1 + t * width
                y = mid + math.sin(i * 2.1 + phase * 0.7) * amp * gain * 0.8
                r = 1 + gain * 2 * abs(math.sin(i * 0.8 + phase * 0.5))
                if active:
                    self._glow_dot(canvas, x, y, r,
                                   glow if i % 5 == 0 else accent,
                                   accent, layers=3)

        elif style == 7:
            pts_top, pts_bot = [], []
            for i in range(100):
                t = i / 99
                v = (0.6 * math.sin(t * math.tau * 2.0 + phase * 0.9)
                     + 0.4 * math.sin(t * math.tau * 4.5 - phase * 0.6))
                env = 0.25 + 0.75 * (math.sin(math.pi * t) ** 0.7)
                x = x1 + width * t
                y_top = mid - v * amp * gain * env
                y_bot = mid + v * 0.6 * amp * gain * env
                pts_top.extend((x, y_top))
                pts_bot.extend((x, y_bot))
            if active:
                poly = pts_top + pts_bot[::-1]
                canvas.create_polygon(*poly, fill=blend_color(accent, glow, 0.3),
                                      outline="", smooth=True)
                self._glow_line(canvas, pts_top, accent, glow, width=2.5, layers=3)

        elif style == 8:
            for i in range(35):
                t = (i / 35 + phase * 0.02) % 1
                x = x1 + t * width
                h = amp * gain * abs(math.sin(i * 1.3 + phase * 0.8))
                y = mid + math.sin(i * 0.9 + phase * 0.6) * h * 0.6
                length = 2 + gain * 4
                angle = math.atan2(math.cos(i * 0.9 + phase), 1) * 0.6
                dx = math.cos(angle) * length
                dy = math.sin(angle) * length
                if active:
                    canvas.create_line(x - dx, y + dy, x + dx, y - dy,
                                       fill=glow, width=2.5)
                    canvas.create_line(x - dx, y + dy, x + dx, y - dy,
                                       fill=accent, width=1.2)

        elif style == 9:
            for i in range(10):
                y = mid - amp * 0.9 + i * amp * 0.2
                canvas.create_line(x1, y, x2, y, fill="#1e2d3d", width=0.5)
            pts = []
            for i in range(90):
                t = i / 89
                v = (0.7 * math.sin(t * math.tau * 2.0 + phase * 0.7)
                     + 0.3 * math.sin(t * math.tau * 5.0 - phase * 0.4))
                env = 0.3 + 0.7 * (math.sin(math.pi * t) ** 0.65)
                x = x1 + width * t
                y = mid - v * amp * gain * env
                pts.extend((x, y))
            if active:
                self._glow_line(canvas, pts, accent, glow, width=2.8, layers=3)

        elif style == 10:
            for i in range(70):
                t = (i / 70 + phase * 0.012) % 1
                x = x1 + t * width
                spread = amp * gain * 1.1
                y = mid + math.sin(i * 1.9 + phase * 0.9) * spread
                r = 0.6 + gain * 1.2 * noise(i + phase, seed=11)
                if active:
                    color = blend_color(glow, accent, noise(i, seed=12))
                    canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="")

        elif style == 11:
            for i in range(45):
                t = i / 45
                x = x1 + t * width
                h = amp * gain * (0.4 + 0.6 * abs(math.sin(i * 0.6 + phase * 0.7)))
                w = 3 + gain * 2
                color = blend_color("#ff7185", accent, h / (amp * gain + 0.01))
                self._gradient_bar(canvas, x, mid - h, mid + h * 0.3, w,
                                   glow, color, steps=6)

        elif style == 12:
            for i in range(35):
                t = (i / 35 + phase * 0.018) % 1
                x = x1 + t * width
                y = mid + math.sin(i * 1.5 + phase * 0.6) * amp * gain * 0.7
                size = 2 + gain * 2.5
                pts = []
                for k in range(6):
                    angle = k * math.pi / 3 + phase * 0.2
                    px = x + size * math.cos(angle)
                    py = y + size * math.sin(angle)
                    pts.extend((px, py))
                if active:
                    canvas.create_polygon(*pts, fill=blend_color(glow, accent, 0.5),
                                          outline=glow, width=1)

        elif style == 13:
            n = 35
            step = width / n
            for i in range(n):
                t = i / n
                h = amp * gain * (0.3 + 0.7 * abs(math.sin(i * 0.5 + phase * 0.8)))
                x = x1 + i * step + step / 2
                w = step * 0.6
                color = blend_color(accent, glow, t)
                self._gradient_bar(canvas, x, mid - h, mid + h, w,
                                   glow, color, steps=8)

        elif style == 14:
            pts = []
            for i in range(100):
                t = i / 99
                v = math.sin(t * math.tau * 2.0 + phase * 0.8)
                env = 0.2 + 0.8 * (math.sin(math.pi * t) ** 0.7)
                y = mid - v * amp * gain * env
                pts.extend((x1 + width * t, y))
            if active:
                self._glow_line(canvas, pts, accent, glow, width=3, layers=3)
                for i in range(0, len(pts), 20):
                    x, y = pts[i], pts[i+1]
                    self._glow_dot(canvas, x, y, 2, glow, accent, layers=2)

        elif style == 15:
            cols = 25
            rows = 5
            for i in range(cols):
                for j in range(rows):
                    t = i / cols
                    x = x1 + t * width
                    y = mid + (j - rows/2) * amp * 0.3
                    h = amp * gain * abs(math.sin(i * 0.4 + j * 0.8 + phase * 0.6))
                    r = 1 + gain * 1.5 * (h / (amp * gain + 0.01))
                    if active and r > 1:
                        self._glow_dot(canvas, x, y - h * 0.5, r, accent, glow, layers=2)

        elif style == 16:
            for i in range(40):
                t = (i / 40 + phase * 0.025) % 1
                x = x1 + t * width
                pulse = abs(math.sin(i * 0.7 + phase * 0.5))
                h = amp * gain * pulse
                y = mid + math.sin(i * 1.2 + phase * 0.8) * h * 0.6
                r = 1.5 + gain * 2 * pulse
                if active:
                    self._glow_dot(canvas, x, y, r,
                                   glow if i % 6 == 0 else accent,
                                   accent, layers=3)

        elif style == 17:
            for i in range(80):
                t = (i / 80 + phase * 0.01) % 1
                x = x1 + t * width
                y = mid + math.sin(i * 2.3 + phase * 0.7) * amp * gain * 0.9
                r = 0.5 + gain * 1.8 * noise(i + phase, seed=18)
                if active:
                    brightness = noise(i, seed=19)
                    color = blend_color(glow, accent, brightness)
                    canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline="")

        elif style == 18:
            for layer in range(4):
                pts = []
                offset = layer * 0.4
                for i in range(90):
                    t = i / 89
                    v = math.sin(t * math.tau * 2.0 + phase * 0.7 + offset)
                    env = 0.25 + 0.75 * (math.sin(math.pi * t) ** 0.7)
                    x = x1 + width * t
                    y = mid - v * amp * gain * env * (1 - layer * 0.15) + (layer - 1.5) * 2
                    pts.extend((x, y))
                if active:
                    color = blend_color(accent, glow, layer / 4)
                    canvas.create_line(*pts, fill=color, width=2.2 - layer * 0.3,
                                       smooth=True, splinesteps=14)

        else:
            pts = []
            for i in range(100):
                t = i / 99
                v = (0.6 * math.sin(t * math.tau * 2.0 + phase * 0.8)
                     + 0.3 * math.sin(t * math.tau * 4.5 - phase * 0.5)
                     + 0.1 * noise(t * 10 + phase * 0.2, seed=20))
                env = 0.2 + 0.8 * (math.sin(math.pi * t) ** 0.7)
                y = mid - v * amp * gain * env
                pts.extend((x1 + width * t, y))
            if active:
                self._glow_line(canvas, pts, accent, glow, width=3, layers=3)
                for i in range(20):
                    t = (i / 20 + phase * 0.03) % 1
                    x = x1 + t * width
                    idx = int(t * 99)
                    if idx < len(pts) // 2:
                        y = pts[idx * 2 + 1]
                        r = 1 + gain * 1.5 * noise(i + phase, seed=21)
                        self._glow_dot(canvas, x, y - 3, r, glow, accent, layers=2)

    def _draw_mic(self, c, x, y, radius, accent, muted=False, level=0.0):
        """Modern studio microphone icon with a reactive audio halo."""
        pulse = 1.0 + (0.035 * math.sin(self.phase * 2) if not muted else 0)
        r = max(8, radius * pulse)
        bg = self.colors["background"]
        shell = "#101d2c"
        metal = "#d9e8f5"

        c.create_oval(x-r-4, y-r-4, x+r+4, y+r+4,
                      fill=blend_color(bg, accent, 0.16), outline="")
        c.create_oval(x-r, y-r, x+r, y+r,
                      fill=shell, outline=blend_color(accent, "#ffffff", 0.22), width=1.2)

        if not muted:
            extent = max(8, min(300, int(300 * max(0.05, level))))
            c.create_arc(x-r-2, y-r-2, x+r+2, y+r+2,
                         start=270, extent=extent, style=tk.ARC,
                         outline=accent, width=max(1, r*0.075))
        else:
            c.create_arc(x-r-2, y-r-2, x+r+2, y+r+2,
                         start=35, extent=290, style=tk.ARC,
                         outline=RED, width=max(1, r*0.075))

        cap_w, cap_top = r*0.72, y-r*0.67
        cap_bottom = y+r*0.40
        c.create_oval(x-cap_w/2, cap_top, x+cap_w/2, cap_top+cap_w*0.55,
                      fill="#e8f2fb", outline="")
        c.create_rectangle(x-cap_w/2, cap_top+cap_w*0.27,
                           x+cap_w/2, cap_bottom-cap_w*0.18,
                           fill="#c8d8e8", outline="")
        c.create_arc(x-cap_w/2, cap_bottom-cap_w*0.55,
                     x+cap_w/2, cap_bottom+cap_w*0.12,
                     start=180, extent=180, style=tk.ARC,
                     outline="#e8f2fb", width=max(1, r*0.10))

        for i in range(4):
            yy = cap_top + cap_w*0.40 + i*cap_w*0.19
            c.create_line(x-cap_w*0.25, yy, x+cap_w*0.25, yy,
                          fill="#526a82", width=max(1, r*0.035))
        c.create_line(x-cap_w*0.24, cap_top+cap_w*0.30,
                      x-cap_w*0.24, cap_bottom-cap_w*0.22,
                      fill="#ffffff", width=max(1, r*0.035))

        mount_top, mount_bottom = y+r*0.12, y+r*0.72
        c.create_arc(x-r*0.58, mount_top, x+r*0.58, mount_bottom,
                     start=180, extent=180, style=tk.ARC,
                     outline=accent if not muted else RED,
                     width=max(1.4, r*0.10))
        c.create_line(x, mount_bottom-r*0.03, x, y+r*0.88,
                      fill=metal, width=max(1, r*0.075))
        c.create_line(x-r*0.25, y+r*0.90, x+r*0.25, y+r*0.90,
                      fill=metal, width=max(1.4, r*0.09))

        if muted:
            c.create_line(x-r*0.55, y-r*0.55, x+r*0.55, y+r*0.55,
                          fill=RED, width=max(2, r*0.15), capstyle=tk.ROUND)
        elif level > 0.18:
            for side in (-1, 1):
                for n in range(2):
                    yy = y-r*0.10+n*r*0.22
                    xx = x+side*r*(0.67+n*0.08)
                    c.create_arc(xx-r*0.22, yy-r*0.22, xx+r*0.22, yy+r*0.22,
                                 start=side*90-45, extent=90,
                                 style=tk.ARC, outline=accent,
                                 width=max(1, r*0.055))

    def draw(self):
        c = self.canvas
        c.delete("all")
        pal = self._palette()
        accent = pal["accent"] if self.connected and not self.muted else (RED if self.muted else GRAY)
        glow = pal["glow"]
        status = "LIVE" if self.connected and not self.muted else ("MUTE" if self.muted else "WAIT")
        bg, edge, text = pal["background"], pal["edge"], pal["text"]
        meter = self.level if self.connected and not self.muted else 0.0
        u = self._u

        shape = self.hud_shape

        if shape == 0:
            self.rrect(c, u(1), u(1), self.W-u(1), self.H-u(1), u(17), fill=bg, outline=edge, width=1)
            self._draw_mic(c,u(29),u(28),u(19),accent,self.muted,meter)
            c.create_text(u(55),u(21),text="MIC",anchor="w",fill=text,font=("Segoe UI",max(6,int(u(8))),"bold"))
            c.create_text(u(55),u(34),text="INPUT 01",anchor="w",fill=MUTED_TEXT,font=("Segoe UI",max(4,int(u(5))),"bold"))
            c.create_line(u(94),u(11),u(94),u(45),fill=edge,width=1)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(104),u(193),u(28),u(13.5),self.phase,meter,accent,glow,pal["muted"])
            c.create_line(u(201),u(11),u(201),u(45),fill=edge,width=1)
            self.rrect(c,u(209),u(14),u(241),u(42),u(9),fill="#1a2837",outline=edge,width=1)
            c.create_oval(u(215),u(19),u(221),u(25),fill=accent,outline="")
            c.create_text(u(225),u(22),text=status,anchor="w",fill=accent,font=("Segoe UI",max(4,int(u(6))),"bold"))
            c.create_line(u(215),u(33),u(235),u(33),fill="#34485b",width=max(1,u(2)),capstyle=tk.ROUND)
            if meter>.005:
                c.create_line(u(215),u(33),u(215+20*meter),u(33),fill=accent,width=max(1,u(2)),capstyle=tk.ROUND)
            c.create_text(u(235),u(37),text=f"{int(meter*100):02d}%",anchor="e",fill=MUTED_TEXT,font=("Segoe UI",max(4,int(u(5)))))

        elif shape == 1:
            self.rrect(c,u(1),u(1),self.W-u(1),self.H-u(1),u(13),fill=bg,outline=edge,width=1)
            c.create_text(u(15),u(12),text="VOICEMEETER  /  INPUT MONITOR",anchor="w",fill=MUTED_TEXT,font=("Segoe UI",max(5,int(u(6))),"bold"))
            c.create_line(u(12),u(20),u(304),u(20),fill=edge,width=1)
            self._draw_mic(c,u(30),u(44),u(15),accent,self.muted,meter)
            c.create_text(u(51),u(39),text="MIC",anchor="w",fill=text,font=("Segoe UI",max(6,int(u(8))),"bold"))
            c.create_text(u(51),u(50),text=status,anchor="w",fill=accent,font=("Segoe UI",max(5,int(u(6))),"bold"))
            self.draw_wave(c,self.cfg.get("wave_style",0),u(103),u(250),u(45),u(17),self.phase,meter,accent,glow,pal["muted"])
            c.create_line(u(263),u(27),u(263),u(60),fill=edge,width=1)
            c.create_text(u(288),u(40),text=f"{int(meter*100):02d}",fill=accent,font=("Segoe UI",max(8,int(u(11))),"bold"))
            c.create_text(u(288),u(52),text="LEVEL",fill=MUTED_TEXT,font=("Segoe UI",max(4,int(u(5))),"bold"))

        elif shape == 2:
            self.rrect(c,u(1),u(1),self.W-u(1),self.H-u(1),u(12),fill=bg,outline=edge,width=1)
            self._draw_mic(c,u(21),u(21),u(15),accent,self.muted,meter)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(43),u(150),u(21),u(11),self.phase,meter,accent,glow,pal["muted"])
            c.create_oval(u(162),u(17),u(168),u(23),fill=accent,outline="")
            c.create_text(u(175),u(21),text="ON" if status=="LIVE" else status,anchor="w",fill=accent,font=("Segoe UI",max(5,int(u(6))),"bold"))

        elif shape == 3:
            self.rrect(c,u(1),u(1),self.W-u(1),self.H-u(1),u(22),fill=bg,outline=edge,width=1)
            c.create_text(u(40),u(14),text="MIC",fill=MUTED_TEXT,font=("Segoe UI",max(6,int(u(7))),"bold"))
            self._draw_mic(c,u(40),u(43),u(23),accent,self.muted,meter)
            c.create_line(u(13),u(76),u(67),u(76),fill=edge,width=1)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(10),u(70),u(94),u(19),self.phase,meter,accent,glow,pal["muted"])
            c.create_text(u(40),u(123),text=status,fill=accent,font=("Segoe UI",max(7,int(u(9))),"bold"))
            c.create_line(u(15),u(139),u(65),u(139),fill="#34485b",width=max(1,u(2)),capstyle=tk.ROUND)
            if meter>.005:
                c.create_line(u(15),u(139),u(15+50*meter),u(139),fill=accent,width=max(1,u(2)),capstyle=tk.ROUND)

        elif shape == 4:
            cx,cy=u(50),u(50)
            c.create_oval(u(2),u(2),self.W-u(2),self.H-u(2),fill=bg,outline=edge,width=1)
            c.create_oval(u(7),u(7),self.W-u(7),self.H-u(7),outline="#26394c",width=1)
            self._draw_mic(c,cx,u(38),u(20),accent,self.muted,meter)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(22),u(78),u(67),u(8),self.phase,meter,accent,glow,pal["muted"])
            c.create_text(cx,u(87),text=status,fill=accent,font=("Segoe UI",max(5,int(u(6))),"bold"))

        elif shape == 5:
            self.rrect(c,u(1),u(1),u(82),self.H-u(1),u(13),fill=bg,outline=edge,width=1)
            self.rrect(c,u(88),u(1),self.W-u(1),self.H-u(1),u(13),fill=bg,outline=edge,width=1)
            self._draw_mic(c,u(27),u(32),u(19),accent,self.muted,meter)
            c.create_text(u(54),u(23),text="MIC",anchor="w",fill=text,font=("Segoe UI",max(6,int(u(7))),"bold"))
            c.create_text(u(54),u(38),text=status,anchor="w",fill=accent,font=("Segoe UI",max(5,int(u(6))),"bold"))
            self.draw_wave(c,self.cfg.get("wave_style",0),u(101),u(231),u(32),u(15),self.phase,meter,accent,glow,pal["muted"])
            c.create_line(u(241),u(12),u(241),u(52),fill=edge,width=1)
            c.create_text(u(263),u(29),text=f"{int(meter*100):02d}%",fill=accent,font=("Segoe UI",max(6,int(u(8))),"bold"))

        elif shape == 6:
            self.rrect(c,u(1),u(1),self.W-u(1),self.H-u(1),u(16),fill=bg,outline=edge,width=1)
            self._draw_mic(c,u(22),u(24),u(15),accent,self.muted,meter)
            c.create_text(u(43),u(24),text="MIC",anchor="w",fill=text,font=("Segoe UI",max(5,int(u(7))),"bold"))
            self.draw_wave(c,self.cfg.get("wave_style",0),u(77),u(270),u(24),u(12),self.phase,meter,accent,glow,pal["muted"])
            c.create_oval(u(288),u(20),u(294),u(26),fill=accent,outline="")
            c.create_text(u(300),u(24),text=f"{int(meter*100):02d}",anchor="w",fill=MUTED_TEXT,font=("Segoe UI",max(5,int(u(6)))))

        elif shape == 7:
            cx,cy=u(62),u(55)
            c.create_oval(u(2),u(2),self.W-u(2),self.H-u(2),fill=bg,outline=edge,width=1)
            for r in (u(22),u(31),u(39)):
                c.create_oval(cx-r,cy-r,cx+r,cy+r,outline="#2a3b4d",width=1)
            self._draw_mic(c,cx,cy,u(18),accent,self.muted,meter)
            if meter>.01:
                angle=-self.phase*3.5
                ex=cx+u(37)*math.cos(angle)
                ey=cy+u(37)*math.sin(angle)
                c.create_line(cx,cy,ex,ey,fill=accent,width=1.2)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(25),u(99),u(99),u(7),self.phase,meter,accent,glow,pal["muted"])
            c.create_text(cx,u(114),text=status,fill=accent,font=("Segoe UI",max(5,int(u(7))),"bold"))

        elif shape == 8:
            self.rrect(c,u(1),u(7),self.W-u(1),u(31),u(11),fill=bg,outline=edge,width=1)
            c.create_oval(u(10),u(15),u(18),u(23),fill=accent,outline="")
            c.create_text(u(25),u(19),text="MIC",anchor="w",fill=text,font=("Segoe UI",max(5,int(u(6))),"bold"))
            self.draw_wave(c,self.cfg.get("wave_style",0),u(62),u(211),u(19),u(9),self.phase,meter,accent,glow,pal["muted"])
            c.create_text(u(224),u(19),text=status,anchor="w",fill=accent,font=("Segoe UI",max(4,int(u(5))),"bold"))

        else:
            self.rrect(c,u(1),u(1),self.W-u(1),self.H-u(1),u(12),fill=bg,outline=edge,width=1)
            self._draw_mic(c,u(24),u(24),u(16),accent,self.muted,meter)
            c.create_text(u(47),u(18),text="MIC INPUT",anchor="w",fill=text,font=("Segoe UI",max(5,int(u(7))),"bold"))
            c.create_text(u(47),u(30),text=status,anchor="w",fill=accent,font=("Segoe UI",max(4,int(u(5))),"bold"))
            c.create_text(u(211),u(24),text=f"{int(meter*100):02d}%",anchor="e",fill=accent,font=("Segoe UI",max(7,int(u(9))),"bold"))
            c.create_line(u(10),u(44),u(226),u(44),fill=edge,width=1)
            self.draw_wave(c,self.cfg.get("wave_style",0),u(12),u(224),u(64),u(14),self.phase,meter,accent,glow,pal["muted"])

    def animate(self):
        if self._toggle_req:
            self._toggle_req = False
            self.toggle()
        self._frame += 1
        self.phase += 0.24
        target = 0.0
        if self.connected and not self.muted:
            if self.mode == "voicemeeter":
                raw = self.audio.get_level(self.cfg["strip"])
            else:
                raw = self.audio.get_level()
            db = 20 * math.log10(raw + 1e-6)
            target = max(0.0, min(1.0, (db + 60.0) / 60.0))
        smoothing = 0.42 if target > self.level else 0.20
        self.level += (target - self.level) * smoothing
        self.draw()
        self.root.after(33, self.animate)

    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        w = tk.Toplevel(self.root)
        self.settings_win = w
        w.title("MicHUD · Design Studio v6.0")
        w.configure(bg="#0e151f")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.geometry("520x980")

        style = ttk.Style(w)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("HUD.TFrame", background="#0e151f")
        style.configure("HUD.TLabel", background="#0e151f", foreground="#dce6f1", font=("Segoe UI", 9))
        style.configure("HUD.Title.TLabel", background="#0e151f", foreground="#f0f5fb", font=("Segoe UI", 16, "bold"))
        style.configure("HUD.Sub.TLabel", background="#0e151f", foreground="#8292a6", font=("Segoe UI", 8))
        style.configure("HUD.TEntry", fieldbackground="#182433", foreground="#e8eef6", insertcolor="#e8eef6", bordercolor="#33465a", padding=6)
        style.configure("HUD.TSpinbox", fieldbackground="#182433", foreground="#e8eef6", arrowsize=10, padding=5)
        style.configure("HUD.TCombobox", fieldbackground="#182433", foreground="#e8eef6", arrowsize=12, padding=6)
        style.configure("HUD.Horizontal.TScale", background="#0e151f", troughcolor="#26384b", bordercolor="#0e151f")
        style.map("HUD.TCombobox", fieldbackground=[("readonly", "#182433")], foreground=[("readonly", "#e8eef6")])
        style.configure("HUD.TButton", background="#26384b", foreground="#edf5fc", bordercolor="#3a4c61", padding=(12, 7), font=("Segoe UI", 8, "bold"))
        style.map("HUD.TButton", background=[("active", "#344b63")])
        style.configure("HUD.TCheckbutton", background="#0e151f", foreground="#dce6f1", font=("Segoe UI", 9))
        style.map("HUD.TCheckbutton", background=[("active", "#0e151f")], foreground=[("active", "#ffffff")])
        style.configure("HUD.TRadiobutton", background="#0e151f", foreground="#dce6f1", font=("Segoe UI", 9))

        canvas = tk.Canvas(w, bg="#0e151f", highlightthickness=0)
        scrollbar = ttk.Scrollbar(w, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="HUD.TFrame")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        f = scroll_frame
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        f.configure(padding=(18, 14, 18, 14))

        ttk.Label(f, text="MIC HUD  /  DESIGN STUDIO v6.0", style="HUD.Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="✨ Voicemeeter + Windows Audio | 20 موجة | معاينة حية", style="HUD.Sub.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))
        tk.Frame(f, bg="#29394b", height=1).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 9))

        ttk.Label(f, text="00  /  AUDIO SOURCE", style="HUD.Sub.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))
        mode_var = tk.StringVar(value=self.cfg.get("mode", "voicemeeter"))
        mode_frame = ttk.Frame(f, style="HUD.TFrame")
        mode_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=3)
        ttk.Radiobutton(mode_frame, text="🎛️ Voicemeeter Banana", variable=mode_var, value="voicemeeter",
                        style="HUD.TRadiobutton").pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="🎤 Windows Audio", variable=mode_var, value="windows",
                        style="HUD.TRadiobutton").pack(side="left", padx=5)

        # Device selection for Windows Audio
        device_var = tk.StringVar()
        device_box = None
        if self.mode == "windows" and PYCAW_AVAILABLE:
            devices = self.audio.get_devices_list()
            if devices:
                ttk.Label(f, text="اختر المايك:", style="HUD.TLabel").grid(row=5, column=0, sticky="w", pady=3)
                device_var.set(devices[0] if devices else "")
                device_box = ttk.Combobox(f, textvariable=device_var, values=devices, state="readonly", width=35, style="HUD.TCombobox")
                device_box.grid(row=5, column=1, sticky="e", pady=3)

        if not PYCAW_AVAILABLE:
            ttk.Label(f, text="⚠️ pycaw غير مثبت - ثبّته بـ: pip install pycaw comtypes",
                      style="HUD.Sub.TLabel", foreground="#ffbd70").grid(row=6, column=0, columnspan=2, sticky="w")
            row_offset = 7
        else:
            row_offset = 6 if device_box else 6

        ttk.Label(f, text="Global hotkey", style="HUD.TLabel").grid(row=row_offset, column=0, sticky="w", pady=3)
        hk = tk.StringVar(value=self.cfg.get("hotkey", "t"))
        ttk.Entry(f, textvariable=hk, width=19, style="HUD.TEntry").grid(row=row_offset, column=1, sticky="e", pady=3)

        ttk.Label(f, text="Voicemeeter strip (0-4)", style="HUD.TLabel").grid(row=row_offset+1, column=0, sticky="w", pady=3)
        st = tk.IntVar(value=self.cfg.get("strip", 0))
        ttk.Spinbox(f, from_=0, to=4, textvariable=st, width=8, style="HUD.TSpinbox").grid(row=row_offset+1, column=1, sticky="e", pady=3)

        ttk.Label(f, text="Window opacity", style="HUD.TLabel").grid(row=row_offset+2, column=0, sticky="w", pady=3)
        op = tk.DoubleVar(value=self.cfg.get("opacity", .95))
        ttk.Scale(f, from_=.3, to=1.0, variable=op, length=170, style="HUD.Horizontal.TScale").grid(row=row_offset+2, column=1, sticky="e", pady=3)

        top = tk.BooleanVar(value=self.cfg.get("topmost", True))
        ttk.Checkbutton(f, text="Keep HUD above other windows", variable=top, style="HUD.TCheckbutton").grid(row=row_offset+3, column=0, columnspan=2, sticky="w", pady=(2, 4))

        ttk.Label(f, text="02  /  INTERFACE SHAPE", style="HUD.Sub.TLabel").grid(row=row_offset+4, column=0, columnspan=2, sticky="w", pady=(8, 4))
        shape_names = [item[0] for item in HUD_SHAPES]
        shape_var = tk.StringVar(value=shape_names[self.hud_shape])
        shape_box = ttk.Combobox(f, textvariable=shape_var, values=shape_names, state="readonly", width=35, style="HUD.TCombobox")
        shape_box.grid(row=row_offset+5, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ttk.Label(f, text="Interface size", style="HUD.TLabel").grid(row=row_offset+6, column=0, sticky="w", pady=3)
        size_var = tk.StringVar(value={"small":"Small · 82%", "medium":"Medium · 100%", "large":"Large · 125%"}.get(self.hud_size, "Medium · 100%"))
        size_box = ttk.Combobox(f, textvariable=size_var, values=list(SIZE_LABELS.keys()), state="readonly", width=21, style="HUD.TCombobox")
        size_box.grid(row=row_offset+6, column=1, sticky="e", pady=3)

        ttk.Label(f, text="03  /  WAVE ENGINE · 20 STYLES", style="HUD.Sub.TLabel").grid(row=row_offset+7, column=0, columnspan=2, sticky="w", pady=(6, 4))
        current = max(0, min(19, int(self.cfg.get("wave_style", 0))))
        wave_var = tk.StringVar(value=WAVE_NAMES[current])
        wave_box = ttk.Combobox(f, textvariable=wave_var, values=WAVE_NAMES, state="readonly", width=35, style="HUD.TCombobox")
        wave_box.grid(row=row_offset+8, column=0, columnspan=2, sticky="ew", pady=(0, 7))

        preview = tk.Canvas(f, width=470, height=80, bg="#0a1219", highlightthickness=1, highlightbackground="#2c3e52")
        preview.grid(row=row_offset+9, column=0, columnspan=2, sticky="ew")

        color_vars = dict(self.colors)
        color_buttons = {}
        preview_phase = [0.0]

        def draw_preview():
            preview.delete("all")
            preview.create_line(10, 40, 460, 40, fill="#1e2d3d", dash=(1, 6))
            idx = WAVE_NAMES.index(wave_var.get()) if wave_var.get() in WAVE_NAMES else 0
            self.draw_wave(preview, idx, 12, 458, 40, 26, preview_phase[0], 0.78,
                           color_vars.get("accent", "#64e6c0"),
                           color_vars.get("glow", "#c0ffed"), "#526174")

        def animate_preview():
            preview_phase[0] += 0.24
            draw_preview()
            if self.settings_win and self.settings_win.winfo_exists():
                w.after(50, animate_preview)

        wave_box.bind("<<ComboboxSelected>>", lambda e: draw_preview())
        w.after(100, animate_preview)

        ttk.Label(f, text="04  /  COLOR LAB", style="HUD.Sub.TLabel").grid(row=row_offset+10, column=0, columnspan=2, sticky="w", pady=(9, 4))
        preset_var = tk.StringVar(value="Custom")
        preset_values = ["Custom"] + list(PALETTES.keys())
        preset_box = ttk.Combobox(f, textvariable=preset_var, values=preset_values, state="readonly", width=22, style="HUD.TCombobox")
        preset_box.grid(row=row_offset+11, column=0, columnspan=2, sticky="ew", pady=(0, 7))

        color_labels = {"accent": "Accent", "glow": "Glow", "background": "Background", "text": "Text"}

        def refresh_color_button(key):
            color = color_vars.get(key, "#64e6c0")
            color_buttons[key].configure(text=f"{color_labels[key]}   {color.upper()}", bg=color,
                                         fg="#101820" if key != "background" else "#ffffff",
                                         activebackground=color)

        def choose_color(key):
            chosen = colorchooser.askcolor(color=color_vars[key], parent=w, title=f"Choose {key} color")
            if chosen and chosen[1]:
                color_vars[key] = chosen[1]
                preset_var.set("Custom")
                refresh_color_button(key)
                draw_preview()

        color_specs = [("accent", "Accent"), ("glow", "Glow"), ("background", "Background"), ("text", "Text")]
        for i, (key, label) in enumerate(color_specs):
            btn = tk.Button(f, text=f"{label}   {color_vars[key].upper()}",
                            command=lambda k=key: choose_color(k), relief="flat", bd=0,
                            padx=8, pady=5, font=("Segoe UI", 8, "bold"),
                            cursor="hand2", width=20)
            btn.grid(row=row_offset+12 + i // 2, column=i % 2, sticky="ew",
                     padx=(0, 5) if i % 2 == 0 else (5, 0), pady=3)
            color_buttons[key] = btn
            refresh_color_button(key)

        def choose_preset(_event=None):
            name = preset_var.get()
            if name in PALETTES:
                color_vars.update(PALETTES[name])
                for key, _label in color_specs:
                    refresh_color_button(key)
                draw_preview()
        preset_box.bind("<<ComboboxSelected>>", choose_preset)

        def apply():
            try:
                self.cfg["mode"] = mode_var.get()
                self.cfg["hotkey"] = hk.get().strip().lower() or "t"
                self.cfg["strip"] = max(0, min(4, int(st.get())))
                self.cfg["opacity"] = round(float(op.get()), 2)
                if device_box and device_var.get():
                    devices = self.audio.get_devices_list()
                    if device_var.get() in devices:
                        idx = devices.index(device_var.get())
                        self.cfg["device_id"] = self.audio.devices[idx]['id']
            except (ValueError, TypeError):
                return
            self.cfg["topmost"] = bool(top.get())
            self.cfg["wave_style"] = WAVE_NAMES.index(wave_var.get()) if wave_var.get() in WAVE_NAMES else 0
            self.cfg["hud_shape"] = shape_names.index(shape_var.get()) if shape_var.get() in shape_names else 0
            self.cfg["hud_size"] = SIZE_LABELS.get(size_var.get(), "medium")
            self.colors = dict(color_vars)
            self.cfg["colors"] = self.colors
            self.hud_shape = self.cfg["hud_shape"]
            self.hud_size = self.cfg["hud_size"]
            self.scale = SIZE_FACTORS[self.hud_size]

            new_mode = self.cfg["mode"]
            if new_mode != self.mode:
                self.audio.close()
                self.mode = new_mode
                if new_mode == "voicemeeter":
                    self.audio = Voicemeeter()
                else:
                    self.audio = WindowsAudio()
                    self.audio.set_device(self.cfg.get("device_id", ""))

            x, y = self.root.winfo_x(), self.root.winfo_y()
            self._set_dimensions()
            self.root.attributes("-alpha", self.cfg["opacity"])
            self.root.attributes("-topmost", self.cfg["topmost"])
            self.canvas.configure(width=self.W, height=self.H)
            self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
            self.cfg["x"], self.cfg["y"] = x, y
            self.register_hotkey()
            save_config(self.cfg)
            self.draw()
            w.destroy()

        update_row = row_offset + 13
        ttk.Button(
            f, text=f"Check for Updates  ·  v{APP_VERSION}",
            command=self.check_for_updates, style="HUD.TButton"
        ).grid(row=update_row, column=0, columnspan=2, sticky="ew", pady=(10, 2))

        buttons = ttk.Frame(f, style="HUD.TFrame")
        buttons.grid(row=row_offset+15, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=w.destroy, style="HUD.TButton").pack(side="right", padx=(7, 0))
        ttk.Button(buttons, text="Apply design", command=apply, style="HUD.TButton").pack(side="right")

    def quit(self):
        save_config(self.cfg)
        try:
            if keyboard is not None:
                if self.hotkey_hook_handle is not None:
                    keyboard.unhook(self.hotkey_hook_handle)
                if self.hotkey_handle is not None:
                    keyboard.remove_hotkey(self.hotkey_handle)
        except Exception:
            pass
        try:
            if self._native_hook:
                ctypes.windll.user32.UnhookWindowsHookEx(self._native_hook)
        except Exception:
            pass
        self.audio.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _log_crash():
    import traceback
    log = os.path.join(os.environ.get("APPDATA", "."), "MicHUD.log")
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S]\n") + traceback.format_exc() + "\n")
    except Exception:
        pass
    try:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("MicHUD error", traceback.format_exc() + "\n\nLog: " + log)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        MicHUD().run()
    except Exception:
        _log_crash()