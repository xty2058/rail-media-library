"""Small, private team login backed by deployment secrets."""
import getpass
import hashlib
import hmac
import json
import re
import secrets
import time
from http.cookies import CookieError, SimpleCookie

COOKIE = 'rail_session'
LIFETIME = 12 * 3600


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
    return salt + ':' + digest.hex()


def valid_name(name):
    return isinstance(name, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{2,40}', name)


class TeamAuth:
    def __init__(self, origin, secret, accounts):
        if len(secret) < 32 or not isinstance(accounts, dict) or not accounts:
            raise ValueError('小组模式需要会话密钥和至少一个账号')
        if any(not valid_name(name) or not isinstance(value, str)
               or not re.fullmatch(r'[0-9a-f]{32}:[0-9a-f]{64}', value) for name, value in accounts.items()):
            raise ValueError('小组账号格式无效')
        self.origin = origin
        self.secret = secret.encode()
        self.accounts = accounts

    def verify(self, name, password):
        expected = self.accounts.get(name, '') if valid_name(name) else ''
        if not isinstance(password, str) or not 0 < len(password) <= 128:
            return False
        actual = password_hash(password, expected.split(':')[0] if expected else '0'*32)
        return hmac.compare_digest(expected, actual)

    def signature(self, body):
        return hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()

    def cookie(self, name=None):
        token = ''
        if name:
            expires = int(time.time())+LIFETIME
            body = f'{name}:{expires}:{self.accounts[name]}'
            token = f'{name}.{expires}.{self.signature(body)}'
        secure = '; Secure' if self.origin.startswith('https://') else ''
        return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={LIFETIME if name else 0}{secure}'

    def user(self, header):
        try:
            cookie = SimpleCookie(header).get(COOKIE)
            if not cookie:
                return None
            name, expires, signature = cookie.value.rsplit('.', 2)
            if name in self.accounts and int(expires) > time.time():
                expected = self.signature(f'{name}:{expires}:{self.accounts[name]}')
                if hmac.compare_digest(signature, expected):
                    return name
        except (CookieError, ValueError):
            pass
        return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='生成小组账号密码散列')
    parser.add_argument('usernames', nargs='+')
    names = parser.parse_args().usernames
    if len(set(names)) != len(names) or any(not valid_name(name) for name in names):
        parser.error('账号使用 2–40 个英文字母、数字、点、横线或下划线，且不得重复')
    accounts = {}
    for name in names:
        password = getpass.getpass(f'{name} 的密码：')
        if not 12 <= len(password) <= 128:
            parser.error('密码长度须为 12–128 个字符')
        accounts[name] = password_hash(password)
    print(json.dumps(accounts))
