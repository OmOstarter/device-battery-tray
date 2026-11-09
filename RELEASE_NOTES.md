# v0.1.1

Kubuntu 與 Windows 加入裝置管理、協定代碼編輯與 USB 拔插排查。

- 介面「更新」改稱「刷新」，維持每 30 秒與手動刷新。
- 手動新增項目可重新命名、刪除，或在原卡片繼續編輯協定代碼；設定會保存。
- 協定頁提供簡易表單、JSON／DBT1 代碼及可複製的本地 agent 提示詞，協助分析本地原廠軟體／驅動。程式不自行反編譯或執行 agent。
- USB 拔插辨認會標記插入／拔除、名稱和 VID／PID，可複製資訊或新增監測；適合排查不同鍵數版本及接收器。
- Kubuntu 擴充電池目錄、UPower、BlueZ 與 HID 搜尋；KDE 隱藏圖示清單使用設備名稱。
- Windows 提供自訂設備系統匣圖示、內建 HID 協定讀取及背景 WMI USB 偵測；缺少原廠 DLL 時，原有三款型號會改用內建 HID 後端。
- Python／Qt 測試與 Windows 封包、設定、編輯視窗及預覽檢查納入發布流程。

## 下載

- `device-battery-tray_0.1.1_all.deb`：Kubuntu 26.04。執行 `sudo apt install ./device-battery-tray_0.1.1_all.deb`。
- `device-battery-tray-kubuntu-0.1.1.tar.gz`：Kubuntu 原始碼及安裝腳本。
- `device-battery-tray-windows-0.1.1.zip`：Windows x64 可執行程式與使用說明。
- `SHA256SUMS`：下載檔案校驗值。

升級前先從系統匣結束程式；原有設定會保留。腳本安裝升級可執行新版 `kubuntu/install.sh --no-udev`。從腳本切換 `.deb` 時，先用舊腳本移除使用者層的啟動項目，避免啟動舊副本。

辨認 USB 設備不等於支援其電量。代碼目前接受 lofree、hecate-original、hecate-upgraded 三種已實作協定；未知協定仍需新增後端。84 鍵版尚未確認協定相容性。同 VID／PID 多台分別綁定電量尚未支援。Windows 通用藍牙電量與新原生 HID 後端的硬體讀值仍待實機驗證；Kubuntu 新 `.deb` 桌面安裝流程也仍待實測。發布附件不包含原廠 DLL。
