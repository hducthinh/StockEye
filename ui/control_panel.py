from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox, QFormLayout, QLabel, QTabWidget, QComboBox, QHBoxLayout, QRadioButton, QButtonGroup
from PyQt5.QtCore import Qt, QTimer
import sys

class ControlPanelUI(QWidget):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setWindowTitle("StockEye Control")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Thiết lập kích thước
        self.resize(360, 600)
        
        # Đưa cửa sổ lên góc phải trên màn hình
        try:
            desktop_geom = QApplication.desktop().availableGeometry()
            x = desktop_geom.width() - self.width() - 20
            y = 20
            self.move(x, y)
        except:
            pass
            
        self.config_path = "config.json"
        self.config_data = self.worker.config_data

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        

        
        self.tabs = QTabWidget()
        
        # --- TAB CƠ BẢN ---
        self.tab_basic = QWidget()
        basic_layout = QFormLayout()
        basic_layout.setContentsMargins(10, 15, 10, 10)
        basic_layout.setSpacing(15)
        

        
        # Cưỡng ép phe hiện tại (giữ lại theo yêu cầu)
        side_layout = QHBoxLayout()
        self.chk_force_side = QCheckBox("BÊN HIỆN TẠI:")
        self.chk_force_side.setChecked(self.config_data.get("force_side_enabled", False))
        
        self.radio_white = QRadioButton("[5] TRẮNG")
        self.radio_black = QRadioButton("[6] ĐEN")
        
        self.side_group = QButtonGroup()
        self.side_group.addButton(self.radio_white)
        self.side_group.addButton(self.radio_black)
        
        if self.config_data.get("force_side", "white") == "black":
            self.radio_black.setChecked(True)
        else:
            self.radio_white.setChecked(True)
            
        def on_force_side_changed():
            is_enabled = self.chk_force_side.isChecked()
            self.radio_white.setEnabled(is_enabled)
            self.radio_black.setEnabled(is_enabled)
            
            # Lưu ngay lập tức vào bộ nhớ (không cần đợi Lưu Settings)
            self.config_data["force_side_enabled"] = is_enabled
            self.config_data["force_side"] = "black" if self.radio_black.isChecked() else "white"
            
            # Gửi tín hiệu quét lại
            mode = "auto" if self.config_data.get("autoplay", False) else "auto_suggest"
            self.worker.request_midgame_sync(turn=mode)
            
        self.chk_force_side.stateChanged.connect(on_force_side_changed)
        self.radio_white.clicked.connect(on_force_side_changed)
        self.radio_black.clicked.connect(on_force_side_changed)
        
        side_layout.addWidget(self.chk_force_side)
        side_layout.addWidget(self.radio_white)
        side_layout.addWidget(self.radio_black)
        side_layout.addStretch()
        
        basic_layout.addRow(side_layout)
        
        # Cập nhật state UI ban đầu mà không trigger event
        self.chk_force_side.blockSignals(True)
        is_enabled = self.chk_force_side.isChecked()
        self.radio_white.setEnabled(is_enabled)
        self.radio_black.setEnabled(is_enabled)
        self.chk_force_side.blockSignals(False)
        
        # Trình độ Bot (Elo)
        self.spin_elo = QSpinBox()
        self.spin_elo.setRange(1320, 4000)
        self.spin_elo.setValue(self.config_data.get("uci_elo", 2000))
        self.spin_elo.setToolTip("Điều chỉnh sức mạnh của Bot. Nên để ngang bằng hoặc cao hơn rank của bạn một chút.")
        lbl_elo = QLabel("Trình độ Bot (Elo):")
        lbl_elo.setToolTip(self.spin_elo.toolTip())
        basic_layout.addRow(lbl_elo, self.spin_elo)
        
        # Tỉ lệ giả vờ lỗi (%)
        self.spin_error = QSpinBox()
        self.spin_error.setRange(0, 100)
        self.spin_error.setSuffix(" %")
        error_val = int(self.config_data.get("human_error_rate", 0.2) * 100)
        self.spin_error.setValue(error_val)
        self.spin_error.setToolTip("Xác suất Bot cố tình đi một nước kém hoàn hảo để giống người thật. Khuyên dùng: 10% đến 20%")
        lbl_error = QLabel("Tỉ lệ giả vờ lỗi:")
        lbl_error.setToolTip(self.spin_error.toolTip())
        basic_layout.addRow(lbl_error, self.spin_error)
        
        # Thời gian suy nghĩ (giây)
        self.spin_bot_delay = QDoubleSpinBox()
        self.spin_bot_delay.setRange(0.0, 10.0)
        self.spin_bot_delay.setSingleStep(0.1)
        self.spin_bot_delay.setValue(self.config_data.get("bot_delay", 0.15))
        self.spin_bot_delay.setToolTip("Độ trễ trước khi Bot click chuột. Giúp tránh bị phát hiện là tool.")
        lbl_delay = QLabel("Thời gian suy nghĩ (giây):")
        lbl_delay.setToolTip(self.spin_bot_delay.toolTip())
        basic_layout.addRow(lbl_delay, self.spin_bot_delay)
        
        self.tab_basic.setLayout(basic_layout)
        self.tabs.addTab(self.tab_basic, "Cơ Bản")
        
        # --- TAB NÂNG CAO ---
        self.tab_adv = QWidget()
        adv_layout = QFormLayout()
        adv_layout.setContentsMargins(10, 15, 10, 10)
        adv_layout.setSpacing(12)
        
        # Autoplay (BOT Mode) - Hidden from UI, logic kept intact
        self.chk_autoplay = QCheckBox()
        self.chk_autoplay.setChecked(self.config_data.get("autoplay", False))
        self.worker.autoplay_ui_signal.connect(self.chk_autoplay.setChecked, Qt.QueuedConnection)
        
        # Limit Strength (Checkbox)
        self.config_data["uci_limit_strength"] = True
        self.chk_limit_strength = QCheckBox()
        self.chk_limit_strength.setChecked(True)
        adv_layout.addRow("Giới hạn sức mạnh:", self.chk_limit_strength)
        
        # Time Limit (s)
        self.spin_time = QDoubleSpinBox()
        self.spin_time.setRange(0.01, 10.0)
        self.spin_time.setSingleStep(0.05)
        self.spin_time.setValue(self.config_data.get("time_limit", 0.1))
        adv_layout.addRow("Thời gian giới hạn (s):", self.spin_time)
        
        # Threads
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(self.config_data.get("threads", 2))
        adv_layout.addRow("Số luồng CPU:", self.spin_threads)
        
        # Stable Frames
        self.spin_stable = QSpinBox()
        self.spin_stable.setRange(1, 10)
        self.spin_stable.setValue(self.config_data.get("stable_frames", 4))
        adv_layout.addRow("Khung hình chờ ổn định:", self.spin_stable)
        
        # Trade Bias (cp)
        self.spin_trade_bias = QSpinBox()
        self.spin_trade_bias.setRange(0, 1000)
        self.spin_trade_bias.setSingleStep(10)
        self.spin_trade_bias.setValue(self.config_data.get("trade_bias", 150))
        adv_layout.addRow("Xu hướng đổi quân:", self.spin_trade_bias)
        

        # Mouse Curvature
        self.spin_curvature = QSpinBox()
        self.spin_curvature.setRange(0, 100)
        self.spin_curvature.setValue(self.config_data.get("mouse_curvature", 30))
        adv_layout.addRow("Độ cong chuột:", self.spin_curvature)
        
        # Scramble Time
        self.spin_scramble = QDoubleSpinBox()
        self.spin_scramble.setRange(1.0, 30.0)
        self.spin_scramble.setSingleStep(1.0)
        self.spin_scramble.setValue(self.config_data.get("scramble_time", 5.0))
        adv_layout.addRow("Thời gian bắt đầu tàn sát (s):", self.spin_scramble)
        
        self.tab_adv.setLayout(adv_layout)
        self.tabs.addTab(self.tab_adv, "Nâng Cao")
        
        main_layout.addWidget(self.tabs)
        
        self.chk_limit_strength.stateChanged.connect(self.toggle_strength_inputs)
        
        # --- KHU VỰC NÚT BẤM ---
        # Nút Lưu Settings
        self.btn_save = QPushButton("LƯU SETTINGS")
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self.save_config)
        main_layout.addWidget(self.btn_save)
        
        # Grid cho 4 nút điều khiển
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 5, 0, 0)
        
        # [1] Nút Bật/Tắt
        self.btn_toggle = QPushButton()
        self.update_toggle_btn_style()
        self.btn_toggle.clicked.connect(self.toggle_tool)
        grid_layout.addWidget(self.btn_toggle, 0, 0)
        
        # [2] Nút Gợi Ý
        self.btn_suggest = QPushButton()
        self.update_suggest_btn_style(self.config_data.get("suggest_mode", True))
        self.btn_suggest.clicked.connect(lambda: self.worker.toggle_suggest_mode())
        self.worker.suggest_ui_signal.connect(self.update_suggest_btn_style, Qt.QueuedConnection)
        grid_layout.addWidget(self.btn_suggest, 0, 1)
        
        # [3] Nút Autoplay
        self.btn_auto = QPushButton()
        self.update_autoplay_btn_style(self.chk_autoplay.isChecked())
        def on_autoplay_click():
            self.worker.toggle_autoplay()
        self.btn_auto.clicked.connect(on_autoplay_click)
        self.chk_autoplay.stateChanged.connect(lambda: self.update_autoplay_btn_style(self.chk_autoplay.isChecked()))
        grid_layout.addWidget(self.btn_auto, 1, 0)
        
        # [4] Nút Autofarm
        self.btn_autofarm = QPushButton()
        self.update_autofarm_btn_style(getattr(self.worker, 'auto_farm', False))
        def on_autofarm_click():
            self.worker.toggle_autofarm()
        self.btn_autofarm.clicked.connect(on_autofarm_click)
        self.worker.autofarm_ui_signal.connect(self.update_autofarm_btn_style, Qt.QueuedConnection)
        grid_layout.addWidget(self.btn_autofarm, 1, 1)
        
        main_layout.addLayout(grid_layout)
        
        self.setLayout(main_layout)
        self.worker.force_side_ui_signal.connect(self.on_force_side_hotkey, Qt.QueuedConnection)
        
        # Cập nhật UI ban đầu
        self.toggle_strength_inputs()
        
        # Kết nối tất cả các sự kiện thay đổi để tự động lưu ngay lập tức
        self.connect_signals_to_save()
        


    def connect_signals_to_save(self):
        # Tắt tính năng auto save
        pass
        


    def update_toggle_btn_style(self):
        if self.worker.is_paused:
            self.btn_toggle.setText("[1] BẬT / TẮT: TẮT")
            self.btn_toggle.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        else:
            self.btn_toggle.setText("[1] BẬT / TẮT: BẬT")
            self.btn_toggle.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")

    def update_suggest_btn_style(self, is_on):
        state = "BẬT" if is_on else "TẮT"
        self.btn_suggest.setText(f"[2] GỢI Ý: {state}")
        self.btn_suggest.setStyleSheet(f"background-color: {'#2196F3' if is_on else '#607D8B'}; color: white; font-weight: bold; padding: 10px;")

    def update_autoplay_btn_style(self, is_on):
        state = "BẬT" if is_on else "TẮT"
        self.btn_auto.setText(f"[3] AUTOPLAY: {state}")
        self.btn_auto.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 10px;")

    def update_autofarm_btn_style(self, is_on):
        state = "BẬT" if is_on else "TẮT"
        self.btn_autofarm.setText(f"[4] AUTOFARM: {state}")
        self.btn_autofarm.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 10px;")

    def toggle_strength_inputs(self):
        is_checked = self.chk_limit_strength.isChecked()
        self.spin_elo.setEnabled(is_checked)
        self.spin_error.setEnabled(is_checked)
        self.spin_time.setEnabled(is_checked)

    def save_config(self):
        import json
        self.config_data["uci_limit_strength"] = self.chk_limit_strength.isChecked()
        self.config_data["uci_elo"] = self.spin_elo.value()
        self.config_data["human_error_rate"] = self.spin_error.value() / 100.0
        self.config_data["time_limit"] = round(self.spin_time.value(), 2)
        self.config_data["bot_delay"] = round(self.spin_bot_delay.value(), 2)
        self.config_data["threads"] = self.spin_threads.value()
        self.config_data["stable_frames"] = self.spin_stable.value()
        self.config_data["trade_bias"] = self.spin_trade_bias.value()
        self.config_data["mouse_curvature"] = self.spin_curvature.value()
        self.config_data["autoplay"] = self.chk_autoplay.isChecked()
        self.config_data["force_side_enabled"] = self.chk_force_side.isChecked()
        self.config_data["force_side"] = "black" if self.radio_black.isChecked() else "white"
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
            self.btn_save.setText("LƯU: ĐÃ LƯU")
        except Exception as e:
            print(f"Lỗi khi lưu config: {e}")
            self.btn_save.setText("LƯU: CÓ LỖI XẢY RA")
            
        QTimer.singleShot(2000, lambda: self.btn_save.setText("LƯU SETTINGS"))

    def toggle_tool(self):
        self.worker.is_paused = not self.worker.is_paused
        self.update_toggle_btn_style()
        if self.worker.is_paused:
            self.worker.moves_ready.emit([]) # Xóa mũi tên cũ trên màn hình
            with self.worker.click_queue.mutex:
                self.worker.click_queue.queue.clear()
            
            # Commented out: Do not wipe user's preferences for 2 and 3 when pausing
            # if self.worker.config_data.get("suggest_mode", False):
            #     self.worker.config_data["suggest_mode"] = False
            #     self.worker.suggest_ui_signal.emit(False)
            # if self.worker.config_data.get("autoplay", False):
            #     self.worker.config_data["autoplay"] = False
            #     self.worker.autoplay_ui_signal.emit(False)
            # if getattr(self.worker, 'auto_farm', False):
            #     self.worker.auto_farm = False
            #     self.worker.autofarm_ui_signal.emit(False)
        else:
            mode = "auto" if self.config_data.get("autoplay", False) else "auto_suggest"
            self.worker.request_midgame_sync(mode)

    def on_force_side_hotkey(self, side):
        self.chk_force_side.setChecked(True)
        if side == "white":
            self.radio_white.setChecked(True)
        else:
            self.radio_black.setChecked(True)
        
        # Sẽ tự kích hoạt on_force_side_changed() vì kết nối tín hiệu
        
    def closeEvent(self, event):
        """Thoát chương trình khi đóng cửa sổ"""
        print("\n[UI] Bảng điều khiển đã bị đóng. Đang thoát chương trình...")
        QApplication.instance().quit()
        event.accept()
