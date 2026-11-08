# Device Battery Tray · 裝置電量

LOFREE 小順青春版(100鍵)、HECATE G3M PRO 與 HECATE G3M PRO 升級版的系統匣電量工具。

## 功能

- 三個裝置各自使用獨立的鍵盤／滑鼠圖示。
- 只有已插入的裝置或接收器才出現在系統匣與總覽；拔除後於下次更新隱藏。
- 電量超過 70% 為綠色；30～70% 為橘色；低於 30% 為紅色。
- 游標懸浮顯示自訂名稱、電量與 USB／2.4 GHz 接收器連線方式。
- 卡片式總覽，支援深色與淺色模式。
- 每個裝置可個別改名，重新啟動後保留。
- 30 秒更新、手動更新、登入自動啟動。

## 版本狀態

| 平台 | 狀態 |
|---|---|
| Windows | 已在作者電腦實測三個裝置，使用本機已安裝的原廠 DLL。 |
| Kubuntu / KDE | 實驗版本。跨平台 Qt 介面與協定測試通過，但使用者回報安裝後無法讀取電量；Linux 實機問題尚待修正。 |

接收器仍插入但無線裝置休眠、權限不足或電量讀取失敗時，保留灰色圖示並顯示狀態。裝置是否插入與電量讀值分開處理，讓後續新增支援型號時可沿用顯示邏輯。自動偵測最多等待 30 秒，也可立即手動更新；目前仍僅支援下列三個型號。

藍牙與同型號多台裝置目前尚未支援。

## Windows

完整原始碼位於 [windows/DeviceBatteryTray.cs](windows/DeviceBatteryTray.cs)。在 PowerShell 編譯：

```powershell
& .\windows\build.ps1
```

執行產生的 `windows/DeviceBatteryTray.exe`。需保留原廠安裝目錄 `C:\Program Files\HECATE` 與 `C:\Program Files\Lofree Key Mapper\Sys64`；程式不包含原廠 DLL，也不會安裝核心驅動。

詳細操作與通訊分析見 [Windows 使用說明](windows/使用說明.md)。

## Kubuntu

請先閱讀 [Kubuntu 安裝與診斷說明](kubuntu/README.md)。目前作為測試版提供，尚不能保證在 Kubuntu 上正常讀取電量。

```bash
cd kubuntu
bash install.sh
```

Python 原始碼直接透過 HID 電量查詢封包通訊，不依賴 Windows DLL。Windows 主機上的直接查詢曾成功讀取三個裝置，但不等同 Linux 實機驗證。

## 測試

Windows 原始碼附有 `--self-test` 與 `--diagnose`；Kubuntu 包含協定／設定／Qt GUI 測試：

```bash
cd kubuntu
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

目前 11 項 Python／Qt 測試已在 Windows 主機上通過，包含拔除隱藏與接收器無電量仍保留圖示的測試。測試不取代 Kubuntu 實機驗證。

## 待處理

見 [TODO.md](TODO.md)。

## 原始碼與授權

此儲存庫僅包含本專案原始碼、文件、測試與腳本；不包含原廠 DLL、使用者名稱設定、硬體狀態紀錄或相依套件安裝環境。

尚未指定開源授權。公開可閱讀原始碼不代表授予任意使用、修改或再散布的授權；專案擁有者可另行決定授權方式。
