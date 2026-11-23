"""
Mic Mute for Voicemeeter & Windows v6.2.0
MicHUD v6.2 - واجهة عائمة احترافية متطورة
✅ يدعم Voicemeeter Banana + كل مايكات Windows
✅ 10 أشكال HUD + 20 موجة + 8 باليتات
✅ أيقونة مايك جديدة + معاينة حية داخل الإعدادات
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
import queue
import subprocess
import tempfile
import zipfile
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, simpledialog

from PIL import Image, ImageDraw, ImageFont, ImageTk

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
    from pycaw.constants import EDataFlow, DEVICE_STATE
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

try:
    import pystray
except ImportError:
    pystray = None

# ---------------------------------------------------------------------------
# الإعدادات
# ---------------------------------------------------------------------------
APP_NAME = "Mic Mute for Voicemeeter & Windows"
APP_VERSION = "7.0.1"
GITHUB_REPO = "Lightoo00/Mic-Mute-for-Voicemeeter-Windows"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CONFIG_PATH = os.path.join(os.environ.get("APPDATA", "."), "MicHUD.json")


def resource_path(relative_path):
    """Resolve bundled assets in development and PyInstaller one-file builds."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

DEFAULTS = {
    "hotkey": "t",
    "hotkey_mode": "toggle",
    "tray_menu": True,
    "toast": True,
    "auto_start": False,
    "start_minimized": False,
    "hud_hotkeys": True,
    "smart_mute": False,
    "smart_apps": "discord, teams, zoom, skype, slack, webex",
    "auto_unmute": False,
    "voice_threshold": 0.03,
    "profiles": {},
    "active_profile": "Default",
    "mode": "voicemeeter",
    "strip": 0,
    "device_id": "",
    "opacity": 0.95,
    "topmost": True,
    "update_check": True,
    "last_update_check": 0,
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
    ("01 · Capsule", (318, 66)),
    ("02 · Studio Rack", (352, 84)),
    ("03 · Micro Strip", (232, 54)),
    ("04 · Vertical Totem", (104, 196)),
    ("05 · Audio Orb", (132, 132)),
    ("06 · Split Modules", (312, 74)),
    ("07 · Glass Rail", (348, 58)),
    ("08 · Radar Dial", (146, 146)),
    ("09 · Minimal Line", (286, 46)),
    ("10 · Console Stack", (272, 96)),
]

SIZE_FACTORS = {"small": 0.82, "medium": 1.0, "large": 1.25}
SS_FACTOR = 3
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
        self._device = None
        self._refresh_devices()
        self._refresh()

    def _refresh_devices(self):
        """Every active capture endpoint (render devices are excluded)."""
        self.devices = []
        if not PYCAW_AVAILABLE:
            return
        found = []
        try:
            found = AudioUtilities.GetAllDevices(EDataFlow.eCapture.value,
                                                DEVICE_STATE.ACTIVE.value)
        except Exception:
            try:
                found = AudioUtilities.GetAllDevices()
            except Exception as exc:
                print("Audio device scan failed:", exc)
                found = []
        seen = set()
        for d in found:
            try:
                name = getattr(d, "FriendlyName", None) or "Microphone"
                if getattr(d, "id", None) in seen:
                    continue
                seen.add(getattr(d, "id", None))
                self.devices.append({"id": getattr(d, "id", ""), "name": name,
                                     "device": d})
            except Exception:
                continue

    def get_devices_list(self):
        """يرجع قائمة بأسماء المايكات"""
        return [d['name'] for d in self.devices]

    def set_device(self, device_id):
        """يضبط المايك المختار"""
        self.device_id = device_id
        self._refresh()

    def _refresh(self):
        """Re-acquire the selected microphone (or the default one)."""
        if not PYCAW_AVAILABLE:
            return
        try:
            target = None
            if self.device_id:
                target = next((d for d in self.devices if d["id"] == self.device_id), None)
            if target is None:
                mic = AudioUtilities.GetMicrophone()
                if mic is not None:
                    target = {"id": getattr(mic, "id", ""), "device": mic}
            if target is None:
                self.volume = None
                self._device = None
                return
            dev = target.get("device") or target.get("AudioDevice")
            interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = interface.QueryInterface(IAudioEndpointVolume)
            self._device = dev
        except Exception:
            self.volume = None
            self._device = None

    def is_alive(self):
        """True when the current microphone still answers (USB unplug detection)."""
        if not PYCAW_AVAILABLE:
            return False
        try:
            if self.volume is not None:
                self.volume.GetMute()
                return True
        except Exception:
            pass
        self._refresh_devices()
        self._refresh()
        try:
            if self.volume is not None:
                self.volume.GetMute()
                return True
        except Exception:
            return False

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
            dev = self._device
            if dev is None:
                mic = AudioUtilities.GetMicrophone()
                dev = mic
            if dev is not None and hasattr(dev, "AudioMeterInformation"):
                return float(dev.AudioMeterInformation.MasterValue)
            return 0.0
        except Exception:
            return 0.0

    def close(self):
        self.volume = None
        self._device = None


# ---------------------------------------------------------------------------
# Microphone usage (Smart Mute) - Windows capability access store
# ---------------------------------------------------------------------------
MIC_USAGE_KEY = (r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager"
                 r"\ConsentStore\microphone")


def microphone_users():
    """Names of the processes that are capturing the microphone right now."""
    users = []
    try:
        base = winreg.OpenKey(winreg.HKEY_CURRENT_USER, MIC_USAGE_KEY)
    except OSError:
        return users

    def label_of(name):
        text = name.replace("#", "\\").replace("/", "\\")
        parts = [p for p in text.split("\\") if p]
        return parts[-1].lower() if parts else name.lower()

    def scan(key, depth=0):
        index = 0
        while True:
            try:
                name = winreg.EnumKey(key, index)
            except OSError:
                return
            index += 1
            try:
                sub = winreg.OpenKey(key, name)
            except OSError:
                continue
            try:
                try:
                    start = int(winreg.QueryValueEx(sub, "LastUsedTimeStart")[0])
                    stop = int(winreg.QueryValueEx(sub, "LastUsedTimeStop")[0])
                except OSError:
                    start, stop = 0, 0
                if start and stop == 0:
                    users.append(label_of(name))
                elif depth == 0 and name.lower() == "nonpackaged":
                    scan(sub, depth + 1)
            finally:
                winreg.CloseKey(sub)

    try:
        scan(base)
    finally:
        winreg.CloseKey(base)
    return users


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

