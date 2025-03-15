# iptv_finder_full.py
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
QUAKE_API_KEY = "6abf676d-ccee-4f81-a2b7-aeb4dd9e31b1"  # 必须替换！
QUAKE_PAGE_SIZE = 50
MAX_RETRIES = 3
TIMEOUT = 20
# ============================================

def quake_search(province, isp):
    """执行360 Quake搜索"""
    headers = {"X-QuakeToken": QUAKE_API_KEY, "Content-Type": "application/json"}
    result_urls = set()
    current_page = 0
    
    try:
        while True:
            query = {
                "query": f'Rozhuk AND province:"{province}" AND isp:"{isp}"',
                "start": current_page * QUAKE_PAGE_SIZE,
                "size": QUAKE_PAGE_SIZE,
                "include": ["ip", "port", "hostname"]
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
                        print(f"API错误: {data.get('message')}")
                        return result_urls
                        
                    for item in data.get("data", []):
                        ip = item.get("ip")
                        port = str(item.get("port", ""))
                        if ip and port.isdigit():
                            result_urls.add(f"http://{ip}:{port}")
                    
                    total = data.get("meta", {}).get("total", 0)
                    if (current_page + 1) * QUAKE_PAGE_SIZE >= total:
                        return result_urls
                        
                    current_page += 1
                    time.sleep(1)
                    break
                    
                except (requests.RequestException, json.JSONDecodeError) as e:
                    print(f"请求失败（{attempt+1}/{MAX_RETRIES}）: {str(e)}")
                    time.sleep(5)

    except Exception as e:
        print(f"搜索异常: {str(e)}")
    
    return result_urls

def check_stream(url, mcast):
    """视频流检测"""
    stream_url = f"{url}/rtp/{mcast}"
    cap = None
    try:
        cap = cv2.VideoCapture(stream_url)
        start_time = time.time()
        frame_count = 0
        
        while (time.time() - start_time) < 5:
            ret, _ = cap.read()
            if ret:
                frame_count += 1
                if frame_count >= 10:
                    return True
        return False
    except:
        return False
    finally:
        if cap is not None:
            cap.release()

def process_province(province_isp):
    """处理单个省份"""
    try:
        province, isp = province_isp.split('_', 1)
        print(f"\n{'='*30}\n处理: {province}{isp}\n{'='*30}")
        
        with open(f'rtp/{province_isp}.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            mcast_match = re.search(r'rtp://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', content)
            if not mcast_match:
                raise ValueError("未找到有效的组播地址")
            mcast = mcast_match.group(1)

        urls = quake_search(province, isp)
        print(f"初始节点数: {len(urls)}")
        
        valid_urls = []
        progress = tqdm(urls, desc="检测节点", unit="个", leave=False)
        for url in progress:
            if check_stream(url, mcast):
                valid_urls.append(url)
            progress.set_postfix(有效数=len(valid_urls))
            time.sleep(0.2)

        if valid_urls:
            output_file = f"playlist/{province}{isp}.txt"
            with open(f'rtp/{province_isp}.txt', 'r', encoding='utf-8') as src:
                template = src.read()
                with open(output_file, 'w', encoding='utf-8') as dst:
                    for url in valid_urls:
                        dst.write(template.replace("rtp://", f"{url}/rtp/") + "\n")
            print(f"生成有效节点: {len(valid_urls)} → {output_file}")
        else:
            print("未找到有效节点")

    except Exception as e:
        print(f"处理异常: {str(e)}")

def merge_results():
    """分类合并结果"""
    all_files = [f for f in os.listdir('playlist') if f.endswith('.txt')]
    cc = OpenCC('t2s')
    
    # 构建分类字典
    categories = {
        "更新时间,#genre#": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "央视频道,#genre#": [],
        "卫视频道,#genre#": [],
        "地方频道,#genre#": [],
        "其他频道,#genre#": []
    }

    # 分类规则
    cctv_pat = re.compile(r'CCTV|央视|中央')
    ws_pat = re.compile(r'卫视|凤凰|星空')
    local_pat = re.compile(r'台|都市|综合')

    # 处理文件内容
    for file in all_files:
        with open(f'playlist/{file}', 'r', encoding='utf-8') as f:
            for line in cc.convert(f.read()).splitlines():
                if '#genre#' in line or not line.strip():
                    continue
                
                channel = line.split(',', 1)[0].strip()
                
                if cctv_pat.search(channel):
                    categories["央视频道,#genre#"].append(line)
                elif ws_pat.search(channel):
                    categories["卫视频道,#genre#"].append(line)
                elif local_pat.search(channel):
                    categories["地方频道,#genre#"].append(line)
                else:
                    categories["其他频道,#genre#"].append(line)

    # 去重处理
    seen = set()
    for cat in list(categories.keys())[1:]:  # 跳过更新时间
        unique = []
        for line in categories[cat]:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        categories[cat] = unique

    # 生成最终文件
    with open('iptv_list.txt', 'w', encoding='utf-8') as f:
        # 写入头部信息
        f.write(f"{list(categories.keys())[0]}\n")
        f.write(f"{categories['更新时间,#genre#'][0]}\n\n")
        
        # 写入各分类
        for cat in list(categories.keys())[1:]:
            if categories[cat]:
                f.write(f"{cat}\n")
                f.write("\n".join(categories[cat]))
                f.write("\n\n")

    print(f"\n合并完成！总频道数: {len(seen)} → iptv_list.txt")

def main():
    os.makedirs("rtp", exist_ok=True)
    os.makedirs("playlist", exist_ok=True)
    
    provinces_isps = []
    for file in os.listdir('rtp'):
        if file.count('_') == 1 and file.endswith('.txt'):
            provinces_isps.append(os.path.splitext(file)[0])
    
    if not provinces_isps:
        print("错误: 请在rtp目录放置 省份_运营商.txt 格式的配置文件")
        return

    print(f"发现 {len(provinces_isps)} 个配置:")
    for idx, pi in enumerate(provinces_isps, 1):
        print(f"{idx}. {pi.replace('_', '')}")

    for province_isp in provinces_isps:
        process_province(province_isp)
        time.sleep(1)

    merge_results()

if __name__ == "__main__":
    print("""IPTV组播源整理工具 v4.0
    功能特点:
    1. 自动分类央视/卫视/地方频道
    2. 生成带时间戳的更新记录
    3. 支持中文运营商名称
    4. 智能去重机制""")
    main()
    print("\n运行完成! 请检查:")
    print("- playlist目录的分省文件")
    print("- iptv_list.txt（分类合并文件）")
