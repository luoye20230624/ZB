# iptv_finder_quake.py
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
QUAKE_API_KEY = "6abf676d-ccee-4f81-a2b7-aeb4dd9e31b1"  # 必须替换！访问 https://quake.360.net 获取
QUAKE_PAGE_SIZE = 50            # 每次查询结果数（建议50-100）
MAX_RETRIES = 3                 # 查询失败重试次数
TIMEOUT = 15                    # 网络请求超时时间（秒）
# ============================================

def get_valid_fields():
    """获取API允许的查询字段"""
    try:
        response = requests.get(
            "https://quake.360.net/api/v3/filter/quake_service",
            headers={"X-QuakeToken": QUAKE_API_KEY},
            timeout=10
        )
        fields = response.json().get("data", [])
        print("可用查询字段:", fields)
        return fields
    except Exception as e:
        print(f"获取字段失败: {str(e)}")
        return []

def quake_search(province, org):
    """通过360 Quake API搜索组播源（修正字段版本）"""
    headers = {"X-QuakeToken": QUAKE_API_KEY, "Content-Type": "application/json"}
    result_urls = set()
    current_page = 0
    
    try:
        while True:
            # 构建符合字段规范的查询
            query = {
                "query": f'Rozhuk AND province: "{province}" AND isp: "{isp}"',
                "start": current_page * QUAKE_PAGE_SIZE,
                "size": QUAKE_PAGE_SIZE,
                "include": ["ip", "port", "hostname"]  # 使用已验证的合法字段
            }

            # 带错误重试的请求
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
                    
                    # 处理API错误
                    if data.get("code") != 0:
                        print(f"API错误: {data.get('message')}")
                        return result_urls
                        
                    # 解析结果（使用正确字段）
                    for item in data.get("data", []):
                        ip = item.get("ip", "")
                        port = str(item.get("port", ""))
                        if ip and port:
                            result_urls.add(f"http://{ip}:{port}")
                    
                    # 分页控制
                    total = data.get("meta", {}).get("total", 0)
                    if (current_page + 1) * QUAKE_PAGE_SIZE >= total:
                        return result_urls
                        
                    current_page += 1
                    time.sleep(1)  # 遵守API速率限制
                    break
                    
                except (requests.RequestException, json.JSONDecodeError) as e:
                    print(f"请求失败（{attempt+1}/{MAX_RETRIES}）: {str(e)}")
                    time.sleep(5)

    except Exception as e:
        print(f"搜索异常: {str(e)}")
        return result_urls

def check_stream(url, mcast, timeout=5):
    """增强版流媒体检测"""
    stream_url = f"{url}/rtp/{mcast}"
    cap = None
    try:
        cap = cv2.VideoCapture(stream_url)
        start_time = time.time()
        frame_count = 0
        
        while (time.time() - start_time) < timeout:
            ret, _ = cap.read()
            if ret:
                frame_count += 1
                if frame_count >= 10:  # 10帧以上视为有效
                    return True
        return False
    except Exception as e:
        print(f"检测异常: {str(e)}")
        return False
    finally:
        if cap is not None:
            cap.release()

def process_province(province_isp):
    """处理单个地区配置"""
    try:
        # 解析配置
        province, isp = province_isp.split('_')
        print(f"\n{'='*30}\n处理: {province}{isp}\n{'='*30}")
        
        # 读取组播配置
        with open(f'rtp/{province_isp}.txt', 'r') as f:
            content = f.read()
            mcast_match = re.search(r'rtp://([\d\.]+:\d+)', content)
            if not mcast_match:
                print("错误：未找到组播地址")
                return
            mcast = mcast_match.group(1)

        # 设置机构参数
        org_mapping = {
            "联通": "CHINA UNICOM China169 Backbone",
            "电信": "Chinanet",
            "移动": "China Mobile communications corporation"
        }
        org = org_mapping.get(isp, "Unknown")

        # 执行搜索
        print("正在搜索节点...")
        urls = quake_search(province, org)
        print(f"初始节点数: {len(urls)}")

        # 有效性检测
        valid_urls = []
        progress = tqdm(urls, desc="检测节点", unit="个", leave=False)
        for url in progress:
            if check_stream(url, mcast):
                valid_urls.append(url)
                progress.set_postfix(valid=len(valid_urls))
            time.sleep(0.1)  # 避免检测过快

        # 生成播放列表
        if valid_urls:
            output_file = f"playlist/{province}{isp}.txt"
            template = content.replace("rtp://", "{}/rtp/")
            with open(output_file, 'w') as f:
                f.write('\n'.join([template.format(url) for url in valid_urls]))
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
