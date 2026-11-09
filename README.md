# Device Battery Tray · 裝置電量

LOFREE 小順青春版(100鍵)、HECATE G3M PRO 與 HECATE G3M PRO 升級版的系統匣電量工具。

## 功能

- 三個裝置各自使用獨立的鍵盤／滑鼠圖示。
- 系統匣只顯示已插入的裝置或接收器；原有型號拔除後隱藏卡片，手動新增的卡片保留狀態。
- 電量超過 70% 為綠色；30～70% 為橘色；低於 30% 為紅色。
- 游標懸浮顯示自訂名稱、電量與 USB／2.4 GHz 接收器連線方式。
- 卡片式總覽，支援深色與淺色模式。
- 每個裝置可個別改名，重新啟動後保留。
- 30 秒刷新、手動刷新、登入自動啟動。

## 版本狀態

| 平台 | 狀態 |
|---|---|
| Windows | 已在作者電腦實測三個裝置，使用本機已安裝的原廠 DLL。 |
| Kubuntu / KDE | 已由作者於 Kubuntu 26.04 確認可正常讀取電量。修正 Linux HID 後端選擇及更新安裝問題。 |

接收器仍插入但無線裝置休眠、權限不足或電量讀取失敗時，保留灰色圖示並顯示狀態。裝置是否插入與電量讀值分開處理，讓後續新增支援型號時可沿用顯示邏輯。自動偵測最多等待 30 秒，也可立即手動刷新；原廠協定支援下列三個型號；Kubuntu 另可透過「新增裝置」搜尋並加入系統電量、藍牙與 HID 設備；無通用電量資訊的型號會顯示狀態。

Kubuntu 可讀取 BlueZ／UPower 已提供的藍牙電量；同 VID／PID 多台的協定查詢分別綁定尚未支援。

## Windows

Windows 原始碼位於 [windows](windows)。在 PowerShell 編譯：

```powershell
& .\windows\build.ps1
```

執行產生的 `windows/DeviceBatteryTray.exe`。如需沿用原廠 DLL 讀取流程，請保留原廠安裝目錄 `C:\Program Files\HECATE` 與 `C:\Program Files\Lofree Key Mapper\Sys64`；程式不包含原廠 DLL，也不會安裝核心驅動。

詳細操作與通訊分析見 [Windows 使用說明](windows/使用說明.md)。

## Kubuntu

請先閱讀 [Kubuntu 安裝與診斷說明](kubuntu/README.md)。[最新 release](https://github.com/OmOstarter/device-battery-tray/releases/latest) 提供 `.deb`、Kubuntu 原始碼安裝包與 Windows 程式。

Kubuntu 26.04 可下載 `.deb`，執行 `sudo apt install ./device-battery-tray_0.1.1_all.deb`。若從腳本安裝切換，先結束程式並用舊版 `kubuntu/uninstall.sh` 移除舊的選單及啟動項目，再安裝 `.deb`；設定會保留。其他版本可使用原始碼安裝：

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

目前 42 項 Python／Qt 測試通過，包含拔除隱藏、接收器無電量仍保留圖示、Linux 後端選擇及存取錯誤診斷。Kubuntu 電量讀取已由作者實測確認；新 `.deb` 安裝流程仍待桌面實測。

## 待處理

見 [TODO.md](TODO.md)。

## 原始碼與授權

此儲存庫僅包含本專案原始碼、文件、測試與腳本；不包含原廠 DLL、使用者名稱設定、硬體狀態紀錄或相依套件安裝環境。

尚未指定開源授權。公開可閱讀原始碼不代表授予任意使用、修改或再散布的授權；專案擁有者可另行決定授權方式。

## v0.1.1 裝置管理

Kubuntu 與 Windows 都提供新增／刪除監測項目、編輯協定代碼、簡易表單、本地 agent 提示詞，以及 USB 拔插辨認。USB 拔插視窗顯示實體設備與 VID／PID，可複製識別資料；辨認成功不代表能直接讀取電量。新增協定代碼只接受已實作且相容的協定，未知協定需先分析並新增後端。

Kubuntu 可透過系統電池目錄、UPower 與 BlueZ 取得系統已提供的電量。Windows 的新增設備使用內建 SetupAPI／HID 與 WMI 列出 USB 設備、追蹤拔插及執行已知協定，不需要額外 Python；本版未提供 Windows 通用藍牙電量讀取。既有 Windows 原廠 DLL 路徑仍保留，缺少 DLL 時會改用內建 HID 後端。