def _rr_pts(x1, y1, x2, y2, r, steps=8):
    """Flat point list for a true rounded rectangle (straight edges, round corners)."""
    r = max(0.0, min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
    pts = []
    corners = (
        (x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0),
        (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180),
    )
    for cx, cy, a0 in corners:
        for i in range(steps + 1):
            a = math.radians(a0 + 90.0 * i / steps)
            pts.extend((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts



# ---------------------------------------------------------------------------
# Antialiased drawing surface (Pillow, supersampled)
# ---------------------------------------------------------------------------
FONT_FILES = {
    "Segoe UI": r"C:\Windows\Fonts\segoeui.ttf",
    "Segoe UI Semibold": r"C:\Windows\Fonts\seguisb.ttf",
    "Segoe UI Bold": r"C:\Windows\Fonts\segoeuib.ttf",
    "Consolas": r"C:\Windows\Fonts\consola.ttf",
}
_FONT_CACHE = {}
_TK_ANCHORS = {"w": "lm", "e": "rm", "center": "mm", "n": "ma", "s": "md",
               "nw": "la", "ne": "ra", "sw": "ld", "se": "rd"}


def _pil_font(family, size, ss):
    key = (family, size, ss)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = FONT_FILES.get(family, FONT_FILES["Segoe UI"])
    try:
        font = ImageFont.truetype(path, max(5, int(round(size * ss))))
    except Exception:
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


class ImgPainter:
    """Same API as a Tk canvas, but rasterised with Pillow at SS× and downsampled.

    Every shape therefore gets real antialiasing instead of Tk's staircase edges.
    """

    def __init__(self, host, width, height, ss=3, bg="#010101", offset=(0.0, 0.0)):
        self.host = host
        self.ss = max(1, int(ss))
        self.w = max(1, int(round(width)))
        self.h = max(1, int(round(height)))
        self.bg = bg
        self.ox, self.oy = offset
        self.base_draw = None
        self._photo = None
        self.delete()

    # -- infrastructure ---------------------------------------------------
    def delete(self, *_tags):
        self._img = Image.new("RGB", (self.w * self.ss, self.h * self.ss), self.bg)
        self._d = ImageDraw.Draw(self._img)
        if self.base_draw is not None:
            self.base_draw(self)

    @staticmethod
    def _flat(args):
        if len(args) == 1 and hasattr(args[0], "__len__"):
            return list(args[0])
        return list(args)

    def _pts(self, args):
        s, ox, oy = self.ss, self.ox, self.oy
        flat = self._flat(args)
        return [((flat[i] + ox) * s, (flat[i + 1] + oy) * s)
                for i in range(0, len(flat) - 1, 2)]

    def _c(self, color):
        return color if color else None

    # -- primitives -------------------------------------------------------
    def create_polygon(self, *args, **kw):
        pts = self._pts(args)
        if len(pts) < 3:
            return None
        fill = self._c(kw.get("fill"))
        outline = self._c(kw.get("outline"))
        width = max(1, int(round(float(kw.get("width", 1)) * self.ss)))
        self._d.polygon(pts, fill=fill, outline=outline, width=width if outline else 0)
        return None

    def create_line(self, *args, **kw):
        pts = self._pts(args)
        if len(pts) < 2:
            return None
        color = self._c(kw.get("fill"))
        if color is None:
            return None
        width = max(1, int(round(float(kw.get("width", 1)) * self.ss)))
        dash = kw.get("dash")
        if dash:
            self._dashed(pts, color, width, dash)
        else:
            self._d.line(pts, fill=color, width=width, joint="curve")
        if kw.get("capstyle") == tk.ROUND and not dash:
            r = width / 2.0
            for px, py in (pts[0], pts[-1]):
                self._d.ellipse([px - r, py - r, px + r, py + r], fill=color)
        return None

    def _dashed(self, pts, color, width, dash):
        on = max(1.0, float(dash[0]) * self.ss)
        off = max(1.0, float(dash[1]) * self.ss)
        if len(dash) > 2:
            off = max(1.0, float(dash[2]) * self.ss)
        pos = 0.0
        drawing = True
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            seg = math.hypot(x2 - x1, y2 - y1)
            if seg < 1e-6:
                continue
            t = 0.0
            while t < seg:
                step = (on if drawing else off) - pos
                step = min(step, seg - t)
                if drawing:
                    ax = x1 + (x2 - x1) * t / seg
                    ay = y1 + (y2 - y1) * t / seg
                    bx = x1 + (x2 - x1) * (t + step) / seg
                    by = y1 + (y2 - y1) * (t + step) / seg
                    self._d.line([(ax, ay), (bx, by)], fill=color, width=width)
                t += step
                pos += step
                if pos >= (on if drawing else off) - 1e-6:
                    pos = 0.0
                    drawing = not drawing

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        s, ox, oy = self.ss, self.ox, self.oy
        box = [(x1 + ox) * s, (y1 + oy) * s, (x2 + ox) * s, (y2 + oy) * s]
        outline = self._c(kw.get("outline"))
        width = max(1, int(round(float(kw.get("width", 1)) * self.ss)))
        self._d.rectangle(box, fill=self._c(kw.get("fill")), outline=outline,
                          width=width if outline else 0)
        return None

    def create_oval(self, x1, y1, x2, y2, **kw):
        s, ox, oy = self.ss, self.ox, self.oy
        box = [(x1 + ox) * s, (y1 + oy) * s, (x2 + ox) * s, (y2 + oy) * s]
        outline = self._c(kw.get("outline"))
        width = max(1, int(round(float(kw.get("width", 1)) * self.ss)))
        self._d.ellipse(box, fill=self._c(kw.get("fill")), outline=outline,
                        width=width if outline else 0)
        return None

    def create_arc(self, x1, y1, x2, y2, start=0.0, extent=90.0, **kw):
        s, ox, oy = self.ss, self.ox, self.oy
        box = [(x1 + ox) * s, (y1 + oy) * s, (x2 + ox) * s, (y2 + oy) * s]
        outline = self._c(kw.get("outline"))
        if outline is None:
            return None
        width = max(1, int(round(float(kw.get("width", 1)) * self.ss)))
        lo, hi = min(start, start + extent), max(start, start + extent)
        a0 = (-hi) % 360.0
        a1 = (-lo) % 360.0
        if a1 <= a0:
            a1 += 360.0
        if a1 - a0 < 0.4:
            return None
        self._d.arc(box, a0, min(a1, a0 + 359.9), fill=outline, width=width)
        return None

    def create_vgrad(self, x1, y1, x2, y2, r, top, bottom):
        """Fill a rounded rect with a vertical gradient (real depth, no banding)."""
        s, ox, oy = self.ss, self.ox, self.oy
        bx0 = int(round((x1 + ox) * s))
        by0 = int(round((y1 + oy) * s))
        bx1 = int(round((x2 + ox) * s))
        by1 = int(round((y2 + oy) * s))
        w, h = bx1 - bx0, by1 - by0
        if w <= 0 or h <= 0:
            return
        c0, c1 = hex_to_rgb(top), hex_to_rgb(bottom)
        strip = Image.new("RGB", (1, h))
        for yy in range(h):
            t = yy / max(1, h - 1)
            strip.putpixel((0, yy), (int(c0[0] + (c1[0] - c0[0]) * t),
                                     int(c0[1] + (c1[1] - c0[1]) * t),
                                     int(c0[2] + (c1[2] - c0[2]) * t)))
        strip = strip.resize((w, h), Image.NEAREST)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, w - 1, h - 1], radius=int(round(r * s)), fill=255)
        self._img.paste(strip, (bx0, by0), mask)

    def create_text(self, x, y, text="", anchor="w", fill="#000000", font=None, **kw):
        if not text:
            return None
        family, size = "Segoe UI", 9
        if isinstance(font, (tuple, list)) and len(font) >= 2:
            family, size = font[0], font[1]
        f = _pil_font(family, size, self.ss)
        s, ox, oy = self.ss, self.ox, self.oy
        self._d.text(((x + ox) * s, (y + oy) * s), str(text), font=f,
                     fill=fill, anchor=_TK_ANCHORS.get(anchor, "lm"))
        return None

    # -- presentation -----------------------------------------------------
    def dot_grid(self, step=32, color="#13202c", radius=0.7):
        for gx in range(step // 2, self.w, step):
            for gy in range(step // 2, self.h, step):
                self._d.ellipse([(gx - radius) * self.ss, (gy - radius) * self.ss,
                                 (gx + radius) * self.ss, (gy + radius) * self.ss],
                                fill=color)

    def flush(self):
        img = self._img
        if self.ss > 1:
            img = img.resize((self.w, self.h), Image.LANCZOS)
        if self._photo is None or self._photo.width() != self.w or self._photo.height() != self.h:
            self._photo = ImageTk.PhotoImage(img, master=self.host)
            self.host._keep_photo = self._photo   # Tk drops the image if Python GCs it
            self.host.delete("hud_image")
            self.host.create_image(0, 0, image=self._photo, anchor="nw", tags="hud_image")
        else:
            self._photo.paste(img)


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
        self.hotkey_mode = "hold" if str(self.cfg.get("hotkey_mode", "toggle")) == "hold" else "toggle"
        self._last_action_ts = 0.0
        self._native_hook = None
        self._native_hook_proc = None
        self._native_vk = 0
        self._press = None
        self._moved = False
        self._frame = 0
        self._toggle_req = False
        self._mute_req = False
        self.tray = None
        self._tray_queue = queue.Queue()
        self._toast_win = None
        self._hud_hidden = False
        self._smart_active = None
        self._smart_streak = 0
        self._mute_until = 0.0
        self._voice_hits = 0
        self._device_check_at = 0.0
        self._device_alive = True
        self._manual_until = 0.0
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
        self.surface = ImgPainter(self.canvas, self.W, self.H, ss=SS_FACTOR)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Settings", command=self.open_settings)
        self.menu.add_command(label="Check for Updates", command=self.check_for_updates)
        self.menu.add_command(label="Toggle Mute", command=self.toggle)
        self.menu.add_separator()
        self.menu.add_command(label="Bigger", command=lambda: self._step_size(1))
        self.menu.add_command(label="Smaller", command=lambda: self._step_size(-1))
        self.menu.add_command(label="Next shape", command=self._cycle_shape)
        self.menu.add_separator()
        timer_menu = tk.Menu(self.menu, tearoff=0)
        for label, secs in (("30 seconds", 30), ("1 minute", 60), ("5 minutes", 300),
                            ("15 minutes", 900)):
            timer_menu.add_command(label=label,
                                   command=lambda s=secs: self.start_mute_timer(s))
        self.menu.add_cascade(label="Mute for...", menu=timer_menu)
        self._profile_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Profiles", menu=self._profile_menu)
        self._refresh_profile_menu()
        self.menu.add_separator()
        self.menu.add_command(label="Hide HUD", command=self._hide_hud)
        self.menu.add_command(label="Exit", command=self.quit)

        self.register_hotkey()
        self.root.after(4000, self._auto_update_check)
        self.sync_state()
        self.animate()
        self._bind_hud_keys()
        self._build_tray()
        if bool(self.cfg.get("start_minimized", False)) and self.tray is not None:
            self._hide_hud()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _fetch_latest_release(self):
        request = urllib.request.Request(
            RELEASE_API,
            headers={"User-Agent": APP_NAME, "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))

    def _latest_release_update(self):
        """Return (version, release, zip_asset); version is None when already current."""
        release = self._fetch_latest_release()
        latest = str(release.get("tag_name", "")).lstrip("vV")
        try:
            current = tuple(int(x) for x in APP_VERSION.split(".")[:3])
            remote = tuple(int(x) for x in latest.split(".")[:3])
        except ValueError:
            return None, release, None
        current = (current + (0, 0, 0))[:3]
        remote = (remote + (0, 0, 0))[:3]
        if remote <= current:
            return None, release, None
        asset = next((a for a in release.get("assets", [])
                      if a.get("name", "").lower().endswith(".zip")), None)
        return latest, release, asset

    def check_for_updates(self, silent=False):
        """Look for a newer release without blocking the HUD, then offer to install."""
        def worker():
            try:
                latest, release, asset = self._latest_release_update()
            except Exception as exc:
                if not silent:
                    self.root.after(0, lambda e=str(exc): messagebox.showerror(
                        APP_NAME,
                        "Could not check for updates. Check your internet connection and "
                        "the GitHub repository." + "\n\n" + e))
                return
            if latest is None:
                if not silent:
                    self.root.after(0, lambda: messagebox.showinfo(
                        APP_NAME, f"You are using the latest version ({APP_VERSION})."))
                return
            if asset is None:
                if not silent:
                    self.root.after(0, lambda: messagebox.showwarning(
                        APP_NAME,
                        "A new version is available, but its ZIP update package was not found."))
                return
            if not getattr(sys, "frozen", False):
                if not silent:
                    self.root.after(0, lambda: messagebox.showinfo(
                        APP_NAME,
                        "Automatic replacement works in the installed EXE. "
                        "You are currently running the Python source."))
                return
            self.root.after(0, lambda: self._offer_update(release, asset))
        threading.Thread(target=worker, daemon=True).start()

    def _offer_update(self, release, asset):
        version = str(release.get("tag_name", "new version"))
        notes = str(release.get("body", "")).strip()
        message = ("Version " + version + " is available." + "\n"
                   + "Current version: " + APP_VERSION + "\n\n"
                   + (notes[:1000] + "\n\n" if notes else "")
                   + "Install it now? The app will restart automatically.")
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
        except tk.TclError:
            pass
        if not messagebox.askyesno(APP_NAME, message, parent=self.root):
            return
        self._install_update(asset)

    def _install_update(self, asset):
        try:
            app_path = sys.executable
            helper = os.path.join(os.path.dirname(app_path), "MicMuteUpdater.exe")
            if not os.path.isfile(helper):
                messagebox.showerror(
                    APP_NAME,
                    "The updater helper is missing. Install the complete release package, "
                    "including MicMuteUpdater.exe.")
                return
            subprocess.Popen([helper, app_path, asset["browser_download_url"], APP_NAME],
                             close_fds=True)
            self.quit()
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Could not start the updater:" + "\n" + str(exc))

    def _auto_update_check(self):
        """Quiet background check on launch (at most once every 6 hours)."""
        if not self.cfg.get("update_check", True):
            return
        if not getattr(sys, "frozen", False):
            return
        now = time.time()
        try:
            last = float(self.cfg.get("last_update_check", 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        if now - last < 6 * 3600:
            return
        self.cfg["last_update_check"] = now
        save_config(self.cfg)
        self.check_for_updates(silent=True)

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
        self._mute_req = False
        self.hotkey_mode = "hold" if str(self.cfg.get("hotkey_mode", "toggle")) == "hold" else "toggle"

        key = str(self.cfg.get("hotkey", "t")).strip().lower() or "t"

        if len(key) == 1 and key.isascii() and key.isalnum():
            self._native_vk = ord(key.upper())
            self._install_native_key_hook()
            return

        if keyboard is not None:
            try:
                self.hotkey_handle = keyboard.add_hotkey(
                    key,
                    self._request_toggle,
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
                                self._hotkey_pressed()
                        elif w_param in (0x0101, 0x0105):
                            self._hotkey_down = False
                            self._hotkey_released()
                except Exception:
                    pass
            return user32.CallNextHookEx(self._native_hook, n_code, w_param, l_param)

        self._native_hook_proc = HOOKPROC(hook_proc)
        module = kernel32.GetModuleHandleW(None)
        self._native_hook = user32.SetWindowsHookExW(13, self._native_hook_proc, module, 0)

    # ---- hotkey -------------------------------------------------------------
    def _refresh_profile_menu(self):
        menu = getattr(self, "_profile_menu", None)
        if menu is None:
            return
        try:
            menu.delete(0, "end")
            names = sorted((self.cfg.get("profiles") or {}).keys())
            if not names:
                menu.add_command(label="(no profiles yet)", state="disabled")
                return
            for name in names:
                menu.add_command(label=name, command=lambda n=name: self.apply_profile(n))
        except Exception:
            pass

    def _hotkey_pressed(self):
        """Runs once per physical press; auto-repeat is filtered by the hook."""
        if self.hotkey_mode == "hold":
            if self.muted:
                self._toggle_req = True
            return
        self._request_toggle()

    def _hotkey_released(self):
        """Only hold-to-talk reacts to the key going up."""
        if self.hotkey_mode == "hold" and not self.muted:
            self._mute_req = True

    def _request_toggle(self):
        # safety net: ignore a duplicate trigger that lands within 150 ms
        now = time.perf_counter()
        if now - self._last_action_ts < 0.15:
            return
        self._last_action_ts = now
        self._toggle_req = True

    def _log_action(self, kind):
        try:
            path = os.path.join(os.environ.get("APPDATA", "."), "MicHUD-actions.log")
            if os.path.exists(path) and os.path.getsize(path) > 131072:
                os.replace(path, path + ".1")
            with open(path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + kind + "\n")
        except Exception:
            pass

    def set_muted(self, new_state):
        new_state = bool(new_state)
        if new_state == self.muted:
            return
        if self.mode == "voicemeeter":
            ok = self.audio.set_mute(self.cfg["strip"], new_state)
        else:
            ok = self.audio.set_mute(new_state)
        if ok:
            self.muted = new_state
            self._log_action("muted" if new_state else "unmuted")
            self.draw()
            self._toast("Microphone muted" if new_state else "Microphone live", new_state)

    def toggle(self):
        # a manual press always wins; automation stays out of the way for 90 s
        self._manual_until = time.time() + 90
        self.set_muted(not self.muted)

    # ---- HUD visibility -----------------------------------------------------
    def _show_hud(self):
        try:
            self.root.deiconify()
            self.root.attributes("-topmost", bool(self.cfg.get("topmost", True)))
            self.root.lift()
            self._hud_hidden = False
        except Exception:
            pass

    def _hide_hud(self):
        try:
            self.root.withdraw()
            self._hud_hidden = True
        except Exception:
            pass

    # ---- in-HUD keys --------------------------------------------------------
    def _bind_hud_keys(self):
        try:
            self.root.bind("<KeyPress>", self._on_hud_key)
        except Exception:
            pass

    def _on_hud_key(self, event):
        if not bool(self.cfg.get("hud_hotkeys", True)):
            return
        ch = (event.char or "").lower()
        if ch in ("+", "="):
            self._step_size(1)
        elif ch in ("-", "_"):
            self._step_size(-1)
        elif ch == "s":
            self._cycle_shape()

    def _step_size(self, delta):
        order = ["small", "medium", "large"]
        idx = order.index(self.hud_size) if self.hud_size in order else 1
        idx = max(0, min(len(order) - 1, idx + delta))
        new_size = order[idx]
        if new_size == self.hud_size:
            return
        self.hud_size = new_size
        self.cfg["hud_size"] = new_size
        self.scale = SIZE_FACTORS[new_size]
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self._set_dimensions()
        self.canvas.configure(width=self.W, height=self.H)
        self.surface = ImgPainter(self.canvas, self.W, self.H, ss=SS_FACTOR)
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
        save_config(self.cfg)
        self.draw()

    def _cycle_shape(self):
        self.hud_shape = (self.hud_shape + 1) % len(HUD_SHAPES)
        self.cfg["hud_shape"] = self.hud_shape
        save_config(self.cfg)
        self.draw()

    # ---- tray icon ----------------------------------------------------------
    def _tray_image(self):
        try:
            img = Image.open(resource_path(os.path.join("assets", "mic-mute.ico")))
            return img.convert("RGBA").copy()
        except Exception:
            return Image.new("RGBA", (64, 64), (18, 24, 34, 255))

    def _build_tray(self):
        if pystray is None or self.tray is not None:
            return
        if not bool(self.cfg.get("tray_menu", True)):
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Mute / unmute mic",
                                 lambda: self._tray_call(self.toggle), default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Hold to talk",
                                 lambda: self._tray_call(self._toggle_hold_mode),
                                 checked=lambda item: self.hotkey_mode == "hold"),
                pystray.MenuItem("Mute for...", pystray.Menu(
                    pystray.MenuItem("30 seconds",
                                     lambda: self._tray_call(lambda: self.start_mute_timer(30))),
                    pystray.MenuItem("1 minute",
                                     lambda: self._tray_call(lambda: self.start_mute_timer(60))),
                    pystray.MenuItem("5 minutes",
                                     lambda: self._tray_call(lambda: self.start_mute_timer(300))),
                    pystray.MenuItem("15 minutes",
                                     lambda: self._tray_call(lambda: self.start_mute_timer(900))),
                )),
                pystray.MenuItem("Profiles", pystray.Menu(
                    lambda: self._tray_profiles())),
                pystray.MenuItem("Show HUD", lambda: self._tray_call(self._show_hud)),
                pystray.MenuItem("Settings...", lambda: self._tray_call(self.open_settings)),
                pystray.MenuItem("Check for updates",
                                 lambda: self._tray_call(self.check_for_updates)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", lambda: self._tray_call(self.quit)),
            )
            self.tray = pystray.Icon("MicMuteHUD", self._tray_image(), APP_NAME, menu)
            self.tray.run_detached()
        except Exception as exc:
            print("Tray unavailable:", exc)
            self.tray = None

    def _tray_profiles(self):
        """Built when the submenu is opened, so new profiles appear immediately."""
        names = sorted((self.cfg.get("profiles") or {}).keys())
        if not names:
            return [pystray.MenuItem("(no profiles yet)", None, enabled=False)]
        return [pystray.MenuItem(name, lambda item, n=name: self._tray_call(
                    lambda: self.apply_profile(n))) for name in names]

    def _stop_tray(self):
        try:
            if self.tray is not None:
                self.tray.stop()
        except Exception:
            pass
        self.tray = None

    def _tray_call(self, fn):
        try:
            self._tray_queue.put(fn)
        except Exception:
            pass

    def _drain_tray(self):
        while True:
            try:
                fn = self._tray_queue.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception:
                pass

    def _toggle_hold_mode(self):
        self.hotkey_mode = "toggle" if self.hotkey_mode == "hold" else "hold"
        self.cfg["hotkey_mode"] = self.hotkey_mode
        save_config(self.cfg)
        self._toast("Hotkey: hold to talk" if self.hotkey_mode == "hold"
                    else "Hotkey: press to toggle", False)

    # ---- toast --------------------------------------------------------------
    def _toast(self, text, muted):
        if not bool(self.cfg.get("toast", True)):
            return
        try:
            if self._toast_win is not None and self._toast_win.winfo_exists():
                self._toast_win.destroy()
        except Exception:
            pass
        try:
            w, h = 216, 52
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = sw - w - 22
            y = sh - h - 70
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.0)
            win.geometry(f"{w}x{h}+{x}+{y + 12}")
            bg = "#1d1521" if muted else "#0f1c1a"
            accent = RED if muted else self.colors.get("accent", "#64e6c0")
            c = tk.Canvas(win, width=w, height=h, bg=bg, highlightthickness=0, bd=0)
            c.pack()
            c.create_rectangle(0, 0, 3, h, fill=accent, outline="")
            c.create_polygon(_rr_pts(18, 13, 30, 31, 6, 6), fill="",
                             outline=accent, width=2)
            c.create_line(24, 31, 24, 38, fill=accent, width=2)
            c.create_line(19, 38, 29, 38, fill=accent, width=2)
            if muted:
                c.create_line(15, 13, 33, 37, fill=RED, width=2)
            c.create_text(42, h // 2, text=text, anchor="w", fill="#eef4f8",
                          font=("Segoe UI Semibold", 10))
            self._toast_win = win
            alpha = {"v": 0.0}

            def fade_in():
                alpha["v"] = min(1.0, alpha["v"] + 0.16)
                try:
                    win.attributes("-alpha", alpha["v"])
                    win.geometry(f"{w}x{h}+{x}+{y + int(12 * (1 - alpha['v']))}")
                except Exception:
                    return
                if alpha["v"] < 1.0:
                    win.after(16, fade_in)
                else:
                    win.after(1150, fade_out)

            def fade_out():
                alpha["v"] = max(0.0, alpha["v"] - 0.13)
                try:
                    if alpha["v"] <= 0.0:
                        win.destroy()
                        return
                    win.attributes("-alpha", alpha["v"])
                except Exception:
                    return
                win.after(16, fade_out)

            win.lift()
            fade_in()
        except Exception:
            pass

    # ---- start with Windows -------------------------------------------------
    def _autostart_command(self):
        if getattr(sys, "frozen", False):
            return '"' + sys.executable + '"'
        script = os.path.abspath(__file__)
        folder = os.path.dirname(sys.executable)
        for name in ("pythonw.exe", "python.exe"):
            candidate = os.path.join(folder, name)
            if os.path.exists(candidate):
                return '"' + candidate + '" "' + script + '"'
        return '"' + sys.executable + '" "' + script + '"'

    def _autostart_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run")
            try:
                winreg.QueryValueEx(key, "MicMuteHUD")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def _set_autostart(self, enabled):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_SET_VALUE)
            try:
                if enabled:
                    winreg.SetValueEx(key, "MicMuteHUD", 0, winreg.REG_SZ,
                                      self._autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, "MicMuteHUD")
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
            return True
        except Exception as exc:
            messagebox.showwarning(APP_NAME, "Could not change the Windows startup entry.\n\n"
                                             + str(exc), parent=self.root)
            return False

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
        try:
            self.root.focus_force()
        except Exception:
            pass
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
            self.root.focus_force()
        except Exception:
            pass
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

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
            "screen": blend_color(self.colors.get("background", "#101923"), "#000000", 0.34),
        }

    # ------------------------------------------------------------------
    # Design system (visual layer)
    # ------------------------------------------------------------------
    def _f(self, size, weight="normal"):
        family = "Segoe UI Semibold" if weight == "bold" else "Segoe UI"
        return (family, max(6, int(round(size * self.scale))), "normal")

    def _label(self, c, x, y, text, size, color, weight="normal", anchor="w", track=0):
        if track:
            text = (" " * track).join(text)
        return c.create_text(x, y, text=text, anchor=anchor, fill=color,
                             font=self._f(size, weight))

    def _panel(self, c, x1, y1, x2, y2, r, bg, border, inset=False):
        """Rounded surface; raised by default, recessed when used as a screen."""
        if hasattr(c, "create_vgrad"):
            if inset:
                c.create_vgrad(x1, y1, x2, y2, r, blend_color(bg, "#000000", 0.30),
                               blend_color(bg, "#ffffff", 0.03))
            else:
                c.create_vgrad(x1, y1, x2, y2, r, blend_color(bg, "#ffffff", 0.055),
                               blend_color(bg, "#000000", 0.10))
            c.create_polygon(_rr_pts(x1, y1, x2, y2, r), fill="", outline=border)
        else:
            c.create_polygon(_rr_pts(x1, y1, x2, y2, r), fill=bg, outline=border)
        if inset:
            c.create_line(x1 + r, y1 + 1.4, x2 - r, y1 + 1.4,
                          fill=blend_color(bg, "#000000", 0.45))
            c.create_line(x1 + r, y2 - 1.4, x2 - r, y2 - 1.4,
                          fill=blend_color(bg, "#ffffff", 0.06))
        else:
            c.create_line(x1 + r, y1 + 1.4, x2 - r, y1 + 1.4,
                          fill=blend_color(bg, "#ffffff", 0.085))
            c.create_line(x1 + r, y2 - 1.4, x2 - r, y2 - 1.4,
                          fill=blend_color(bg, "#000000", 0.34))

    def _orb(self, c, x, y, r, bg, border, accent, live, level):
        c.create_oval(x - r, y - r, x + r, y + r, fill=bg)
        c.create_oval(x - r * 0.96, y - r * 0.96, x + r * 0.96, y + r * 0.96,
                      outline=blend_color(bg, "#ffffff", 0.05))
        c.create_oval(x - r, y - r, x + r, y + r, outline=border)
        c.create_oval(x - r + 1.4, y - r + 1.4, x + r - 1.4, y + r - 1.4,
                      outline=blend_color(bg, "#ffffff", 0.06))
        c.create_oval(x - r + 7, y - r + 7, x + r - 7, y + r - 7,
                      outline=blend_color(bg, accent, 0.11), width=4.5)
        if live:
            ext = 359.9 * max(0.0, min(1.0, level))
            if ext > 10.0:
                for ring_r, col, wd in ((7, blend_color(bg, accent, 0.30), 4.5),
                                        (4, accent, 2.0)):
                    c.create_arc(x - r + ring_r, y - r + ring_r, x + r - ring_r,
                                 y + r - ring_r, start=90, extent=-ext,
                                 style=tk.ARC, outline=col, width=wd)

    def _led(self, c, x, y, color, bg, r=2.6):
        c.create_oval(x - r * 2.3, y - r * 2.3, x + r * 2.3, y + r * 2.3,
                      fill=blend_color(bg, color, 0.14), outline="")
        c.create_oval(x - r * 1.5, y - r * 1.5, x + r * 1.5, y + r * 1.5,
                      fill=blend_color(bg, color, 0.40), outline="")
        c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
        c.create_oval(x - r * 0.42, y - r * 0.58, x + r * 0.08, y - r * 0.08,
                      fill=blend_color(color, "#ffffff", 0.8), outline="")

    def _segments(self, c, x1, x2, y, h, level, accent, bg, count=None):
        """Hardware-style segmented VU meter."""
        span = max(1.0, x2 - x1)
        count = count or max(6, int(span / 4.4))
        gap = max(1.0, span * 0.022)
        w = max(1.0, (span - gap * (count - 1)) / count)
        filled = max(0.0, min(1.0, level)) * count
        for i in range(count):
            sx = x1 + i * (w + gap)
            frac = (i + 1) / count
            if i < filled - 1e-6:
                t = min(1.0, filled - i)
                col = blend_color(accent, blend_color(accent, "#ffffff", 0.35), 1.0 - t)
                if frac > 0.80:
                    col = blend_color(col, RED, (frac - 0.80) / 0.20 * 0.9)
            else:
                col = blend_color(bg, "#ffffff", 0.09)
            c.create_rectangle(sx, y, sx + w, y + h, fill=col, outline="")

    def _wave_screen(self, c, x1, y1, x2, y2, bg, border, accent, live):
        """Inset 'display' that the spectrum is drawn inside."""
        r = min(14.0, (y2 - y1) / 2)
        self._panel(c, x1, y1, x2, y2, r,
                    blend_color(bg, "#000000", 0.34),
                    blend_color(border, accent, 0.20 if live else 0.04), inset=True)


    # ------------------------------------------------------------------
    # Wave engine · smooth, size-aware visualisers
    # ------------------------------------------------------------------
    @staticmethod
    def _spline(pts, steps=7):
        """Catmull-Rom through the control points → dense smooth polyline."""
        if len(pts) < 3:
            return list(pts)
        p = [pts[0]] + list(pts) + [pts[-1]]
        out = []
        for i in range(len(p) - 3):
            p0, p1, p2, p3 = p[i], p[i + 1], p[i + 2], p[i + 3]
            for s in range(steps):
                t = s / steps
                t2, t3 = t * t, t * t * t
                out.append((
                    0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                           + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                           + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                    0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                           + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                           + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)))
        out.append(pts[-1])
        return out

    def _signal(self, x1, x2, mid, amp, phase, shape=1, n=13):
        """Sample a musical-looking signal and return a smooth point list."""
        span = x2 - x1
        ctrl = []
        for i in range(n):
            t = i / (n - 1)
            env = 0.38 + 0.62 * math.sin(math.pi * t) ** 0.55   # lively, fades at the ends
            v = math.sin(t * math.tau * shape + phase)
            v += 0.32 * math.sin(t * math.tau * (shape * 2.3) - phase * 0.7)
            v += 0.12 * math.sin(t * math.tau * (shape * 4.1) + phase * 1.3)
            ctrl.append((x1 + span * t, mid - v * env * amp * 0.62))
        return self._spline(ctrl)

    @staticmethod
    def _flat(pts):
        out = []
        for x, y in pts:
            out.extend((x, y))
        return out

    def _bars(self, c, x1, x2, mid, amp, phase, cols, peak, color_a, color_b,
              bg, mirror=True, gap=0.45, cap=True):
        span = max(1.0, x2 - x1)
        cw = span / cols
        w = max(1.3, cw * (1 - gap))
        for i in range(cols):
            cx = x1 + cw * (i + 0.5)
            wobble = abs(math.sin(i * 0.7 + phase * 0.55)) * 0.55 + \
                     0.45 * abs(math.sin(i * 1.9 - phase * 0.9))
            h = max(0.9, amp * peak * (0.12 + 0.88 * wobble))
            head = blend_color(color_b, color_a, min(1.0, 0.35 + wobble * 0.65))
            body = blend_color(bg, color_b, 0.55)
            style = tk.ROUND if cap else tk.BUTT
            if mirror:
                c.create_line(cx, mid - h, cx, mid + h * 0.85, fill=body, width=w, capstyle=style)
                c.create_line(cx, mid - h, cx, mid - h * 0.45, fill=head, width=w, capstyle=style)
            else:
                c.create_line(cx, mid + h * 0.18, cx, mid - h, fill=body, width=w, capstyle=style)
                c.create_line(cx, mid - h, cx, mid - h * 0.55, fill=head, width=w, capstyle=style)

    def draw_wave(self, canvas, style, x1, x2, mid, amp, phase, level,
                  accent, glow=None, quiet=None, bg=None):
        style = max(0, min(19, int(style or 0)))
        gain = max(0.0, min(1.0, float(level or 0.0)))
        glow = glow or "#c0ffed"
        quiet = quiet or "#526174"
        bg = bg or "#0b1016"
        c = canvas
        width = max(1.0, x2 - x1)
        active = gain > 0.035
        soft = blend_color(bg, accent, 0.30)
        faint = blend_color(bg, accent, 0.13)
        energy = 0.30 + 0.70 * gain           # keeps quiet input visible, no flat line
        dot = max(0.9, min(2.1, amp * 0.11))
        cols = max(9, min(24, int(width / 5.6)))

        c.create_line(x1, mid, x2, mid, fill=blend_color(bg, "#ffffff", 0.06), dash=(1, 5))

        if not active:
            return

        if style == 0:      # Crystal Waves · clean oscilloscope
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.15)
            echo = self._signal(x1, x2, mid, amp * energy * 0.55, phase - 0.9, 1.55)
            c.create_line(*self._flat(echo), fill=blend_color(bg, accent, 0.22), width=1.4)
            c.create_line(*self._flat(pts), fill=blend_color(bg, accent, 0.26), width=5.0)
            c.create_line(*self._flat(pts), fill=accent, width=1.9)
            return

        if style == 1:      # Neon Flow · glowing bars
            self._bars(c, x1, x2, mid, amp, phase, cols, energy, glow, accent, bg)
            return

        if style == 2:      # Particle Storm · beads riding the wave
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.4)
            step = max(2, len(pts) // 34)
            for i in range(0, len(pts), step):
                px, py = pts[i]
                r = dot * (0.55 + 0.7 * abs(math.sin(i * 0.35 + phase)))
                c.create_oval(px - r, py - r, px + r, py + r,
                              fill=glow if i % 12 == 0 else accent, outline="")
            return

        if style == 3:      # Aurora Borealis · layered ribbons
            for k in range(3):
                pts = self._signal(x1, x2, mid + (k - 1) * amp * 0.52,
                                   amp * energy * (1 - k * 0.26), phase + k * 0.55, 0.85 + k * 0.4)
                flat = self._flat(pts)
                c.create_line(*flat, fill=blend_color(bg, accent, 0.20), width=4.0)
                c.create_line(*flat, fill=blend_color(accent, glow, 0.20 + k * 0.25), width=1.8)
            return

        if style == 4:      # Digital Rain · falling streaks
            cols_r = max(6, min(10, int(width / 8.5)))
            wd = max(1.6, width / cols_r * 0.34)
            for i in range(cols_r):
                cx = x1 + width * (i + 0.5) / cols_r
                h = amp * 1.35 * (0.45 + 0.55 * noise(i, seed=8))
                head = mid - amp * 0.95 + ((phase * 0.05 + noise(i, seed=9)) % 1.0) * (amp * 1.9 - h)
                tail = min(mid + amp * 0.95, head + h)
                c.create_line(cx, head, cx, tail, fill=faint, width=wd)
                c.create_line(cx, head, cx, head + h * 0.45, fill=soft, width=wd)
                c.create_line(cx, head, cx, head + h * 0.16, fill=glow, width=wd)
            return

        if style == 5:      # Plasma Field · filled body + bright crest
            pts = self._signal(x1, x2, mid, amp * energy, phase, 0.95)
            body = [(x1, mid)] + pts + [(x2, mid)]
            c.create_polygon(*self._flat(body), fill=blend_color(bg, accent, 0.30), outline="")
            c.create_line(*self._flat(pts), fill=blend_color(accent, glow, 0.55), width=2.6)
            c.create_line(*self._flat(pts), fill=glow, width=1.2)
            return

        if style == 6:      # Quantum Dots · twinkling cluster
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.7)
            step = max(3, len(pts) // 18)
            for i in range(0, len(pts), step):
                px, py = pts[i]
                pulse = 0.45 + 0.55 * abs(math.sin(i * 0.5 + phase * 1.6))
                r = dot * 1.35 * pulse
                halo = r * 2.6
                c.create_oval(px - halo, py - halo, px + halo, py + halo,
                              fill=blend_color(bg, accent, 0.10 * pulse), outline="")
                c.create_oval(px - r, py - r, px + r, py + r,
                              fill=blend_color(accent, glow, pulse), outline="")
            return

        if style == 7:      # Liquid Metal · beveled wave
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.05)
            flat = self._flat(pts)
            c.create_line(*flat, fill=blend_color(bg, accent, 0.30), width=max(3.0, amp * 0.36))
            c.create_line(*flat, fill=blend_color(accent, glow, 0.45), width=max(1.6, amp * 0.18))
            c.create_line(*flat, fill=blend_color(glow, "#ffffff", 0.30), width=max(1.0, amp * 0.05))
            return

        if style == 8:      # Electric Storm · jagged trace
            n = 26
            pts = []
            for i in range(n):
                t = i / (n - 1)
                env = math.sin(math.pi * t) ** 0.5
                v = math.sin(t * math.tau * 2.2 + phase * 1.4)
                v *= 0.45 + 0.55 * noise(t * 7 + phase * 0.3, seed=11)
                pts.append((x1 + width * t, mid - v * env * amp * energy * 0.75))
            flat = self._flat(pts)
            c.create_line(*flat, fill=blend_color(bg, accent, 0.28), width=4.0)
            c.create_line(*flat, fill=glow, width=1.6)
            return

        if style == 9:      # Holographic · scan mesh + trace
            grid = blend_color(bg, accent, 0.18)
            for k in (-1.4, -0.7, 0.7, 1.4):
                c.create_line(x1, mid + k * amp * 0.55, x2, mid + k * amp * 0.55, fill=grid)
            for k in range(5):
                gx = x1 + width * (k + 0.5) / 5
                c.create_line(gx, mid - amp * 0.80, gx, mid + amp * 0.80, fill=grid)
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.3)
            c.create_line(*self._flat(pts), fill=accent, width=1.9)
            c.create_line(*self._flat(pts), fill=blend_color(bg, glow, 0.30), width=4.2)
            return

        if style == 10:     # Cosmic Dust · guide wave + drifting dust
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.2)
            c.create_line(*self._flat(pts), fill=blend_color(bg, accent, 0.22), width=1.4)
            for i in range(cols):
                px = x1 + width * noise(i, seed=13)
                py = mid + (noise(i, seed=17) - 0.5) * amp * 1.5 * gain
                r = dot * (0.35 + 0.55 * noise(i + phase * 0.15, seed=19))
                c.create_oval(px - r, py - r, px + r, py + r,
                              fill=blend_color(accent, glow, noise(i, seed=23)), outline="")
            return

        if style == 11:     # Fire Waves · warm rising bars
            for i in range(cols):
                cx = x1 + width * (i + 0.5) / cols
                wob = abs(math.sin(i * 0.62 + phase * 0.55)) * 0.6 + \
                      0.4 * abs(math.sin(i * 1.7 - phase * 0.8))
                h = max(1.0, amp * energy * (0.15 + 0.85 * wob))
                w = max(1.4, width / cols * 0.55)
                c.create_line(cx, mid + h * 0.15, cx, mid - h, fill=blend_color(bg, RED, 0.45),
                              width=w, capstyle=tk.ROUND)
                c.create_line(cx, mid - h * 0.35, cx, mid - h, fill=blend_color(accent, glow, 0.55),
                              width=w, capstyle=tk.ROUND)
                c.create_line(cx, mid - h * 0.86, cx, mid - h, fill=glow, width=w,
                              capstyle=tk.ROUND)
            return

        if style == 12:     # Ice Crystals · mirrored thin bars
            for i in range(cols):
                cx = x1 + width * (i + 0.5) / cols
                wob = abs(math.sin(i * 0.55 + phase * 0.45))
                h = max(0.9, amp * energy * (0.18 + 0.82 * wob))
                w = max(1.2, width / cols * 0.34)
                c.create_line(cx, mid - h, cx, mid + h * 0.85,
                              fill=blend_color(accent, glow, 0.25 + 0.45 * wob),
                              width=w, capstyle=tk.ROUND)
            return

        if style == 13:     # Sound Spectrum · dense centre bars
            self._bars(c, x1, x2, mid, amp, phase * 1.5, cols + 5, energy,
                       glow, accent, bg, mirror=True, gap=0.34)
            return

        if style == 14:     # Wave Rider · bold glowing trace
            pts = self._signal(x1, x2, mid, amp * energy, phase, 0.85)
            flat = self._flat(pts)
            c.create_line(*flat, fill=blend_color(bg, accent, 0.25), width=6.0)
            c.create_line(*flat, fill=glow, width=2.2)
            return

        if style == 15:     # Neon Grid · stacked blocks
            rows = 3
            for i in range(cols):
                cx = x1 + width * (i + 0.5) / cols
                level_i = abs(math.sin(i * 0.62 + phase * 0.6)) * energy
                for j in range(rows):
                    if level_i < (j + 0.35) / rows:
                        continue
                    cell = max(1.6, amp * 0.19)
                    py = mid + amp * 0.45 - j * cell * 1.9
                    c.create_rectangle(cx - cell, py - cell, cx + cell, py + cell,
                                       fill=blend_color(accent, glow, j / rows * 0.7),
                                       outline="")
            return

        if style == 16:     # Pulse Matrix · two dot rows
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.1)
            step = max(2, len(pts) // 24)
            for i in range(0, len(pts), step):
                px, py = pts[i]
                for k in (-1, 1):
                    r = dot * (1.0 - 0.25 * abs(k))
                    c.create_oval(px - r, py + k * amp * 0.30 - r, px + r,
                                  py + k * amp * 0.30 + r,
                                  fill=accent if k < 0 else soft, outline="")
            return

        if style == 17:     # Star Field · trace + stars
            pts = self._signal(x1, x2, mid, amp * energy, phase, 1.25)
            c.create_line(*self._flat(pts), fill=blend_color(bg, accent, 0.28), width=1.3)
            step = max(2, len(pts) // 18)
            for i in range(0, len(pts), step):
                px, py = pts[i]
                r = dot * (0.5 + 0.8 * noise(i, seed=31))
                yy = py + (noise(i, seed=29) - 0.5) * amp * 0.7
                c.create_oval(px - r, yy - r, px + r, yy + r,
                              fill=blend_color(accent, glow, noise(i, seed=37)), outline="")
            return

        if style == 18:     # Energy Flow · trace + travelling packets
            pts = self._signal(x1, x2, mid, amp * energy, phase * 0.8, 0.95)
            flat = self._flat(pts)
            c.create_line(*flat, fill=blend_color(bg, accent, 0.40), width=1.8)
            n = len(pts)
            for i in range(9):
                idx = int(((i / 9 + phase * 0.035) % 1.0) * (n - 1))
                px, py = pts[idx]
                r = dot * 1.1
                c.create_oval(px - r * 2.0, py - r * 2.0, px + r * 2.0, py + r * 2.0,
                              fill=blend_color(bg, glow, 0.18), outline="")
                c.create_oval(px - r, py - r, px + r, py + r, fill=glow, outline="")
            return

        # 19 · Final Frontier · layered traces + sparkles
        for k, off in ((0, 0.0), (1, 0.34)):
            pts = self._signal(x1, x2, mid, amp * energy * (1 - k * 0.35),
                               phase + off, 1.0 + k * 0.4)
            c.create_line(*self._flat(pts),
                          fill=blend_color(accent, glow, k * 0.4) if k == 0
                          else blend_color(bg, accent, 0.45),
                          width=2.2 - k * 0.9)
        for i in range(8):
            px = x1 + width * ((i / 8 + phase * 0.02) % 1.0)
            py = mid - math.sin(i * 1.7 + phase) * amp * energy * 0.6
            r = dot * 0.8
            c.create_oval(px - r, py - r, px + r, py + r, fill=glow, outline="")

    def _draw_mic(self, c, x, y, s, accent, muted=False, level=0.0):
        """Stroke-style studio microphone with a reactive level ring."""
        bg = self.colors["background"]
        stroke = RED if muted else accent
        metal = blend_color(bg, "#ffffff", 0.62) if not muted else blend_color(bg, "#ffffff", 0.40)

        # --- level ring ----------------------------------------------------
        if not muted:
            for k, rr_ in ((1.34, 0.045), (1.16, 0.075)):
                c.create_oval(x - s * rr_, y - s * rr_, x + s * rr_, y + s * rr_,
                              fill=blend_color(bg, accent, k), outline="")
        rr = s * 0.94
        c.create_oval(x - rr, y - rr, x + rr, y + rr, outline=blend_color(bg, stroke, 0.13))
        if muted:
            c.create_arc(x - rr, y - rr, x + rr, y + rr, start=0, extent=359.9,
                         style=tk.ARC, outline=blend_color(stroke, bg, 0.15),
                         width=max(1.6, s * 0.09))
        else:
            ext = 359.9 * max(0.0, min(1.0, level))
            if ext > 10.0:
                c.create_arc(x - rr, y - rr, x + rr, y + rr, start=90, extent=-ext,
                             style=tk.ARC, outline=blend_color(bg, stroke, 0.30),
                             width=max(3.2, s * 0.20))
                c.create_arc(x - rr, y - rr, x + rr, y + rr, start=90, extent=-ext,
                             style=tk.ARC, outline=stroke, width=max(1.6, s * 0.10))

        # --- capsule body ---------------------------------------------------
        half = s * 0.28
        top, bot = y - s * 0.56, y + s * 0.24
        c.create_polygon(_rr_pts(x - half, top, x + half, bot, half, 10),
                         fill=blend_color(bg, "#ffffff", 0.10 if not muted else 0.05),
                         outline=metal if not muted else blend_color(metal, bg, 0.25),
                         width=max(1.4, s * 0.08))

        # grille slots
        g_top = top + half * 0.85
        g_bot = bot - half * 1.15
        rows = 3 if s < 22 else 4
        for i in range(rows):
            yy = g_top + (g_bot - g_top) * i / max(1, rows - 1)
            c.create_line(x - half * 0.56, yy, x + half * 0.56, yy,
                          fill=blend_color(bg, "#ffffff", 0.42 if not muted else 0.22),
                          width=max(1.0, s * 0.045))

        # --- yoke, stem, base ----------------------------------------------
        yoke = s * 0.44
        c.create_arc(x - yoke, y - s * 0.05 - yoke, x + yoke, y - s * 0.05 + yoke,
                     start=200, extent=140, style=tk.ARC,
                     outline=metal, width=max(1.4, s * 0.075))
        c.create_line(x, y + s * 0.40, x, y + s * 0.60, fill=metal,
                      width=max(1.2, s * 0.06))
        c.create_line(x - s * 0.17, y + s * 0.66, x + s * 0.17, y + s * 0.66,
                      fill=metal, width=max(1.4, s * 0.075), capstyle=tk.ROUND)

        # --- mute slash -----------------------------------------------------
        if muted:
            c.create_line(x - s * 0.50, y - s * 0.54, x + s * 0.50, y + s * 0.32,
                          fill=blend_color(bg, RED, 0.30),
                          width=max(4.0, s * 0.22), capstyle=tk.ROUND)
            c.create_line(x - s * 0.50, y - s * 0.54, x + s * 0.50, y + s * 0.32,
                          fill=RED, width=max(2.0, s * 0.11), capstyle=tk.ROUND)

    def draw(self):
        c = self.surface
        c.delete("all")
        pal = self._palette()
        bg = pal["background"]
        text = pal["text"]
        accent = pal["accent"]
        glow = pal["glow"]
        live = self.connected and not self.muted
        muted = self.muted
        state = accent if live else (RED if muted else GRAY)
        status = "LIVE" if live else ("MUTE" if muted else "WAIT")
        if muted and self._mute_until:
            left = max(0, int(self._mute_until - time.time() + 0.99))
            status = "MUTE " + (f"{left // 60}:{left % 60:02d}" if left >= 60 else f"{left}s")
        meter = self.level if live else 0.0
        panel_bg = blend_color(bg, RED, 0.055) if muted else bg
        border = blend_color(panel_bg, state, 0.30 if live else 0.20)
        edge = blend_color(panel_bg, "#ffffff", 0.10)
        dim = blend_color(panel_bg, text, 0.46)
        u = self._u
        shape = self.hud_shape
        wave_style = self.cfg.get("wave_style", 0)
        quiet = pal["muted"]
        tiny = self.scale >= 0.88

        if shape == 0:
            self._panel(c, u(1), u(1), u(317), u(65), u(20), panel_bg, border)
            self._draw_mic(c, u(45), u(33), u(19), state, muted, meter)
            self._label(c, u(80), u(24), "MIC", 9, text, "bold")
            if tiny:
                self._label(c, u(80), u(37), "INPUT 01", 6.5, dim)
            c.create_line(u(146), u(15), u(146), u(51), fill=edge)
            self._wave_screen(c, u(156), u(14), u(242), u(52), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(168), u(230), u(33), u(17),
                           self.phase, meter, state, glow, quiet, pal["screen"])
            c.create_line(u(252), u(15), u(252), u(51), fill=edge)
            self._led(c, u(265), u(26), state, panel_bg, u(2.8))
            self._label(c, u(274), u(26), status, 7, state, "bold")
            self._segments(c, u(258), u(306), u(40), u(4), meter, state, panel_bg, count=12)

        elif shape == 1:
            self._panel(c, u(1), u(1), u(351), u(83), u(16), panel_bg, border)
            if tiny:
                self._label(c, u(16), u(15), "VOICEMEETER  INPUT MONITOR", 6, dim, "bold", track=1)
            c.create_line(u(14), u(25), u(338), u(25), fill=edge)
            self._draw_mic(c, u(38), u(54), u(18), state, muted, meter)
            self._label(c, u(66), u(48), "MIC", 9, text, "bold")
            self._led(c, u(70), u(62), state, panel_bg, u(2.4))
            self._label(c, u(78), u(62), status, 6.5, state, "bold")
            self._wave_screen(c, u(138), u(34), u(284), u(74), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(152), u(270), u(54), u(18),
                           self.phase, meter, state, glow, quiet)
            c.create_line(u(294), u(34), u(294), u(74), fill=edge)
            self._label(c, u(321), u(48), f"{int(meter * 100):02d}", 15, state, "bold", "center")
            self._label(c, u(336), u(50), "%", 6, dim, "normal", "w")
            if tiny:
                self._label(c, u(321), u(67), "LEVEL", 5.5, dim, "bold", "center", track=1)

        elif shape == 2:
            self._panel(c, u(1), u(1), u(231), u(53), u(16), panel_bg, border)
            self._draw_mic(c, u(28), u(27), u(15), state, muted, meter)
            self._wave_screen(c, u(51), u(11), u(152), u(43), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(61), u(142), u(27), u(14),
                           self.phase, meter, state, glow, quiet)
            self._led(c, u(168), u(27), state, panel_bg, u(2.6))
            self._label(c, u(176), u(27), status, 6.5, state, "bold")

        elif shape == 3:
            self._panel(c, u(1), u(1), u(103), u(195), u(24), panel_bg, border)
            if tiny:
                self._label(c, u(52), u(19), "MIC", 6.5, dim, "bold", "center", track=1)
            self._draw_mic(c, u(52), u(57), u(24), state, muted, meter)
            self._wave_screen(c, u(14), u(90), u(90), u(136), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(24), u(80), u(113), u(20),
                           self.phase, meter, state, glow, quiet)
            self._led(c, u(34), u(154), state, panel_bg, u(2.6))
            self._label(c, u(42), u(154), status, 6.5, state, "bold")
            self._segments(c, u(18), u(86), u(166), u(4), meter, state, panel_bg, count=11)
            self._label(c, u(52), u(183), f"{int(meter * 100)}%", 11, state, "bold", "center")

        elif shape == 4:
            self._orb(c, u(66), u(66), u(64), panel_bg, border, state, live, meter)
            self._draw_mic(c, u(66), u(54), u(21), state, muted, meter)
            self._label(c, u(66), u(97), status, 6.5, state, "bold", "center", track=1)
            self._label(c, u(66), u(114), f"{int(meter * 100)}%", 8, dim, "bold", "center")

        elif shape == 5:
            self._panel(c, u(1), u(1), u(96), u(73), u(17), panel_bg, border)
            self._panel(c, u(104), u(1), u(311), u(73), u(17), panel_bg, border)
            self._draw_mic(c, u(31), u(36), u(17), state, muted, meter)
            self._label(c, u(54), u(29), "MIC", 7, text, "bold")
            self._label(c, u(54), u(42), status, 6, state, "bold")
            self._wave_screen(c, u(116), u(12), u(246), u(62), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(128), u(234), u(37), u(22),
                           self.phase, meter, state, glow, quiet)
            c.create_line(u(257), u(18), u(257), u(56), fill=edge)
            self._label(c, u(280), u(37), f"{int(meter * 100):02d}%", 12, state, "bold", "center")

        elif shape == 6:
            self._panel(c, u(1), u(1), u(347), u(57), u(19), panel_bg, border)
            self._draw_mic(c, u(31), u(29), u(17), state, muted, meter)
            self._label(c, u(55), u(24), "MIC", 8, text, "bold")
            self._label(c, u(55), u(37), status, 6, state, "bold")
            self._wave_screen(c, u(112), u(10), u(252), u(48), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(124), u(240), u(29), u(17),
                           self.phase, meter, state, glow, quiet)
            c.create_line(u(264), u(14), u(264), u(44), fill=edge)
            self._label(c, u(296), u(29), f"{int(meter * 100):02d}", 14, state, "bold", "center")
            self._label(c, u(311), u(31), "%", 6, dim, "normal", "w")
            if tiny:
                self._label(c, u(296), u(46), "LEVEL", 5.5, dim, "bold", "center", track=1)

        elif shape == 7:
            self._orb(c, u(73), u(73), u(72), panel_bg, border, state, live, meter)
            cx, cy = u(73), u(73)
            ticks = 28
            lit = max(0.0, min(1.0, meter)) * ticks
            for i in range(ticks):
                a = math.radians(-90 + i * 360.0 / ticks)
                r0, r1 = u(54), u(66)
                on = i < lit
                col = state if on else blend_color(panel_bg, "#ffffff", 0.09)
                c.create_line(cx + math.cos(a) * r0, cy + math.sin(a) * r0,
                              cx + math.cos(a) * r1, cy + math.sin(a) * r1,
                              fill=col, width=u(1.7) if on else u(1.1),
                              capstyle=tk.ROUND)
            self._draw_mic(c, cx, cy - u(2), u(20), state, muted, meter)
            self._label(c, u(73), u(116), status, 6.5, state, "bold", "center", track=1)

        elif shape == 8:
            self._panel(c, u(1), u(1), u(285), u(45), u(22), panel_bg, border)
            self._draw_mic(c, u(25), u(22), u(15), state, muted, meter)
            self._label(c, u(48), u(23), "MIC", 6.5, text, "bold", track=1)
            self.draw_wave(c, wave_style, u(92), u(222), u(23), u(13),
                           self.phase, meter, state, glow, quiet)
            self._label(c, u(272), u(23), status, 6.5, state, "bold", "e")

        else:
            self._panel(c, u(1), u(1), u(271), u(95), u(18), panel_bg, border)
            self._draw_mic(c, u(35), u(32), u(18), state, muted, meter)
            self._label(c, u(59), u(27), "MIC INPUT", 7, text, "bold")
            if tiny:
                self._label(c, u(59), u(40), "STRIP 01", 5.5, dim, "bold", "w", track=1)
            self._label(c, u(218), u(31), f"{int(meter * 100):02d}", 15, state, "bold", "center")
            self._label(c, u(233), u(33), "%", 6, dim, "normal", "w")
            if tiny:
                self._label(c, u(218), u(48), "LEVEL", 5.5, dim, "bold", "center", track=1)
            c.create_line(u(12), u(58), u(260), u(58), fill=edge)
            self._wave_screen(c, u(12), u(64), u(260), u(88), panel_bg, border, state, live)
            self.draw_wave(c, wave_style, u(24), u(248), u(76), u(11),
                           self.phase, meter, state, glow, quiet, pal["screen"])

        c.flush()

    def animate(self):
        self._drain_tray()
        if self._toggle_req:
            self._toggle_req = False
            self.toggle()
        if self._mute_req:
            self._mute_req = False
            self.set_muted(True)
        self._frame += 1
        self.phase += 0.24
        if self._frame % 30 == 0:
            self._automation_tick()
        target = 0.0
        if self.connected and not self.muted:
            if self.mode == "voicemeeter":
                raw = self.audio.get_level(self.cfg["strip"])
            else:
                raw = self.audio.get_level()
            db = 20 * math.log10(raw + 1e-6)
            target = max(0.0, min(1.0, (db + 60.0) / 60.0))
        elif self.connected and self.muted and self.cfg.get("auto_unmute"):
            # voice activation has to listen while the output is muted
            try:
                raw = (self.audio.get_level(self.cfg["strip"])
                       if self.mode == "voicemeeter" else self.audio.get_level())
                db = 20 * math.log10(raw + 1e-6)
                probe = max(0.0, min(1.0, (db + 60.0) / 60.0))
            except Exception:
                probe = 0.0
            threshold = float(self.cfg.get("voice_threshold", 0.03))
            if self.hotkey_mode != "hold" and probe >= threshold:
                self._voice_hits += 1
                if self._voice_hits >= 6:      # ~200 ms of speech
                    self._voice_hits = 0
                    self.set_muted(False)
            else:
                self._voice_hits = 0
        smoothing = 0.42 if target > self.level else 0.20
        self.level += (target - self.level) * smoothing
        self.draw()
        self.root.after(33, self.animate)

    # ---- automation: smart mute, timer, device watchdog -----------------------
    def _automation_tick(self):
        now = time.time()
        # mute timer
        if self._mute_until and now >= self._mute_until:
            self._mute_until = 0.0
            self.set_muted(False)
        # smart mute (a manual toggle or a running timer takes priority)
        if self.cfg.get("smart_mute") and not self._mute_until and now >= self._manual_until:
            keywords = [k.strip().lower() for k in
                        str(self.cfg.get("smart_apps", "")).split(",") if k.strip()]
            active = None
            try:
                for user in microphone_users():
                    if any(k in user for k in keywords):
                        active = user
                        break
            except Exception:
                active = None
            if active == self._smart_active:
                self._smart_streak = 0
            else:
                self._smart_streak += 1
                if self._smart_streak >= 2:          # ~2 s of stability
                    self._smart_active = active
                    self._smart_streak = 0
                    if active and self.muted:
                        self.set_muted(False)
                        self._toast("Call detected - mic live", False)
                    elif not active and not self.muted:
                        self.set_muted(True)
                        self._toast("Smart mute - mic muted", True)
        # windows device watchdog
        if self.mode == "windows" and now - self._device_check_at > 3.0:
            self._device_check_at = now
            try:
                alive = self.audio.is_alive()
            except Exception:
                alive = True
            if self._device_alive and not alive:
                self._device_alive = False
                self._toast("Microphone disconnected", True)
            elif not self._device_alive and alive:
                self._device_alive = True
                self._toast("Microphone reconnected", False)

    def start_mute_timer(self, seconds):
        seconds = max(5, int(seconds))
        self.set_muted(True)
        self._mute_until = time.time() + seconds
        label = f"{seconds}s" if seconds < 90 else f"{round(seconds / 60)} min"
        self._toast("Muted for " + label, True)

    # ---- profiles ------------------------------------------------------------
    PROFILE_KEYS = ("hud_shape", "hud_size", "wave_style", "colors", "hotkey",
                    "hotkey_mode", "opacity", "theme")

    def _profile_snapshot(self):
        snap = {}
        for key in self.PROFILE_KEYS:
            value = self.cfg.get(key)
            snap[key] = dict(value) if isinstance(value, dict) else value
        return snap

    def apply_profile(self, name):
        profiles = self.cfg.get("profiles") or {}
        profile = profiles.get(name)
        if not profile:
            return False
        for key, value in profile.items():
            if key == "colors" and isinstance(value, dict):
                self.colors = dict(DEFAULTS["colors"])
                self.colors.update(value)
                self.cfg["colors"] = dict(self.colors)
            elif key in self.PROFILE_KEYS:
                self.cfg[key] = value
        self.cfg["active_profile"] = name
        self.hud_shape = max(0, min(len(HUD_SHAPES) - 1, int(self.cfg.get("hud_shape", 0))))
        self.hud_size = self.cfg.get("hud_size", "medium")
        if self.hud_size not in SIZE_FACTORS:
            self.hud_size = "medium"
        self.scale = SIZE_FACTORS[self.hud_size]
        self.hotkey_mode = "hold" if str(self.cfg.get("hotkey_mode", "toggle")) == "hold" else "toggle"
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self._set_dimensions()
        self.canvas.configure(width=self.W, height=self.H)
        self.surface = ImgPainter(self.canvas, self.W, self.H, ss=SS_FACTOR)
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.root.attributes("-alpha", float(self.cfg.get("opacity", 0.95)))
        self.register_hotkey()
        save_config(self.cfg)
        self.draw()
        self._toast("Profile: " + name, self.muted)
        return True

    def save_profile(self, name):
        name = (name or "").strip()
        if not name:
            return False
        profiles = dict(self.cfg.get("profiles") or {})
        profiles[name] = self._profile_snapshot()
        self.cfg["profiles"] = profiles
        self.cfg["active_profile"] = name
        save_config(self.cfg)
        return True

    def delete_profile(self, name):
        profiles = dict(self.cfg.get("profiles") or {})
        if name in profiles:
            del profiles[name]
            self.cfg["profiles"] = profiles
            save_config(self.cfg)
            return True
        return False

    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return

        ACCENT = self.colors.get("accent", "#64e6c0")
        BG = "#0c131c"
        CARD = "#121b26"
        LINE = "#24313f"
        TXT = "#e9f0f7"
        SUB = "#8091a5"
        FIELD = "#17222f"

        w = tk.Toplevel(self.root)
        self.settings_win = w
        w.title("MicHUD · Design Studio")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.option_add("*TCombobox*Listbox.background", FIELD)
        w.option_add("*TCombobox*Listbox.foreground", TXT)
        w.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        w.option_add("*TCombobox*Listbox.selectForeground", "#0b1219")

        style = ttk.Style(w)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("S.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("L.TLabel", background=BG, foreground=TXT, font=("Segoe UI", 9))
        style.configure("Sub.TLabel", background=BG, foreground=SUB, font=("Segoe UI", 8))
        style.configure("Sec.TLabel", background=BG, foreground=SUB,
                        font=("Segoe UI Semibold", 8))
        style.configure("Mono.TLabel", background=BG, foreground=SUB, font=("Consolas", 8))
        style.configure("S.TCombobox", fieldbackground=FIELD, background=CARD,
                        foreground=TXT, arrowcolor=SUB, bordercolor=LINE,
                        lightcolor=LINE, darkcolor=LINE, padding=(7, 5))
        style.map("S.TCombobox",
                  fieldbackground=[("readonly", FIELD)],
                  foreground=[("readonly", TXT)],
                  bordercolor=[("focus", ACCENT)])
        style.configure("S.TEntry", fieldbackground=FIELD, foreground=TXT,
                        insertcolor=TXT, bordercolor=LINE, lightcolor=LINE,
                        darkcolor=LINE, padding=(7, 5))
        style.configure("S.TSpinbox", fieldbackground=FIELD, foreground=TXT,
                        arrowcolor=SUB, bordercolor=LINE, lightcolor=LINE,
                        darkcolor=LINE, padding=(7, 4))
        style.configure("S.TCheckbutton", background=BG, foreground=TXT,
                        font=("Segoe UI", 9), focuscolor=BG)
        style.map("S.TCheckbutton", background=[("active", BG)],
                  foreground=[("active", TXT)])
        style.configure("S.Vertical.TScrollbar", background=LINE, troughcolor=BG,
                        bordercolor=BG, arrowcolor=SUB, darkcolor=LINE, lightcolor=LINE,
                        gripcount=0, width=10)
        style.map("S.Vertical.TScrollbar",
                  background=[("active", ACCENT)],
                  arrowcolor=[("active", TXT)])

        outer = tk.Frame(w, bg=BG)
        outer.pack(fill="both", expand=True, padx=22, pady=18)
        outer.columnconfigure(0, weight=0, minsize=404)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        # ---------------- header ----------------
        head = tk.Frame(outer, bg=BG)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        tk.Label(head, text="MICHUD", bg=BG, fg=TXT, font=("Segoe UI Semibold", 17)).pack(side="left")
        tk.Label(head, text="DESIGN STUDIO", bg=BG, fg=SUB,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(10, 0), pady=(6, 0))
        tk.Label(head, text=f"v{APP_VERSION}", bg=FIELD, fg=SUB,
                 font=("Segoe UI Semibold", 8), padx=8, pady=3).pack(side="right")

        # ---------------- left column (scrollable) ----------------
        left_holder = tk.Frame(outer, bg=BG, width=404)
        left_holder.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        left_holder.grid_propagate(False)
        left_scroll = ttk.Scrollbar(left_holder, orient="vertical",
                                    style="S.Vertical.TScrollbar",
                                    command=lambda *a: left_canvas.yview(*a))
        left_scroll.pack(side="right", fill="y")
        left_canvas = tk.Canvas(left_holder, bg=BG, highlightthickness=0, bd=0, width=392)
        left_canvas.pack(side="left", fill="both", expand=True)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left = tk.Frame(left_canvas, bg=BG)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")
        left.columnconfigure(1, weight=1)

        def _sync_scroll(event=None):
            if event is not None and getattr(event, "widget", None) is left_canvas:
                left_canvas.itemconfigure(left_window, width=event.width)
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            need = left.winfo_reqheight() > left_canvas.winfo_height() + 2
            if need:
                if not left_scroll.winfo_ismapped():
                    left_scroll.pack(side="right", fill="y")
            else:
                if left_scroll.winfo_ismapped():
                    left_scroll.pack_forget()
                left_canvas.yview_moveto(0)

        left.bind("<Configure>", lambda e: left_canvas.after_idle(_sync_scroll))
        left_canvas.bind("<Configure>", _sync_scroll)

        def _wheel(event):
            if left.winfo_reqheight() > left_canvas.winfo_height() + 2:
                left_canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        w.bind("<MouseWheel>", _wheel)

        row = [0]

        def nxt(span=1):
            row[0] += 1
            return row[0] - 1

        def section(title):
            r = nxt()
            tk.Frame(left, bg=LINE, height=1).grid(row=r, column=0, columnspan=2,
                                                   sticky="ew", pady=(10, 0))
            r = nxt()
            tk.Label(left, text=title, bg=BG, fg=SUB,
                     font=("Segoe UI Semibold", 8)).grid(row=r, column=0, columnspan=2,
                                                         sticky="w", pady=(9, 6))

        def field_row(label, widget):
            r = nxt()
            tk.Label(left, text=label, bg=BG, fg=TXT,
                     font=("Segoe UI", 9)).grid(row=r, column=0, sticky="w", pady=4)
            widget.grid(row=r, column=1, sticky="e", pady=4)

        def segmented(options, variable):
            frame = tk.Frame(left, bg=LINE, padx=1, pady=1)
            buttons = {}

            def select(value):
                variable.set(value)
                for key, btn in buttons.items():
                    on = key == value
                    btn.configure(bg=ACCENT if on else FIELD,
                                  fg="#0b1219" if on else TXT)

            for idx, (label, value) in enumerate(options):
                b = tk.Button(frame, text=label, relief="flat", bd=0, cursor="hand2",
                              font=("Segoe UI Semibold", 8), padx=13, pady=6,
                              highlightthickness=0,
                              command=lambda v=value: select(v))
                b.pack(side="left", padx=(0 if idx == 0 else 1, 0))
                buttons[value] = b
            select(variable.get())
            return frame

        section("01 · AUDIO SOURCE")
        mode_var = tk.StringVar(value=self.cfg.get("mode", "voicemeeter"))
        src = segmented([("Voicemeeter", "voicemeeter"), ("Windows Audio", "windows")], mode_var)
        r = nxt()
        src.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, 4))

        probe = self.audio if isinstance(self.audio, WindowsAudio) else WindowsAudio()
        dev_names = probe.get_devices_list() if PYCAW_AVAILABLE else []
        dev_ids = {d["name"]: d["id"] for d in getattr(probe, "devices", [])}
        current_dev = next((n for n, i in dev_ids.items()
                            if i == self.cfg.get("device_id", "")), None)
        device_var = tk.StringVar(value=current_dev or (dev_names[0] if dev_names else ""))
        if dev_names:
            dev_box = ttk.Combobox(left, textvariable=device_var, values=dev_names,
                                   state="readonly", style="S.TCombobox", width=24)
            dev_label = tk.Label(left, text="Input device", bg=BG, fg=TXT, font=("Segoe UI", 9))
            dev_row = nxt()
            dev_label.grid(row=dev_row, column=0, sticky="w", pady=4)
            dev_box.grid(row=dev_row, column=1, sticky="e", pady=4)

            def sync_device_row(*_):
                if mode_var.get() == "windows":
                    dev_label.grid()
                    dev_box.grid()
                else:
                    dev_label.grid_remove()
                    dev_box.grid_remove()
            sync_device_row()
            mode_var.trace_add("write", sync_device_row)
        else:
            dev_box = None

        hk = tk.StringVar(value=self.cfg.get("hotkey", "t"))
        field_row("Hotkey", ttk.Entry(left, textvariable=hk, width=14, style="S.TEntry"))
        hmode = tk.StringVar(value="hold" if self.hotkey_mode == "hold" else "toggle")
        field_row("Hotkey action",
                  segmented([("Press to toggle", "toggle"), ("Hold to talk", "hold")], hmode))
        st = tk.IntVar(value=self.cfg.get("strip", 0))
        field_row("Voicemeeter strip", ttk.Spinbox(left, from_=0, to=4, textvariable=st,
                                                   width=6, style="S.TSpinbox"))

        r = nxt()
        op_row = tk.Frame(left, bg=BG)
        op_row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=4)
        tk.Label(op_row, text="Opacity", bg=BG, fg=TXT, font=("Segoe UI", 9)).pack(side="left")
        op_val = tk.Label(op_row, text=f"{int(round(float(self.cfg.get('opacity', .95)) * 100))}%",
                          bg=BG, fg=ACCENT, font=("Segoe UI Semibold", 8), width=5, anchor="e")
        op_val.pack(side="right")
        op = tk.DoubleVar(value=self.cfg.get("opacity", .95))

        slider = tk.Canvas(op_row, width=152, height=18, bg=BG,
                           highlightthickness=0, bd=0, cursor="hand2")
        slider.pack(side="right", padx=(0, 10))

        def paint_slider(*_):
            slider.delete("all")
            v = max(0.0, min(1.0, (float(op.get()) - 0.3) / 0.7))
            slider.create_line(5, 9, 147, 9, fill=LINE, width=4, capstyle=tk.ROUND)
            slider.create_line(5, 9, 5 + 142 * v, 9, fill=ACCENT, width=4,
                               capstyle=tk.ROUND)
            slider.create_oval(5 + 142 * v - 5, 4, 5 + 142 * v + 5, 14,
                               fill="#0b1219", outline=ACCENT, width=2)
            op_val.configure(text=f"{int(round(float(op.get()) * 100))}%")

        def slide(event):
            op.set(round(0.3 + max(0.0, min(1.0, (event.x - 5) / 142)) * 0.7, 2))
            paint_slider()

        slider.bind("<Button-1>", slide)
        slider.bind("<B1-Motion>", slide)
        paint_slider()

        top = tk.BooleanVar(value=self.cfg.get("topmost", True))
        r = nxt()
        ttk.Checkbutton(left, text="Keep HUD above other windows", variable=top,
                        style="S.TCheckbutton").grid(row=r, column=0, columnspan=2,
                                                     sticky="w", pady=(6, 2))

        upd = tk.BooleanVar(value=self.cfg.get("update_check", True))
        r = nxt()
        ttk.Checkbutton(left, text="Install updates automatically on launch", variable=upd,
                        style="S.TCheckbutton").grid(row=r, column=0, columnspan=2,
                                                     sticky="w", pady=(2, 2))

        section("02 · LOOK")
        shape_names = [item[0] for item in HUD_SHAPES]
        shape_var = tk.StringVar(value=shape_names[self.hud_shape])
        shape_box = ttk.Combobox(left, textvariable=shape_var, values=shape_names,
                                 state="readonly", style="S.TCombobox", width=24)
        field_row("Interface shape", shape_box)

        size_var = tk.StringVar(value={"small": "Small", "medium": "Medium",
                                       "large": "Large"}.get(self.hud_size, "Medium"))
        r = nxt()
        tk.Label(left, text="Size", bg=BG, fg=TXT, font=("Segoe UI", 9)).grid(
            row=r, column=0, sticky="w", pady=4)
        segmented([("S", "Small"), ("M", "Medium"), ("L", "Large")], size_var).grid(
            row=r, column=1, sticky="e", pady=4)

        section("03 · WAVE ENGINE")
        current = max(0, min(19, int(self.cfg.get("wave_style", 0))))
        wave_var = tk.StringVar(value=WAVE_NAMES[current])
        wave_box = ttk.Combobox(left, textvariable=wave_var, values=WAVE_NAMES,
                                state="readonly", style="S.TCombobox", width=24)
        field_row("Spectrum style", wave_box)

        section("04 · COLOR")
        color_vars = dict(self.colors)
        color_buttons = {}
        color_specs = [("accent", "ACCENT"), ("glow", "GLOW"),
                       ("background", "PANEL"), ("text", "TEXT")]

        preset_var = tk.StringVar(value="Custom")
        preset_box = ttk.Combobox(left, textvariable=preset_var,
                                  values=["Custom"] + list(PALETTES.keys()),
                                  state="readonly", style="S.TCombobox", width=24)
        field_row("Palette preset", preset_box)

        def refresh_color_button(key):
            color = color_vars.get(key, "#64e6c0")
            label = dict(color_specs)[key]
            btn = color_buttons[key]
            btn.configure(text=f"{label}   {color.upper()}",
                          bg=color,
                          fg="#0b1219" if key != "background" else "#ffffff",
                          activebackground=color)

        def choose_color(key):
            chosen = colorchooser.askcolor(color=color_vars[key], parent=w,
                                           title=f"Choose {key} color")
            if chosen and chosen[1]:
                color_vars[key] = chosen[1]
                preset_var.set("Custom")
                refresh_color_button(key)
                draw_preview()

        r = nxt()
        grid_frame = tk.Frame(left, bg=BG)
        grid_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # ---------------- right column: live preview ----------------
        right = tk.Frame(outer, bg=BG)
        right.grid(row=1, column=1, sticky="nsew")
        tk.Label(right, text="LIVE PREVIEW", bg=BG, fg=SUB,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(0, 6))
        holder = tk.Frame(right, bg=BG)
        holder.pack(fill="both", expand=True)
        stage = tk.Frame(holder, bg="#080d13", highlightthickness=1,
                         highlightbackground=LINE)
        stage.pack(fill="both", expand=True)
        STAGE_W, STAGE_H = 388, 340
        thumb = tk.Canvas(stage, width=STAGE_W, height=STAGE_H, bg="#080d13",
                          highlightthickness=0, bd=0)
        thumb.pack(fill="both", expand=True)
        caption = tk.Label(right, text="", bg=BG, fg=SUB, font=("Segoe UI", 8),
                           justify="left")
        caption.pack(anchor="w", pady=(10, 0))
        tk.Label(right, text="Drag to move   ·   Left click mutes   ·   Right click opens the menu",
                 bg=BG, fg="#5b6b7d", font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

        preview_phase = [self.phase]
        state = {"busy": False, "surface": None}

        def draw_preview(*_):
            if state["busy"]:
                return
            state["busy"] = True
            keep = (self.surface, self.colors, self.hud_shape, self.scale,
                    self.W, self.H, self.muted, self.connected, self.level,
                    self.cfg)
            try:
                idx = shape_names.index(shape_var.get()) if shape_var.get() in shape_names else 0
                size_key = {"Small": "small", "Medium": "medium",
                            "Large": "large"}.get(size_var.get(), "medium")
                self.colors = dict(color_vars)
                self.hud_shape = idx
                self.muted = False
                self.connected = True
                self.level = 0.62
                self.cfg = dict(self.cfg)
                self.cfg["wave_style"] = (WAVE_NAMES.index(wave_var.get())
                                          if wave_var.get() in WAVE_NAMES else 0)
                wbox = max(STAGE_W, thumb.winfo_width())
                hbox = max(220, thumb.winfo_height())
                base = SIZE_FACTORS[size_key]
                self.scale = 1.0
                self._set_dimensions()
                fit = min(1.7, (wbox - 80.0) / self.W, (hbox - 80.0) / self.H)
                self.scale = base * fit
                self._set_dimensions()
                surf = state["surface"]
                if surf is None or surf.w != int(wbox) or surf.h != int(hbox):
                    surf = ImgPainter(thumb, wbox, hbox, ss=2, bg="#080d13")
                    surf.base_draw = lambda q: q.dot_grid()
                    state["surface"] = surf
                surf.ox, surf.oy = (wbox - self.W) / 2, (hbox - self.H) / 2
                self.surface = surf
                self.draw()
                caption.configure(
                    text=f"{shape_names[idx]}   ·   {WAVE_NAMES[self.cfg['wave_style']]}"
                         f"   ·   zoom {int(round(self.scale / base * 100))}%")
            finally:
                (self.surface, self.colors, self.hud_shape, self.scale,
                 self.W, self.H, self.muted, self.connected, self.level,
                 self.cfg) = keep
                state["busy"] = False

        for i, (key, label) in enumerate(color_specs):
            btn = tk.Button(grid_frame, text="", relief="flat", bd=0, cursor="hand2",
                            font=("Segoe UI Semibold", 8), pady=8, highlightthickness=0,
                            command=lambda k=key: choose_color(k))
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 4) if i % 2 == 0 else (4, 0),
                     pady=3)
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

        def tick():
            if not (self.settings_win and self.settings_win.winfo_exists()):
                return
            preview_phase[0] += 0.24
            self.phase = preview_phase[0]
            draw_preview()
            w.after(110, tick)

        section("05 · SYSTEM")
        tray_var = tk.BooleanVar(value=self.cfg.get("tray_menu", True))
        toast_var = tk.BooleanVar(value=self.cfg.get("toast", True))
        auto_var = tk.BooleanVar(value=self._autostart_enabled())
        mini_var = tk.BooleanVar(value=self.cfg.get("start_minimized", False))
        keys_var = tk.BooleanVar(value=self.cfg.get("hud_hotkeys", True))
        for var, label in (
            (tray_var, "Tray icon with quick menu"),
            (toast_var, "Toast popup when muting"),
            (auto_var, "Start with Windows"),
            (mini_var, "Start minimized (tray only)"),
            (keys_var, "HUD keys:  + / -  size,  S  shape"),
        ):
            r = nxt()
            ttk.Checkbutton(left, text=label, variable=var,
                            style="S.TCheckbutton").grid(row=r, column=0, columnspan=2,
                                                          sticky="w", pady=(2, 2))

        section("06 · AUTOMATION")
        smart_var = tk.BooleanVar(value=self.cfg.get("smart_mute", False))
        r = nxt()
        ttk.Checkbutton(left, text="Smart mute: muted unless a call app uses the mic",
                        variable=smart_var, style="S.TCheckbutton").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(2, 2))
        apps_var = tk.StringVar(value=self.cfg.get("smart_apps", ""))
        field_row("Call apps", ttk.Entry(left, textvariable=apps_var, width=24,
                                         style="S.TEntry"))
        voice_var = tk.BooleanVar(value=self.cfg.get("auto_unmute", False))
        r = nxt()
        ttk.Checkbutton(left, text="Auto-unmute when you start talking",
                        variable=voice_var, style="S.TCheckbutton").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(2, 2))
        thr_var = tk.DoubleVar(value=float(self.cfg.get("voice_threshold", 0.03)))
        field_row("Voice threshold", ttk.Spinbox(left, from_=0.01, to=0.5, increment=0.01,
                                                 textvariable=thr_var, width=6,
                                                 style="S.TSpinbox"))

        section("07 · PROFILES")
        prof_names = sorted((self.cfg.get("profiles") or {}).keys())
        prof_var = tk.StringVar(value=self.cfg.get("active_profile", "")
                                or (prof_names[0] if prof_names else ""))
        prof_box = ttk.Combobox(left, textvariable=prof_var, values=prof_names or [""],
                                state="readonly", style="S.TCombobox", width=20)
        field_row("Profile", prof_box)
        btn_row = tk.Frame(left, bg=BG)
        r = nxt()
        btn_row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 2))

        def save_profile_click():
            name = simpledialog.askstring("Save profile", "Profile name:", parent=w,
                                          initialvalue=prof_var.get() or "Gaming")
            if name and self.save_profile(name):
                prof_box.configure(values=sorted((self.cfg.get("profiles") or {}).keys()))
                prof_var.set(name)
                self._refresh_profile_menu()

        def delete_profile_click():
            if prof_var.get() and self.delete_profile(prof_var.get()):
                names = sorted((self.cfg.get("profiles") or {}).keys())
                prof_box.configure(values=names or [""])
                prof_var.set(names[0] if names else "")
                self._refresh_profile_menu()

        def apply_profile_click():
            if prof_var.get():
                self.apply_profile(prof_var.get())

        for text, cmd, primary in (("Apply", apply_profile_click, True),
                                   ("Save current as...", save_profile_click, False),
                                   ("Delete", delete_profile_click, False)):
            tk.Button(btn_row, text=text, command=cmd, relief="flat", bd=0,
                      bg=ACCENT if primary else FIELD, fg="#0b1219" if primary else TXT,
                      activebackground=ACCENT if primary else LINE,
                      activeforeground="#0b1219" if primary else TXT,
                      cursor="hand2", padx=12, pady=6,
                      font=("Segoe UI Semibold", 8), highlightthickness=0).pack(
                side="left", padx=(0, 6))

        # ---------------- footer ----------------
        r = nxt()
        tk.Frame(left, bg=LINE, height=1).grid(row=r, column=0, columnspan=2,
                                               sticky="ew", pady=(16, 12))

        def apply():
            try:
                self.cfg["mode"] = mode_var.get()
                self.cfg["hotkey"] = hk.get().strip().lower() or "t"
                self.cfg["hotkey_mode"] = "hold" if hmode.get() == "hold" else "toggle"
                self.cfg["strip"] = max(0, min(4, int(st.get())))
                self.cfg["opacity"] = round(float(op.get()), 2)
                if mode_var.get() == "windows" and device_var.get():
                    if device_var.get() in dev_ids:
                        self.cfg["device_id"] = dev_ids[device_var.get()]
            except (ValueError, TypeError):
                return
            self.cfg["topmost"] = bool(top.get())
            self.cfg["update_check"] = bool(upd.get())
            self.cfg["tray_menu"] = bool(tray_var.get())
            self.cfg["toast"] = bool(toast_var.get())
            self.cfg["start_minimized"] = bool(mini_var.get())
            self.cfg["hud_hotkeys"] = bool(keys_var.get())
            self.cfg["smart_mute"] = bool(smart_var.get())
            self.cfg["smart_apps"] = apps_var.get().strip()
            self.cfg["auto_unmute"] = bool(voice_var.get())
            try:
                self.cfg["voice_threshold"] = max(0.005, min(0.6, float(thr_var.get())))
            except (tk.TclError, ValueError):
                pass
            want_auto = bool(auto_var.get())
            if want_auto != self._autostart_enabled():
                self._set_autostart(want_auto)
            self.cfg["auto_start"] = want_auto
            if self.cfg["tray_menu"]:
                self._build_tray()
            else:
                self._stop_tray()
            self.cfg["wave_style"] = (WAVE_NAMES.index(wave_var.get())
                                      if wave_var.get() in WAVE_NAMES else 0)
            self.cfg["hud_shape"] = (shape_names.index(shape_var.get())
                                     if shape_var.get() in shape_names else 0)
            self.cfg["hud_size"] = {"Small": "small", "Medium": "medium",
                                    "Large": "large"}.get(size_var.get(), "medium")
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
            elif self.mode == "windows" and hasattr(self.audio, "set_device"):
                self.audio.set_device(self.cfg.get("device_id", ""))

            x, y = self.root.winfo_x(), self.root.winfo_y()
            self._set_dimensions()
            self.root.attributes("-alpha", self.cfg["opacity"])
            self.root.attributes("-topmost", self.cfg["topmost"])
            self.canvas.configure(width=self.W, height=self.H)
            self.canvas.delete("all")
            self.surface = ImgPainter(self.canvas, self.W, self.H, ss=SS_FACTOR)
            self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
            self.cfg["x"], self.cfg["y"] = x, y
            self.register_hotkey()
            save_config(self.cfg)
            self.draw()
            w.destroy()

        footer = tk.Frame(outer, bg=BG)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        apply_btn = tk.Button(footer, text="Apply design", command=apply, relief="flat",
                              bd=0, bg=ACCENT, fg="#0b1219", activebackground=ACCENT,
                              activeforeground="#0b1219", cursor="hand2", padx=18, pady=9,
                              font=("Segoe UI Semibold", 9), highlightthickness=0)
        apply_btn.pack(side="right")
        cancel_btn = tk.Button(footer, text="Cancel", command=w.destroy, relief="flat", bd=0,
                               bg=FIELD, fg=TXT, activebackground=LINE, activeforeground=TXT,
                               cursor="hand2", padx=18, pady=9,
                               font=("Segoe UI Semibold", 9), highlightthickness=0)
        cancel_btn.pack(side="right", padx=(0, 8))
        updates = tk.Label(footer, text="Check for updates", bg=BG, fg=SUB,
                           font=("Segoe UI", 8), cursor="hand2")
        updates.pack(side="left")
        updates.bind("<Button-1>", lambda e: self.check_for_updates())

        # keep the two columns visually balanced
        stage.configure(width=352, height=300)
        w.update_idletasks()
        max_h = min(880, max(560, self.root.winfo_screenheight() - 110))
        h = max(580, left.winfo_reqheight() + 150, right.winfo_reqheight() + 96)
        w.geometry(f"940x{min(int(h), max_h)}")
        w.update_idletasks()
        _sync_scroll()

        shape_box.bind("<<ComboboxSelected>>", draw_preview)
        wave_box.bind("<<ComboboxSelected>>", draw_preview)
        for var in (shape_var, size_var):
            var.trace_add("write", lambda *_: draw_preview())
        w.after(60, draw_preview)
        w.after(160, tick)

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
        self._stop_tray()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def _claim_single_instance():
    """A second copy would install a second global hotkey hook and fight the first."""
    _claim_single_instance.handle = None
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        handle = kernel32.CreateMutexW(None, True, "Local\\MicHUD-single-instance")
        if not handle:
            return True
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        _claim_single_instance.handle = handle
        return True
    except Exception:
        return True


def _already_running_notice():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.after(4500, root.destroy)
        messagebox.showinfo(APP_NAME,
                            "Mic Mute is already running." + "\n"
                            + "Use the HUD window or the tray icon of the open copy.")
        root.destroy()
    except Exception:
        pass


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
    if not _claim_single_instance():
        _already_running_notice()
        sys.exit(0)
    try:
        MicHUD().run()
    except Exception:
        _log_crash()