# iptv_finder_final.py
import os
import time
import requests
import json
import cv2
import re
from tqdm import tqdm
from opencc import OpenCC

# ================= 配置区域 =================
QUAKE_API_KEY = "6abf676d-ccee-4f81-a2b7-aeb4dd9e31b1"  # 必须替换为有效密钥
QUAKE_PAGE_SIZE = 50            # 每次查询结果数
MAX_RETRIES = 3                 # 最大重试次数
TIMEOUT = 20                    # 请求超时时间
# ============================================

def quake_search(province, isp):
    """执行360 Quake搜索（精确参数版）"""
    headers = {"X-QuakeToken": QUAKE_API_KEY, "Content-Type": "application/json"}
    result_urls = set()
    current_page = 0
    
    try:
        while True:
            # 构建与网页完全一致的查询语句
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
                    
                    # 检查API返回状态
                    if data.get("code") != 0:
                        print(f"API错误: {data.get('message')}")
                        return result_urls
                        
                    # 解析结果数据
                    for item in data.get("data", []):
                        ip = item.get("ip")
                        port = str(item.get("port", ""))
                        if ip and port.isdigit():
                            result_urls.add(f"http://{ip}:{port}")
                    
                    # 分页控制
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
    """增强版流媒体检测"""
    stream_url = f"{url}/rtp/{mcast}"
    cap = None
    try:
        cap = cv2.VideoCapture(stream_url)
        start_time = time.time()
        frame_count = 0
        
        # 双条件检测：超时5秒或收到10帧
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
    """处理单个省份配置"""
    try:
        # 解析文件名（支持中文_分隔）
        province, isp = province_isp.split('_', 1)
        print(f"\n{'='*30}\n处理: {province}{isp}\n{'='*30}")
        
        # 读取组播地址
        with open(f'rtp/{province_isp}.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            mcast_match = re.search(r'rtp://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)', content)
            if not mcast_match:
                raise ValueError("配置文件必须包含有效的rtp地址（如 rtp://239.77.0.1:5146）")
            mcast = mcast_match.group(1)

        # 执行搜索
        urls = quake_search(province, isp)
        print(f"初始节点数: {len(urls)}")
        
        # 有效性检测
        valid_urls = []
        progress = tqdm(urls, desc="检测节点", unit="个", leave=False)
        for url in progress:
            if check_stream(url, mcast):
                valid_urls.append(url)
            progress.set_postfix(有效数=len(valid_urls))
            time.sleep(0.2)  # 控制检测频率

        # 生成播放列表
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
    """合并并优化结果文件"""
    all_files = [f for f in os.listdir('playlist') if f.endswith('.txt')]
    merged_content = []
    cc = OpenCC('t2s')  # 繁体转简体
    
    # 合并内容
    for file in all_files:
        with open(f'playlist/{file}', 'r', encoding='utf-8') as f:
            content = cc.convert(f.read())
            merged_content.extend(content.splitlines())
    
    # 高级去重（忽略空行和注释）
    seen = set()
    unique_lines = []
    for line in merged_content:
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#"):
            continue
        if clean_line not in seen:
            seen.add(clean_line)
            unique_lines.append(line)
    
    # 生成最终文件
    with open('iptv_list.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(unique_lines))
    print(f"\n合并完成！总频道数: {len(unique_lines)}")

def main():
    # 初始化环境
    os.makedirs("rtp", exist_ok=True)
    os.makedirs("playlist", exist_ok=True)
    
    # 获取所有配置文件
    provinces_isps = []
    for file in os.listdir('rtp'):
        if file.count('_') == 1 and file.endswith('.txt'):
            provinces_isps.append(os.path.splitext(file)[0])
    
    if not provinces_isps:
        print("错误: rtp目录中未找到符合 省份_运营商.txt 格式的文件")
        print("示例文件: 湖南_中国电信.txt")
        return

    # 处理每个地区
    print(f"发现 {len(provinces_isps)} 个配置:")
    for idx, pi in enumerate(provinces_isps, 1):
        print(f"{idx}. {pi.replace('_', '')}")
    
    for province_isp in provinces_isps:
        process_province(province_isp)
        time.sleep(1)  # 请求间隔

    # 合并结果
    merge_results()

if __name__ == "__main__":
    print("""IPTV组播源搜索工具 最终版
    使用前请确认:
    1. 已在rtp目录放置配置文件
    2. 已替换有效的API密钥
    3. 网络连接正常""")
    main()
    print("\n运行完成! 请检查:")
    print("1. playlist目录下的分省文件")
    print("2. 根目录下的iptv_list.txt（合并文件）")
