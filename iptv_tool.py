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

# 修复临时目录路径问题
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    os.environ['PATH'] = os.pathsep.join([
        os.path.join(base_path, 'cv2'),
        os.path.join(base_path, 'numpy', '.libs'),
        os.environ['PATH']
    ])

# 获取文档目录路径
def get_documents_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        return winreg.QueryValueEx(key, "Personal")[0]
    except Exception:
        return os.path.expanduser('~\\Documents')

# 省份列表
PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"
]

# 运营商列表
OPERATORS = ["电信", "移动", "联通", "广电"]

class IPTVApp:
    def __init__(self, root):
        self.root = root
        root.title("IPTV组播源采集工具 v2.1")
        root.geometry("400x300")
        
        # 创建主容器
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控件初始化
        self._create_widgets(main_frame)

    def _create_widgets(self, parent):
        """创建界面控件"""
        ttk.Label(parent, text="Quake API密钥:").grid(row=0, column=0, sticky=tk.W)
        self.api_entry = ttk.Entry(parent, width=30)
        self.api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(parent, text="选择省份:").grid(row=1, column=0, sticky=tk.W)
        self.province_combo = ttk.Combobox(parent, values=PROVINCES, state="readonly")
        self.province_combo.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(parent, text="选择运营商:").grid(row=2, column=0, sticky=tk.W)
        self.operator_combo = ttk.Combobox(parent, values=OPERATORS, state="readonly")
        self.operator_combo.grid(row=2, column=1, padx=5, pady=5)
        
        self.progress = ttk.Progressbar(parent, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        self.status = ttk.Label(parent, text="就绪")
        self.status.grid(row=4, column=0, columnspan=2)
        
        self.start_btn = ttk.Button(parent, text="开始采集", command=self.start_process)
        self.start_btn.grid(row=5, column=0, columnspan=2, pady=10)

    def start_process(self):
        """启动采集流程"""
        api_key = self.api_entry.get().strip()
        province = self.province_combo.get()
        operator = self.operator_combo.get()
        
        if not self._validate_input(api_key, province, operator):
            return
            
        self._disable_ui()
        thread = threading.Thread(
            target=self.run_collection,
            args=(api_key, province, operator),
            daemon=True
        )
        thread.start()

    def _validate_input(self, api_key, province, operator):
        """验证输入有效性"""
        errors = []
        if not api_key:
            errors.append("请先输入API密钥")
        if not province:
            errors.append("请选择省份")
        if not operator:
            errors.append("请选择运营商")
            
        if errors:
            self.show_error("，".join(errors))
            return False
        return True

    def _disable_ui(self):
        """禁用界面控件"""
        self.start_btn.config(state=tk.DISABLED)
        self.status.config(text="正在启动采集任务...")

    def run_collection(self, api_key, province, operator):
        """执行采集任务"""
        try:
            # 创建必要目录
            self._create_config_file(province, operator)
            
            # 执行搜索
            self._update_status("正在搜索节点...")
            urls = self.quake_search(api_key, province, operator)
            print(f"找到{len(urls)}个潜在节点")
            
            # 检测有效性
            self._update_status("正在检测节点有效性...")
            valid_urls = self.check_urls(urls, "239.0.0.1:1234")
            print(f"检测到{len(valid_urls)}个有效节点")
            
            # 保存结果
            if valid_urls:
                success = self.save_playlist(province, operator, valid_urls)
                if success:
                    self.show_success(f"成功生成{len(valid_urls)}个节点")
                else:
                    self.show_error("文件保存失败")
            else:
                self.show_error("未找到有效节点")
                
        except Exception as e:
            error_msg = f"运行错误：{str(e)}"
            print(error_msg)
            self.show_error(error_msg)
        finally:
            self._enable_ui()

    def _create_config_file(self, province, operator):
        """创建示例配置文件"""
        config_dir = os.path.join(get_documents_path(), "IPTV-Configs")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, f"{province}_{operator}.txt")
        if not os.path.exists(config_file):
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\n")
                f.write("CCTV测试频道,rtp://239.0.0.1:1234\n")

    def quake_search(self, api_key, province, operator):
        """执行Quake搜索"""
        headers = {"X-QuakeToken": api_key, "Content-Type": "application/json"}
        result_urls = set()
        
        try:
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{operator}"',
                "size": 50,
                "include": ["ip", "port"]
            }
            
            print(f"正在发送请求：{json.dumps(query, indent=2)}")
            response = requests.post(
                "https://quake.360.net/api/v3/search/quake_service",
                headers=headers,
                json=query,
                timeout=20
            )
            response.raise_for_status()
            
            data = response.json()
            print(f"收到响应：{json.dumps(data, indent=2)}")
            
            if data.get("code") != 0:
                raise Exception(f"API错误：{data.get('message', '未知错误')}")
                
            for item in data.get("data", []):
                ip = item.get("ip", "")
                port = str(item.get("port", ""))
                if ip and port.isdigit():
                    result_urls.add(f"http://{ip}:{port}")
                    
            return list(result_urls)
            
        except Exception as e:
            raise Exception(f"搜索失败: {str(e)}")

    def check_urls(self, urls, mcast):
        """检测URL有效性"""
        valid = []
        progress = tqdm(urls, desc="检测节点", unit="个", leave=False)
        
        for url in progress:
            try:
                cap = cv2.VideoCapture(f"{url}/rtp/{mcast}")
                if cap.isOpened() and cap.read()[0]:
                    valid.append(url)
                cap.release()
                time.sleep(0.2)
            except Exception as e:
                print(f"检测异常：{str(e)}")
            finally:
                progress.set_postfix(valid=len(valid))
                
        return valid

    def save_playlist(self, province, operator, urls):
        """保存播放列表"""
        try:
            output_dir = os.path.join(get_documents_path(), "IPTV-Playlists")
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{province}{operator}.txt")
            
            print(f"正在保存到：{output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\n")
                for url in urls:
                    f.write(f"CCTV测试频道,{url}/rtp/239.0.0.1:1234\n")
                f.flush()
                os.fsync(f.fileno())
            
            print("文件保存成功")
            return os.path.exists(output_file)
            
        except Exception as e:
            print(f"保存失败：{str(e)}")
            return False

    def _update_status(self, text):
        """更新状态信息"""
        self.root.after(0, lambda: self.status.config(text=text))

    def show_error(self, message):
        """显示错误信息"""
        self.root.after(0, lambda: 
            self.status.config(text=message, foreground="red"))
        self.root.after(3000, lambda: 
            self.status.config(text="就绪", foreground="black"))

    def show_success(self, message):
        """显示成功信息"""
        self.root.after(0, lambda: 
            self.status.config(text=message, foreground="green"))
        self.root.after(3000, lambda: 
            self.status.config(text="就绪", foreground="black"))

    def _enable_ui(self):
        """启用界面控件"""
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = IPTVApp(root)
    root.mainloop()
