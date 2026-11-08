# v0.1.0

LOFREE / HECATE 裝置電量工具的首次正式發布。Kubuntu 版已由作者確認可正常使用。

- Linux 優先使用 hidraw 後端，修正原本 libusb 後端無法找到裝置的問題。
- 更新時沿用既有虛擬環境，修正唯讀 activate.csh 導致安裝失敗的問題。
- 診斷輸出加入實際 HID 後端、裝置路徑、控制介面與存取錯誤。
- 三個裝置各自的系統匣圖示、改名、主題、登入啟動與 30 秒更新。
- 15 項 Python／Qt 自動測試通過。

## 下載與安裝

- `device-battery-tray_0.1.0_all.deb`：Kubuntu 26.04，使用系統 Python／Qt 套件。下載後執行 `sudo apt install ./device-battery-tray_0.1.0_all.deb`，安裝後重新插拔接收器，從選單開啟「裝置電量」。此套件不內含 Python／Qt，apt 需要可用的 universe 套件來源；不支援 Kubuntu 24.04 的系統依賴。
- `device-battery-tray-kubuntu-0.1.0.tar.gz`：Python 原始碼與安裝腳本，可使用獨立 venv 安裝。
- `device-battery-tray-windows-0.1.0.zip`：Windows x64 程式與說明，仍需本機原廠 DLL。

從腳本安裝切換到 `.deb` 前，先結束程式並執行舊版 `kubuntu/uninstall.sh`，避免使用者層級的選單項目繼續啟動舊副本。移除腳本會保留名稱／主題設定；安裝 `.deb` 後可重新勾選登入自動啟動。

藍牙與同型號多台裝置尚未支援；Windows 原廠 DLL 不隨發布附件提供。`.deb` 的套件結構與自動建置會驗證，但首次 `.deb` 的桌面安裝仍待實機確認。
