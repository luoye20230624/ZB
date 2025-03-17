import tkinter as tk
from tkinter import ttk
import threading

class IPTVApp:
    def __init__(self, master):
        self.master = master
        master.title("IPTV采集工具 v5.0")
        master.geometry("600x400")

        # 输入框区域
        self.create_input_fields()
        
        # 状态显示框
        self.status_box = tk.Text(master, height=10, state='disabled')
        self.status_box.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # 操作按钮
        self.btn_start = ttk.Button(master, text="开始采集", command=self.start_collection)
        self.btn_start.pack(pady=5)

    def create_input_fields(self):
        frame = ttk.Frame(self.master)
        frame.pack(pady=10, fill=tk.X)

        # API Key输入
        ttk.Label(frame, text="API Key:").grid(row=0, column=0, padx=5)
        self.api_entry = ttk.Entry(frame, width=40)
        self.api_entry.grid(row=0, column=1, padx=5)

        # 省份选择
        provinces = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏",
    "陕西", "甘肃", "青海", "宁夏", "新疆", "台湾", "香港", "澳门"]# 完整省份列表需补充
        ttk.Label(frame, text="省份:").grid(row=1, column=0, padx=5)
        self.province_combo = ttk.Combobox(frame, values=provinces, state="readonly")
        self.province_combo.grid(row=1, column=1, padx=5)

        # 运营商选择
        isps = ["电信", "移动", "联通", "广电"]
        ttk.Label(frame, text="运营商:").grid(row=2, column=0, padx=5)
        self.isp_combo = ttk.Combobox(frame, values=isps, state="readonly")
        self.isp_combo.grid(row=2, column=1, padx=5)

    def log_status(self, message):
        self.status_box.configure(state='normal')
        self.status_box.insert(tk.END, message + "\n")
        self.status_box.see(tk.END)
        self.status_box.configure(state='disabled')

    def start_collection(self):
        api_key = self.api_entry.get()
        province = self.province_combo.get()
        isp = self.isp_combo.get()
        
        if not all([api_key, province, isp]):
            self.log_status("错误：请填写所有必填项！")
            return
        
        # 使用线程防止界面冻结
        thread = threading.Thread(target=self.run_collection, args=(api_key, province, isp))
        thread.start()

    def run_collection(self, api_key, province, isp):
        try:
            # 这里调用你的采集函数，需修改原代码参数传递方式
            self.log_status(f"开始采集 {province}{isp}...")
            # 示例调用（需适配原代码）
            # main(api_key, province, isp) 
            self.log_status("采集完成！")
        except Exception as e:
            self.log_status(f"发生错误：{str(e)}")
