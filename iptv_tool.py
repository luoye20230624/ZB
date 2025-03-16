# iptv_gui.py
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

# 省份列表（中国所有省份）
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
        root.title("IPTV组播源采集工具 v2.0")
        root.geometry("400x300")
        
        # 创建主容器
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API密钥输入
        ttk.Label(main_frame, text="Quake API密钥:").grid(row=0, column=0, sticky=tk.W)
        self.api_entry = ttk.Entry(main_frame, width=30)
        self.api_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # 省份选择
        ttk.Label(main_frame, text="选择省份:").grid(row=1, column=0, sticky=tk.W)
        self.province_combo = ttk.Combobox(main_frame, values=PROVINCES, state="readonly")
        self.province_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # 运营商选择
        ttk.Label(main_frame, text="选择运营商:").grid(row=2, column=0, sticky=tk.W)
        self.operator_combo = ttk.Combobox(main_frame, values=OPERATORS, state="readonly")
        self.operator_combo.grid(row=2, column=1, padx=5, pady=5)
        
        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        # 状态标签
        self.status = ttk.Label(main_frame, text="就绪")
        self.status.grid(row=4, column=0, columnspan=2)
        
        # 操作按钮
        self.start_btn = ttk.Button(main_frame, text="开始采集", command=self.start_process)
        self.start_btn.grid(row=5, column=0, columnspan=2, pady=10)

    def start_process(self):
        api_key = self.api_entry.get()
        province = self.province_combo.get()
        operator = self.operator_combo.get()
        
        if not api_key:
            self.show_error("请先输入API密钥！")
            return
        if not province:
            self.show_error("请选择省份！")
            return
        if not operator:
            self.show_error("请选择运营商！")
            return
            
        # 禁用按钮防止重复点击
        self.start_btn.config(state=tk.DISABLED)
        self.status.config(text="正在启动采集任务...")
        
        # 使用线程执行耗时操作
        thread = threading.Thread(
            target=self.run_collection,
            args=(api_key, province, operator),
            daemon=True
        )
        thread.start()

    def run_collection(self, api_key, province, operator):
        try:
            # 创建必要目录
            os.makedirs("rtp", exist_ok=True)
            os.makedirs("playlist", exist_ok=True)
            
            # 生成配置文件
            config_file = f"rtp/{province}_{operator}.txt"
            if not os.path.exists(config_file):
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(f"{province}{operator},#genre#\n")
                    f.write(f"CCTV测试频道,rtp://239.0.0.1:1234\n")
            
            # 执行采集逻辑
            self.status.config(text="正在搜索节点...")
            urls = self.quake_search(api_key, province, operator)
            
            self.status.config(text="正在检测节点有效性...")
            valid_urls = self.check_urls(urls, "239.0.0.1:1234")  # 示例组播地址
            
            # 生成播放列表
            if valid_urls:
                self.save_playlist(province, operator, valid_urls)
                self.show_success(f"成功获取{len(valid_urls)}个有效节点！")
            else:
                self.show_error("未找到有效节点")
                
        except Exception as e:
            self.show_error(f"发生错误：{str(e)}")
        finally:
            self.start_btn.config(state=tk.NORMAL)

    def quake_search(self, api_key, province, operator):
        """Quake API搜索逻辑"""
        headers = {"X-QuakeToken": api_key, "Content-Type": "application/json"}
        result_urls = set()
        
        try:
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{operator}"',
                "size": 50,
                "include": ["ip", "port"]
            }
            
            response = requests.post(
                "https://quake.360.net/api/v3/search/quake_service",
                headers=headers,
                json=query,
                timeout=20
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("code") != 0:
                raise Exception(data.get("message", "API返回错误"))
                
            for item in data.get("data", []):
                ip = item.get("ip")
                port = str(item.get("port"))
                if ip and port.isdigit():
                    result_urls.add(f"http://{ip}:{port}")
                    
            return list(result_urls)
            
        except Exception as e:
            raise Exception(f"搜索失败: {str(e)}")

    def check_urls(self, urls, mcast):
        """检测URL有效性"""
        valid = []
        for url in tqdm(urls, desc="检测节点"):
            try:
                cap = cv2.VideoCapture(f"{url}/rtp/{mcast}")
                if cap.isOpened() and cap.read()[0]:
                    valid.append(url)
                cap.release()
                time.sleep(0.2)
            except:
                continue
        return valid

    def save_playlist(self, province, operator, urls):
        """保存播放列表"""
        output_file = f"playlist/{province}{operator}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{province}{operator},#genre#\n")
            for url in urls:
                f.write(f"CCTV测试频道,{url}/rtp/239.0.0.1:1234\n")

    def show_error(self, message):
        self.status.config(text=message, foreground="red")
        self.root.after(3000, lambda: self.status.config(text="就绪", foreground="black"))

    def show_success(self, message):
        self.status.config(text=message, foreground="green")
        self.root.after(3000, lambda: self.status.config(text="就绪", foreground="black"))

if __name__ == "__main__":
    root = tk.Tk()
    app = IPTVApp(root)
    root.mainloop()
