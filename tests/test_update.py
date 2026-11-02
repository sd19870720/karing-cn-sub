"""Offline safety and publication-boundary tests. No proxy connections are made."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import update
import validate
import yaml


NOW = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
NODE = {'name': 'source-label', 'server': '8.8.8.8', 'port': 1080,
        'type': 'socks5', 'udp': False}
SOURCE = [
    {'protocol': 'socks5', 'ip': '8.8.8.8', 'port': 1080,
     'geolocation': {'country': 'CN', 'city': 'Shanghai'}},
    {'protocol': 'socks5', 'ip': '1.1.1.1', 'port': 1080,
     'geolocation': {'country': 'CN', 'city': 'Beijing'}},
]


def https_ok(body='User-agent: *', seconds=0.1):
    return {'ok': True, 'body': body, 'seconds': seconds}


def geo_response(ip='223.5.5.5', country='CN', city='Shenzhen'):
    return https_ok(json.dumps({'ip': ip, 'country_code': country, 'city': city}))


class RequestTests(unittest.TestCase):
    @patch('validate.shutil.which', return_value='/usr/bin/curl')
    @patch('validate.subprocess.run')
    def test_socks_request_cannot_be_bypassed_by_no_proxy_and_keeps_tls_checks(self, run, _which):
        run.return_value = subprocess.CompletedProcess([], 0, 'HTTP/2 200\r\ncontent-type: text/plain\r\n\r\nok', '')
        with patch.dict(os.environ, {'NO_PROXY': '*', 'no_proxy': '*',
                                     'HTTPS_PROXY': 'http://unwanted.invalid:8080'}):
            result = validate.request('https://example.com/', NODE)
        self.assertTrue(result['ok'])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--proxy') + 1], 'socks5h://8.8.8.8:1080')
        self.assertEqual(command[command.index('--noproxy') + 1], '')
        self.assertEqual(command[command.index('--proto') + 1], '=https')
        self.assertEqual(command[1], '--disable')
        self.assertIn('--include', command)
        self.assertNotIn('--write-out', command)
        for insecure in ('-k', '--insecure', '--proxy-insecure'):
            self.assertNotIn(insecure, command)
        self.assertLessEqual(float(command[command.index('--max-time') + 1]), 12)
        self.assertLessEqual(run.call_args.kwargs['timeout'], 15)

    @patch('validate.shutil.which', return_value='/usr/bin/curl')
    @patch('validate.subprocess.run')
    def test_intermediate_http_headers_are_not_returned_as_body(self, run, _which):
        run.return_value = subprocess.CompletedProcess(
            [], 0, 'HTTP/1.1 100 Continue\r\n\r\nHTTP/2 200\r\ncontent-type: text/plain\r\n\r\nfinal body', '')
        response = validate.request('https://example.com/', NODE)
        self.assertTrue(response['ok'])
        self.assertEqual(response['body'], 'final body')

    @patch('validate.shutil.which', return_value='/usr/bin/curl')
    @patch('validate.subprocess.run')
    def test_http_error_and_truncated_headers_are_not_success(self, run, _which):
        for output, reason in (
            ('HTTP/2 403\r\ncontent-type: text/plain\r\n\r\nblocked', 'http_403'),
            ('HTTP/2 200\r\ncontent-type: text/plain', 'invalid_response'),
        ):
            with self.subTest(reason=reason):
                run.return_value = subprocess.CompletedProcess([], 0, output, '')
                response = validate.request('https://example.com/', NODE)
                self.assertFalse(response['ok'])
                self.assertEqual(response['reason'], reason)

    @patch('validate.shutil.which', return_value='/usr/bin/curl')
    @patch('validate.subprocess.run', side_effect=subprocess.TimeoutExpired('curl', 11))
    def test_proxy_timeout_has_no_direct_retry(self, run, _which):
        self.assertEqual(validate.request('https://example.com/', NODE),
                         {'ok': False, 'reason': 'timeout'})
        run.assert_called_once()

    def test_invalid_or_private_exit_response_is_rejected(self):
        self.assertIsNone(validate.geolocation(geo_response(ip='127.0.0.1')))
        self.assertIsNone(validate.geolocation(https_ok('not JSON')))
        self.assertIsNone(validate.geolocation(https_ok(json.dumps({'success': False, 'ip': '223.5.5.5'}))))


class DomesticGeolocationTests(unittest.TestCase):
    def test_mainland_plain_text_extracts_actual_ip_and_city(self):
        result = validate.geolocation(https_ok('当前 IP：223.5.5.5  来自于：中国 广东 深圳 电信\n'))
        self.assertEqual(result, {'ip': '223.5.5.5', 'country': 'CN', 'city': '深圳'})

    def test_hong_kong_macao_and_taiwan_are_not_accepted_as_mainland_exits(self):
        regions = (
            ('香港', 'HK'), ('香港特别行政区', 'HK'),
            ('澳门', 'MO'), ('澳门特别行政区', 'MO'),
            ('台湾', 'TW'), ('台湾省', 'TW'),
        )
        for region, country in regions:
            with self.subTest(region=region):
                response = https_ok(f'当前 IP：223.5.5.5 来自于：中国 {region} 城市 运营商')
                result = validate.geolocation(response)
                self.assertEqual(result['country'], country)
                with patch('validate.request', side_effect=[https_ok(), response]):
                    checked = validate.check_candidate(NODE, {validate.GEO_URLS[0]: '9.9.9.9'})
                self.assertFalse(checked['ok'])
                self.assertEqual(checked['reason'], 'non_cn_exit')

    def test_invalid_private_or_incomplete_plain_text_is_rejected(self):
        for body in (
            '当前 IP：999.1.1.1 来自于：中国 北京 北京',
            '当前 IP：127.0.0.1 来自于：中国 北京 北京',
            '当前 IP：10.1.2.3 来自于：中国 北京 北京',
            '当前 IP：223.5.5.5 来自于：中国',
            '<html>当前 IP：223.5.5.5 来自于：中国 北京 北京</html>',
        ):
            with self.subTest(body=body):
                self.assertIsNone(validate.geolocation(https_ok(body)))


class BaselineTests(unittest.TestCase):
    def test_domestic_geolocation_success_avoids_foreign_checkers(self):
        with patch('validate.request', side_effect=[
            https_ok(), https_ok('当前 IP：223.5.5.5 来自于：中国 北京 北京 电信'),
        ]) as request:
            result = validate.baseline()
        self.assertEqual(result, {validate.GEO_URLS[0]: '223.5.5.5'})
        self.assertEqual([call.args[0] for call in request.call_args_list],
                         [validate.DOMESTIC_URL, validate.GEO_URLS[0]])

    def test_foreign_geolocation_is_only_fallback_after_domestic_checker_failure(self):
        with patch('validate.request', side_effect=[
            https_ok(), {'ok': False, 'reason': 'timeout'},
            geo_response(ip='9.9.9.9', country='US'), {'ok': False, 'reason': 'timeout'},
        ]) as request:
            result = validate.baseline()
        self.assertEqual(result, {validate.GEO_URLS[1]: '9.9.9.9'})
        self.assertEqual([call.args[0] for call in request.call_args_list],
                         [validate.DOMESTIC_URL, *validate.GEO_URLS])

    def test_unusable_domestic_geo_response_also_allows_fallback(self):
        with patch('validate.request', side_effect=[
            https_ok(), https_ok('not an IP response'),
            geo_response(ip='9.9.9.9', country='US'), {'ok': False, 'reason': 'timeout'},
        ]):
            self.assertEqual(validate.baseline(), {validate.GEO_URLS[1]: '9.9.9.9'})

    def test_no_usable_geo_checker_raises_instead_of_validating_nodes(self):
        with patch('validate.request', side_effect=[https_ok()] + [
            {'ok': False, 'reason': 'timeout'} for _ in validate.GEO_URLS
        ]):
            with self.assertRaises(RuntimeError):
                validate.baseline()


class CandidateTests(unittest.TestCase):
    def test_exhausted_budget_makes_no_network_request(self):
        with patch('validate.time.monotonic', return_value=100.0), \
             patch('validate.request') as request:
            result = validate.check_candidate(NODE, {validate.GEO_URLS[0]: '9.9.9.9'}, deadline=100.0)
        self.assertEqual(result, {'ok': False, 'reason': 'budget_exhausted'})
        request.assert_not_called()

    def test_domestic_page_success_does_not_accept_non_cn_exit(self):
        with patch('validate.request', side_effect=[https_ok(), geo_response(country='US')]):
            result = validate.check_candidate(NODE, {validate.GEO_URLS[0]: '9.9.9.9'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'non_cn_exit')

    def test_same_as_checker_exit_is_rejected_even_when_country_is_cn(self):
        with patch('validate.request', side_effect=[https_ok(), geo_response(ip='9.9.9.9')]):
            result = validate.check_candidate(NODE, {validate.GEO_URLS[0]: '9.9.9.9'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'same_as_checker')

    def test_one_verified_cn_geo_can_pass_when_other_geo_service_times_out(self):
        direct = {validate.GEO_URLS[0]: '9.9.9.9', validate.GEO_URLS[1]: '9.9.9.9'}
        with patch('validate.request', side_effect=[
            https_ok(seconds=0.2), geo_response(city='Shenzhen'), {'ok': False, 'reason': 'timeout'},
        ]) as request:
            result = validate.check_candidate(NODE, direct)
        self.assertTrue(result['ok'])
        self.assertEqual(result['city'], 'Shenzhen')
        self.assertEqual(result['exit_ip'], '223.5.5.5')
        self.assertTrue(all(call.args[1] == NODE for call in request.call_args_list))

    def test_domestic_page_alone_without_verified_exit_is_not_enough(self):
        with patch('validate.request', side_effect=[https_ok(), {'ok': False, 'reason': 'timeout'}]):
            result = validate.check_candidate(NODE, {validate.GEO_URLS[0]: '9.9.9.9'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'exit_unverified')


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / 'subscription.yaml'
        self.status_path = Path(self.directory.name) / 'status.json'

    def seed_previous(self, expires_at):
        self.output.write_text('previous subscription', encoding='utf-8')
        self.status_path.write_text(json.dumps({
            'last_success': {'checked_at': (NOW - timedelta(hours=1)).isoformat(),
                             'expires_at': expires_at, 'nodes': 1},
        }), encoding='utf-8')

    def test_all_failed_deletes_previous_subscription_even_when_it_has_not_expired(self):
        self.seed_previous((NOW + timedelta(hours=1)).isoformat())
        with patch('update.baseline', return_value={'geo': '9.9.9.9'}), \
             patch('update.check_candidate', return_value={'ok': False, 'reason': 'timeout'}):
            status = update.refresh(SOURCE, self.output, self.status_path, now=NOW)
        self.assertEqual(status['state'], 'no_verified_nodes')
        self.assertEqual(status['passed'], 0)
        self.assertEqual(status['failures'], {'timeout': 2})
        self.assertFalse(self.output.exists())
        self.assertFalse(status['subscription_available'])
        self.assertFalse(status['serving_previous'])
        self.assertEqual(json.loads(self.status_path.read_text())['state'], 'no_verified_nodes')

    def test_checker_error_retains_only_unexpired_previous_success(self):
        self.seed_previous((NOW + timedelta(seconds=1)).isoformat())
        with patch('update.baseline', side_effect=RuntimeError('checker unreachable')), \
             patch('update.check_candidate') as candidate:
            status = update.refresh(SOURCE, self.output, self.status_path, now=NOW)
        self.assertEqual(status['state'], 'checker_error')
        self.assertTrue(status['serving_previous'])
        self.assertEqual(self.output.read_text(), 'previous subscription')
        candidate.assert_not_called()

    def test_checker_error_deletes_expired_previous_success(self):
        for expiration in (NOW, NOW - timedelta(seconds=1)):
            with self.subTest(expires_at=expiration):
                self.seed_previous(expiration.isoformat())
                status = {'state': 'checker_error', 'checked_at': NOW.isoformat()}
                update.save_result(None, status, self.output, self.status_path, NOW)
                self.assertFalse(self.output.exists())
                self.assertFalse(status['serving_previous'])

    def test_checker_error_does_not_retain_unvalidated_legacy_file(self):
        self.output.write_text('unvalidated legacy subscription', encoding='utf-8')
        status = {'state': 'checker_error', 'checked_at': NOW.isoformat()}
        update.save_result(None, status, self.output, self.status_path, NOW)
        self.assertFalse(self.output.exists())
        self.assertFalse(status['serving_previous'])

    def test_checker_error_invalid_expiration_is_not_treated_as_a_valid_lease(self):
        for expiration in ('not-a-date', '2026-11-02T10:00:00', None):
            with self.subTest(expires_at=expiration):
                self.seed_previous(expiration)
                status = {'state': 'checker_error', 'checked_at': NOW.isoformat()}
                update.save_result(None, status, self.output, self.status_path, NOW)
                self.assertFalse(self.output.exists())
                self.assertFalse(status['serving_previous'])

    def test_success_contains_only_passed_nodes_and_uses_exit_geography(self):
        def candidate_result(node, direct, deadline=None):
            if node['server'] == '8.8.8.8':
                return {'ok': True, 'reason': 'passed', 'city': 'Shenzhen',
                        'exit_ip': '223.5.5.5', 'seconds': 0.2}
            return {'ok': False, 'reason': 'timeout'}

        with patch('update.baseline', return_value={'geo': '9.9.9.9'}), \
             patch('update.check_candidate', side_effect=candidate_result):
            status = update.refresh(SOURCE, self.output, self.status_path, now=NOW)
        config = yaml.safe_load(self.output.read_text(encoding='utf-8'))
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(status['passed'], 1)
        self.assertEqual(len(config['proxies']), 1)
        node = config['proxies'][0]
        self.assertEqual(node['server'], '8.8.8.8')
        self.assertTrue(node['name'].startswith('深圳-'))
        self.assertNotIn('上海', node['name'])
        self.assertFalse(node['udp'])
        self.assertEqual(config['proxy-groups'][0]['proxies'], [node['name']])
        self.assertEqual(status['last_success']['expires_at'], (NOW + timedelta(hours=2)).isoformat())
        self.assertFalse(status['serving_previous'])


if __name__ == '__main__':
    unittest.main()
