import time
import argparse
import ctypes
from ctypes import wintypes

import win32gui
import win32con


# ===== 設定 =====
TARGET_TITLE = "Roblox"  # 完全一致

# 既存クリック点（通常モードで使う）
CLICK_POINTS = [
    (0.855241, 0.938957),
]

# マウス移動速さ・滑らかさ
MOVE_DURATION_SEC = 0.35
MOVE_STEPS = 80

DOT_RADIUS_PX = 8
SHOW_SECONDS_AFTER_CLICK = 2.0

# キャリブレーション時の暗幕透明度（0-255）。小さいほど透明。
CALIBRATE_OVERLAY_ALPHA = 140

# キャプチャ/終了キー（ゲーム側割当回避）
CAPTURE_KEY_VK = win32con.VK_F1
EXIT_KEY_VK = win32con.VK_F2
# =================


# ===== 互換: ULONG_PTR が無い環境向け =====
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)


# ===== DPI aware =====
def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # Per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ===== SendInput(マウス) =====
user32 = ctypes.windll.user32
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]

def send_input(inputs):
    arr = (INPUT * len(inputs))(*inputs)
    n = user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))
    if n != len(arr):
        raise ctypes.WinError(ctypes.get_last_error())
    
def mouse_move_screen(x_screen: int, y_screen: int):
    """画面座標へカーソル移動（クリックなし）"""
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    ax = int(x_screen * 65535 / max(1, screen_w - 1))
    ay = int(y_screen * 65535 / max(1, screen_h - 1))

    move = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(
        mi=MOUSEINPUT(dx=ax, dy=ay, mouseData=0,
                      dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                      time=0, dwExtraInfo=0)
    ))
    send_input([move])


def smooth_move_screen(x0: int, y0: int, x1: int, y1: int, duration_sec: float = 0.30, steps: int = 60):
    """(x0,y0)->(x1,y1) を分割して連続移動"""
    steps = max(1, int(steps))
    dt = duration_sec / steps if steps > 0 else 0.0
    for i in range(1, steps + 1):
        t = i / steps
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        mouse_move_screen(x, y)
        if dt > 0:
            time.sleep(dt)


def move_cursor_via_center(hwnd, rx: float, ry: float, duration_sec: float = 0.30, steps: int = 60):
    """中心へ配置→中心から目標(rx,ry)へスムーズ移動"""
    cx_s, cy_s = client_relative_to_screen(hwnd, 0.5, 0.5)
    tx_s, ty_s = client_relative_to_screen(hwnd, rx, ry)

    mouse_move_screen(cx_s, cy_s)
    time.sleep(0.02)  # 安定化のための短い待ち

    smooth_move_screen(cx_s, cy_s, tx_s, ty_s, duration_sec=duration_sec, steps=steps)

def mouse_click_screen():
    """左クリック入力のみ（カーソル移動はしない）"""
    down = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(
        mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=0)
    ))
    up = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(
        mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=0)
    ))
    send_input([down, up])


# ===== ウィンドウ探索/座標変換 =====
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

def get_client_size(hwnd):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    return (right - left, bottom - top)

def client_relative_to_screen(hwnd, rx: float, ry: float):
    cw, ch = get_client_size(hwnd)
    cx = int(rx * cw)
    cy = int(ry * ch)
    sx, sy = win32gui.ClientToScreen(hwnd, (cx, cy))
    return sx, sy

def get_client_screen_rect(hwnd):
    cw, ch = get_client_size(hwnd)
    tl = win32gui.ClientToScreen(hwnd, (0, 0))
    br = win32gui.ClientToScreen(hwnd, (cw, ch))
    return (tl[0], tl[1], br[0], br[1])

def screen_to_client_relative(hwnd, sx: int, sy: int):
    cx, cy = win32gui.ScreenToClient(hwnd, (sx, sy))
    cw, ch = get_client_size(hwnd)
    if cw <= 0 or ch <= 0:
        raise RuntimeError("Invalid client size")
    rx = cx / cw
    ry = cy / ch
    return cx, cy, rx, ry

