"""Check credentials, prepaid balance and model availability without paid inference.
Run from backend: python -m scripts.check_deepseek
"""
import httpx
from app.core.config import get_settings


def main() -> int:
    try:
        settings = get_settings()
    except Exception:
        print('Application settings are invalid. Complete the environment setup first.')
        return 1
    key = settings.deepseek_api_key.strip()
    if not key:
        print('Set DEEPSEEK_API_KEY in the project .env or server environment first.')
        return 1
    try:
        with httpx.Client(timeout=15, headers={'Authorization': f'Bearer {key}'}) as client:
            balance = client.get('https://api.deepseek.com/user/balance')
            if balance.status_code != 200:
                print(f'DeepSeek credential/balance check failed (HTTP {balance.status_code}).')
                return 1
            data = balance.json()
            if not data.get('is_available'):
                print('Credentials accepted, but no usable prepaid balance is available.')
                return 1
            models = client.get('https://api.deepseek.com/models')
            if models.status_code != 200:
                print(f'DeepSeek model check failed (HTTP {models.status_code}).')
                return 1
            if 'deepseek-flash' not in {m.get('id') for m in models.json().get('data', [])}:
                print('Credentials accepted, but deepseek-flash was not listed for this account.')
                return 1
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        print('DeepSeek check could not complete. Check connectivity and retry.')
        return 1
    print('DeepSeek key accepted; balance available; deepseek-flash listed. No paid inference performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
