import sys
import os
import time
import requests
import json
import re
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal


class Worker(QThread):
    status_signal = pyqtSignal(str)

    def __init__(self, api_key, province, isp):
        super().__init__()
        self.api_key = api_key
        self.province = province
        self.isp = isp

    def run(self):
        self.status_signal.emit("采集开始...")
        try:
            # 你原本的quake_search方法和其他逻辑在这里调用
            # 假设我们只是做个示例：
            time.sleep(3)
            self.status_signal.emit(f"采集完成: {self.province} - {self.isp}")
        except Exception as e:
            self.status_signal.emit(f"错误: {str(e)}")


class IPTVCollector(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IPTV 采集工具")
        self.setGeometry(100, 100, 400, 300)

        # 创建控件
        self.api_key_label = QLabel("API Key:")
        self.api_key_input = QLineEdit(self)

        self.province_label = QLabel("选择省份:")
        self.province_combo = QComboBox(self)
        self.province_combo.addItems(["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"])

        self.isp_label = QLabel("选择运营商:")
        self.isp_combo = QComboBox(self)
        self.isp_combo.addItems(["电信", "移动", "联通", "广电"])

        self.status_box = QTextEdit(self)
        self.status_box.setReadOnly(True)

        self.start_button = QPushButton("开始采集", self)
        self.start_button.clicked.connect(self.start_collection)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self.api_key_label)
        layout.addWidget(self.api_key_input)
        layout.addWidget(self.province_label)
        layout.addWidget(self.province_combo)
        layout.addWidget(self.isp_label)
        layout.addWidget(self.isp_combo)
        layout.addWidget(self.status_box)
        layout.addWidget(self.start_button)

        self.setLayout(layout)

    def start_collection(self):
        api_key = self.api_key_input.text()
        province = self.province_combo.currentText()
        isp = self.isp_combo.currentText()

        self.status_box.append(f"开始采集：{province} - {isp}")
        self.worker = Worker(api_key, province, isp)
        self.worker.status_signal.connect(self.update_status)
        self.worker.start()

    def update_status(self, message):
        self.status_box.append(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IPTVCollector()
    window.show()
    sys.exit(app.exec_())
