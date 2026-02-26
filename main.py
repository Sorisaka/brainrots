"""
Windows11向け SendInput 入力自動化スクリプト。

必要パッケージ:
  pip install pywin32

実行例:
  python main.py --title Roblox --match partial --duration-minutes 60
  python main.py --title "Roblox" --match exact
  python main.py --title Roblox --debug-fire-keys --debug-fire-click
"""

import argparse
import ctypes
import random
import time
from ctypes import wintypes

import win32con
import win32gui


# ===== Win32 / DPI =====
def set_dpi_aware() -> None:
    """DPI aware を設定（Per-monitor v2 を優先）。"""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


user32 = ctypes.WinDLL("user32", use_last_error=True)

# ===== SendInput 定数 =====
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)

# pairごとの仕様
PAIR_DIFF_LIMIT = 0.2
WS_MAX_HOLD = 2.0
AD_MAX_HOLD = 0.5
MIN_HOLD = 0.2


# ===== SendInput 構造体（サイズ整合が重要） =====
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


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
user32.GetSystemMetrics.restype = ctypes.c_int


def send_input(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))
    if sent != len(arr):
        err = ctypes.get_last_error()
        raise OSError(err, f"SendInput failed: sent={sent}/{len(arr)} sizeof(INPUT)={ctypes.sizeof(INPUT)}")


def vk_to_scancode(vk_code: int) -> int:
    sc = user32.MapVirtualKeyW(vk_code, 0)
    if sc == 0:
        raise RuntimeError(f"MapVirtualKeyW failed for vk={vk_code}")
    return int(sc)


def key_down_char(ch: str) -> None:
    vk = ord(ch.upper())
    sc = vk_to_scancode(vk)
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


def key_up_char(ch: str) -> None:
    vk = ord(ch.upper())
    sc = vk_to_scancode(vk)
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


# ===== マウス補助（クリック将来実装向け） =====
def get_client_size(hwnd: int) -> tuple[int, int]:
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    return right - left, bottom - top


def client_relative_to_screen(hwnd: int, rx: float, ry: float) -> tuple[int, int]:
    cw, ch = get_client_size(hwnd)
    cx = int(rx * cw)
    cy = int(ry * ch)
    sx, sy = win32gui.ClientToScreen(hwnd, (cx, cy))
    return sx, sy


def mouse_move_screen(x_screen: int, y_screen: int) -> None:
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    ax = int(x_screen * 65535 / max(1, screen_w - 1))
    ay = int(y_screen * 65535 / max(1, screen_h - 1))

    move = INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(
            mi=MOUSEINPUT(
                dx=ax,
                dy=ay,
                mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )
    send_input([move])


def smooth_move_screen(x0: int, y0: int, x1: int, y1: int, duration_sec: float, steps: int) -> None:
    steps = max(1, int(steps))
    dt = duration_sec / steps if steps > 0 else 0.0
    for i in range(1, steps + 1):
        t = i / steps
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        mouse_move_screen(x, y)
        if dt > 0:
            time.sleep(dt)


def move_cursor_via_center(hwnd: int, rx: float, ry: float, duration_sec: float, steps: int) -> None:
    """中心へ配置後、中心→目標へ分割移動。"""
    cx_s, cy_s = client_relative_to_screen(hwnd, 0.5, 0.5)
    tx_s, ty_s = client_relative_to_screen(hwnd, rx, ry)
    mouse_move_screen(cx_s, cy_s)
    time.sleep(0.02)
    smooth_move_screen(cx_s, cy_s, tx_s, ty_s, duration_sec=duration_sec, steps=steps)


def mouse_click_only() -> None:
    """左クリック down/up のみ（移動なし）。"""
    down = INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(
            mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=0)
        ),
    )
    up = INPUT(
        type=INPUT_MOUSE,
        union=INPUT_UNION(
            mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=0)
        ),
    )
    send_input([down, up])


def perform_click_action(hwnd: int) -> None:
    """将来のクリック処理フック。

    TODO:
      1) 対象座標(相対)を決定
      2) move_cursor_via_center(hwnd, rx, ry, duration_sec, steps)
      3) mouse_click_only()
    """
    _ = hwnd
    mouse_click_only()


# ===== ウィンドウ関連 =====
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


