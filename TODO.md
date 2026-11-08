# 待處理

- [x] Windows 與 Kubuntu：僅在裝置或接收器實際插入時顯示對應系統匣圖示。接收器仍插著但裝置休眠時，保留圖示並顯示讀取狀態。
- [x] Kubuntu：確認安裝的 hidapi wheel 中 `hid` 使用 libusb，與僅設定 hidraw 的 udev 規則不一致；改為優先使用 `hidraw`，並加入後端、介面及存取錯誤診斷。Linux 枚舉已能找到控制介面，15 項測試通過。
- [x] Kubuntu：作者已確認修正後可在 Kubuntu 正常使用。
- [ ] Kubuntu：驗證首次 `.deb` 桌面安裝、移除與從腳本版本遷移。
- [ ] Kubuntu：在 KDE Plasma 實機驗證系統匣、udev active-seat 存取權限、安裝與移除流程。
- [ ] 決定正式授權與版本發布方式。

後端選擇與唯讀 venv 更新問題已修正，作者確認可使用；`.deb` 首次安裝與完整移除流程仍待實測。
