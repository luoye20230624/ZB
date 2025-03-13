# iptv_finder.py
import os
import time
import requests
import json
import cv2
import re
from tqdm import tqdm
from datetime import datetime
from opencc import OpenCC

# ================= 配置区域 =================
QUAKE_API_KEY = "YOUR_API_KEY"  # 必须替换！访问 https://quake.360.net 获取
QUAKE_PAGE_SIZE = 50            # 每次查询结果数（建议50-100）
MAX_RETRIES = 3                 # 查询失败重试次数
TIMEOUT = 15                    # 网络请求超时时间（秒）
# ============================================

def quake_search(province, org):
    """通过360 Quake API搜索组播源"""
    headers = {"X-QuakeToken": QUAKE_API_KEY, "Content-Type": "application/json"}
    result_urls = set()
    current_page = 0
    
    try:
        while True:
            query = {
                "query": f'service:"Rozhuk" AND country:"CN" AND region:"{province}" AND org:"{org}"',
                "start": current_page * QUAKE_PAGE_SIZE,
                "size": QUAKE_PAGE_SIZE,
                "include": ["service.ip", "service.port"]
            }

            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.post(
                        "https://quake.360.net/api/v3/search/quake_service",
                        headers=headers,
                        json=query,
                        timeout=TIMEOUT
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("code") != 0:
                        print(f"API错误：{data.get('message')}")
                        return result_urls
                        
                    # 解析结果
                    for item in data.get("data", []):
                        ip = item["service"]["ip"]
                        port = item["service"]["port"]
                        result_urls.add(f"http://{ip}:{port}")
                    
                    total = data.get("meta", {}).get("total", 0)
                    if (current_page + 1) * QUAKE_PAGE_SIZE >= total:
                        return result_urls
                        
                    current_page += 1
                    time.sleep(1)  # API速率限制
                    break
                    
                except (requests.RequestException, json.JSONDecodeError) as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"请求失败，正在重试... ({attempt+1}/{MAX_RETRIES})")
                        time.sleep(5)
                    else:
                        print(f"最终请求失败：{str(e)}")
                        return result_urls

    except Exception as e:
        print(f"发生意外错误：{str(e)}")
        return result_urls

def check_stream(url, mcast):
    """检测视频流有效性"""
    try:
        stream_url = f"{url}/rtp/{mcast}"
        cap = cv2.VideoCapture(stream_url)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return width > 0 and height > 0
        return False
    except:
        return False
    finally:
        if 'cap' in locals():
            cap.release()

def process_province(province_isp):
    """处理单个省份运营商"""
    try:
        province, isp = province_isp.split('_')
        print(f"\n{'='*30}\n开始处理：{province}{isp}\n{'='*30}")

        # 读取组播配置
        with open(f'rtp/{province_isp}.txt', 'r') as f:
            config = f.read()
            mcast = re.search(r'rtp://([\d\.]+:\d+)', config).group(1)

        # 运营商映射
        org_map = {
            "联通": "CHINA UNICOM China169 Backbone",
            "电信": "Chinanet",
            "移动": "China Mobile communications corporation"
        }
        org = org_map.get(isp, "Unknown")

        # 执行搜索
        print("正在搜索节点...")
        urls = quake_search(province, org)
        print(f"找到初始节点 {len(urls)} 个")

        # 有效性检测
        valid_urls = []
        progress = tqdm(urls, desc="检测节点", unit="个", leave=False)
        for url in progress:
            if check_stream(url, mcast):
                valid_urls.append(url)
                progress.set_postfix(valid=len(valid_urls))

        # 生成播放列表
        if valid_urls:
            output_file = f"playlist/{province}{isp}.txt"
            with open(output_file, 'w') as f:
                f.write(config.replace("rtp://", f"{valid_urls[0]}/rtp/"))
                for url in valid_urls[1:]:
                    f.write(config.replace("rtp://", f"{url}/rtp/"))
            print(f"\n生成有效节点 {len(valid_urls)} 个 → {output_file}")
        else:
            print("未找到有效节点")

    except Exception as e:
        print(f"处理失败：{str(e)}")

def merge_files():
    """合并所有播放列表"""
    all_files = [f for f in os.listdir('playlist') if f.endswith('.txt')]
    merged_content = []
    cc = OpenCC('t2s')  # 繁体转简体

    for filename in all_files:
        with open(f'playlist/{filename}', 'r') as f:
            content = cc.convert(f.read())
            merged_content.append(content)

    # 去重处理
    seen = set()
    unique_content = []
    for line in '\n'.join(merged_content).split('\n'):
        if line.strip() and line not in seen:
            seen.add(line)
            unique_content.append(line)

    # 生成最终文件
    with open('iptv_list.txt', 'w') as f:
        f.write('\n'.join(unique_content))
    print(f"\n合并完成！总频道数：{len(unique_content)} → iptv_list.txt")

def main():
    # 初始化环境
    os.makedirs("rtp", exist_ok=True)
    os.makedirs("playlist", exist_ok=True)

    # 获取所有地区配置
    provinces_isps = []
    for file in os.listdir('rtp'):
        if file.count('_') == 1 and file.endswith('.txt'):
            provinces_isps.append(file[:-4])  # 移除.txt后缀

    if not provinces_isps:
        print("错误：未找到地区配置文件")
        print("请在rtp目录放置类似 广东_电信.txt 的配置文件")
        return

    # 处理每个地区
    print(f"发现 {len(provinces_isps)} 个地区配置：")
    for idx, pi in enumerate(provinces_isps, 1):
        print(f"{idx}. {pi.replace('_', '')}")

    for province_isp in provinces_isps:
        process_province(province_isp)
        time.sleep(1)  # 防止请求过载

    # 合并结果
    merge_files()

if __name__ == "__main__":
    print("""IPTV组播源搜索工具 v2.0
    1. 确保已在rtp目录放置配置文件（示例：广东_电信.txt）
    2. 最终结果将在playlist目录和iptv_list.txt生成
    3. 需要有效的360 Quake API密钥""")
    main()
    print("\n运行结束！请检查以下文件：\n1. playlist目录中的分省列表\n2. iptv_list.txt（合并后列表）")
