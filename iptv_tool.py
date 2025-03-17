# iptv_tool.py
import tkinter as tk
from tkinter import ttk
import os
import time
import requests
import json
import cv2
import re
from tqdm import tqdm
from datetime import datetime
from opencc import OpenCC
import threading
import sys
import winreg
import logging
from logging.handlers import RotatingFileHandler

# ------------------ 日志配置 ------------------
def setup_logging():
    log_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    log_file = os.path.join(log_dir, 'error.log')
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # 文件日志（最多保留3个10MB文件）
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ------------------ 路径修复 ------------------
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    os.environ['PATH'] = os.pathsep.join([
        os.path.join(base_path, 'cv2'),
        os.path.join(base_path, 'numpy', '.libs'),
        os.environ['PATH']
    ])

# ------------------ 常量定义 ------------------
PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"
]

OPERATORS = ["电信", "移动", "联通", "广电"]

# ------------------ 主程序 ------------------
class IPTVApp:
    def __init__(self, root):
        self.root = root
        root.title("IPTV组播源采集工具 v3.0")
        root.geometry("400x300")
        
        self._create_widgets()
        self._setup_ui()

    def _create_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API密钥
        ttk.Label(self.main_frame, text="Quake API密钥:").grid(row=0, column=0, sticky=tk.W)
        self.api_entry = ttk.Entry(self.main_frame, width=30)
        self.api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # 省份选择
        ttk.Label(self.main_frame, text="选择省份:").grid(row=1, column=0, sticky=tk.W)
        self.province_combo = ttk.Combobox(self.main_frame, values=PROVINCES, state="readonly")
        self.province_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # 运营商选择
        ttk.Label(self.main_frame, text="选择运营商:").grid(row=2, column=0, sticky=tk.W)
        self.operator_combo = ttk.Combobox(self.main_frame, values=OPERATORS, state="readonly")
        self.operator_combo.grid(row=2, column=1, padx=5, pady=5)
        
        # 进度条
        self.progress = ttk.Progressbar(self.main_frame, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # 状态显示
        self.status = ttk.Label(self.main_frame, text="就绪")
        self.status.grid(row=4, column=0, columnspan=2)
        
        # 开始按钮
        self.start_btn = ttk.Button(self.main_frame, text="开始采集", command=self._start_process)
        self.start_btn.grid(row=5, column=0, columnspan=2, pady=10)

    def _setup_ui(self):
        self.province_combo.current(0)
        self.operator_combo.current(0)

    def _start_process(self):
        api_key = self.api_entry.get().strip()
        province = self.province_combo.get()
        operator = self.operator_combo.get()
        
        if not self._validate_input(api_key, province, operator):
            return
        
        self._disable_ui()
        thread = threading.Thread(
            target=self._run_collection,
            args=(api_key, province, operator),
            daemon=True
        )
        thread.start()

    def _validate_input(self, api_key, province, operator):
        if len(api_key) != 32 or not api_key.isalnum():
            self._show_error("API密钥应为32位字母数字组合")
            return False
        if not province or not operator:
            self._show_error("请选择省份和运营商")
            return False
        return True

    def _disable_ui(self):
        self.start_btn.config(state=tk.DISABLED)
        self._update_status("正在启动任务...")

    def _run_collection(self, api_key, province, operator):
        try:
            self._create_config(province, operator)
            urls = self._quake_search(api_key, province, operator)
            valid_urls = self._check_urls(urls, "239.0.0.1:1234")
            
            if valid_urls and self._save_playlist(province, operator, valid_urls):
                self._show_success(f"成功保存{len(valid_urls)}个节点")
            else:
                self._show_error("未找到有效节点")
                
        except Exception as e:
            logger.error("采集任务失败", exc_info=True)
            self._show_error(f"错误：{str(e)} (详情请查看error.log)")
        finally:
            self._enable_ui()

    def _quake_search(self, api_key, province, operator):
        try:
            headers = {"X-QuakeToken": api_key}
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{operator}"',
                "size": 50,
                "include": ["ip", "port"]
            }
            
            logger.debug(f"请求参数：{json.dumps(query, indent=2)}")
            response = requests.post(
                "https://quake.360.net/api/v3/search/quake_service",
                headers=headers,
                json=query,
                timeout=20
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"API响应：{json.dumps(data, indent=2)}")
            
            if data.get("code") != 0:
                raise ValueError(data.get("message", "API返回未知错误"))
                
            return [f"http://{item['ip']}:{item['port']}" 
                   for item in data.get("data", []) 
                   if item.get("ip") and str(item.get("port", "")).isdigit()]
            
        except Exception as e:
            logger.error("API请求失败", exc_info=True)
            raise

    def _check_urls(self, urls, mcast):
        valid = []
        with tqdm(urls, desc="检测节点", unit="个") as pbar:
            for url in pbar:
                try:
                    cap = cv2.VideoCapture(f"{url}/rtp/{mcast}")
                    if cap.isOpened() and cap.read()[0]:
                        valid.append(url)
                    cap.release()
                except Exception as e:
                    logger.warning(f"检测失败：{url} - {str(e)}")
                finally:
                    time.sleep(0.1)
        return valid

    def _save_playlist(self, province, operator, urls):
        try:
            docs_path = os.path.join(os.path.expanduser('~'), 'Documents')
            output_dir = os.path.join(docs_path, "IPTV-Playlists")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{province}{operator}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\n")
                for url in urls:
                    f.write(f"CCTV测试频道,{url}/rtp/239.0.0.1:1234\n")
            
            if os.path.getsize(output_file) < 50:
                raise ValueError("生成文件内容异常")
                
            logger.info(f"文件已保存：{output_file}")
            return True
        except Exception as e:
            logger.error("保存失败", exc_info=True)
            return False

    def _create_config(self, province, operator):
        config_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'IPTV-Configs')
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, f"{province}_{operator}.txt")
        
        if not os.path.exists(config_file):
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\nCCTV测试频道,rtp://239.0.0.1:1234\n")

    def _update_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def _show_error(self, message):
        self.root.after(0, lambda: self.status.config(text=message, foreground="red"))
        self.root.after(3000, lambda: self.status.config(text="就绪", foreground="black"))

    def _show_success(self, message):
        self.root.after(0, lambda: self.status.config(text=message, foreground="green"))
        self.root.after(3000, lambda: self.status.config(text="就绪", foreground="black"))

    def _enable_ui(self):
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = IPTVApp(root)
    root.mainloop()
