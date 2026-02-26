# brainrots / Windows11 SendInput 自動化スクリプト

このリポジトリは、`main.py` 1ファイルで動く **Windows11向け入力自動化ツール**です。
対象ウィンドウ（例: Roblox）に対して、`SendInput` ベースのキーボード/マウス入力を送ります。

## できること

- DPI aware（Per-monitor v2優先）で動作。
- `ctypes.WinDLL("user32", use_last_error=True)` と `INPUT` 構造体を明示定義し、サイズ不整合を回避。
- キー入力を scancode (`MapVirtualKeyW`) で送信。
- 常駐ループで一定周期（15分±4分）にキーイベントを発火。
- キーイベントは合計時間 `3秒±1秒`（正規分布、クリップ）で実施。
  - `main.py` 冒頭の `EVENT_TOTAL_*` 定数を変更するだけで調整可能。
- `W/S` と `A/D` をペア管理し、
  - ペア内差分を 0.2秒以内に維持
  - 前回までの差分（debt）を次回で回収
  - `W/S` の各キー上限 2.0秒、`A/D` の各キー上限 0.5秒
- クリック処理の拡張フック（座標計算や分割移動は TODO）を用意。
- デバッグ用に起動直後のキー発火 / クリック発火オプションあり。

---

## 動作環境

- OS: **Windows 11**（Windows API利用のため必須）
- Python: 3.10+ 推奨
- 依存:

```bash
pip install pywin32
```

---

## 実行方法

### 1) 基本実行（完全一致）

```bash
python main.py --title "Roblox" --match exact
```

### 2) 部分一致で実行

```bash
python main.py --title "Roblox" --match partial
```

### 3) 60分で自動停止

```bash
python main.py --title "Roblox" --duration-minutes 60
```

### 4) デバッグ: 起動直後にキーイベントを1回発火

```bash
python main.py --title "Roblox" --debug-fire-keys
```

### 5) デバッグ: 起動直後にクリックを1回発火

```bash
python main.py --title "Roblox" --debug-fire-click
```

### 6) 両方デバッグ

```bash
python main.py --title "Roblox" --debug-fire-keys --debug-fire-click
```

### 7) 差分回収テスト（待機を1秒固定で連続実行）

```bash
python main.py --title "Roblox" --debug-fast-interval
```

---

## CLIオプション

- `--title <str>`: 対象ウィンドウタイトル（既定: `Roblox`）
- `--match exact|partial`: タイトル一致方式（既定: `exact`）
- `--duration-minutes <float>`: N分で終了（未指定なら無限）
- `--debug-fire-keys`: 起動時にキーイベントを即時1回実行
- `--debug-fire-click`: 起動時にクリックアクションを即時1回実行
- `--debug-fast-interval`: 待機を常に1秒に固定（差分回収テスト向け）

---

## ログの見方

主に以下を出力します。

- `[WAIT]`: 次イベントまでの待機秒数
- `[EVENT]`: 今回イベント合計時間、ペア差分、debt状態
- `[SUB]`: 各キーの押下時間
- `[WARN]`: 前面化失敗など（処理は継続）

---

## 安全停止

- `Ctrl + C` (`KeyboardInterrupt`) で停止可能。
- 停止時は `finally` で `W/A/S/D` 全キーを `keyup` して終了するため、押しっぱなし残りを防ぎます。

---

## クリック機能について（現状）

`perform_click_action(hwnd)` が将来拡張ポイントです。
現時点では `mouse_click_only()` を呼ぶだけで、
位置計算・カーソル分割移動は TODO のままです。

既に以下の補助関数が定義済みです。

- `client_relative_to_screen(hwnd, rx, ry)`
- `move_cursor_via_center(hwnd, rx, ry, duration_sec, steps)`
- `mouse_click_only()`

---

## 注意事項

- このツールは Windows API で入力を送るため、利用先アプリや規約に従って使用してください。
- ゲーム/サービスの利用規約違反となる使い方は避けてください。
