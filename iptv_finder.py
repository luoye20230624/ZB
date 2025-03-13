# iptv_finder_quake_fixed.py
import os
import time
import requests
import json
import cv2
import re
from tqdm import tqdm
from opencc import OpenCC

# ================= 配置区域 =================
QUAKE_API_KEY = "6abf676d-ccee-4f81-a2b7-aeb4dd9e31b1"  # 必须替换！
QUAKE_PAGE_SIZE = 30
# ============================================

def quake_search(province, isp):
    """精确匹配网页查询参数"""
    headers = {"X-QuakeToken": QUAKE_API_KEY, "Content-Type": "application/json"}
    result_urls = set()
    current_page = 0
    
    try:
        while True:
            # 完全匹配浏览器查询参数
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{isp}"',
                "start": current_page * QUAKE_PAGE_SIZE,
                "size": QUAKE_PAGE_SIZE,
                "include": ["ip", "port", "service_name"]  # 根据实际返回字段调整
            }

            response = requests.post(
                "https://quake.360.net/api/v3/search/quake_service",
                headers=headers,
                json=query,
                timeout=15
            )
            data = response.json()
            
            # 解析结果
            for item in data.get("data", []):
                ip = item.get("ip")
                port = str(item.get("port"))
                if ip and port.isdigit():
                    result_urls.add(f"http://{ip}:{port}")
            
            # 分页控制
            if (current_page + 1) * QUAKE_PAGE_SIZE >= data.get("meta", {}).get("total", 0):
                break
            current_page += 1
            time.sleep(1)

        return result_urls
    except Exception as e:
        print(f"搜索异常: {str(e)}")
        return []

def process_province(province_isp):
    """增强版省份处理"""
    try:
        # 正确解析文件名
        province, isp = province_isp.split('_', 1)  # 处理"湖南_中国电信"格式
        print(f"\n{'='*30}\n处理: {province}{isp}\n{'='*30}")
        
        # 读取组播地址（增强正则匹配）
        with open(f'rtp/{province_isp}.txt', 'r') as f:
            content = f.read()
            mcast_match = re.search(r'rtp://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', content)
            if not mcast_match:
                raise ValueError("组播地址格式错误，请确保文件包含类似 rtp://239.77.0.1:5146 的地址")
            mcast = mcast_match.group(1)

        # 执行搜索
        urls = quake_search(province, isp)
        print(f"初始节点数: {len(urls)}")
        
        # 有效性检测（增强超时处理）
        valid_urls = []
        for url in tqdm(urls, desc="检测节点"):
            try:
                cap = cv2.VideoCapture(f"{url}/rtp/{mcast}")
                if cap.isOpened() and cap.read()[0]:
                    valid_urls.append(url)
                cap.release()
            except:
                continue
            time.sleep(0.2)  # 避免请求过载

        # 生成播放列表
        if valid_urls:
            output_file = f"playlist/{province}{isp}.txt"
            with open(output_file, 'w') as f:
                f.write(f"{province}{isp},#genre#\n")
                with open(f'rtp/{province_isp}.txt', 'r') as src:
                    template = src.read()
                    for url in valid_urls:
                        f.write(template.replace("rtp://", f"{url}/rtp/") + "\n")
            print(f"生成有效节点: {len(valid_urls)} → {output_file}")
        else:
            print("未找到有效节点")

    except Exception as e:
        print(f"处理异常: {str(e)}")

def merge_results():
    """合并并优化最终结果"""
    all_files = [f for f in os.listdir('playlist') if f.endswith('.txt')]
    merged_content = []
    cc = OpenCC('t2s')  # 繁体转简体
    
    # 合并内容
    for file in all_files:
        with open(f'playlist/{file}', 'r') as f:
            content = cc.convert(f.read())
            merged_content.extend(content.splitlines())
    
    # 去重处理
    seen = set()
    unique_lines = []
    for line in merged_content:
        clean_line = re.sub(r'\s+', '', line)
        if clean_line and clean_line not in seen:
            seen.add(clean_line)
            unique_lines.append(line)
    
    # 生成最终文件
    with open('iptv_list.txt', 'w') as f:
        f.write('\n'.join(unique_lines))
    print(f"\n合并完成！总频道数: {len(unique_lines)} → iptv_list.txt")

def main():
    # 初始化环境
    os.makedirs("rtp", exist_ok=True)
    os.makedirs("playlist", exist_ok=True)
    
    # 验证字段
    get_valid_fields()

    # 获取所有配置
    provinces_isps = []
    for file in os.listdir('rtp'):
        if file.count('_') == 1 and file.endswith('.txt'):
            provinces_isps.append(file[:-4])  # 移除.txt后缀
    
    if not provinces_isps:
        print("错误：rtp目录缺少配置文件")
        print("请按 省份_运营商.txt 格式创建文件（如 广东_电信.txt）")
        return

    # 处理每个地区
    print(f"\n发现 {len(provinces_isps)} 个配置:")
    for idx, pi in enumerate(provinces_isps, 1):
        print(f"{idx}. {pi.replace('_', '')}")

    for province_isp in provinces_isps:
        process_province(province_isp)
        time.sleep(1)  # 请求间隔

    # 合并结果
    merge_results()

if __name__ == "__main__":
    print("""IPTV组播源搜索工具（360 Quake版）v2.1
    使用说明：
    1. 在rtp目录放置配置文件（示例见代码注释）
    2. 替换有效的API密钥
    3. 安装依赖库：pip install requests opencv-python tqdm opencc""")
    main()
    print("\n运行结束！请检查：\n1. playlist目录的分省文件\n2. iptv_list.txt（最终合并文件）")
