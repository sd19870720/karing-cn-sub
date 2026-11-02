"""Publish only SOCKS5 nodes passing bounded HTTPS and China-exit checks."""
import argparse
import base64
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import time
import urllib.request

import yaml
from validate import baseline, check_candidate

RAW = 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.json'
API = 'https://api.github.com/repos/proxifly/free-proxy-list/contents/proxies/countries/CN/data.json'
MONOSANS_RAW = 'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json'
MONOSANS_API = 'https://api.github.com/repos/monosans/proxy-list/contents/proxies.json'
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


def fetch_proxifly():
    try:
        return request_json(RAW)
    except Exception as error:
        print(f'Raw source unavailable ({type(error).__name__}); trying GitHub API')
    result = request_json(API)
    if result.get('encoding') != 'base64' or not result.get('content'):
        raise ValueError('GitHub API did not return file content')
    return json.loads(base64.b64decode(result['content']))


def normalize_monosans(items):
    result = []
    for item in items:
        if item.get('protocol') != 'socks5' or item.get('username') or item.get('password'):
            continue
        geo = item.get('geolocation') or {}
        if (geo.get('country') or {}).get('iso_code') != 'CN':
            continue
        city = ((geo.get('city') or {}).get('names') or {}).get('en') or '待核验'
        result.append({'protocol': 'socks5', 'ip': item.get('host'), 'port': item.get('port'),
                       'geolocation': {'country': 'CN', 'city': city}})
    return result


def fetch_monosans():
    try:
        return normalize_monosans(request_json(MONOSANS_RAW))
    except Exception:
        metadata = request_json(MONOSANS_API)
        if metadata.get('encoding') != 'base64':
            sha = metadata['sha']
            if len(sha) != 40 or any(c not in '0123456789abcdef' for c in sha):
                raise ValueError('Invalid Git blob identifier')
            metadata = request_json('https://api.github.com/repos/monosans/proxy-list/git/blobs/' + sha)
        return normalize_monosans(json.loads(base64.b64decode(metadata['content'])))


def fetch_source():
    combined = []
    successful_sources = 0
    for fetcher in (fetch_proxifly, fetch_monosans):
        try:
            combined.extend(fetcher())
            successful_sources += 1
        except Exception as error:
            print(f'{fetcher.__name__} unavailable: {type(error).__name__}')
    if not successful_sources:
        raise RuntimeError('All public sources are unavailable')
    return combined


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
        raise ValueError('No eligible candidates')
    nodes = []
    for city, address, port in sorted(candidates.values()):
        nodes.append({
            'name': f'{CITIES.get(city, city)}-{address}-{port}',
            'type': 'socks5', 'server': address, 'port': port, 'udp': False,
        })
    return make_config(nodes)


def make_config(nodes):
    group = '国内节点-手动选择'
    return {
        'allow-lan': False, 'mode': 'global', 'log-level': 'warning',
        'proxies': nodes,
        'proxy-groups': [{'name': group, 'type': 'select',
                          'proxies': [node['name'] for node in nodes]}],
        'rules': [f'MATCH,{group}'],
    }


def write_config(config, destination):
    header = (
        '# 仅发布本轮通过 HTTPS 及国内出口检查的 SOCKS5 节点。\n'
        '# 结果仅代表检测环境；iPhone、抖音及 UDP 尚未验收。\n'
        '# 来源：proxifly/free-proxy-list 与 monosans/proxy-list\n'
        '# SPDX-License-Identifier: GPL-3.0-only\n'
        '# 许可与转换源码：https://github.com/sd19870720/karing-cn-sub\n'
        '# 地区名称来自出口查询结果，可能与抖音使用的数据库不同。\n'
        '# UDP 能力未经确认，因此关闭 UDP。\n'
    )
    text = header + yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    if yaml.safe_load(text) != config:
        raise ValueError('YAML round-trip validation failed')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(destination)


def save_result(config, status, output, status_path, now):
    previous = {}
    if status_path.exists():
        try:
            previous = json.loads(status_path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
    last_success = previous.get('last_success')
    if config is not None:
        write_config(config, output)
        last_success = {'checked_at': now.isoformat(),
                        'expires_at': (now + timedelta(hours=2)).isoformat(),
                        'nodes': len(config['proxies'])}
        status['serving_previous'] = False
    else:
        retain = False
        if status['state'] == 'checker_error' and last_success and output.exists():
            try:
                retain = datetime.fromisoformat(last_success['expires_at']) > now
            except (ValueError, KeyError, TypeError):
                pass
        if not retain:
            output.unlink(missing_ok=True)
        status['serving_previous'] = retain
    status['last_success'] = last_success
    status['subscription_available'] = output.exists()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = status_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(status_path)


def refresh(source, output, status_path, now=None):
    now = now or datetime.now(timezone.utc)
    status = {'checked_at': now.isoformat(), 'state': 'checker_error',
              'environment': 'GitHub Actions runner' if os.environ.get('GITHUB_ACTIONS') else 'local checker', 'candidates': 0,
              'passed': 0, 'failures': {}, 'iphone_and_douyin': 'not_verified'}
    try:
        direct = baseline()
        status['exit_check_services'] = list(direct)
        try:
            candidates = build_config(source)['proxies']
        except ValueError:
            if source == []:
                candidates = []
            elif isinstance(source, list):
                candidates = []
            else:
                raise
        status['candidates_available'] = len(candidates)
        candidates = candidates[:300]
        status['candidates'] = len(candidates)
        deadline = time.monotonic() + 300
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda node: check_candidate(node, direct, deadline=deadline), candidates))
        nodes = []
        for node, result in zip(candidates, results):
            if not result['ok']:
                continue
            node = dict(node)
            area = CITIES.get(result['city'], result['city'])
            node['name'] = f'{area}-{node["server"]}-{node["port"]}'
            nodes.append(node)
        status.update(state='ok' if nodes else 'no_verified_nodes', passed=len(nodes),
                      failures=dict(Counter(result['reason'] for result in results if not result['ok'])))
        config = make_config(nodes) if nodes else None
    except Exception as error:
        status['error'] = type(error).__name__ + ': ' + str(error)[:200]
        config = None
    save_result(config, status, output, status_path, now)
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, help='Use a saved source JSON for offline verification')
    parser.add_argument('--output', type=Path, default=Path('subscription.yaml'))
    parser.add_argument('--status', type=Path, default=Path('status.json'))
    args = parser.parse_args()
    try:
        source = (json.loads(args.input.read_text(encoding='utf-8-sig'))
                  if args.input else fetch_source())
    except Exception as error:
        now = datetime.now(timezone.utc)
        status = {'checked_at': now.isoformat(), 'state': 'checker_error',
                  'error': type(error).__name__, 'passed': 0}
        save_result(None, status, args.output, args.status, now)
    else:
        status = refresh(source, args.output, args.status)
    print(json.dumps(status, ensure_ascii=False))


if __name__ == '__main__':
    main()
