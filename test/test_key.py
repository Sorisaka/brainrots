import time
import ctypes
from ctypes import wintypes

import win32gui
import win32con

# ===== 設定 =====
TARGET_TITLE = "Roblox"  # 完全一致
# ==============

def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # Per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# use_last_error=True が重要
user32 = ctypes.WinDLL("user32", use_last_error=True)

# --- WinAPI 定数 ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# ctypes.wintypes に無い環境があるので安全に定義
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)

# --- 構造体（これがサイズ一致の肝）---
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]

# SendInput / MapVirtualKey のシグネチャ
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT

def send_input(inputs):
    arr = (INPUT * len(inputs))(*inputs)
    n = user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))
    if n != len(arr):
        err = ctypes.get_last_error()
        raise OSError(err, f"SendInput failed: sent={n}/{len(arr)} sizeof(INPUT)={ctypes.sizeof(INPUT)}")

def key_down_char(ch: str):
    vk = ord(ch.upper())
    sc = user32.MapVirtualKeyW(vk, 0)
    inp = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUT_UNION(
            ki=KEYBDINPUT(
                wVk=0,
                wScan=sc,
                dwFlags=KEYEVENTF_SCANCODE,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    send_input([inp])

def key_up_char(ch: str):
    vk = ord(ch.upper())
    sc = user32.MapVirtualKeyW(vk, 0)
    inp = INPUT(
        type=INPUT_KEYBOARD,
        union=INPUT_UNION(
            ki=KEYBDINPUT(
                wVk=0,
                wScan=sc,
                dwFlags=KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    send_input([inp])

def find_window_by_title_exact(title_exact: str):
    found = []

    def enum_proc(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if title == title_exact:
            found.append(hwnd)

    win32gui.EnumWindows(enum_proc, None)
    return found[0] if found else None

def activate_window(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass

def main():
    set_dpi_aware()

    hwnd = find_window_by_title_exact(TARGET_TITLE)
    if not hwnd:
        raise RuntimeError(f'Window not found (exact match). TARGET_TITLE="{TARGET_TITLE}"')

    print("[OK] target:", win32gui.GetWindowText(hwnd))
    print("sizeof(INPUT) =", ctypes.sizeof(INPUT), "(64bitなら通常40が期待値)")
    print("3秒後にWASDテスト開始 ...")

    activate_window(hwnd)
    time.sleep(3.0)

    for ch in ["w", "a", "s", "d"]:
        print(f"Hold {ch.upper()} for 1s")
        key_down_char(ch)
        time.sleep(1.0)
        key_up_char(ch)
        time.sleep(0.2)

    print("done")

if __name__ == "__main__":
    main()