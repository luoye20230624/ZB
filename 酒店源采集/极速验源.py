import os
import requests
from tqdm import tqdm
import threading
import time
#  获取远程港澳台直播源文件
url = "https://raw.githubusercontent.com/frxz751113/AAAAA/main/IPTV/TW.txt"          #源采集地址
r = requests.get(url)
open('1.txt','wb').write(r.content)         #打开源文件并临时写入


def test_connectivity(url):
    try:
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False

def process_line(line, output_file):
    parts = line.strip().split(',')
    if len(parts) != 2:
        return
    channel_name, channel_url = parts
    if 'genre' in line.lower():
        output_file.write(line)
        return
    if test_connectivity(channel_url):
        output_file.write(f"{channel_name},{channel_url}\n")
    else:
        return

with open("1.txt", "r", encoding='utf-8') as source_file, open("output.txt", "w", encoding='utf-8') as output_file:
    lines = source_file.readlines()

    print("任务完成")


