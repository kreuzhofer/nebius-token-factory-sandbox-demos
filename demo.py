"""Explicit HTTPS client for the Nebius Sandboxes beta API."""
import argparse
import base64
import getpass
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                os.environ.setdefault(name.strip(), value.strip())


class API:
    def __init__(self, token, project, base=None):
        self.base = (base or 'https://api.tokenfactory.nebius.com/sandboxes/v1').rstrip('/')
        if not self.base.startswith('https://'):
            raise ValueError('HTTPS required')
        self.headers = {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'}
        if project:
            self.headers['Project'] = project

    def request(self, method, path, body=None):
        req = urllib.request.Request(self.base+path, method=method, headers=self.headers,
            data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            # Responses can echo request metadata including runtime credentials.
            raise RuntimeError(f'{method} {path}: HTTP {exc.code}; check credentials, Project header and sandbox access') from None

    def wait(self, operation_id, seconds):
        deadline = time.monotonic()+seconds
        try:
            while time.monotonic() < deadline:
                operation = self.request('GET', '/operations/'+operation_id)
                status = operation['status']
                if status in ('SUCCESS', 'FAILED', 'CANCELLED'):
                    if status != 'SUCCESS':
                        raise RuntimeError(f'Operation {operation_id}: {status}')
                    return operation
                time.sleep(1)
            raise TimeoutError(f'Operation {operation_id} exceeded local deadline')
        except (KeyboardInterrupt, TimeoutError):
            try:
                self.request('DELETE', '/operations/'+operation_id)
            except Exception:
                print(f'Cancellation unconfirmed: {operation_id}; server timeout remains active')
            raise


def decode(stream):
    if stream.get('truncated'):
        raise RuntimeError('Sandbox output was truncated')
    value = stream.get('value', '')
    return base64.b64decode(value).decode() if stream.get('encoding') == 'base64' else value


def execute(api, image, mode, env):
    operation = api.request('POST', '/instances', {
        'image': image, 'command': '/usr/local/bin/python3', 'args': ['-', mode],
        'stdin': {'value': (ROOT/'agent.py').read_text(), 'encoding': 'ascii', 'close': True},
        'env': env, 'preserve_env': False, 'disposable': mode == 'agent',
        'networking': {'enabled': mode == 'agent'}, 'timeout': 360 if mode == 'agent' else 30,
        'resources_limits': {'max_layer_bytes': 268435456}, 'truncate_output_at': 65536})
    operation_id = operation['uuid']
    print(f'{mode} operation: {operation_id}', flush=True)
    result = api.wait(operation_id, 420)['metadata']['result']
    for stream in ('stdout', 'stderr'):
        output = decode(result.get(stream) or {})
        if output:
            print(output, end='' if output.endswith('\n') else '\n')
    state = result['state']
    if state.get('timed_out') or state.get('signal', -1) not in (None, -1, 0) or state.get('exit_code') != 0:
        raise RuntimeError(f'Sandbox process failed: {state}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['configure', 'images', 'models', 'smoke', 'agent', 'all'])
    parser.add_argument('--image', help='Existing sandbox image UUID or tag:NAME (must contain /usr/local/bin/python3)')
    args = parser.parse_args()
    if args.command == 'configure':
        if (ROOT/'.env').exists():
            raise RuntimeError('.env already exists; edit it to change credentials')
        token = getpass.getpass('Sandbox API token (hidden): ')
        project = input('Sandbox Project ID: ').strip()
        inference = getpass.getpass('Inference API key (blank uses sandbox token): ') or token
        model = input('Token Factory model ID (may be set later): ').strip()
        fd = os.open(ROOT/'.env', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as output:
            output.write(f'CONTREE_TOKEN={token}\nCONTREE_PROJECT={project}\nNEBIUS_API_KEY={inference}\nNEBIUS_MODEL={model}\n')
        print('Credentials saved in .env with mode 0600')
        return
    load_env()
    if args.command == 'models':
        token = os.environ.get('NEBIUS_API_KEY')
        if not token:
            raise RuntimeError('Set NEBIUS_API_KEY first')
        api = API(token, None, 'https://api.tokenfactory.nebius.com/v1')
        for model in api.request('GET', '/models')['data']:
            print(model['id'])
        return
    token = os.environ.get('CONTREE_TOKEN') or os.environ.get('NEBIUS_API_KEY')
    if not token:
        raise RuntimeError('Run configure or set CONTREE_TOKEN first')
    api = API(token, os.environ.get('CONTREE_PROJECT'), os.environ.get('CONTREE_BASE_URL'))
    if args.command == 'images':
        print(json.dumps(api.request('GET', '/images?limit=100&offset=0'), indent=2))
        return
    env = {}
    if args.command in ('agent', 'all'):
        for name in ('NEBIUS_API_KEY', 'NEBIUS_MODEL'):
            if not os.environ.get(name):
                raise RuntimeError(f'Set {name} before running the agent')
            env[name] = os.environ[name]
    image = args.image or os.environ.get('CONTREE_IMAGE')
    if not image:
        imported = api.request('POST', '/images/import', {
            'registry': {'url': 'docker://docker.io/library/python:3.12-slim'}, 'timeout': 300})
        print(f'Image import operation: {imported["uuid"]}', flush=True)
        completed = api.wait(imported['uuid'], 360)
        image = completed.get('result_image_uuid') or (completed.get('result') or {}).get('image')
        if not image:
            raise RuntimeError('Import succeeded without a result image UUID')
        print(f'Reuse image with --image {image}', flush=True)
    if args.command in ('smoke', 'all'):
        execute(api, image, 'smoke', {})
    if args.command in ('agent', 'all'):
        execute(api, image, 'agent', env)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not dump objects that could include credentials.
        print(f'{type(exc).__name__}: {exc}')
        raise SystemExit(1)
