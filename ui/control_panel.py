from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, QPushButton, QCheckBox, 
    QSpinBox, QDoubleSpinBox, QFormLayout, QLabel, QTabWidget, QComboBox, 
    QHBoxLayout, QRadioButton, QButtonGroup, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QTimer
import sys

class ControlPanelUI(QWidget):
    def __init__(self, worker, share_board=None, overlay=None):
        super().__init__()
        self.worker = worker
        self.share_board = share_board
        self.overlay = overlay
        self.setWindowTitle("StockEye Control")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Thiết lập kích thước nhỏ gọn
        self.resize(320, 250)
        
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
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(6)
        
        self.tabs = QTabWidget()
        
        # --- TAB CƠ BẢN ---
        self.tab_basic = QWidget()
        basic_layout = QFormLayout()
        basic_layout.setContentsMargins(12, 8, 12, 4)
        basic_layout.setSpacing(8)
        
        # 1. Bàn cờ phụ
        self.chk_share_board = QCheckBox()
        self.chk_share_board.setChecked(self.config_data.get("show_share_board", True))
        if self.share_board:
            self.share_board.setVisible(self.chk_share_board.isChecked())
            if hasattr(self.share_board, "visibility_changed"):
                self.share_board.visibility_changed.connect(
                    lambda visible: self.chk_share_board.setChecked(visible) if self.chk_share_board.isChecked() != visible else None
                )
        def on_share_board_toggle(state):
            is_checked = state == Qt.Checked
            if self.share_board:
                self.share_board.setVisible(is_checked)
        self.chk_share_board.stateChanged.connect(on_share_board_toggle)
        basic_layout.addRow("Bàn cờ phụ:", self.chk_share_board)

        # 2. Gợi ý (Bàn cờ chính)
        self.chk_draw_main = QCheckBox()
        self.chk_draw_main.setChecked(self.config_data.get("draw_on_main_board", False))
        def on_draw_main_toggle(state):
            is_checked = state == Qt.Checked
            if self.overlay and hasattr(self.overlay, "set_draw_on_main_board"):
                self.overlay.set_draw_on_main_board(is_checked)
        self.chk_draw_main.stateChanged.connect(on_draw_main_toggle)
        basic_layout.addRow("Gợi ý (Bàn cờ chính):", self.chk_draw_main)

        # 3. Cưỡng ép phe hiện tại (Bên hiện tại)
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
            
        def on_force_side_toggle():
            is_enabled = self.chk_force_side.isChecked()
            self.radio_white.setEnabled(is_enabled)
            self.radio_black.setEnabled(is_enabled)
            
        self.chk_force_side.stateChanged.connect(on_force_side_toggle)
        self.chk_force_side.stateChanged.connect(self.save_config)
        self.radio_white.toggled.connect(self.save_config)
        self.radio_black.toggled.connect(self.save_config)
        
        side_layout.addWidget(self.chk_force_side)
        side_layout.addWidget(self.radio_white)
        side_layout.addWidget(self.radio_black)
        side_layout.addStretch()
        
        basic_layout.addRow(side_layout)
        on_force_side_toggle()

        # 4. Giới hạn sức mạnh (Mặc định: TẮT / Không giới hạn sức mạnh)
        self.chk_limit_strength = QCheckBox()
        self.chk_limit_strength.setChecked(self.config_data.get("uci_limit_strength", False))
        self.chk_limit_strength.setToolTip("Mặc định TẮT (Không giới hạn sức mạnh - Bot đánh Max Elo). Bật lên để giới hạn Elo và độ trễ trong tab Nâng Cao.")
        lbl_strength = QLabel("Giới hạn sức mạnh:")
        lbl_strength.setToolTip(self.chk_limit_strength.toolTip())
        basic_layout.addRow(lbl_strength, self.chk_limit_strength)

        self.tab_basic.setLayout(basic_layout)
        self.tabs.addTab(self.tab_basic, "Cơ Bản")
        
        # --- TAB NÂNG CAO ---
        self.tab_adv = QWidget()
        adv_layout = QFormLayout()
        adv_layout.setContentsMargins(15, 15, 15, 15)
        adv_layout.setSpacing(14)
        
        self.preset_is_updating = False
        
        # Chế độ chơi (Presets)
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(["Cờ siêu chớp (1 Phút)", "Cờ chớp (3 Phút)", "Cờ nhanh (10 Phút)", "Tùy chỉnh"])
        preset_idx = self.config_data.get("preset_index", 3)
        self.combo_preset.setCurrentIndex(preset_idx)
        self.combo_preset.currentIndexChanged.connect(self.apply_preset)
        adv_layout.addRow("Chế độ chơi:", self.combo_preset)
        
        # Trình độ Bot (Elo)
        self.spin_elo = QSpinBox()
        self.spin_elo.setRange(1320, 4000)
        self.spin_elo.setValue(self.config_data.get("uci_elo", 2000))
        self.spin_elo.setToolTip("Điều chỉnh sức mạnh của Bot khi Bật giới hạn sức mạnh.")
        lbl_elo = QLabel("Trình độ Bot (Elo):")
        lbl_elo.setToolTip(self.spin_elo.toolTip())
        adv_layout.addRow(lbl_elo, self.spin_elo)
        
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
        
        self.tab_adv.setLayout(adv_layout)

        # Đặt tab Nâng Cao vào QScrollArea
        scroll_adv = QScrollArea()
        scroll_adv.setWidgetResizable(True)
        scroll_adv.setFrameShape(QFrame.NoFrame)
        scroll_adv.setWidget(self.tab_adv)
        self.tabs.addTab(scroll_adv, "Nâng Cao")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(self.tabs)
        
        self.chk_limit_strength.stateChanged.connect(self.toggle_strength_inputs)
        
        # --- KHU VỰC NÚT BẤM ---
        # Nút Lưu Settings
        self.btn_save = QPushButton("LƯU SETTINGS")
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 7px;")
        self.btn_save.clicked.connect(self.save_config)
        main_layout.addWidget(self.btn_save)
        
        # Grid cho các nút điều khiển
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(0, 2, 0, 0)
        
        # [2] Nút Bật/Tắt Gợi Ý
        self.btn_suggest = QPushButton()
        self.update_suggest_btn_style(self.config_data.get("suggest_mode", False))
        self.btn_suggest.clicked.connect(lambda: self.worker.toggle_suggest_mode())
        self.worker.suggest_ui_signal.connect(self.update_suggest_btn_style, Qt.QueuedConnection)
        grid_layout.addWidget(self.btn_suggest, 0, 0)
        
        # [F10] Nút Ẩn Tool (Stealth Mode / Boss Key)
        self.btn_stealth = QPushButton()
        self.update_stealth_btn_style(False)
        self.btn_stealth.clicked.connect(lambda: self.worker.toggle_stealth_signal.emit())
        grid_layout.addWidget(self.btn_stealth, 1, 0)
        
        main_layout.addLayout(grid_layout)
        
        self.setLayout(main_layout)
        self.worker.exit_app_signal.connect(self.close, Qt.QueuedConnection)
        self.worker.force_side_ui_signal.connect(self.on_force_side_hotkey, Qt.QueuedConnection)
        
        # Cập nhật UI ban đầu
        self.toggle_strength_inputs()
        
        # Kết nối tất cả các sự kiện thay đổi để tự động lưu ngay lập tức
        self.connect_signals_to_save()
        
        # Áp dụng preset nếu đang chọn (phải gọi sau khi tạo xong UI)
        if self.combo_preset.currentIndex() != 3:
            self.apply_preset(self.combo_preset.currentIndex())

    def connect_signals_to_save(self):
        # Checkboxes
        self.chk_limit_strength.stateChanged.connect(self.save_config)
        self.chk_share_board.stateChanged.connect(self.save_config)
        self.chk_draw_main.stateChanged.connect(self.save_config)
        # SpinBoxes
        self.spin_elo.valueChanged.connect(self.save_config)
        self.spin_time.valueChanged.connect(self.save_config)
        self.spin_threads.valueChanged.connect(self.save_config)
        self.spin_stable.valueChanged.connect(self.save_config)
        
        # Tự động nhảy sang "Tùy chỉnh" nếu người dùng tự kéo số
        def on_custom_change():
            if not self.preset_is_updating:
                self.preset_is_updating = True
                self.combo_preset.setCurrentIndex(3)
                self.preset_is_updating = False
        
        self.spin_time.valueChanged.connect(on_custom_change)

    def apply_preset(self, index):
        if self.preset_is_updating: return
        self.preset_is_updating = True
        
        if index == 0: # Cờ siêu chớp (1 Phút)
            self.spin_time.setValue(0.05)
        elif index == 1: # Cờ chớp (3 Phút)
            self.spin_time.setValue(0.1)
        elif index == 2: # Cờ nhanh (10 Phút)
            self.spin_time.setValue(0.25)
            
        self.preset_is_updating = False
        if index != 3:
            self.save_config()

    def on_tab_changed(self, index):
        if index == 0:
            self.resize(320, 250)
        else:
            self.resize(340, 300)

    def update_suggest_btn_style(self, is_on):
        if is_on:
            self.btn_suggest.setText("[2] GỢI Ý: ĐANG BẬT")
            self.btn_suggest.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 7px;")
        else:
            self.btn_suggest.setText("[2] GỢI Ý: ĐANG TẮT")
            self.btn_suggest.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 7px;")

    def update_stealth_btn_style(self, is_stealth):
        if is_stealth:
            self.btn_stealth.setText("[F10] ĐANG ẨN (BẤM F10 ĐỂ HIỆN)")
            self.btn_stealth.setStyleSheet("background-color: #D32F2F; color: white; font-weight: bold; padding: 6px;")
        else:
            self.btn_stealth.setText("[F10] ẨN TOOL (STEALTH MODE)")
            self.btn_stealth.setStyleSheet("background-color: #37474F; color: white; font-weight: bold; padding: 6px;")

    def toggle_strength_inputs(self):
        is_checked = self.chk_limit_strength.isChecked()
        self.spin_elo.setEnabled(is_checked)
        self.spin_time.setEnabled(is_checked)

    def save_config(self):
        import json
        self.config_data["uci_limit_strength"] = self.chk_limit_strength.isChecked()
        self.config_data["uci_elo"] = self.spin_elo.value()
        self.config_data["time_limit"] = round(self.spin_time.value(), 2)
        self.config_data["threads"] = self.spin_threads.value()
        self.config_data["stable_frames"] = self.spin_stable.value()
        self.config_data["preset_index"] = self.combo_preset.currentIndex()
        self.config_data["force_side_enabled"] = self.chk_force_side.isChecked()
        self.config_data["force_side"] = "black" if self.radio_black.isChecked() else "white"
        self.config_data["show_share_board"] = self.chk_share_board.isChecked()
        self.config_data["draw_on_main_board"] = self.chk_draw_main.isChecked()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4)
            if hasattr(self.worker, 'engine') and self.worker.engine:
                try:
                    self.worker.engine.reload_config()
                except Exception:
                    pass
            self.btn_save.setText("LƯU: ĐÃ LƯU")
        except Exception as e:
            print(f"Lỗi khi lưu config: {e}")
            self.btn_save.setText("LƯU: CÓ LỖI XẢY RA")
            
        QTimer.singleShot(2000, lambda: self.btn_save.setText("LƯU SETTINGS"))

    def closeEvent(self, event):
        """Thoát chương trình khi đóng cửa sổ"""
        if getattr(self, '_is_closing', False):
            event.accept()
            return
        self._is_closing = True

        print("\n[UI] Bảng điều khiển đã bị đóng. Đang thoát chương trình...")
        if hasattr(self, 'worker') and self.worker:
            self.worker.running = False
            if hasattr(self.worker, 'engine') and self.worker.engine:
                try:
                    self.worker.engine.close()
                except Exception:
                    pass
        if self.share_board:
            try:
                self.share_board.close()
            except Exception:
                pass
        if hasattr(self, 'overlay') and self.overlay:
            try:
                self.overlay.close()
            except Exception:
                pass
        QApplication.instance().quit()
        event.accept()

    def on_force_side_hotkey(self, side):
        self.chk_force_side.setChecked(True)
        if side == "white":
            self.radio_white.setChecked(True)
        else:
            self.radio_black.setChecked(True)
        self.save_config()
        # Buộc đồng bộ lại màu sau khi ép phe
        self.worker.request_midgame_sync("auto_suggest")
