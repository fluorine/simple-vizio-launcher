import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.instance = launcher.Launcher({'tv_host': '127.0.0.1', 'auth_token': 'test'})

    def test_stock_home_suppresses_redirect_and_sends_home_key(self):
        with patch.object(self.instance, 'call') as call:
            self.instance.open_stock()
        self.assertTrue(self.instance.stock_mode)
        self.assertFalse(self.instance.seen_stock)
        self.assertEqual(call.call_args.args[0], '/key_command/')
        self.assertEqual(call.call_args.args[1]['KEYLIST'][0]['CODE'], 15)

    def test_stock_home_error_reenables_redirect(self):
        with patch.object(self.instance, 'call', side_effect=RuntimeError('disconnected')):
            with self.assertRaises(RuntimeError):
                self.instance.open_stock()
        self.assertFalse(self.instance.stock_mode)

    def test_pair_saves_token_and_defaults_watchfree_off(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            replies = [{'ITEM': {'CHALLENGE_TYPE': 1, 'PAIRING_REQ_TOKEN': 3}},
                       {'ITEM': {'AUTH_TOKEN': 'test-token'}}]
            with patch.object(launcher, 'CONFIG', config), patch.object(launcher, 'request_tv', side_effect=replies), patch('builtins.input', return_value='1234'):
                launcher.pair('127.0.0.1')
            data = json.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(data['auth_token'], 'test-token')
            self.assertFalse(data['redirect_watchfree'])


if __name__ == '__main__':
    unittest.main()
