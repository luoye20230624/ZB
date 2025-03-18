# iptv_tool.py
import tkinter as tk
from tkinter import ttk
import os
import time
import requests
import json
import cv2
import random
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
        log_file,
        maxBytes=10*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
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
        root.title("IPTV组播源采集工具 v5.2 by luoye")
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
        """执行采集任务核心逻辑"""
        try:
            # 加载频道配置
            channels = self._load_multicast_channels(province, operator)
            if not channels:
                self._show_error("没有可用的频道配置", persistent=True)
                return
                
            # 提取所有独立组播地址
            mcast_addresses = list({mcast.split('rtp://')[1] for (_, mcast) in channels})
            if len(mcast_addresses) < 3:
                self._show_error("需要至少3个不同的组播地址", persistent=True)
                return
                
            # 获取服务器列表
            servers = self._quake_search(api_key, province, operator)
            valid_servers = []
            
            # 服务器去重
            seen_servers = set()
            for server_url in servers:
                server_identity = server_url.split('//')[1].split('/')[0]  # ip:port
                if server_identity in seen_servers:
                    continue
                seen_servers.add(server_identity)
                
                # 状态页检测
                if not self._check_status_page(server_url):
                    continue
                
                # 随机选择3个地址检测
                success_count = 0
                selected_mcasts = random.sample(mcast_addresses, 3)
                for mcast in selected_mcasts:
                    if self._check_multicast_stream(server_url, mcast):
                        success_count += 1
                    else:
                        break  # 任一失败即终止
                
                # 三个检测都成功则记录
                if success_count == 3:
                    valid_servers.append(server_url)
                    logger.info(f"有效服务器：{server_url} 通过3/3检测")

            # 生成播放列表
            if valid_servers:
                self._save_playlist(province, operator, valid_servers, channels)
                total_entries = len(valid_servers) * len(channels)
                self._show_success(f"发现{len(valid_servers)}个有效服务器，生成{total_entries}条播放地址")
            else:
                self._show_error("未找到有效服务器")
                
        except Exception as e:
            logger.error("采集任务失败", exc_info=True)
            self._show_error(f"错误：{str(e)} (详情请查看error.log)")
        finally:
            self._enable_ui()

    def _load_multicast_channels(self, province, operator):
        """加载频道配置文件"""
        config_file = os.path.join(self.config_dir, f"{province}_{operator}.txt")
        channels = []
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if ',rtp://' not in line:
                        logger.warning(f"配置文件第{line_num}行格式错误：{line}")
                        continue
                        
                    parts = line.split(',rtp://', 1)
                    name = parts[0].strip()
                    address = 'rtp://' + parts[1].strip()
                    channels.append((name, address))
            
            if not channels:
                logger.error("配置文件中未找到有效频道")
            else:
                logger.info(f"成功加载 {len(channels)} 个频道配置")
                
            return channels
        except Exception as e:
            logger.error(f"配置文件加载失败：{str(e)}")
            return []

    def _quake_search(self, api_key, province, operator):
        """执行Quake API查询"""
        try:
            headers = {"X-QuakeToken": api_key}
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{operator}"',
                "size": 50,
                "include": ["ip", "port"]
            }
            
            logger.debug(f"发送API请求：{json.dumps(query, indent=2)}")
            response = requests.post(
                "https://quake.360.net/api/v3/search/quake_service",
                headers=headers,
                json=query,
                timeout=20
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"收到API响应：{json.dumps(data, indent=2)}")
            
            if data.get("code") != 0:
                raise ValueError(f"API错误：{data.get('message', '未知错误')}")
                
            return [
                f"http://{item['ip']}:{item['port']}"
                for item in data.get("data", [])
                if item.get("ip") and str(item.get("port", "")).isdigit()
            ]
            
        except Exception as e:
            logger.error("API请求失败", exc_info=True)
            raise

    def _check_status_page(self, base_url):
        """检测状态页可用性"""
        status_url = f"{base_url}/stat"
        try:
            response = requests.get(status_url, timeout=5)
            if response.status_code == 200:
                logger.debug(f"状态页可访问：{status_url}")
                return True
            logger.debug(f"状态页异常响应：{status_url} ({response.status_code})")
            return False
        except Exception as e:
            logger.debug(f"状态页检测失败：{status_url} - {str(e)}")
            return False

    def _check_multicast_stream(self, base_url, mcast):
        """检测组播流有效性"""
        stream_url = f"{base_url}/rtp/{mcast}"
        result = [False]
        
        def _capture():
            try:
                cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
                if cap.isOpened():
                    start_time = time.time()
                    # 5秒内检测到有效帧即成功
                    while (time.time() - start_time) < 5:
                        ret, _ = cap.read()
                        if ret:
                            result[0] = True
                            break
                        time.sleep(0.1)
                    cap.release()
            except Exception as e:
                logger.debug(f"视频流检测异常：{stream_url} - {str(e)}")
        
        logger.debug(f"开始检测组播流：{stream_url}")
        thread = threading.Thread(target=_capture)
        thread.start()
        thread.join(8)  # 总超时8秒
        
        if result[0]:
            logger.info(f"组播流有效：{stream_url}")
        else:
            logger.debug(f"组播流无效：{stream_url}")
        return result[0]

    def _save_playlist(self, province, operator, servers, channels):
        """保存播放列表文件"""
        try:
            output_file = os.path.join(self.playlist_dir, f"{province}{operator}.txt")
            entry_count = 0
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"{province}{operator},#genre#\n")
                
                # 写入所有有效组合
                seen = set()
                for server in servers:
                    for (name, mcast_full) in channels:
                        mcast = mcast_full.split('rtp://')[1]
                        entry = f"{name},{server}/rtp/{mcast}"
                        if entry not in seen:
                            f.write(f"{entry}\n")
                            seen.add(entry)
                            entry_count += 1
            
            logger.info(f"成功写入 {entry_count} 条播放地址到 {output_file}")
            return True
        except Exception as e:
            logger.error("保存播放列表失败", exc_info=True)
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
        for widget in [self.start_btn, self.clear_btn]:
            widget.config(state=tk.DISABLED)

    def _enable_ui(self):
        """启用界面控件"""
        for widget in [self.start_btn, self.clear_btn]:
            widget.config(state=tk.NORMAL)

if __name__ == "__main__":
    try:
        # 处理控制台编码问题
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