def activate_window(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ===== オーバーレイ（transparent / dim）=====
class Overlay:
    CLASS_NAME = "ClickTestOverlay"
    TRANSPARENT_COLORREF = 0x00FF00  # colorkey用（緑）

    def __init__(self, rect, points_screen, mode: str = "transparent", alpha: int = 180):
        self.rect = rect
        self.points = points_screen
        self.mode = mode
        self.alpha = max(0, min(255, int(alpha)))
        self.hwnd = None
        self._register_class()
        self._create_window()

    def _register_class(self):
        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = win32gui.GetModuleHandle(None)
        wndclass.lpszClassName = self.CLASS_NAME
        wndclass.lpfnWndProc = self._wndproc
        wndclass.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        try:
            win32gui.RegisterClass(wndclass)
        except win32gui.error:
            pass

    def _create_window(self):
        L, T, R, B = self.rect
        w = R - L
        h = B - T

        ex_style = (win32con.WS_EX_LAYERED |
                    win32con.WS_EX_TOPMOST |
                    win32con.WS_EX_TRANSPARENT |
                    win32con.WS_EX_TOOLWINDOW)
        style = win32con.WS_POPUP

        self.hwnd = win32gui.CreateWindowEx(
            ex_style, self.CLASS_NAME, "", style,
            L, T, w, h,
            0, 0, win32gui.GetModuleHandle(None), None
        )

        if self.mode == "transparent":
            win32gui.SetLayeredWindowAttributes(
                self.hwnd,
                self.TRANSPARENT_COLORREF,
                255,
                win32con.LWA_COLORKEY
            )
        elif self.mode == "dim":
            win32gui.SetLayeredWindowAttributes(
                self.hwnd,
                0,
                self.alpha,
                win32con.LWA_ALPHA
            )
        else:
            raise ValueError(f"Unknown overlay mode: {self.mode}")

        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.UpdateWindow(self.hwnd)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_PAINT:
            hdc, ps = win32gui.BeginPaint(hwnd)
            try:
                L, T, R, B = self.rect
                w = R - L
                h = B - T

                # 背景
                if self.mode == "transparent":
                    brush = win32gui.CreateSolidBrush(self.TRANSPARENT_COLORREF)
                else:
                    brush = win32gui.CreateSolidBrush(0x000000)  # 黒
                win32gui.FillRect(hdc, (0, 0, w, h), brush)
                win32gui.DeleteObject(brush)

                # 点
                pen = win32gui.CreatePen(win32con.PS_SOLID, 2, 0x0000FF)
                null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
                old_pen = win32gui.SelectObject(hdc, pen)
                old_brush = win32gui.SelectObject(hdc, null_brush)

                Ls, Ts, _, _ = self.rect
                r = DOT_RADIUS_PX
                for (sx, sy) in self.points:
                    x = sx - Ls
                    y = sy - Ts
                    win32gui.Ellipse(hdc, x - r, y - r, x + r, y + r)

                win32gui.SelectObject(hdc, old_pen)
                win32gui.SelectObject(hdc, old_brush)
                win32gui.DeleteObject(pen)

            finally:
                win32gui.EndPaint(hwnd, ps)
            return 0

        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def redraw(self):
        win32gui.InvalidateRect(self.hwnd, None, True)
        win32gui.UpdateWindow(self.hwnd)

    def close(self):
        if self.hwnd:
            try:
                win32gui.DestroyWindow(self.hwnd)
            except Exception:
                pass
            self.hwnd = None


def pump_messages():
    win32gui.PumpWaitingMessages()

def key_edge_pressed(vk: int, prev_down: bool):
    down = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
    return down, (down and not prev_down)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-click", action="store_true", help="描画のみ（自動クリックしない）")
    ap.add_argument("--calibrate", action="store_true",
                    help=f"位置合わせモード（暗幕 alpha={CALIBRATE_OVERLAY_ALPHA}, F1=取得, F2=終了）")
    args = ap.parse_args()

    set_dpi_aware()

    hwnd = find_window_by_title_exact(TARGET_TITLE)
    if not hwnd:
        raise RuntimeError(f'Window not found. TARGET_TITLE="{TARGET_TITLE}"')

    print("[OK] target:", win32gui.GetWindowText(hwnd))
    activate_window(hwnd)
    time.sleep(0.2)

    client_rect = get_client_screen_rect(hwnd)
    points_screen = [client_relative_to_screen(hwnd, rx, ry) for (rx, ry) in CLICK_POINTS]

    # --- オーバーレイ設定の統合 ---
    # calibrate のときは dim + alpha=CALIBRATE_OVERLAY_ALPHA に固定
    if args.calibrate:
        overlay_mode = "dim"
        overlay_alpha = CALIBRATE_OVERLAY_ALPHA
    else:
        overlay_mode = "transparent"
        overlay_alpha = 255  # transparentでは未使用

    ov = Overlay(client_rect, points_screen, mode=overlay_mode, alpha=overlay_alpha)
    ov.redraw()

    # --- 動作モード ---
    # calibrate: 取得ループ（自動クリックはしない）
    if args.calibrate:
        print()
        print("=== CALIBRATE MODE ===")
        print("F1 : 現在のマウス位置を (client_x, client_y, rx, ry) として出力")
        print("F2 : 終了")
        print(f"(overlay: dim, alpha={CALIBRATE_OVERLAY_ALPHA})")
        print()

        prev_f1 = False
        prev_f2 = False
        while True:
            pump_messages()

            prev_f2, f2_edge = key_edge_pressed(EXIT_KEY_VK, prev_f2)
            if f2_edge:
                break

            prev_f1, f1_edge = key_edge_pressed(CAPTURE_KEY_VK, prev_f1)
            if f1_edge:
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                sx, sy = int(pt.x), int(pt.y)

                cx, cy, rx, ry = screen_to_client_relative(hwnd, sx, sy)
                in_client = (0.0 <= rx <= 1.0) and (0.0 <= ry <= 1.0)

                print()
                print(f"[CAPTURE] screen=({sx},{sy}) client=({cx},{cy}) rel=({rx:.6f},{ry:.6f}) in_client={in_client}")
                print("  -> COPY: (%.6f, %.6f)" % (rx, ry))
                print()

            time.sleep(0.01)

        ov.close()
        print("bye")
        return

    # no-click: 描画のみ（自動クリックしない）
    if args.no_click:
        print()
        print("=== NO-CLICK MODE ===")
        print("点を表示するだけです。終了は F2。")
        print()
        prev_f2 = False
        while True:
            pump_messages()
            prev_f2, f2_edge = key_edge_pressed(EXIT_KEY_VK, prev_f2)
            if f2_edge:
                break
            time.sleep(0.01)

        ov.close()
        print("bye")
        return

    # 通常: 1秒後にクリック（従来）
    print("1秒後に CLICK_POINTS[0] を左クリックします...")
    t0 = time.time()
    while time.time() - t0 < 1.0:
        pump_messages()
        time.sleep(0.01)

    rx, ry = CLICK_POINTS[0]

    # 中心へ配置 → 目標へ連続移動
    move_cursor_via_center(hwnd, rx, ry, duration_sec=MOVE_DURATION_SEC, steps=MOVE_STEPS)

    # 左クリック（移動はしない）
    mouse_click_screen()
    print("moved + clicked")

    t1 = time.time()
    while time.time() - t1 < SHOW_SECONDS_AFTER_CLICK:
        pump_messages()
        time.sleep(0.01)

    ov.close()
    print("done")


if __name__ == "__main__":
    main()
