"""Build a Clash-compatible candidate list; never connect to proxy endpoints."""
import argparse
import base64
import ipaddress
import json
from pathlib import Path
import urllib.request

import yaml

RAW = 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.json'
API = 'https://api.github.com/repos/proxifly/free-proxy-list/contents/proxies/countries/CN/data.json'
CITIES = {
    'Beijing': '北京', 'Changzhou': '常州', 'Chengdu': '成都',
    'Chongqing': '重庆', 'Dalian': '大连', 'Fuzhou': '福州',
    'Guangzhou': '广州', 'Handan': '邯郸', 'Hangzhou': '杭州',
    'Jiaxing': '嘉兴', 'Jinan': '济南', 'Nanjing': '南京',
    'Nanning': '南宁', 'Nanyang': '南阳', 'Ningbo': '宁波',
    'Pudong': '上海浦东', 'Qingdao': '青岛', 'Quanzhou': '泉州',
    'Shanghai': '上海', 'Shenyang': '沈阳', 'Shenzhen': '深圳',
    'Suzhou': '苏州', 'Tianjin': '天津', 'Wuhan': '武汉',
    'Xiamen': '厦门', 'Zhengzhou': '郑州', 'Zhongshan': '中山',
}


def request_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'karing-cn-config-updater'})
    with urllib.request.urlopen(req, timeout=25) as response:
        payload = response.read(5_000_001)
    if len(payload) > 5_000_000:
        raise ValueError('Source exceeds the 5 MB limit')
    return json.loads(payload)


def fetch_source():
    try:
        return request_json(RAW)
    except Exception as error:
        print(f'Raw source unavailable ({type(error).__name__}); trying GitHub API')
    result = request_json(API)
    if result.get('encoding') != 'base64' or not result.get('content'):
        raise ValueError('GitHub API did not return file content')
    return json.loads(base64.b64decode(result['content']))


def build_config(source):
    if not isinstance(source, list):
        raise ValueError('Expected a JSON array')
    candidates = {}
    for item in source:
        if not isinstance(item, dict):
            continue
        geo = item.get('geolocation') or {}
        city = geo.get('city')
        if (item.get('protocol') != 'socks5' or geo.get('country') != 'CN'
                or not isinstance(city, str) or not city or city == 'Unknown'):
            continue
        try:
            address = ipaddress.ip_address(item.get('ip'))
            port = int(item.get('port'))
        except (ValueError, TypeError):
            continue
        if not address.is_global or not 1 <= port <= 65535:
            continue
        key = (str(address), port)
        candidates.setdefault(key, (city, str(address), port))
    if not candidates:
        raise ValueError('No eligible candidates: keeping the existing configuration')
    nodes = []
    for city, address, port in sorted(candidates.values()):
        nodes.append({
            'name': f'{CITIES.get(city, city)}-{address}-{port}',
            'type': 'socks5', 'server': address, 'port': port, 'udp': False,
        })
    group = '国内候选-手动选择'
    return {
        'allow-lan': False, 'mode': 'global', 'log-level': 'warning',
        'proxies': nodes,
        'proxy-groups': [{'name': group, 'type': 'select',
                          'proxies': [node['name'] for node in nodes]}],
        'rules': [f'MATCH,{group}'],
    }


def write_config(config, destination):
    header = (
        '# 自动生成的公开 SOCKS5 候选配置；未实测连接或抖音效果。\n'
        '# 来源：https://github.com/proxifly/free-proxy-list\n'
        '# SPDX-License-Identifier: GPL-3.0-only\n'
        '# 许可与转换源码：https://github.com/sd19870720/karing-cn-sub\n'
        '# 城市名称来自上游元数据，可能与实际出口或抖音显示不同。\n'
        '# UDP 能力未经确认，因此关闭 UDP。\n'
    )
    text = header + yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    if yaml.safe_load(text) != config:
        raise ValueError('YAML round-trip validation failed')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, help='Use a saved source JSON for offline verification')
    parser.add_argument('--output', type=Path, default=Path('subscription.yaml'))
    args = parser.parse_args()
    source = (json.loads(args.input.read_text(encoding='utf-8-sig'))
              if args.input else fetch_source())
    config = build_config(source)
    write_config(config, args.output)
    print(f'Wrote {len(config["proxies"])} candidates to {args.output}; no proxy connections were tested')


if __name__ == '__main__':
    main()
