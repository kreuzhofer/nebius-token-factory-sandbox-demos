"""Entrypoint shared by coordinator, receipt, and report sandbox jobs."""
import asyncio
import hashlib
import json
import os
import signal
import time
from pathlib import Path


BOOTSTRAP = '''import os, subprocess, sys, time
os.environ['RECEIPT_DEADLINE'] = str(time.monotonic() + int(os.environ.get('RECEIPT_JOB_TIMEOUT', '1800')) - 60)
try:
    install = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
         '--no-cache-dir', '-r', '/app/receipt_demo/requirements.txt'],
        env={'PATH': os.defpath}, capture_output=True, timeout=240)
    if install.returncode:
        print('Dependency installation failed; check the pinned requirements and package access.', flush=True)
        sys.exit(1)
    from receipt_demo.execution import main
    main()
except Exception as exc:
    print('Agent bootstrap failed: ' + type(exc).__name__, flush=True)
    sys.exit(1)
'''

INFERENCE_ENV = ('NEBIUS_API_KEY', 'NEBIUS_BASE_URL', 'NEBIUS_VISION_MODEL',
                 'NEBIUS_AGENT_MODEL', 'NEBIUS_VISION_BASE_URL')


def artifact_refs(artifacts):
    refs = {}
    for name, path in artifacts.items():
        data = Path(path).read_bytes()
        if not data or (name.endswith('.pdf') and not data.startswith(b'%PDF-')):
            raise RuntimeError('Report agent returned invalid artifacts')
        refs[name] = {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return refs


async def run(root=Path('/app')):
    from .agents import Models, ReceiptAgent, ReportAgent, CoordinatorAgent, log
    from .documents import prepare
    from .models import Receipt

    started_at = time.time()
    config = json.loads((root / 'workflow.json').read_text())
    role = config.get('role', 'coordinator')
    execution = None
    # Capture credentials needed for child dispatch before Models removes the inference key.
    if role == 'coordinator' and config.get('mode') == 'v2':
        from sandbox_jobs import SandboxJobs
        from .orchestration import SandboxExecution
        child_env = {key: os.environ[key] for key in INFERENCE_ENV if os.environ.get(key)}
        api = SandboxJobs(os.environ.pop('CONTREE_TOKEN'), os.environ.pop('CONTREE_PROJECT', None),
                          os.environ.pop('CONTREE_BASE_URL', None))
        execution = SandboxExecution(api, config, child_env, root)
    models = Models()
    output, work = root / 'output', root / 'work'
    output.mkdir(parents=True, exist_ok=True)
    log('configuration', role=role, mode=config.get('mode', 'v1'),
        agent_model=models.agent_name, vision_model=models.vision_name)
    try:
        if role == 'coordinator':
            sources = json.loads((root / 'inputs.json').read_text())
            return await CoordinatorAgent(models, execution=execution).run(sources, work, output)
        if role == 'receipt':
            source = json.loads((root / 'inputs.json').read_text())[0]
            receipt = await ReceiptAgent(models).run(source, work / 'pages')
            # Original files travel separately; worker-local paths are not portable.
            receipt.rendered_pages = []
            response = {'status': 'completed', 'receipt': receipt.model_dump(),
                        'started_at': started_at, 'finished_at': time.time()}
        elif role == 'report':
            receipts = [Receipt.model_validate(item) for item in json.loads((root / 'receipts.json').read_text())]
            sources = {s['receipt_id']: s for s in json.loads((root / 'inputs.json').read_text())}
            for receipt in receipts:
                source = sources[receipt.receipt_id]
                try:
                    receipt.rendered_pages, _, _ = prepare(source['path'], work / 'pages' / receipt.receipt_id)
                except Exception:
                    if not receipt.error:
                        raise  # A readable original becoming unavailable is a report failure.
                    receipt.rendered_pages = []
            artifacts = await ReportAgent(models).run(receipts, output)
            response = {'status': 'completed', 'artifacts': artifact_refs(artifacts)}
        else:
            raise ValueError('Unknown sandbox agent role')
    except Exception as exc:
        response = {'status': 'failed', 'error': f'{role} workflow failed ({type(exc).__name__})'}
        log('worker.error', role=role, error=response['error'])
    finally:
        await models.close()
    (output / 'result.json').write_text(json.dumps(response, ensure_ascii=False, indent=2))
    return response


def main():
    async def managed():
        loop, task = asyncio.get_running_loop(), asyncio.current_task()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, task.cancel)
        return await run()
    asyncio.run(managed())
