import os
import requests
import re
import base64
import cv2
import datetime
from datetime import datetime
from bs4 import BeautifulSoup
import fileinput
from opencc import OpenCC

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

for keyword in keywords:
    province, isp, mcast = keyword.split("_")
    # 根据不同的 isp 设置不同的 org 值
    if province == "北京" and isp == "联通":
        org = "China Unicom Beijing Province Network"
    elif isp == "联通":
        org = "CHINA UNICOM China169 Backbone"
    elif isp == "电信":
        org = "Chinanet"
    elif isp == "移动":
        org = "China Mobile communications corporation"

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

            valid_ips = []

            # 遍历所有视频链接
            for url in result_urls:
                video_url = url + "/rtp/" + mcast

                # 用OpenCV读取视频
                cap = cv2.VideoCapture(video_url)

                # 检查视频是否成功打开
                if not cap.isOpened():
                    print(f"{current_time} {video_url} 无效")
                    continue  # Skip to the next URL

                # 读取视频的宽度和高度
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"{current_time} {video_url} 的分辨率为 {width}x{height}")

                if width > 0 and height > 0:
                    valid_ips.append(url)
                cap.release()

            if valid_ips:
                rtp_filename = f'rtp/{province}_{isp}.txt'
                with open(rtp_filename, 'r', encoding='utf-8') as file:
                    data = file.read()
                txt_filename = f'{province}{isp}.txt'
                with open(txt_filename, 'w') as new_file:
                    for url in valid_ips:
                        new_data = data.replace("rtp://", f"{url}/rtp/")
                        new_file.write(new_data)

                print(f'已生成播放列表，保存至{txt_filename}')
            else:
                print(f"未找到合适的 IP 地址。")

        except (requests.Timeout, requests.RequestException) as e:
            timeout_cnt += 1
            print(f"{current_time} [{province}]搜索请求发生超时，异常次数：{timeout_cnt}")
            if timeout_cnt <= 5:
                continue
            else:
                print(f"{current_time} 搜索IPTV频道源[]，超时次数过多：{timeout_cnt} 次，停止处理")
print('节目表制作完成！ 文件输出在当前文件夹！')

# 合并自定义频道文件
file_contents = []
grouped_contents = {
    '💚央视频道&爬虫,#genre#': [],
    '💚卫视频道&爬虫,#genre#': [],
    '💚数字频道&爬虫,#genre#': [],
    '💚省级频道&爬虫,#genre#': [],
    '💚凤凰CHC&爬虫,#genre#': [],
}

file_paths = ["c.txt", "c1.txt", "c2.txt", "e.txt", "DD.txt", "df.txt", "df1.txt", "f.txt", "f1.txt"]  # 替换为实际的文件路径列表
for file_path in file_paths:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding="utf-8") as file:
            content = file.readlines()
            # 将内容按组存入字典
            for line in content:
                for key in grouped_contents.keys():
                    if key in line:
                        grouped_contents[key].append(line)
                        break  # 找到对应组后停止

# 将内容按需要的顺序写入合并后的文件
with open("GAT.txt", "w", encoding="utf-8") as output:
    # 按顺序写入不同的分组
    for group in ['💚央视频道&爬虫,#genre#', '💚卫视频道&爬虫,#genre#', '💚数字频道&爬虫,#genre#', '💚省级频道&爬虫,#genre#', '💚凤凰CHC&爬虫,#genre#']:
        if group in grouped_contents:
            output.write(''.join(grouped_contents[group]))

# 读取临时文件，并生成结果文件
with open("GAT.txt", 'r', encoding="utf-8") as file:
    content = file.read()

# 写入合并后的文件
with open("iptv_list.txt", "w", encoding="utf-8") as output:
    output.write(content)

for line in fileinput.input("iptv_list.txt", inplace=True):
    line = line.replace("008广", "广")
    line = line.replace("家庭电影", "家庭影院")    
    line = line.replace("CHC", "CHC")  
    print(line, end="")

with open('iptv_list.txt', 'r', encoding="utf-8") as file:
    lines = file.readlines()

# 使用列表来存储唯一的行的顺序 
unique_lines = [] 
seen_lines = set() 

# 遍历每一行，如果是新的就加入unique_lines 
for line in lines:
    if line not in seen_lines:
        unique_lines.append(line)
        seen_lines.add(line)

# 将唯一的行写入新的文档 
with open('iptv_list.txt', 'w', encoding="utf-8") as file:
    file.writelines(unique_lines)

# 简体转繁体
converter = OpenCC('t2s.json')  # 繁转简
with open('iptv_list.txt', 'r', encoding='utf-8') as file:
    traditional_text = file.read()

# 进行繁体字转简体字的转换
simplified_text = converter.convert(traditional_text)

# 将转换后的简体字写入txt文件
with open('iptv_list.txt', 'w', encoding='utf-8') as file:
    file.write(simplified_text)

# TXT转M3U
def txt_to_m3u(input_file, output_file):
    # 读取txt文件内容
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 打开m3u文件并写入内容
    now = datetime.utcnow() + datetime.timedelta(hours=8)
    current_time = now.strftime("%m-%d %H:%M")
    with open(output_file, 'w', encoding='utf-8') as f:  
        f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml" catchup="append" catchup-source="?playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}"\n')
        f.write(f'#EXTINF:-1 group-title="💚更新时间{current_time}",河南卫视\n')    
        f.write(f'http://61.163.181.78:9901/tsfile/live/1034_1.m3u8?key=txiptv&playlive=1&authid=0\n')    
        # 初始化genre变量
        genre = ''
        # 遍历txt文件内容
        for line in lines:
            line = line.strip()
            if "," in line:  # 防止文件里面缺失","号报错
                channel_name, channel_url = line.split(',', 1)
                if channel_url == '#genre#':
                    genre = channel_name
                    print(genre)
                else:
                    # 将频道信息写入m3u文件
                    f.write(f'#EXTINF:-1 tvg-id="{channel_name}" tvg-name="{channel_name}" tvg-logo="https://live.fanmingming.com/tv/{channel_name}.png" group-title="{genre}",{channel_name}\n')
                    f.write(f'{channel_url}\n')

# 将txt文件转换为m3u文件
txt_to_m3u('iptv_list.txt', 'iptv_list.m3u')

# 任务结束，删除不必要的过程文件
files_to_remove = ["北京联通.txt", "上海电信.txt", "江苏电信.txt", "天津联通.txt", "湖北电信.txt", "湖南电信.txt", "广东电信.txt", "陕西电信.txt", "四川电信.txt", "河南电信.txt", "河南联通.txt", "GAT.txt", "DD.txt", "TW.txt", "a.txt", "b.txt", "b2.txt", "HK.txt", "c.txt", "c1.txt", "c2.txt", "e.txt", "f.txt", "f1.txt", "df.txt", "df1.txt", "TT.txt", "zhibo.txt"]

for file in files_to_remove:
    if os.path.exists(file):
        os.remove(file)
    else:  # 如果文件不存在，则提示异常并打印提示信息
        print(f"文件 {file} 不存在，跳过删除。")

print("任务运行完毕，分类频道列表可查看文件夹内iptv_list.txt文件！")
