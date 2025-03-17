# iptv_tool.py
import tkinter as tk
from tkinter import ttk
import os
import time
import requests
import json
import cv2
from tqdm import tqdm
import threading
import sys
import logging
from logging.handlers import RotatingFileHandler

# ------------------ 日志配置 ------------------
def setup_logging():
    log_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    log_file = os.path.join(log_dir, 'error.log')
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

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
        root.title("IPTV组播源采集工具 v4.4")
        root.geometry("500x400")
        
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self._init_dirs()
        self._create_widgets()
        self._setup_ui()

    def _init_dirs(self):
        """初始化存储目录"""
        self.config_dir = os.path.join(self.base_dir, 'config')
        self.playlist_dir = os.path.join(self.base_dir, 'playlist')
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.playlist_dir, exist_ok=True)

    def _create_widgets(self):
        """创建界面组件"""
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API密钥输入
        ttk.Label(self.main_frame, text="Quake API密钥:").grid(row=0, column=0, sticky=tk.W)
        self.api_entry = ttk.Entry(self.main_frame, width=40)
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
        
        # 状态显示区
        self.status_frame = ttk.LabelFrame(self.main_frame, text="运行状态", padding=10)
        self.status_frame.grid(row=4, column=0, columnspan=2, pady=10, sticky=tk.NSEW)
        
        self.status_text = tk.Text(self.status_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # 操作按钮
        self.btn_frame = ttk.Frame(self.main_frame)
        self.btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.start_btn = ttk.Button(self.btn_frame, text="开始采集", command=self._start_process)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(self.btn_frame, text="清除状态", command=self._clear_status)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

    def _setup_ui(self):
        """初始化界面状态"""
        self.province_combo.current(0)
        self.operator_combo.current(0)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(4, weight=1)

    def _clear_status(self):
        """清除状态信息"""
        self.status_text.configure(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.configure(state=tk.DISABLED)

    def _start_process(self):
        """启动采集流程"""
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
        """验证输入有效性"""
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        
        if len(api_key) != 36:
            self._show_error("API密钥必须为36位字符", persistent=True)
            return False
            
        if not all(c in allowed_chars for c in api_key):
            self._show_error("包含非法字符（只允许字母、数字、-和_）", persistent=True)
            return False
            
        if not province:
            self._show_error("请选择省份", persistent=True)
            return False
            
        if not operator:
            self._show_error("请选择运营商", persistent=True)
            return False
            
        return True

    def _run_collection(self, api_key, province, operator):
        """执行采集任务"""
        try:
            # 从配置文件加载组播地址
            mcast = self._load_multicast_address(province, operator)
            if not mcast:
                self._show_error("找不到组播配置", persistent=True)
                return
                
            urls = self._quake_search(api_key, province, operator)
            valid_urls = self._check_urls(urls, mcast)
            
            if valid_urls:
                self._save_playlist(province, operator, valid_urls, mcast)
                self._show_success(f"成功保存{len(valid_urls)}个有效节点")
            else:
                self._show_error("未找到有效节点")
                
        except Exception as e:
            logger.error("采集任务失败", exc_info=True)
            self._show_error(f"错误：{str(e)} (详情请查看error.log)")
        finally:
            self._enable_ui()

    def _load_multicast_address(self, province, operator):
        """从配置文件加载组播地址"""
        config_file = os.path.join(self.config_dir, f"{province}_{operator}.txt")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f.readlines():
                    if line.startswith("CCTV"):
                        parts = line.split(',')
                        if len(parts) > 1 and 'rtp://' in parts[1]:
                            return parts[1].strip().split('rtp://')[1]
            logger.error(f"配置文件中未找到有效组播地址：{config_file}")
            return None
        except Exception as e:
            logger.error(f"加载配置文件失败：{str(e)}")
            return None

    def _quake_search(self, api_key, province, operator):
        """执行Quake API搜索"""
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
                raise ValueError(f"API错误：{data.get('message', '未知错误')}")
                
            return [f"http://{item['ip']}:{item['port']}" 
                   for item in data.get("data", []) 
                   if item.get("ip") and str(item.get("port", "")).isdigit()]
            
        except Exception as e:
            logger.error("API请求失败", exc_info=True)
            raise

    def _check_urls(self, urls, mcast):
        """双阶段检测流程"""
        valid = []
        try:
            with tqdm(urls, desc="检测节点", unit="个", disable=True) as pbar:
                for url in pbar:
                    try:
                        # 第一阶段：状态页检测
                        if not self._check_status_page(url):
                            continue
                            
                        # 第二阶段：组播流检测
                        if self._check_multicast_stream(url, mcast):
                            valid.append(url)
                            
                    except Exception as e:
                        logger.warning(f"检测异常：{url} - {str(e)}")
                    finally:
                        time.sleep(0.1)
        except Exception as e:
            logger.error(f"检测流程异常：{str(e)}")
        return valid

    def _check_status_page(self, base_url):
        """状态页检测（HTTP 200验证）"""
        status_url = f"{base_url}/stat"
        try:
            response = requests.get(status_url, timeout=5)
            if response.status_code == 200:
                logger.debug(f"状态页可访问：{status_url}")
                return True
        except Exception as e:
            logger.debug(f"状态页检测失败：{status_url} - {str(e)}")
        return False

    def _check_multicast_stream(self, base_url, mcast):
        """组播流检测（带超时）"""
        stream_url = f"{base_url}/rtp/{mcast}"
        result = [False]
        
        def _capture():
            try:
                cap = cv2.VideoCapture(f"rtp://{stream_url}", cv2.CAP_FFMPEG)
                if cap.isOpened() and cap.read()[0]:
                    result[0] = True
                cap.release()
            except:
                pass
        
        thread = threading.Thread(target=_capture)
        thread.start()
        thread.join(5)  # 5秒超时
        
        if result[0]:
            logger.debug(f"组播流有效：rtp://{stream_url}")
            return True
        return False

    def _save_playlist(self, province, operator, urls, mcast):
        """保存播放列表（HTTP协议）"""
        try:
            output_file = os.path.join(self.playlist_dir, f"{province}{operator}.txt")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\n")
                for url in urls:
                    f.write(f"CCTV测试频道,{url}/rtp/{mcast}\n")  # 正确HTTP格式
            
            if os.path.getsize(output_file) < 50:
                raise ValueError("生成文件内容异常")
                
            logger.info(f"播放列表已保存：{output_file}")
            return True
        except Exception as e:
            logger.error("保存失败", exc_info=True)
            return False

    def _show_error(self, message, persistent=False):
        """显示错误信息"""
        self._update_status(f"[错误] {message}", "red", persistent)

    def _show_success(self, message, persistent=False):
        """显示成功信息"""
        self._update_status(f"[成功] {message}", "green", persistent)

    def _update_status(self, message, color="black", persistent=False):
        """更新状态信息"""
        self.status_text.configure(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED, foreground=color)
        
        if not persistent:
            self.root.after(5000, self._clear_status)

    def _disable_ui(self):
        """禁用界面控件"""
        self.start_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)

    def _enable_ui(self):
        """启用界面控件"""
        self.start_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    try:
        if sys.stdout and hasattr(sys.stdout, 'fileno'):
            sys.stdout = open(sys.stdout.fileno(), 
                            mode='w',
                            encoding='utf-8', 
                            errors='ignore')
    except Exception as e:
        sys.stdout = open(os.devnull, 'w')
    
    root = tk.Tk()
    app = IPTVApp(root)
    root.mainloop()