def find_window_by_title_partial(title_part: str):
    found = []
    needle = title_part.lower()

    def enum_proc(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if needle in title.lower():
            found.append(hwnd)

    win32gui.EnumWindows(enum_proc, None)
    return found[0] if found else None


def activate_window(hwnd: int) -> None:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        print(f"[WARN] failed to foreground window: {exc}")


# ===== キーイベント =====
def release_all_wasd() -> None:
    for ch in "wasd":
        try:
            key_up_char(ch)
        except Exception:
            pass


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def distribute_pair_duration(pair_total: float, cap_each: float, debt: float) -> tuple[float, float, float]:
    """pair_total を2キーへ分配し、差分(debt)も更新する。返り値: (left, right, new_debt)。"""
    if pair_total <= 0:
        return 0.0, 0.0, debt

    # 目標差分は debt 回収方向（反対符号）へ寄せる。
    target_diff = clamp(-debt, -PAIR_DIFF_LIMIT, PAIR_DIFF_LIMIT)

    # 実現可能な差分範囲（cap・非負条件）
    min_diff = max(-PAIR_DIFF_LIMIT, pair_total - 2.0 * cap_each, -pair_total)
    max_diff = min(PAIR_DIFF_LIMIT, 2.0 * cap_each - pair_total, pair_total)
    if min_diff > max_diff:
        mid = (min_diff + max_diff) / 2.0
        min_diff = mid
        max_diff = mid

    diff = clamp(target_diff, min_diff, max_diff)
    left = (pair_total + diff) / 2.0
    right = (pair_total - diff) / 2.0

    # 最短0.2秒制限との衝突は「可能なら補正、不可能なら許容」にする。
    if 0 < left < MIN_HOLD and right >= MIN_HOLD:
        move = min(MIN_HOLD - left, right - MIN_HOLD)
        if move > 0:
            left += move
            right -= move
    if 0 < right < MIN_HOLD and left >= MIN_HOLD:
        move = min(MIN_HOLD - right, left - MIN_HOLD)
        if move > 0:
            right += move
            left -= move

    left = clamp(left, 0.0, cap_each)
    right = clamp(right, 0.0, cap_each)
    new_debt = debt + (left - right)
    return left, right, new_debt


def build_event_durations(pair_debts: dict[str, float]) -> tuple[float, dict[str, float]]:
    total_event = clamp(random.gauss(3.0, 1.0), 0.2, 5.0)

    # 合計時間を ws と ad にランダム配分（各pairの上限を守る）
    ws_max_total = 2.0 * WS_MAX_HOLD
    ad_max_total = 2.0 * AD_MAX_HOLD

    ws_total_min = max(0.0, total_event - ad_max_total)
    ws_total_max = min(ws_max_total, total_event)
    ws_total = random.uniform(ws_total_min, ws_total_max)
    ad_total = total_event - ws_total

    w_t, s_t, pair_debts["ws"] = distribute_pair_duration(ws_total, WS_MAX_HOLD, pair_debts["ws"])
    a_t, d_t, pair_debts["ad"] = distribute_pair_duration(ad_total, AD_MAX_HOLD, pair_debts["ad"])

    durations = {"w": w_t, "s": s_t, "a": a_t, "d": d_t}
    return total_event, durations


def emit_key_hold(ch: str, duration: float) -> None:
    if duration <= 0:
        return
    if duration < MIN_HOLD:
        print(f"  [SUB] key={ch.upper()} hold={duration:.3f}s (min-hold conflict accepted)")
    else:
        print(f"  [SUB] key={ch.upper()} hold={duration:.3f}s")

    key_down_char(ch)
    try:
        time.sleep(duration)
    finally:
        key_up_char(ch)


def random_key_event(pair_debts: dict[str, float]) -> None:
    total_event, durations = build_event_durations(pair_debts)
    ws_diff = abs(durations["w"] - durations["s"])
    ad_diff = abs(durations["a"] - durations["d"])

    print(
        "[EVENT] total={:.3f}s ws_diff={:.3f}s ad_diff={:.3f}s debts(ws={:.3f}, ad={:.3f})".format(
            total_event,
            ws_diff,
            ad_diff,
            pair_debts["ws"],
            pair_debts["ad"],
        )
    )

    # キー種類の上限は設けず、4キー全部を使ってよい。
    for ch in random.sample(["w", "s", "a", "d"], 4):
        emit_key_hold(ch, durations[ch])


def run_loop(hwnd: int, duration_minutes: float | None) -> None:
    pair_debts = {"ws": 0.0, "ad": 0.0}
    loop_start = time.monotonic()
    hard_limit = loop_start + (duration_minutes * 60.0) if duration_minutes is not None else None

    while True:
        now = time.monotonic()
        if hard_limit is not None and now >= hard_limit:
            print("[INFO] duration-minutes reached. exiting.")
            return

        interval_sec = max(1.0, random.gauss(15 * 60, 4 * 60))

        if hard_limit is not None:
            remain_global = hard_limit - now
            if remain_global <= 0:
                print("[INFO] duration-minutes reached. exiting.")
                return
            interval_sec = min(interval_sec, remain_global)

        print(f"[WAIT] next event in {interval_sec:.3f}s")

        sleep_left = interval_sec
        while sleep_left > 0:
            chunk = min(0.5, sleep_left)
            time.sleep(chunk)
            sleep_left -= chunk
            if hard_limit is not None and time.monotonic() >= hard_limit:
                print("[INFO] duration-minutes reached during wait. exiting.")
                return

        activate_window(hwnd)
        random_key_event(pair_debts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SendInput-based WASD random hold automation")
    parser.add_argument("--title", default="Roblox", help="target window title")
    parser.add_argument("--match", choices=["exact", "partial"], default="exact", help="title matching mode")
    parser.add_argument("--duration-minutes", type=float, default=None, help="auto stop after N minutes")
    parser.add_argument(
        "--debug-fire-keys",
        action="store_true",
        help="fire one randomized WASD event immediately at startup (for debug)",
    )
    parser.add_argument(
        "--debug-fire-click",
        action="store_true",
        help="fire click action immediately at startup (for debug)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_dpi_aware()

    hwnd = find_window_by_title_exact(args.title) if args.match == "exact" else find_window_by_title_partial(args.title)
    if not hwnd:
        raise RuntimeError(f"window not found: title={args.title!r} match={args.match}")

    title = win32gui.GetWindowText(hwnd)
    print(f"[OK] target hwnd={hwnd} title={title!r}")
    print(f"[OK] sizeof(INPUT)={ctypes.sizeof(INPUT)}")

    try:
        if args.debug_fire_keys or args.debug_fire_click:
            activate_window(hwnd)
        if args.debug_fire_keys:
            print("[DEBUG] fire randomized key event now")
            random_key_event({"ws": 0.0, "ad": 0.0})
        if args.debug_fire_click:
            print("[DEBUG] fire click action now")
            perform_click_action(hwnd)

        run_loop(hwnd, args.duration_minutes)
    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received. stopping safely.")
    finally:
        release_all_wasd()
        print("[INFO] all WASD released. bye.")


if __name__ == "__main__":
    main()
