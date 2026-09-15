"""Run the Python receipt agents in one Nebius Sandbox job (standard-library launcher)."""
import argparse
import json
import os
from pathlib import Path

from demo import ROOT, load_env
from sandbox_jobs import SandboxJobs, retrieve_result


BOOTSTRAP = '''import os, subprocess, sys
try:
    install = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
         '--no-cache-dir', '-r', '/app/receipt_demo/requirements.txt'],
        env={'PATH': os.defpath}, capture_output=True, timeout=240)
    if install.returncode:
        print('Dependency installation failed; check the pinned requirements and package access.', flush=True)
        sys.exit(1)
    from receipt_demo.agents import main
    main()
except Exception as exc:
    print('Coordinator bootstrap failed: ' + type(exc).__name__, flush=True)
    sys.exit(1)
'''


def inputs_for_run(paths, profile):
    if paths:
        return [(f'input-{i:03}', Path(path), '') for i, path in enumerate(paths, 1)]
    root = ROOT / 'fixtures' / 'receipts'
    manifest = json.loads((root / 'manifest.json').read_text())
    selected = manifest['profiles'].get(profile)
    if selected is None:
        raise ValueError('Unknown profile; choose ' + ', '.join(manifest['profiles']))
    by_id = {item['input_id']: item for item in manifest['inputs']}
    credits = {}
    for source in json.loads((root / 'public-sources.json').read_text()):
        credits[source['receipt_id']] = '\n'.join(str(source.get(key, '')) for key in (
            'author', 'credit', 'source_page', 'license', 'license_url',
            'local_modifications', 'upstream_modifications'))
    # Only file, input identity, and publication credit leave the launcher.
    # No expected values, source groups, or synthetic recipes enter agent context.
    return [(key, root / by_id[key]['path'], credits.get(key, 'Synthetic demo receipt')) for key in selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*', help='Receipt files; defaults to a shared fixture profile')
    parser.add_argument('--profile', default='demo')
    parser.add_argument('--output', default='receipt-output', type=Path)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--image', help='Existing Python 3.12 sandbox image')
    parser.add_argument('--retrieve', help='Retry retrieval from a completed coordinator filesystem image, without inference')
    parser.add_argument('--timeout', default=1800, type=int, help='Sandbox seconds, including dependency setup')
    args = parser.parse_args()
    if not 300 <= args.timeout <= 3600:
        parser.error('--timeout must be between 300 and 3600 seconds')
    load_env(args.env_file)
    token = os.environ.get('CONTREE_TOKEN') or os.environ.get('NEBIUS_API_KEY')
    if not token:
        raise RuntimeError('Configure CONTREE_TOKEN or NEBIUS_API_KEY with demo.py configure')
    api = SandboxJobs(token, os.environ.get('CONTREE_PROJECT'), os.environ.get('CONTREE_BASE_URL'))
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ('result.json', 'report.json', 'report.pdf')):
        raise RuntimeError('Choose a fresh output directory to preserve previous results')
    image = args.retrieve
    if not image:
        if not os.environ.get('NEBIUS_API_KEY'):
            raise RuntimeError('Set NEBIUS_API_KEY for Token Factory inference')
        sources = inputs_for_run(args.inputs, args.profile)
        if not sources or len(sources) > 30:
            raise ValueError('Supply between 1 and 30 receipts')
        if sum(path.stat().st_size for _, path, _ in sources) > 50 * 1024 * 1024:
            raise ValueError('Receipt inputs exceed the 50 MiB demo limit')
        image = api.python_image(args.image or os.environ.get('CONTREE_IMAGE'))
        files, inputs = {}, []
        for receipt_id, path, credit in sources:
            remote = '/app/inputs/' + receipt_id + path.suffix.lower()
            files[remote] = api.upload(path.read_bytes())
            inputs.append({'receipt_id': receipt_id, 'source': path.name, 'path': remote, 'credit': credit})
        for path in (ROOT / 'receipt_demo').iterdir():
            if path.suffix == '.py' or path.name == 'requirements.txt':
                files['/app/receipt_demo/' + path.name] = api.upload(path.read_bytes())
        files['/app/inputs.json'] = api.upload(json.dumps(inputs).encode())
        env = {key: os.environ[key] for key in (
            'NEBIUS_API_KEY', 'NEBIUS_BASE_URL', 'NEBIUS_VISION_MODEL', 'NEBIUS_AGENT_MODEL',
            'NEBIUS_VISION_BASE_URL') if os.environ.get(key)}
        operation, image = api.run(image, files, BOOTSTRAP, env, args.timeout)
        (args.output / 'job.json').write_text(json.dumps({'operation_id': operation, 'image': image}, indent=2))
        print(f'Coordinator filesystem: {image}; retrieving artifacts', flush=True)
    response = retrieve_result(api, image, args.output)
    print(f'{response["status"]}: {args.output.resolve()}', flush=True)
    if response['status'] == 'failed':
        raise RuntimeError('Coordinator returned a failed run; see result.json')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # SDK/API exceptions may include prompts or credentials; expose our safe messages only.
        print(f'{type(exc).__name__}: {exc}')
        raise SystemExit(1)
