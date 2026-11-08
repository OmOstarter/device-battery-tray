# 裝置電量 · Kubuntu / KDE Plasma 版本

可安裝的 Python + Qt 版本，保留 Windows 版的操作：三個獨立系統匣圖示、鍵盤／滑鼠圖案、電量變色、懸浮名稱與百分比、深淺色卡片總覽、每個裝置個別改名、登入自動啟動、30 秒輪詢、離線灰色圖示。

**驗證狀態：2026-11-08 作者已確認修正版可在 Kubuntu 正常使用。** Linux 後端選擇與唯讀虛擬環境更新問題已修正；新 `.deb` 的桌面安裝仍待實測。Windows 版不會被替換。

## 安裝

### Kubuntu 26.04：使用 .deb

從 [最新 release](https://github.com/OmOstarter/device-battery-tray/releases/latest) 下載 `device-battery-tray_0.1.0_all.deb`，在下載目錄執行：

```bash
sudo apt install ./device-battery-tray_0.1.0_all.deb
```

apt 會安裝系統 Python、PySide6 與 HID 依賴（需要 universe 套件來源），不使用 pip 或 venv。安裝後重新插拔接收器，從選單開啟「裝置電量」；亦可執行 `device-battery-tray --diagnose`。此 `.deb` 以 Kubuntu 26.04 為支援目標，不適用於缺少 PySide6 系統套件的 Kubuntu 24.04。

若先前使用下方腳本安裝，請先結束程式並執行舊版 `bash uninstall.sh`，再安裝 `.deb`，避免舊的使用者選單項目覆蓋系統版本。設定會保留，登入啟動可重新勾選。`.deb` 使用 `sudo apt remove device-battery-tray` 移除；移除前先在程式內取消登入自動啟動並結束程式。

### 原始碼安裝

需要一般 Kubuntu 圖形桌面、Python 3.10 以上與網路下載相依套件。預期使用 Kubuntu 24.04 或較新版本；其他版本尚未實測。

解壓縮後，在本目錄開啟終端機執行：

```bash
sudo apt update
sudo apt install python3-venv libxcb-cursor0 libxkbcommon-x11-0 libegl1 libgl1
bash install.sh
```

**不要使用 `sudo bash install.sh`，也不需要用 root 執行應用程式。** 安裝腳本以一般使用者建立獨立虛擬環境，只在安裝裝置權限規則時使用 sudo。相依套件取自 PyPI。

安裝後重新插拔鍵盤／接收器，在 KDE 應用程式選單搜尋 **裝置電量**。程式不會安裝或啟動 Windows 原廠驅動。

預設安裝到 `~/.local/share/device-battery-tray`，名稱與主題設定放在 `~/.config/device-battery-tray/preferences.json`；遵循 `XDG_DATA_HOME` 與 `XDG_CONFIG_HOME`。重新安裝會保留設定。

若裝置權限已由管理者配置，可用 `bash install.sh --no-udev` 跳過 udev 安裝。規則只比對下方五組 VID/PID，使用 active-seat `uaccess`，不給所有人存取所有 HID 裝置的權限。

## 使用

- 每個已插入的型號各有一個系統匣圖示；拔除裝置或接收器後，於下次更新隱藏圖示與卡片。接收器仍插著但無法讀取電量時，保留灰色圖示。KDE 若將圖示放入隱藏項目，可在系統匣設定將它設為一直顯示。
- 大於 70% 綠色；30～70% 橘色；低於 30% 紅色。讀不到時灰色，絕不冒用之前的電量或顯示假的 0%。
- 懸浮查看自訂名稱、電量與連線方式。點擊圖示開啟總覽；右鍵可更新、改名或結束全部。
- 「重新命名」支援 1～32 個字元；三個名稱獨立儲存，不影響裝置辨識。
- 深淺色模式會記住。關閉總覽後繼續在系統匣執行。
- 可在總覽勾選登入自動啟動。再次啟動程式會開啟已有的總覽，不建立重複圖示。
- 藍牙模式與同型號多台裝置尚未支援；目前每個已知型號最多一個圖示。

## 支援識別與通訊

| 裝置 | USB VID:PID | 控制集合 usage page |
|---|---|---|
| LOFREE 小順青春版(100鍵) | `05AC:024F` | `FF02` |
| HECATE G3M PRO 有線 | `320F:706B` | `FF1C` |
| HECATE G3M PRO 接收器 | `320F:706E` | `FF1C` |
| HECATE G3M PRO 升級版有線 | `35BB:D3FC` | `FF02` |
| HECATE G3M PRO 升級版接收器 | `35BB:D3FB` | `FF02` |

鍵盤的有線／接收器共用 VID/PID；以產品描述 `Air100@Lofree` 與 `2.4G Wireless Receiver` 區分。只開啟符合的廠商控制集合，不抓取按鍵或滑鼠移動內容。

LOFREE 與升級版使用 17-byte 電量命令 `08 04`，read flag 依韌體採 `80` 或 legacy `00`，總和校驗為 `55`，回應 byte 6 是百分比。原版使用 64-byte 電量命令 `04 20 00 1A 06 00 00 00`，回應 byte 8 是百分比。原始碼內僅有電量查詢，無設定／韌體寫入命令。

Windows 主機已確認三個裝置喚醒後，直接透過 Python HIDAPI、完全不呼叫原廠 DLL，即可讀到鍵盤 100%、原版滑鼠 95%、升級版滑鼠 100%，三者均使用 2.4 GHz 接收器。已將升級版真實回應加入測試。Kubuntu 修正後也已由作者確認可正常使用；休眠或讀不到時如實顯示狀態。

## 診斷

Linux 版優先載入 `hidapi` 套件的 `hidraw` 模組，與安裝的 hidraw udev 權限規則一致。部分 Linux wheel 的 `hid` 模組使用 libusb；舊版直接 `import hid`，可能無法枚舉或開啟由核心驅動使用的鍵盤／滑鼠介面，而顯示未連線。僅包含 hidraw 的原始碼編譯套件可能將模組命名為 `hid`，程式亦支援此情況。

若已安裝舊版，先從系統匣「結束全部圖示」，在新版原始碼的本目錄執行 `bash install.sh --no-udev`，更新後重新開啟；已安裝的 udev 規則不需要變更。

```bash
app="$HOME/.local/share/device-battery-tray"
"$app/.venv/bin/python" "$app/device-battery-tray.py" --list-devices
"$app/.venv/bin/python" "$app/device-battery-tray.py" --diagnose
```

若自訂了 `XDG_DATA_HOME`，請使用安裝腳本輸出的實際路徑。診斷 JSON 含裝置名稱、連線、狀態、百分比與電量原始回應；不會上傳。退出碼 0 表示三個電量皆成功，2 表示至少一個裝置未取得電量，1 表示程式／相依套件錯誤。未插入的裝置也會造成診斷碼 2。

`--list-devices` 現在列出已知型號的全部介面，`control_interface` 標示是否可用於電量查詢；一般輸入介面僅供診斷，不會送出查詢。`backend` 顯示實際載入的模組，`access_error` 顯示 hidraw 節點是否不存在或缺少讀寫權限。`--diagnose` 也包含 `backend` 與實際查詢的 `path`。容器或受限執行環境可能看得到 sysfs 裝置資料，卻沒有 `/dev/hidraw*`，此時請在主機桌面的終端機執行。

遇到無法存取裝置，先確認 udev 規則安裝成功，再重新插拔裝置。接收器存在不等於無線裝置已喚醒：請移動滑鼠或按鍵後按「立即更新」。不要用 root 常駐程式取代權限設定。

若需回報問題，提供 Kubuntu 版本、連線方式、`--list-devices` 與 `--diagnose` 輸出；分享前可自行移除自訂名稱及裝置序號。

## 開發與測試

使用 `python3 kubuntu/build-deb.py`（在儲存庫根目錄執行）可建立 `dist/device-battery-tray_0.1.0_all.deb`，需要 `dpkg-deb`，不需要 root。GitHub release 流程會執行測試、建置兩個平台附件並提供 SHA256SUMS。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python device-battery-tray.py
# 不讀硬體的示例介面截圖：
QT_QPA_PLATFORM=offscreen .venv/bin/python device-battery-tray.py --preview-ui preview.png
```

完整原始碼、安裝／移除腳本及測試都包含在本資料夾，適合放入 GitHub。授權方式由擁有者決定；未擅自替專案選擇開源授權，也未附帶原廠 DLL。

## 移除

先從圖示選「結束全部圖示」，再在解壓縮資料夾執行 `bash uninstall.sh`。腳本移除安裝目錄、選單項目、自動啟動項目與專用 udev 規則，保留個人名稱／主題設定。

## 技術參考

- [Qt QSystemTrayIcon：KDE 與 StatusNotifierItem 支援](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)
- [HIDAPI Linux hidraw 後端及多 usage 解析](https://github.com/libusb/hidapi/blob/master/linux/hid.c)
- [cython-hidapi API](https://github.com/trezor/cython-hidapi/blob/master/hid.pyx)
- [Linux hidraw 說明](https://cdn.kernel.org/doc/html/latest/hid/hidraw.html)

## 本次驗證結果

- 2026-11-08 Linux 排查：已安裝 hidapi 0.15.0 的 `hid` 模組連結 libusb，枚舉回傳空清單；同套件的 `hidraw` 可枚舉已連線的 LOFREE 與 HECATE 電量控制介面。修正後診斷可辨識已插入裝置，但本次受限環境未提供 `/dev/hidraw*`，尚未確認實機電量百分比。
- 修正後 15 項 Python／Qt 測試通過，包含 Linux 後端選擇、原始碼編譯套件的匯入 fallback、存取錯誤及診斷介面。
- 11 項 Python／Qt 測試通過，包含真實樣本、無效校驗、接收器辨識、顏色邊界、斷線清值、設定保存、改名對話框、主題切換，以及插拔顯示行為。
- Windows 主機下以 Qt offscreen 檢查深／淺色介面。
- Bash install.sh／uninstall.sh 語法檢查通過。
- 壓縮包已確認 LF 換行、Linux 執行權限，且不包含測試環境與快取。
- 後續作者實測：修正後的腳本安裝與 Kubuntu 電量功能正常。新 `.deb` 尚待桌面實際安裝驗證。
