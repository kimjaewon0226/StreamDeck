import sys
import subprocess
import webbrowser
import pyautogui
import time
import json
import os
import math
import shutil
import threading
import pyperclip
import pygetwindow as gw
import ctypes
import winreg

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("my.streamdeck.app.v1")
except Exception:
    pass

from PySide6.QtGui import (QIcon, QAction, QCloseEvent, QPixmap, QMouseEvent, 
                           QDrag, QDropEvent, QMovie, QPainter, QPainterPath, QColor, QPen)
from PySide6.QtCore import QSize, Qt, QPoint, QMimeData, QTimer, QRectF
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QWidget, 
                               QGridLayout, QStackedWidget, QInputDialog, QMenu, 
                               QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox, QLabel, QSystemTrayIcon, QSlider)

# 전역 단축키를 위한 keyboard 라이브러리 시도
try:
    import keyboard
except ImportError:
    keyboard = None


def set_autostart(enable=True):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "MyCustomStreamDeck"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            # 파이썬 스크립트 또는 빌드된 exe의 절대 경로 확보
            if getattr(sys, 'frozen', False):
                app_path = f'"{sys.executable}"'
            else:
                app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"자동 실행 레지스트리 설정 오류: {e}")


class DisplayLabel(QLabel):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setFixedSize(150, 200)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.movie = None
        self.current_pixmap = None
        self.load_display_content()

    def load_display_content(self):
        display_path = self.main_app.settings.get("display_icon", "")
        if display_path and os.path.exists(display_path):
            if display_path.lower().endswith('.gif'):
                if self.movie:
                    self.movie.stop()
                    self.movie.frameChanged.disconnect()
                self.movie = QMovie(display_path)
                
                def update_gif_frame():
                    try:
                        if not self.isHidden() and self.movie:
                            pix = self.movie.currentPixmap()
                            if not pix.isNull():
                                self.current_pixmap = pix.scaled(
                                    self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                                )
                                self.update()
                    except RuntimeError:
                        pass

                self.movie.frameChanged.connect(update_gif_frame)
                self.movie.start()
                self.setText("")
            else:
                if self.movie:
                    self.movie.stop()
                    self.movie = None
                pixmap = QPixmap(display_path)
                if not pixmap.isNull():
                    self.current_pixmap = pixmap.scaled(
                        self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                    )
                self.setText("")
            self.update()
        else:
            if os.path.exists("deck_display.gif"):
                if self.movie:
                    self.movie.stop()
                    self.movie.frameChanged.disconnect()
                self.movie = QMovie("deck_display.gif")
                
                def update_gif_frame():
                    try:
                        if not self.isHidden() and self.movie:
                            pix = self.movie.currentPixmap()
                            if not pix.isNull():
                                self.current_pixmap = pix.scaled(
                                    self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                                )
                                self.update()
                    except RuntimeError:
                        pass

                self.movie.frameChanged.connect(update_gif_frame)
                self.movie.start()
                self.setText("")
            elif os.path.exists("icon.png"):
                pixmap = QPixmap("icon.png")
                if not pixmap.isNull():
                    self.current_pixmap = pixmap.scaled(
                        self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                    )
                self.setText("")
            else:
                self.current_pixmap = None
                self.setText("🖥️ 디스플레이\n(GIF/이미지 드래그)")
            self.update()

    def paintEvent(self, event):
        if self.current_pixmap and not self.current_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
            path = QPainterPath()
            path.addRoundedRect(rect, 15.0, 15.0)

            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(self.rect(), self.current_pixmap)
            painter.restore()

            pen = QPen(QColor(255, 255, 255, 75), 1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        else:
            super().paintEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.ico', '.bmp', '.webp', '.gif')):
                    icons_dir = "icons"
                    if not os.path.exists(icons_dir):
                        os.makedirs(icons_dir)
                    
                    base_name = os.path.basename(file_path)
                    dest_path = os.path.join(icons_dir, f"display_{int(time.time())}_{base_name}")
                    try:
                        shutil.copyfile(file_path, dest_path)
                        display_icon = dest_path
                    except Exception:
                        display_icon = file_path

                    self.main_app.settings["display_icon"] = display_icon
                    self.main_app.save_settings()
                    self.load_display_content()
                    event.acceptProposedAction()
                    return
        event.ignore()


class CustomButton(QPushButton):
    def __init__(self, button_id, default_name, default_path, main_app, page_idx, slot_idx):
        super().__init__()
        self.button_id = button_id
        self.main_app = main_app
        self.page_idx = page_idx
        self.slot_idx = slot_idx
        self.settings = main_app.settings

        self.btn_movie = None
        self.current_bg_pixmap = None
        self.is_hovered = False
        self.is_pressed_state = False

        self.update_button_size()

        self.btn_name = self.settings.get(f"{button_id}_name", default_name)
        self.btn_path = self.settings.get(f"{button_id}_path", default_path)
        self.btn_icon = self.settings.get(f"{button_id}_icon", "")
        self.btn_hotkey = self.settings.get(f"{button_id}_hotkey", "")

        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

        self.update_style()
        self.update_ui()
        self.register_hotkey()

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

        self.press_pos = QPoint()
        self.is_dragging = False
        self.setAcceptDrops(True)

    def __del__(self):
        try:
            if hasattr(self, 'btn_movie') and self.btn_movie:
                self.btn_movie.stop()
                self.btn_movie = None
        except Exception:
            pass

    def register_hotkey(self):
        if keyboard and self.btn_hotkey:
            try:
                keyboard.add_hotkey(self.btn_hotkey, self.run_program)
            except Exception as e:
                print(f"단축키 등록 실패 ({self.btn_hotkey}): {e}")

    def update_button_size(self):
        mode = self.main_app.layout_modes[self.main_app.current_mode_idx]
        cols, rows = mode
        if cols == 3 and rows == 2:
            self.setFixedSize(100, 100)
        elif cols == 3 and rows == 3:
            self.setFixedSize(68, 68)
        elif cols == 4 and rows == 2:
            self.setFixedSize(72, 79)
        else:  # 4x3
            self.setFixedSize(68, 68)

    def update_ui(self):
        if hasattr(self, 'btn_movie') and self.btn_movie:
            try:
                self.btn_movie.stop()
                self.btn_movie.frameChanged.disconnect()
            except Exception:
                pass
            self.btn_movie = None

        self.current_bg_pixmap = None

        if self.btn_icon and os.path.exists(self.btn_icon):
            if self.btn_icon.lower().endswith('.gif'):
                self.btn_movie = QMovie(self.btn_icon)
                
                def update_gif_frame():
                    try:
                        if not self.isHidden() and self.btn_movie:
                            pix = self.btn_movie.currentPixmap()
                            if not pix.isNull():
                                self.current_bg_pixmap = pix.scaled(
                                    self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                                )
                                self.update()
                    except RuntimeError:
                        pass

                self.btn_movie.frameChanged.connect(update_gif_frame)
                self.btn_movie.start()
                self.setText("")
            else:
                pixmap = QPixmap(self.btn_icon)
                if not pixmap.isNull():
                    self.current_bg_pixmap = pixmap.scaled(
                        self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                    )
                self.setText("")
            
            self.setIcon(QIcon())
            self.update()
        else:
            self.setIcon(QIcon())
            self.setText(self.btn_name)
            self.update_style()
            self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.is_pressed_state = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self.current_bg_pixmap and not self.current_bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
            path = QPainterPath()
            path.addRoundedRect(rect, 15.0, 15.0)

            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(self.rect(), self.current_bg_pixmap)

            if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
                if self.button_id in self.main_app.selected_for_deletion:
                    painter.fillPath(path, QColor(255, 50, 50, 110))
                else:
                    painter.fillPath(path, QColor(0, 0, 0, 80))
            elif hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
                if self.is_hovered:
                    painter.fillPath(path, QColor(52, 152, 219, 130))
                else:
                    painter.fillPath(path, QColor(52, 152, 219, 75))
            else:
                if self.is_pressed_state:
                    painter.fillPath(path, QColor(0, 0, 0, 90))
                elif self.is_hovered:
                    painter.fillPath(path, QColor(255, 255, 255, 65))
            painter.restore()

            if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
                if self.button_id in self.main_app.selected_for_deletion:
                    pen = QPen(QColor("#ff5555"), 3)
                else:
                    pen = QPen(QColor("#ff5555"), 2, Qt.DashLine)
            elif hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
                pen = QPen(QColor("#3498db"), 2)
            else:
                if self.is_hovered:
                    pen = QPen(QColor(255, 255, 255, 200), 2)
                else:
                    pen = QPen(QColor(255, 255, 255, 75), 1)

            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
        else:
            super().paintEvent(event)

    def update_style(self):
        if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
            if self.button_id in self.main_app.selected_for_deletion:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 50, 50, 0.4); 
                        color: white; border: 3px solid #ff5555; 
                        border-radius: 15px; font-weight: bold; font-size: 13px;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(0, 0, 0, 0.3); 
                        color: rgba(255, 255, 255, 0.6); 
                        border: 2px dashed #ff5555; border-radius: 15px; font-size: 13px;
                    }
                """)
        elif hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(52, 152, 219, 0.3);
                    border: 2px solid #3498db;
                    border-radius: 15px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(52, 152, 219, 0.5);
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.25);
                    border-radius: 15px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.25);
                    border: 1px solid rgba(255, 255, 255, 0.5);
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.05);
                }
            """)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_pressed_state = True
            self.update()

            if hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
                self.press_pos = event.pos()
                return

            if self.main_app.is_pinned:
                return
            
            self.press_pos = event.globalPosition().toPoint()
            self.is_dragging = False
            
            if not (hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode):
                self.main_app.drag_position = event.globalPosition().toPoint() - self.main_app.frameGeometry().topLeft()
                self.main_app.dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
            if event.buttons() & Qt.LeftButton:
                if (event.pos() - self.press_pos).manhattanLength() > 5:
                    drag = QDrag(self)
                    mime_data = QMimeData()
                    mime_data.setText(f"{self.page_idx},{self.slot_idx}")
                    drag.setMimeData(mime_data)
                    
                    pixmap = self.grab()
                    drag.setPixmap(pixmap)
                    drag.HotSpot = event.pos()
                    
                    drag.exec_(Qt.MoveAction)
            return

        if self.main_app.is_pinned:
            super().mouseMoveEvent(event)
            return

        if event.buttons() & Qt.LeftButton:
            if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
                return

            current_pos = event.globalPosition().toPoint()
            if (current_pos - self.press_pos).manhattanLength() > 4:
                self.is_dragging = True
            
            if self.main_app.dragging:
                self.main_app.move(current_pos - self.main_app.drag_position)
                event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_pressed_state = False
            self.update()
            self.main_app.dragging = False
            
            if hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
                return

            if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
                super().mouseReleaseEvent(event)
                self.run_program()
                return

            if self.is_dragging:
                event.accept()
                return
                
        super().mouseReleaseEvent(event)
        
        if not self.is_dragging and event.button() == Qt.LeftButton:
            self.run_program()

    def dragEnterEvent(self, event):
        if (hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode) or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.ico', '.bmp', '.webp', '.gif')):
                    icons_dir = "icons"
                    if not os.path.exists(icons_dir):
                        os.makedirs(icons_dir)
                    
                    base_name = os.path.basename(file_path)
                    dest_path = os.path.join(icons_dir, f"{int(time.time())}_{base_name}")
                    try:
                        shutil.copyfile(file_path, dest_path)
                        self.btn_icon = dest_path
                    except Exception:
                        self.btn_icon = file_path

                    self.settings[f"{self.button_id}_icon"] = self.btn_icon
                    self.update_ui()
                    self.main_app.save_settings()
                    event.acceptProposedAction()
                    return

        if hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode and event.mimeData().text():
            source_data = event.mimeData().text().split(',')
            if len(source_data) == 2:
                src_page = int(source_data[0])
                src_slot = int(source_data[1])
                
                target_page = self.page_idx
                target_slot = self.slot_idx

                if src_page == target_page and src_slot != target_slot:
                    self.main_app.swap_temp_buttons(target_page, src_slot, target_slot)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def run_program(self):
        if hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode:
            return

        if hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode:
            if not self.button_id.startswith("dyn_"):
                self.main_app.show_glass_message("경고", "기초 기본 버튼은 삭제할 수 없습니다.")
                return
            
            if self.button_id in self.main_app.selected_for_deletion:
                self.main_app.selected_for_deletion.remove(self.button_id)
            else:
                self.main_app.selected_for_deletion.append(self.button_id)
            
            self.update_style()
            self.main_app.update_delete_ui()
            return

        if self.btn_hotkey:
            try:
                keys = [k.strip() for k in self.btn_hotkey.split('+')]
                pyautogui.hotkey(*keys)
            except Exception as e:
                print(f"버튼 단축키 실행 오류: {e}")

        if not self.btn_path:
            return
            
        if self.btn_path.startswith("special:multiaction:"):
            try:
                raw_actions = self.btn_path.replace("special:multiaction:", "")
                actions = json.loads(raw_actions)
                
                def execute_actions():
                    for act in actions:
                        time.sleep(0.5)
                        self.execute_single_action(act)
                        
                threading.Thread(target=execute_actions, daemon=True).start()
                return
            except Exception as e:
                print(f"멀티 액션 실행 오류: {e}")

        self.execute_single_action(self.btn_path)

    def execute_single_action(self, path_str):
        if path_str == "special:copy":
            pyautogui.hotkey('ctrl', 'c')
        elif path_str == "special:macro":
            subprocess.Popen(["notepad.exe"])
            time.sleep(1)
            pyautogui.write("Hello! This is my Stream Deck Macro.", interval=0.05)
            pyautogui.press("enter")
        elif path_str == "special:vol_up":
            pyautogui.press('volumeup')
        elif path_str == "special:vol_down":
            pyautogui.press('volumedown')
        elif path_str == "special:mute":
            pyautogui.press('volumemute')
        elif path_str == "special:play_pause":
            pyautogui.press('playpause')
        elif path_str.startswith("http://") or path_str.startswith("https://"):
            webbrowser.open(path_str)
        elif path_str.startswith("special:text:"):
            text_to_type = path_str.replace("special:text:", "")
            pyperclip.copy(text_to_type)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
        else:
            try:
                target_path = os.path.normpath(path_str)
                if hasattr(os, 'startfile'):
                    os.startfile(target_path)
                else:
                    subprocess.Popen([target_path], shell=True) 
            except Exception as e:
                print(f"개별 실행 오류 ({path_str}): {e}")

    def show_menu(self, position):
        if (hasattr(self.main_app, 'delete_mode') and self.main_app.delete_mode) or \
           (hasattr(self.main_app, 'edit_mode') and self.main_app.edit_mode):
            return 

        menu = QMenu(self)
        action_rename = QAction("✏️ 이름 변경", self)
        action_rename.triggered.connect(self.edit_name)
        menu.addAction(action_rename)
        
        action_hotkey = QAction("⌨️ 키보드 단축키 지정 (녹화 방식)", self)
        action_hotkey.triggered.connect(self.edit_hotkey)
        menu.addAction(action_hotkey)

        action_reset_hotkey = QAction("🔄 단축키 초기화", self)
        action_reset_hotkey.triggered.connect(self.reset_hotkey)
        menu.addAction(action_reset_hotkey)
        
        action_change_prog = QAction("📂 실행 파일/프로그램 연결", self)
        action_change_prog.triggered.connect(self.edit_program)
        menu.addAction(action_change_prog)

        action_change_steam = QAction("🎮 바탕화면 게임 아이콘으로 연결", self)
        action_change_steam.triggered.connect(self.edit_steam)
        menu.addAction(action_change_steam)

        action_change_web = QAction("🌐 웹사이트 주소 연결 (URL)", self)
        action_change_web.triggered.connect(self.edit_web_url)
        menu.addAction(action_change_web)

        action_change_text = QAction("💬 텍스트 매크로 (자동 타이핑)", self)
        action_change_text.triggered.connect(self.edit_text_macro)
        menu.addAction(action_change_text)

        action_multiaction = QAction("⚡ 멀티 액션 (순차 실행) 설정", self)
        action_multiaction.triggered.connect(self.edit_multiaction)
        menu.addAction(action_multiaction)

        action_reset_multiaction = QAction("⚡ 멀티 액션 취소", self)
        action_reset_multiaction.triggered.connect(self.reset_multiaction)
        menu.addAction(action_reset_multiaction)

        action_change_icon = QAction("🖼️ 아이콘 이미지/GIF 변경", self)
        action_change_icon.triggered.connect(self.edit_icon)
        menu.addAction(action_change_icon)
        
        menu.exec_(self.mapToGlobal(position))

    def edit_multiaction(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "멀티 액션 순차 실행할 파일들 다중 선택", 
            "", 
            "모든 파일 (*.*);;실행 및 바로가기 (*.exe *.bat *.cmd *.url *.lnk)",
            options=QFileDialog.DontResolveSymlinks
        )
        
        if files:
            self.btn_path = f"special:multiaction:{json.dumps(files)}"
            self.btn_name = "멀티 액션"
            self.btn_icon = ""
            self.settings[f"{self.button_id}_path"] = self.btn_path
            self.settings[f"{self.button_id}_name"] = self.btn_name
            self.settings[f"{self.button_id}_icon"] = ""
            self.update_ui()
            self.main_app.save_settings()
            
            file_names = ", ".join([os.path.basename(f) for f in files])
            self.main_app.show_glass_message("완료", f"총 {len(files)}개의 작업이 순차 실행되도록 설정되었습니다!\n({file_names})")

    def reset_multiaction(self):
        if not self.btn_path or not self.btn_path.startswith("special:multiaction:"):
            self.main_app.show_glass_message("알림", "이 버튼에는 설정된 멀티 액션이 없습니다.")
            return

        reply = self.main_app.show_glass_message("멀티 액션 취소", "이 버튼에 설정된 멀티 액션(순차 실행)을 취소하시겠습니까?", is_question=True)

        if reply == QMessageBox.Yes:
            self.btn_path = ""
            self.btn_name = "빈 버튼"
            self.btn_icon = ""
            self.settings[f"{self.button_id}_path"] = self.btn_path
            self.settings[f"{self.button_id}_name"] = self.btn_name
            self.settings[f"{self.button_id}_icon"] = ""
            self.update_ui()
            self.main_app.save_settings()
            self.main_app.show_glass_message("완료", "멀티 액션 설정이 성공적으로 취소되었습니다!")

    def edit_name(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("이름 변경")
        dialog.setLabelText("새 이름:")
        dialog.setTextValue(self.btn_name)
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 18px;
                color: #1f2937;
            }
            QLabel {
                color: #1f2937;
                background: transparent;
                font-weight: bold;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #1f2937;
                padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d1d5db;
            }
        """)
        if dialog.exec() == QInputDialog.Accepted:
            new_name = dialog.textValue()
            if new_name:
                self.btn_name = new_name
                self.btn_icon = ""
                self.settings[f"{self.button_id}_name"] = self.btn_name
                self.settings[f"{self.button_id}_icon"] = ""
                self.update_ui()
                self.main_app.save_settings()

    def edit_hotkey(self):
        if not keyboard:
            self.main_app.show_glass_message("경고", "keyboard 라이브러리가 설치되어 있지 않습니다.")
            return

        rec_box = QMessageBox(self)
        rec_box.setWindowTitle("키보드 단축키 녹화")
        rec_box.setText("원하는 단축키 조합(예: Ctrl+Shift+M, F9 등)을 누르신 후,\n[단축키 저장 완료] 버튼을 눌러주세요!")
        
        btn_save_rec = rec_box.addButton("단축키 저장 완료", QMessageBox.AcceptRole)
        rec_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 20px;
            }
            QLabel {
                color: #1f2937;
                background: transparent;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d1d5db;
                border: 1px solid #9ca3af;
            }
            QPushButton:pressed {
                background-color: #9ca3af;
            }
        """)
        
        recorded_keys = []

        def on_key_down(e):
            name = e.name.lower()
            if name not in recorded_keys:
                recorded_keys.append(name)

        hook = keyboard.hook(on_key_down)
        rec_box.exec()
        keyboard.unhook(hook)

        if recorded_keys:
            self.btn_hotkey = "+".join(recorded_keys)
            self.settings[f"{self.button_id}_hotkey"] = self.btn_hotkey
            self.main_app.save_settings()
            self.register_hotkey()
            self.main_app.show_glass_message("완료", f"단축키 [{self.btn_hotkey}]가 성공적으로 지정되었습니다!")
        else:
            self.main_app.show_glass_message("알림", "입력된 단축키가 없습니다.")

    def reset_hotkey(self):
        if not self.btn_hotkey:
            self.main_app.show_glass_message("알림", "이 버튼에는 설정된 단축키가 없습니다.")
            return

        reply = self.main_app.show_glass_message("단축키 초기화", f"현재 설정된 단축키 [{self.btn_hotkey}]를 초기화하시겠습니까?", is_question=True)

        if reply == QMessageBox.Yes:
            try:
                if keyboard:
                    keyboard.remove_hotkey(self.btn_hotkey)
            except Exception:
                pass

            self.btn_hotkey = ""
            self.settings.pop(f"{self.button_id}_hotkey", None)
            self.main_app.save_settings()
            
            self.main_app.show_glass_message("완료", "단축키가 성공적으로 초기화되었습니다!")

    def edit_program(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "파일 선택 (모든 파일 및 바로가기)", 
            "", 
            "모든 파일 (*.*);;실행 파일 (*.exe *.bat *.cmd *.lnk *.url)",
            options=QFileDialog.DontResolveSymlinks
        )
        if path:
            self.btn_path = path
            self.settings[f"{self.button_id}_path"] = self.btn_path
            self.main_app.save_settings()

    def edit_steam(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "바탕화면의 게임 아이콘 선택", 
            "", 
            "게임 바로가기 (*.url *.lnk);;모든 파일 (*.*)",
            options=QFileDialog.DontResolveSymlinks
        )
        if path:
            self.btn_path = path
            self.settings[f"{self.button_id}_path"] = self.btn_path
            self.main_app.save_settings()
            game_name = os.path.basename(path)
            self.main_app.show_glass_message("완료", f"[{game_name}] 연결이 완료되었습니다!")

    def edit_web_url(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("웹사이트 주소 연결")
        dialog.setLabelText("연결할 웹 주소 (https://...):")
        dialog.setTextValue("https://")
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 18px;
                color: #1f2937;
            }
            QLabel { color: #1f2937; background: transparent; font-weight: bold; font-size: 13px; }
            QLineEdit {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #1f2937;
                padding: 6px;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d1d5db; }
        """)
        if dialog.exec() == QInputDialog.Accepted:
            url = dialog.textValue()
            if url:
                self.btn_path = url
                self.settings[f"{self.button_id}_path"] = self.btn_path
                self.main_app.save_settings()
                self.main_app.show_glass_message("완료", f"[{url}] 웹사이트 주소 연결이 완료되었습니다!")

    def edit_text_macro(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("텍스트 매크로 설정")
        dialog.setLabelText("자동으로 입력할 텍스트를 입력하세요:")
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 18px;
                color: #1f2937;
            }
            QLabel { color: #1f2937; background: transparent; font-weight: bold; font-size: 13px; }
            QLineEdit {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #1f2937;
                padding: 6px;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d1d5db; }
        """)
        if dialog.exec() == QInputDialog.Accepted:
            text = dialog.textValue()
            if text:
                self.btn_path = f"special:text:{text}"
                self.settings[f"{self.button_id}_path"] = self.btn_path
                self.main_app.save_settings()
                self.main_app.show_glass_message("완료", "텍스트 매크로 설정이 완료되었습니다!")

    def edit_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, "아이콘 이미지/GIF 선택", "", "이미지 및 GIF (*.png *.jpg *.jpeg *.ico *.gif)")
        if path:
            icons_dir = "icons"
            if not os.path.exists(icons_dir):
                os.makedirs(icons_dir)
            
            base_name = os.path.basename(path)
            dest_path = os.path.join(icons_dir, f"{int(time.time())}_{base_name}")
            try:
                shutil.copyfile(path, dest_path)
                self.btn_icon = dest_path
            except Exception:
                self.btn_icon = path

            self.settings[f"{self.button_id}_icon"] = self.btn_icon
            self.update_ui()
            self.main_app.save_settings()


class StreamDeckApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("나만의 스트림덱") 
        self.setMinimumSize(320, 320) 
        if os.path.exists("icon.png"):
            self.setWindowIcon(QIcon("icon.png"))
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 프로그램 실행 시 자동 실행 등록
        set_autostart(True)

        self.themes = {
            "다크 네이비 (기본)": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f2027, stop:0.5 #203a43, stop:1 #2c5364)",
            "시크한 블랙": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #141414, stop:0.5 #282828, stop:1 #3c3c3c)",
            "네온 블루": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0575E6, stop:0.5 #00f2fe, stop:1 #1e3c72)",
            "에메랄드 그린": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #134E5E, stop:0.5 #71B280, stop:1 #11998e)",
            "로열 퍼플": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2b5876, stop:0.5 #4e4376, stop:1 #4e4376)"
        }

        self.settings = self.load_settings()
        self.apply_theme_stylesheet()
        
        self.delete_mode = False 
        self.edit_mode = False  
        self.temp_pages_data = [] 
        self.selected_for_deletion = []
        self.delete_execute_buttons = []
        self.is_pinned = False  

        self.layout_modes = [
            (3, 2),  # 0: 3x2
            (3, 3),  # 1: 3x3
            (4, 2),  # 2: 4x2
            (4, 3)   # 3: 4x3
        ]
        self.current_mode_idx = 0  

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        self.display_label = DisplayLabel(self)
        right_layout.addWidget(self.display_label, alignment=Qt.AlignCenter)

        media_box = QWidget()
        media_layout = QVBoxLayout(media_box)
        media_layout.setContentsMargins(5, 5, 5, 5)
        media_layout.setSpacing(6)
        
        media_title = QLabel("🎛️ 미디어 제어")
        media_title.setStyleSheet("color: white; font-weight: bold; font-size: 11px; background: transparent;")
        media_title.setAlignment(Qt.AlignCenter)
        media_layout.addWidget(media_title)

        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(4)
        
        btn_prev_track = QPushButton("⏮")
        btn_prev_track.setFixedSize(44, 30)
        btn_prev_track.setStyleSheet("background-color: rgba(255,255,255,0.15); color: white; border-radius: 6px; font-weight: bold;")
        btn_prev_track.clicked.connect(lambda: pyautogui.press('prevtrack'))

        btn_play_pause = QPushButton("⏯")
        btn_play_pause.setFixedSize(44, 30)
        btn_play_pause.setStyleSheet("background-color: rgba(52,152,219,0.5); color: white; border-radius: 6px; font-weight: bold;")
        btn_play_pause.clicked.connect(lambda: pyautogui.press('playpause'))

        btn_next_track = QPushButton("⏭")
        btn_next_track.setFixedSize(44, 30)
        btn_next_track.setStyleSheet("background-color: rgba(255,255,255,0.15); color: white; border-radius: 6px; font-weight: bold;")
        btn_next_track.clicked.connect(lambda: pyautogui.press('nexttrack'))

        row1_layout.addWidget(btn_prev_track)
        row1_layout.addWidget(btn_play_pause)
        row1_layout.addWidget(btn_next_track)
        media_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(4)

        btn_mute = QPushButton("🔇")
        btn_mute.setFixedSize(44, 30)
        btn_mute.setStyleSheet("background-color: rgba(192,57,43,0.5); color: white; border-radius: 6px; font-weight: bold;")
        btn_mute.clicked.connect(lambda: pyautogui.press('volumemute'))

        btn_vdown = QPushButton("🔉")
        btn_vdown.setFixedSize(44, 30)
        btn_vdown.setStyleSheet("background-color: rgba(255,255,255,0.15); color: white; border-radius: 6px; font-weight: bold;")
        btn_vdown.clicked.connect(lambda: pyautogui.press('volumedown'))

        btn_vup = QPushButton("🔊")
        btn_vup.setFixedSize(44, 30)
        btn_vup.setStyleSheet("background-color: rgba(39,174,96,0.5); color: white; border-radius: 6px; font-weight: bold;")
        btn_vup.clicked.connect(lambda: pyautogui.press('volumeup'))

        row2_layout.addWidget(btn_mute)
        row2_layout.addWidget(btn_vdown)
        row2_layout.addWidget(btn_vup)
        media_layout.addLayout(row2_layout)

        opacity_label = QLabel("✨ 창 불투명도")
        opacity_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 10px; background: transparent;")
        opacity_label.setAlignment(Qt.AlignCenter)
        media_layout.addWidget(opacity_label)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(15, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.15); 
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(52, 152, 219, 0.5);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.vol_slider.valueChanged.connect(self.on_opacity_changed)
        media_layout.addWidget(self.vol_slider)

        right_layout.addWidget(media_box, alignment=Qt.AlignCenter)
        main_layout.addWidget(right_panel)

        self.setCentralWidget(central_widget)

        self.dynamic_button_widgets = []
        self.refresh_pages()
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        
        tray_menu = QMenu(self)
        show_action = QAction("스트림덱 열기", self)
        show_action.triggered.connect(self.show)
        
        # 완전히 종료할 때만 자동 실행 레지스트리 제거
        def full_quit():
            set_autostart(False)
            QApplication.instance().quit()

        quit_action = QAction("완전히 종료", self)
        quit_action.triggered.connect(full_quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

        self.dragging = False
        self.drag_position = QPoint()

        if keyboard:
            try:
                keyboard.add_hotkey('ctrl+shift+space', self.toggle_window_visibility_global)
            except Exception:
                pass

    def apply_theme_stylesheet(self):
        bg_image_path = self.settings.get("bg_image", "")
        if bg_image_path and os.path.exists(bg_image_path):
            normalized_path = os.path.abspath(bg_image_path).replace(os.sep, '/')
            bg_style = f"background-image: url('{normalized_path}'); background-position: center; background-repeat: no-repeat;"
        else:
            theme_name = self.settings.get("theme_name", "다크 네이비 (기본)")
            gradient_bg = self.themes.get(theme_name, self.themes["다크 네이비 (기본)"])
            bg_style = f"background: {gradient_bg};"

        self.setStyleSheet(f"""
            QMainWindow {{
                background: transparent;
            }}
            QWidget#centralWidget {{
                {bg_style}
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }}
            
            QMenu {{
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 6px;
                color: #1f2937;
                font-size: 12px;
                font-weight: bold;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: #f3f4f6;
            }}
        """)

    def show_glass_message(self, title, text, is_question=False):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        
        if os.path.exists("icon.png"):
            pixmap = QPixmap("icon.png").scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            msg_box.setIconPixmap(pixmap)

        if is_question:
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.button(QMessageBox.Yes).setText("예")
            msg_box.button(QMessageBox.No).setText("아니오")
        else:
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.button(QMessageBox.Ok).setText("확인")

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 20px;
            }
            QLabel {
                color: #1f2937;
                background: transparent;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d1d5db;
                border: 1px solid #9ca3af;
            }
            QPushButton:pressed {
                background-color: #9ca3af;
            }
        """)
        return msg_box.exec()

    def change_theme(self):
        theme_list = list(self.themes.keys())
        current_theme = self.settings.get("theme_name", "다크 네이비 (기본)")

        dialog = QInputDialog(self)
        dialog.setWindowTitle("UI 테마 변경")
        dialog.setLabelText("원하는 컬러 테마를 선택하세요:")
        dialog.setComboBoxItems(theme_list)
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 20px;
                color: #1f2937;
            }
            QLabel { color: #1f2937; background: transparent; font-weight: bold; font-size: 13px; }
            QComboBox {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #1f2937;
                padding: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1f2937;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                outline: none;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d1d5db; }
        """)
        if dialog.exec() == QInputDialog.Accepted:
            selected_theme = dialog.textValue()
            if selected_theme:
                self.settings["theme_name"] = selected_theme
                self.settings["bg_image"] = ""
                self.save_settings()
                self.apply_theme_stylesheet()
                self.show_glass_message("완료", f"[{selected_theme}] 테마가 적용되었습니다!")

    def set_custom_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "배경 이미지 선택", "", "이미지 파일 (*.png *.jpg *.jpeg)")
        if path:
            bg_dir = "backgrounds"
            if not os.path.exists(bg_dir):
                os.makedirs(bg_dir)
            
            base_name = os.path.basename(path)
            dest_path = os.path.join(bg_dir, f"{int(time.time())}_{base_name}")
            try:
                shutil.copyfile(path, dest_path)
                self.settings["bg_image"] = dest_path
            except Exception:
                self.settings["bg_image"] = path

            self.save_settings()
            self.apply_theme_stylesheet()
            self.show_glass_message("완료", "커스텀 배경 이미지가 적용되었습니다!")

    def reset_custom_background(self):
        self.settings["bg_image"] = ""
        self.save_settings()
        self.apply_theme_stylesheet()
        self.show_glass_message("완료", "기본 테마 배경으로 초기화되었습니다!")

    def on_opacity_changed(self, value):
        opacity = value / 100.0
        self.setWindowOpacity(opacity)

    def toggle_window_visibility_global(self):
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(self, "toggle_visibility_slot", Qt.QueuedConnection)

    def toggle_visibility_slot(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.is_pinned:
                return
            
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.dragging = True
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_pinned:
            return

        if self.dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        current_pos = self.pos()
        
        if self.is_pinned:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.show()
            self.move(current_pos)
            try:
                hwnd = int(self.winId())
                ctypes.windll.user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
            except Exception:
                pass
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.show()
            self.move(current_pos)
            try:
                hwnd = int(self.winId())
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
            except Exception:
                pass
                
        self.refresh_pages()

    def zoom_in(self):
        if self.current_mode_idx > 0:
            self.current_mode_idx -= 1
            self.refresh_pages()

    def zoom_out(self):
        if self.current_mode_idx < len(self.layout_modes) - 1:
            self.current_mode_idx += 1
            self.refresh_pages()

    def toggle_edit_mode(self):
        if not self.edit_mode:
            self.edit_mode = True
            pages_data = self.get_pages_data_from_settings()
            self.temp_pages_data = [list(p) for p in pages_data]
            current_idx = self.stacked_widget.currentIndex()
            self.refresh_pages()
            self.stacked_widget.setCurrentIndex(current_idx)
        else:
            reply = self.show_glass_message('편집 저장 확인', '변경된 버튼 배치를 저장하시겠습니까?', is_question=True)
            if reply == QMessageBox.Yes:
                self.save_pages_data_to_settings(self.temp_pages_data)
            
            self.edit_mode = False
            current_idx = self.stacked_widget.currentIndex()
            self.refresh_pages()
            self.stacked_widget.setCurrentIndex(current_idx)

    def cancel_edit_mode(self):
        self.edit_mode = False
        current_idx = self.stacked_widget.currentIndex()
        self.refresh_pages()
        self.stacked_widget.setCurrentIndex(current_idx)

    def swap_temp_buttons(self, page_idx, src_slot, target_slot):
        pages_data = self.temp_pages_data if self.edit_mode else self.get_pages_data_from_settings()
        
        while len(pages_data) <= page_idx:
            pages_data.append([])
            
        page_list = pages_data[page_idx]
        while len(page_list) <= max(src_slot, target_slot):
            page_list.append("")

        page_list[src_slot], page_list[target_slot] = page_list[target_slot], page_list[src_slot]
        
        if not self.edit_mode:
            self.save_pages_data_to_settings(pages_data)

        current_idx = self.stacked_widget.currentIndex()
        self.refresh_pages()
        self.stacked_widget.setCurrentIndex(current_idx)

    def edit_page_title(self, page_idx):
        page_titles = self.settings.setdefault("page_titles", {})
        current_title = page_titles.get(str(page_idx), f"페이지 {page_idx + 1}")
        
        dialog = QInputDialog(self)
        dialog.setWindowTitle("페이지 이름 변경")
        dialog.setLabelText("새 페이지 이름:")
        dialog.setTextValue(current_title)
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #ffffff;
                border: 2px solid #d1d5db;
                border-radius: 20px;
                color: #1f2937;
            }
            QLabel { color: #1f2937; background: transparent; font-weight: bold; font-size: 13px; }
            QLineEdit {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                color: #1f2937;
                padding: 6px;
            }
            QPushButton {
                background-color: #e5e7eb;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d1d5db; }
        """)
        if dialog.exec() == QInputDialog.Accepted:
            new_title = dialog.textValue()
            if new_title:
                page_titles[str(page_idx)] = new_title
                self.save_settings()
                self.refresh_pages()
                self.stacked_widget.setCurrentIndex(page_idx)

    def export_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "설정 백업 내보내기", "streamdeck_backup.json", "JSON 파일 (*.json)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.settings, f, ensure_ascii=False, indent=4)
                self.show_glass_message("성공", "설정이 성공적으로 백업되었습니다!")
            except Exception as e:
                self.show_glass_message("오류", f"백업 중 오류가 발생했습니다:\n{e}")

    def import_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "설정 백업 불러오기", "", "JSON 파일 (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.settings = data
                    self.save_settings()
                    self.apply_theme_stylesheet()
                    self.refresh_pages()
                    self.show_glass_message("성공", "설정을 성공적으로 복원했습니다!")
                else:
                    self.show_glass_message("경고", "올바른 설정 파일 형식이 아닙니다.")
            except Exception as e:
                self.show_glass_message("오류", f"설정을 불러올 수 없습니다:\n{e}")

    def closeEvent(self, event: QCloseEvent):
        event.ignore() 
        self.hide()    
        self.tray_icon.showMessage(
            "나만의 스트림덱",
            "프로그램이 백그라운드에서 실행 중입니다.\n트레이 아이콘을 더블클릭하면 다시 열립니다.",
            QSystemTrayIcon.Information,
            2000 
        )

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick: 
            self.show()
            self.activateWindow()

    def load_settings(self):
        if not os.path.exists("settings.json"):
            initial_data = {
                "dynamic_buttons": [],
                "pages_data": [],
                "page_titles": {},
                "theme_name": "다크 네이비 (기본)",
                "bg_image": "",
                "display_icon": ""
            }
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=4)
            return initial_data
        else:
            with open("settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if "pages_data" not in data:
                    data["pages_data"] = []
                return data

    def save_settings(self):
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def get_pages_data_from_settings(self):
        pages_data = self.settings.get("pages_data", [])
        if not pages_data:
            dyn_list = self.settings.get("dynamic_buttons", [])
            if dyn_list:
                default_page_size = 6
                pages_data = [dyn_list[i:i + default_page_size] for i in range(0, len(dyn_list), default_page_size)]
            else:
                pages_data = [[]]
        return pages_data

    def save_pages_data_to_settings(self, pages_data):
        self.settings["pages_data"] = pages_data
        flat_list = []
        for p in pages_data:
            flat_list.extend([b for b in p if b])
        self.settings["dynamic_buttons"] = flat_list
        self.save_settings()

    def refresh_pages(self):
        while self.stacked_widget.count() > 0:
            widget = self.stacked_widget.widget(0)
            self.stacked_widget.removeWidget(widget)
            widget.deleteLater()
            
        self.dynamic_button_widgets.clear()
        self.delete_execute_buttons.clear()
        
        pages_data = self.temp_pages_data if self.edit_mode else self.get_pages_data_from_settings()
        if not pages_data:
            pages_data = [[]]
            
        total_pages = len(pages_data)
        page_titles = self.settings.get("page_titles", {})

        for page_idx in range(total_pages):
            page_widget = QWidget()
            page_layout = QVBoxLayout(page_widget)
            
            cols, rows = self.layout_modes[self.current_mode_idx]
            page_size = cols * rows

            if rows == 3:
                page_layout.setAlignment(Qt.AlignTop)
                page_layout.setSpacing(6)
                page_layout.setContentsMargins(10, 4, 10, 8)
            else:
                page_layout.setAlignment(Qt.AlignCenter)
                page_layout.setSpacing(5)
                page_layout.setContentsMargins(10, 10, 10, 10)

            default_title_text = f"페이지 {page_idx + 1}"
            page_title_str = page_titles.get(str(page_idx), default_title_text)
            
            lbl_title = QLabel(f"{page_title_str}")
            lbl_title.setStyleSheet("color: rgba(255,255,255,0.85); font-weight: bold; background: transparent; font-size: 16px;")
            lbl_title.setAlignment(Qt.AlignCenter)
            lbl_title.setCursor(Qt.PointingHandCursor)
            lbl_title.mousePressEvent = lambda event, p=page_idx: self.edit_page_title(p)
            page_layout.addWidget(lbl_title)

            grid_widget = QWidget()
            grid_layout = QGridLayout(grid_widget)
            grid_layout.setSpacing(5) 
            grid_layout.setContentsMargins(0, 0, 0, 0) 
            
            page_buttons = pages_data[page_idx] if page_idx < len(pages_data) else []
            
            for i in range(page_size):
                row = i // cols
                col = i % cols
                if i < len(page_buttons) and page_buttons[i]:
                    btn_id = page_buttons[i]
                    new_btn = CustomButton(btn_id, "빈 버튼", "", self, page_idx, i)
                else:
                    new_btn = CustomButton(f"empty_{page_idx}_{i}", "빈 공간", "", self, page_idx, i)
                    new_btn.setEnabled(False)
                    new_btn.setStyleSheet("background-color: rgba(255,255,255,0.02); border: 1px dashed rgba(255,255,255,0.1); border-radius: 15px;")
                
                grid_layout.addWidget(new_btn, row, col)
                self.dynamic_button_widgets.append(new_btn)
                
            page_layout.addWidget(grid_widget, alignment=Qt.AlignCenter)
            
            control_layout = QHBoxLayout()
            control_layout.setSpacing(4)

            if not self.delete_mode:
                if not self.edit_mode:
                    btn_add = QPushButton("➕ 추가")
                    btn_add.setFixedSize(50, 32)
                    btn_add.setStyleSheet("background-color: rgba(39, 174, 96, 0.5); color: white; font-weight: bold; border-radius: 8px; font-size: 10px;")
                    btn_add.clicked.connect(self.add_new_button)
                    
                    btn_remove = QPushButton("➖ 삭제")
                    btn_remove.setFixedSize(50, 32)
                    btn_remove.setStyleSheet("background-color: rgba(192, 57, 43, 0.5); color: white; font-weight: bold; border-radius: 8px; font-size: 10px;")
                    btn_remove.clicked.connect(self.toggle_delete_mode)

                    btn_edit = QPushButton("편집")
                    btn_edit.setFixedSize(42, 32)
                    btn_edit.setStyleSheet("background-color: rgba(41, 128, 185, 0.6); color: white; font-weight: bold; border-radius: 8px; font-size: 10px;")
                    btn_edit.clicked.connect(self.toggle_edit_mode)

                    btn_pin = QPushButton("📌" if not self.is_pinned else "🔒")
                    btn_pin.setFixedSize(28, 32)
                    btn_pin.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); color: white; border-radius: 8px; font-size: 10px;")
                    btn_pin.clicked.connect(self.toggle_pin)

                    btn_zoom_in = QPushButton("+")
                    btn_zoom_in.setFixedSize(24, 32)
                    btn_zoom_in.setStyleSheet("background-color: rgba(255, 255, 255, 0.15); color: white; font-weight: bold; border-radius: 8px; font-size: 13px;")
                    btn_zoom_in.clicked.connect(self.zoom_in)

                    btn_zoom_out = QPushButton("-")
                    btn_zoom_out.setFixedSize(24, 32)
                    btn_zoom_out.setStyleSheet("background-color: rgba(255, 255, 255, 0.15); color: white; font-weight: bold; border-radius: 8px; font-size: 13px;")
                    btn_zoom_out.clicked.connect(self.zoom_out)

                    btn_backup = QPushButton("⚙️")
                    btn_backup.setFixedSize(28, 32)
                    btn_backup.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(155, 89, 182, 0.6); 
                            color: white; 
                            font-weight: bold; 
                            border-radius: 8px; 
                            font-size: 13px; 
                            text-align: center; 
                            padding: 0px;
                        }
                        QPushButton::menu-indicator { 
                            image: none; 
                        }
                    """)
                    
                    backup_menu = QMenu(self)
                    act_export = QAction("💾 설정 백업하기 (내보내기)", self)
                    act_export.triggered.connect(self.export_settings)
                    act_import = QAction("📂 설정 복원하기 (불러오기)", self)
                    act_import.triggered.connect(self.import_settings)
                    act_theme = QAction("🎨 UI 컬러 테마 변경", self)
                    act_theme.triggered.connect(self.change_theme)
                    act_bg_img = QAction("🖼️ 창 배경 이미지 설정", self)
                    act_bg_img.triggered.connect(self.set_custom_background)
                    act_bg_reset = QAction("🔄 배경 이미지 초기화 (기본 테마)", self)
                    act_bg_reset.triggered.connect(self.reset_custom_background)
                    
                    backup_menu.addAction(act_export)
                    backup_menu.addAction(act_import)
                    backup_menu.addSeparator()
                    backup_menu.addAction(act_theme)
                    backup_menu.addAction(act_bg_img)
                    backup_menu.addAction(act_bg_reset)
                    
                    btn_backup.clicked.connect(lambda checked, b=btn_backup, m=backup_menu: m.exec(b.mapToGlobal(QPoint(0, b.height() + 2))))

                    btn_exit = QPushButton("❌")
                    btn_exit.setFixedSize(28, 32)
                    btn_exit.setStyleSheet("background-color: rgba(100, 100, 100, 0.5); color: white; font-weight: bold; border-radius: 8px; font-size: 10px;")
                    btn_exit.clicked.connect(QApplication.instance().quit)
                    
                    control_layout.addWidget(btn_add)
                    control_layout.addWidget(btn_remove)
                    control_layout.addWidget(btn_edit)
                    control_layout.addWidget(btn_pin)
                    control_layout.addWidget(btn_zoom_in)
                    control_layout.addWidget(btn_zoom_out)
                    control_layout.addWidget(btn_backup)
                    control_layout.addWidget(btn_exit)
                else:
                    btn_save = QPushButton("💾 저장")
                    btn_save.setFixedSize(110, 32)
                    btn_save.setStyleSheet("background-color: rgba(39, 174, 96, 0.8); color: white; font-weight: bold; border-radius: 8px; font-size: 12px;")
                    btn_save.clicked.connect(self.toggle_edit_mode)

                    btn_cancel_edit = QPushButton("❌ 취소")
                    btn_cancel_edit.setFixedSize(110, 32)
                    btn_cancel_edit.setStyleSheet("background-color: rgba(192, 57, 43, 0.6); color: white; font-weight: bold; border-radius: 8px; font-size: 12px;")
                    btn_cancel_edit.clicked.connect(self.cancel_edit_mode)

                    control_layout.addWidget(btn_save)
                    control_layout.addWidget(btn_cancel_edit)
            else:
                btn_execute = QPushButton("🗑️ 0개 삭제")
                btn_execute.setFixedSize(110, 32)
                btn_execute.setEnabled(False)
                btn_execute.setStyleSheet("background-color: rgba(255, 50, 50, 0.3); color: white; font-weight: bold; border-radius: 8px; font-size: 12px;")
                btn_execute.clicked.connect(self.execute_bulk_delete)
                self.delete_execute_buttons.append(btn_execute)
                
                btn_cancel = QPushButton("❌ 취소")
                btn_cancel.setFixedSize(110, 32)
                btn_cancel.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); color: white; font-weight: bold; border-radius: 8px; font-size: 12px;")
                btn_cancel.clicked.connect(self.toggle_delete_mode)
                
                control_layout.addWidget(btn_execute)
                control_layout.addWidget(btn_cancel)
                
            page_layout.addLayout(control_layout)
            
            nav_layout = QHBoxLayout()
            btn_prev = QPushButton("◀ 이전")
            btn_prev.setFixedSize(75, 28)
            if page_idx == 0:
                btn_prev.setEnabled(False)
                btn_prev.setStyleSheet("background-color: rgba(0,0,0,0.3); color: gray; border-radius: 5px; font-size: 11px;")
            else:
                btn_prev.setStyleSheet("background-color: rgba(255,255,255,0.2); color: white; border-radius: 5px; font-size: 11px;")
                btn_prev.clicked.connect(lambda checked=False, idx=page_idx: self.stacked_widget.setCurrentIndex(idx - 1))
                
            lbl_page = QLabel(f"{page_idx + 1} / {total_pages}")
            lbl_page.setStyleSheet("color: white; font-weight: bold; background: transparent; font-size: 12px;")
            lbl_page.setAlignment(Qt.AlignCenter)
            
            btn_next = QPushButton("다음 ▶")
            btn_next.setFixedSize(75, 28)
            if page_idx == total_pages - 1:
                btn_next.setEnabled(False)
                btn_next.setStyleSheet("background-color: rgba(0,0,0,0.3); color: gray; border-radius: 5px; font-size: 11px;")
            else:
                btn_next.setStyleSheet("background-color: rgba(255,255,255,0.2); color: white; border-radius: 5px; font-size: 11px;")
                btn_next.clicked.connect(lambda checked=False, idx=page_idx: self.stacked_widget.setCurrentIndex(idx + 1))
                
            nav_layout.addWidget(btn_prev)
            nav_layout.addWidget(lbl_page)
            nav_layout.addWidget(btn_next)
            
            page_layout.addLayout(nav_layout)
            self.stacked_widget.addWidget(page_widget)

    def add_new_button(self):
        pages_data = self.get_pages_data_from_settings()
        if not pages_data:
            pages_data = [[]]
            
        current_page_idx = self.stacked_widget.currentIndex()
        if current_page_idx >= len(pages_data):
            current_page_idx = len(pages_data) - 1
            
        cols, rows = self.layout_modes[self.current_mode_idx]
        page_size = cols * rows
        
        target_page_idx = current_page_idx
        if len(pages_data[target_page_idx]) >= page_size:
            target_page_idx += 1
            while len(pages_data) <= target_page_idx:
                pages_data.append([])

        new_id = f"dyn_{int(time.time() * 1000)}_{target_page_idx}_{len(pages_data[target_page_idx])}"
        pages_data[target_page_idx].append(new_id)
        
        self.settings[f"{new_id}_name"] = "빈 버튼"
        self.settings[f"{new_id}_path"] = ""
        self.settings[f"{new_id}_icon"] = ""
        
        self.save_pages_data_to_settings(pages_data)
        
        self.refresh_pages()
        self.stacked_widget.setCurrentIndex(target_page_idx)

    def toggle_delete_mode(self):
        self.delete_mode = not self.delete_mode
        self.selected_for_deletion.clear()
        
        current_idx = self.stacked_widget.currentIndex() 
        self.refresh_pages() 
        self.stacked_widget.setCurrentIndex(current_idx)

    def update_delete_ui(self):
        count = len(self.selected_for_deletion)
        for btn in self.delete_execute_buttons:
            btn.setText(f"🗑️ {count}개 삭제")
            if count > 0:
                btn.setEnabled(True)
                btn.setStyleSheet("background-color: rgba(255, 50, 50, 0.8); color: white; font-weight: bold; border-radius: 10px; border: 1px solid #ff5555;")
            else:
                btn.setEnabled(False)
                btn.setStyleSheet("background-color: rgba(255, 50, 50, 0.3); color: white; font-weight: bold; border-radius: 10px;")

    def execute_bulk_delete(self):
        count = len(self.selected_for_deletion)
        if count == 0:
            return
            
        reply = self.show_glass_message("다중 삭제 확인", f"선택한 {count}개의 버튼을 정말로 삭제하시겠습니까?\n(선택한 자리의 빈자리는 해당 페이지 내에서 정리됩니다.)", is_question=True)
        
        if reply == QMessageBox.Yes:
            pages_data = self.get_pages_data_from_settings()
            new_pages_data = []
            
            for page in pages_data:
                cleaned_page = [b for b in page if b and b not in self.selected_for_deletion]
                new_pages_data.append(cleaned_page)
                
            new_pages_data = [p for p in new_pages_data if len(p) > 0]
            if not new_pages_data:
                new_pages_data = [[]]
                
            for btn_id in self.selected_for_deletion:
                self.settings.pop(f"{btn_id}_name", None)
                self.settings.pop(f"{btn_id}_path", None)
                self.settings.pop(f"{btn_id}_icon", None)
                self.settings.pop(f"{btn_id}_hotkey", None)
                
            self.save_pages_data_to_settings(new_pages_data)
            
            current_idx = self.stacked_widget.currentIndex()
            self.delete_mode = False
            self.selected_for_deletion.clear()
            self.refresh_pages()
            
            new_max_idx = self.stacked_widget.count() - 1
            if current_idx > new_max_idx:
                self.stacked_widget.setCurrentIndex(new_max_idx)
            else:
                self.stacked_widget.setCurrentIndex(current_idx)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = StreamDeckApp()
    window.show()
    sys.exit(app.exec())