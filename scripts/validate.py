"""Bounded HTTP CONNECT/SOCKS5 HTTPS checks without direct fallback."""
import ipaddress
import json
import re
import shutil
import subprocess
import time

DOMESTIC_URL = 'https://www.baidu.com/robots.txt'
GEO_URLS = ('https://myip.ipip.net/', 'https://api.ip.sb/geoip', 'https://ipwho.is/')


def request(url, node=None):
    curl = shutil.which('curl') or shutil.which('curl.exe')
    if not curl:
        return {'ok': False, 'reason': 'curl_missing'}
    command = [curl, '--disable', '--silent', '--show-error',
               '--connect-timeout', '4', '--max-time', '8',
               '--max-filesize', '65536', '--proto', '=https',
               '--include', '--url', url]
    if node is None:
        command += ['--noproxy', '*']
    else:
        host = node['server']
        if ':' in host:
            host = f'[{host}]'
        protocol = {'socks5': 'socks5h', 'http': 'http'}.get(node.get('type', 'socks5'))
        if protocol is None:
            return {'ok': False, 'reason': 'unsupported_proxy_type'}
        command += ['--proxy', f'{protocol}://{host}:{node["port"]}', '--noproxy', '']
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=11)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'reason': 'timeout'}
    if result.returncode:
        return {'ok': False, 'reason': {7: 'connection_failed', 28: 'timeout',
                35: 'tls_failed', 60: 'certificate_failed', 97: 'socks_failed'}.get(
                    result.returncode, f'curl_{result.returncode}')}
    try:
        body = result.stdout.replace('\r\n', '\n')
        code = None
        while body.startswith('HTTP/'):
            headers, separator, body = body.partition('\n\n')
            if not separator:
                raise ValueError('Missing header separator')
            code = headers.splitlines()[0].split()[1]
        elapsed = time.monotonic() - started
    except (ValueError, IndexError):
        return {'ok': False, 'reason': 'invalid_response'}
    if code not in ('200', '204'):
        return {'ok': False, 'reason': 'http_' + str(code)}
    return {'ok': True, 'body': body, 'seconds': elapsed}


def geolocation(response):
    if not response.get('ok'):
        return None
    match = re.fullmatch(r'\s*当前 IP[:：]\s*(\S+)\s+来自于[:：]\s*(.*?)\s*', response.get('body', ''))
    if match:
        try:
            address = ipaddress.ip_address(match.group(1))
            parts = match.group(2).split()
            if not address.is_global or len(parts) < 2:
                return None
            country = 'CN' if parts[0] == '中国' else 'OTHER'
            for prefix, code in (('香港', 'HK'), ('澳门', 'MO'), ('澳門', 'MO'),
                                 ('台湾', 'TW'), ('臺灣', 'TW')):
                if parts[1].startswith(prefix):
                    country = code
                    break
            return {'ip': str(address), 'country': country,
                    'city': parts[2] if len(parts) >= 3 else parts[1]}
        except ValueError:
            return None
    try:
        value = json.loads(response['body'])
        address = ipaddress.ip_address(value['ip'])
        if not address.is_global or value.get('success') is False:
            return None
        return {'ip': str(address), 'country': value.get('country_code'),
                'city': value.get('city') or value.get('region') or 'CN'}
    except (ValueError, KeyError, TypeError):
        return None


def baseline():
    if not request(DOMESTIC_URL).get('ok'):
        raise RuntimeError('Domestic HTTPS check target is unavailable from the checker')
    direct = {}
    for url in GEO_URLS:
        geo = geolocation(request(url))
        if geo:
            direct[url] = geo['ip']
            if url == GEO_URLS[0]:
                break
    if not direct:
        raise RuntimeError('No exit-IP check target is available from the checker')
    return direct


def check_candidate(node, direct, deadline=None):
    if deadline is not None and time.monotonic() >= deadline:
        return {'ok': False, 'reason': 'budget_exhausted'}
    webpage = request(DOMESTIC_URL, node)
    if not webpage.get('ok'):
        return {'ok': False, 'reason': webpage['reason']}
    verified = []
    for url, checker_ip in direct.items():
        if deadline is not None and time.monotonic() >= deadline:
            return {'ok': False, 'reason': 'budget_exhausted'}
        geo = geolocation(request(url, node))
        if not geo:
            continue
        if geo['ip'] == checker_ip:
            return {'ok': False, 'reason': 'same_as_checker'}
        if geo['country'] != 'CN':
            return {'ok': False, 'reason': 'non_cn_exit'}
        verified.append(geo)
    if not verified:
        return {'ok': False, 'reason': 'exit_unverified'}
    return {'ok': True, 'reason': 'passed', 'city': verified[0]['city'],
            'exit_ip': verified[0]['ip'], 'seconds': webpage['seconds']}
