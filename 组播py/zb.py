import os
import requests
import re
import base64
import cv2
import datetime
from datetime import datetime
from bs4 import BeautifulSoup
from opencc import OpenCC
import fileinput

# 获取rtp目录下的文件名
files = os.listdir('rtp')

files_name = []

# 去除后缀名并保存至provinces_isps
for file in files:
    name, extension = os.path.splitext(file)
    files_name.append(name)

# 忽略不符合要求的文件名
provinces_isps = [name for name in files_name if name.count('_') == 1]

# 打印结果
print(f"本次查询：{provinces_isps}的组播节目")

keywords = []

for province_isp in provinces_isps:
    # 读取文件并删除空白行
    try:
        with open(f'rtp/{province_isp}.txt', 'r', encoding='utf-8') as file:
            lines = file.readlines()
            lines = [line.strip() for line in lines if line.strip()]
        # 获取第一行中以包含 "rtp://" 的值作为 mcast
        if lines:
            first_line = lines[0]
            if "rtp://" in first_line:
                mcast = first_line.split("rtp://")[1].split(" ")[0]
                keywords.append(province_isp + "_" + mcast)
    except FileNotFoundError:
        print(f"文件 '{province_isp}.txt' 不存在. 跳过此文件.")

# 遍历所有省份和ISP组合
final_channels = []  # 存储所有组播频道信息

# 直接从指定的文件中读取组播频道并写入到最终列表
additional_files = [
    "北京联通.txt", "上海电信.txt", "江苏电信.txt", "天津联通.txt", 
    "湖北电信.txt", "湖南电信.txt", "广东电信.txt", "陕西电信.txt", 
    "四川电信.txt", "河南电信.txt", "河南联通.txt"
]

for file_path in additional_files:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            final_channels.append(content)
    else:
        print(f"文件 {file_path} 不存在，跳过")

# 遍历所有有效 IP 地址并测试第一个组播视频流
for keyword in keywords:
    province, isp, mcast = keyword.split("_")
    current_time = datetime.now()
    timeout_cnt = 0
    result_urls = set() 
    while len(result_urls) == 0 and timeout_cnt <= 5:
        try:
            search_url = 'https://fofa.info/result?qbase64='
            search_txt = f'\"Rozhuk\" && country=\"CN\" && region=\"{province}\"'
            bytes_string = search_txt.encode('utf-8')
            search_txt = base64.b64encode(bytes_string).decode('utf-8')
            search_url += search_txt
            print(f"{current_time} 查询运营商 : {province}{isp} ，查询网址 : {search_url}")
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            html_soup = BeautifulSoup(html_content, "html.parser")
            pattern = r"http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"
            urls_all = re.findall(pattern, html_content)
            result_urls = set(urls_all)
            print(f"{current_time} result_urls:{result_urls}")

            valid_ip = None

            # 遍历所有有效的 IP 地址，只测试每个 IP 的第一个组播视频流
            for url in result_urls:
                video_url = url + "/rtp/" + mcast

                # 用OpenCV读取视频
                cap = cv2.VideoCapture(video_url)

                # 检查视频是否成功打开
                if cap.isOpened():
                    # 读取视频的宽度和高度
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    print(f"{current_time} {video_url} 的分辨率为 {width}x{height}")

                    # 如果视频成功打开，记录该有效 IP
                    valid_ip = url
                    cap.release()  # 关闭视频流
                    break  # 找到第一个成功的流，退出内层循环

                else:
                    print(f"{current_time} {video_url} 无效")

            if valid_ip:
                # 生成播放列表
                rtp_filename = f'rtp/{province}_{isp}.txt'
                with open(rtp_filename, 'r', encoding='utf-8') as file:
                    data = file.read()
                # 使用有效 IP 更新播放列表
                new_data = data.replace("rtp://", f"{valid_ip}/rtp/")
                final_channels.append(new_data)  # 添加更新后的频道信息到列表

                print(f'已生成播放列表，保存至{rtp_filename}')
            else:
                print(f"未找到合适的 IP 地址。")

        except (requests.Timeout, requests.RequestException) as e:
            timeout_cnt += 1
            print(f"{current_time} [{province}]搜索请求发生超时，异常次数：{timeout_cnt}")
            if timeout_cnt <= 5:
                continue
            else:
                print(f"{current_time} 搜索IPTV频道源[]，超时次数过多：{timeout_cnt} 次，停止处理")

# 写入最终的iptv_list.txt文件
with open("iptv_list.txt", "w", encoding="utf-8") as output:
    output.write('\n'.join(final_channels))

print('节目表制作完成！ 文件输出在当前文件夹！')

# 合并自定义频道文件
file_contents = []
file_paths = ["北京联通.txt", "上海电信.txt", "江苏电信.txt", "天津联通.txt", "湖北电信.txt", "湖南电信.txt", "广东电信.txt", "陕西电信.txt", "四川电信.txt", "河南电信.txt", "河南联通.txt"]  # 替换为实际的文件路径列表
for file_path in file_paths:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding="utf-8") as file:
            content = file.read()
            file_contents.append(content)
    else:
        print(f"文件 {file_path} 不存在，跳过")

# 写入合并后的文件
with open("iptv_list.txt", "a", encoding="utf-8") as output:
    output.write('\n'.join(file_contents))

# 分类整理并生成 M3U 文件
m3u_channels = []  # 用于存储 M3U 文件内容
for line in final_channels:
    if line.strip():  # 确保行不为空
        m3u_channels.append(f'#EXTINF:-1,{line.strip()}\n{line.strip()}')

# 写入 M3U 文件
with open("iptv_list.m3u", "w", encoding="utf-8") as m3u_output:
    m3u_output.write('#EXTM3U\n')
    m3u_output.write('\n'.join(m3u_channels))

print("M3U 文件生成完成！")

# 处理iptv_list.txt文件的开头内容
with open("iptv_list.txt", 'r', encoding='utf-8') as file:
    lines = file.readlines()
    if lines and "<html>" in lines[0]:  # 检查是否是错误页面
        print("检测到错误页面内容，清空文件。")
        lines = []  # 清空文件内容

# 将有效内容重新写入
with open("iptv_list.txt", "w", encoding='utf-8') as output:
    output.writelines(lines)

print("任务运行完毕，分类频道列表可查看文件夹内iptv_list.txt和iptv_list.m3u文件！")
