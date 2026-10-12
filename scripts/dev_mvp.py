"""Run both loopback-only MVP servers with a shared ephemeral gateway secret."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def load_local_environment(env, path):
    """Literal, allowlisted .env values; existing process configuration wins."""
    allowed = {'AI_PROVIDER', 'HF_TOKEN', 'HF_MODEL', 'HF_FREE_TIER_CONFIRMED',
               'HF_DAILY_REQUEST_LIMIT', 'HF_MONTHLY_REQUEST_LIMIT', 'TEACHERLENS_PROVIDER',
               'TEACHERLENS_OLLAMA_URL', 'TEACHERLENS_OLLAMA_MODEL', 'TEACHERLENS_OLLAMA_LOCALES'}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'): continue
            key, separator, value = line.partition('=')
            if not separator or key.strip() not in allowed:
                raise ValueError('Unsupported local .env setting. See .env.example; values are never executed.')
            env.setdefault(key.strip(), value.strip())
    return env


def frontend_environment(env):
    return {key: value for key, value in env.items() if key.upper() != 'HF_TOKEN'}


def configuration_summary(env, process_env):
    """Show launcher inputs, not secrets or a claim about an already-running server."""
    from teacherlens.student.huggingface import MODEL, ROUTE
    selected = env.get('AI_PROVIDER', env.get('TEACHERLENS_PROVIDER', 'demo'))
    token_present = bool(env.get('HF_TOKEN'))
    confirmed = env.get('HF_FREE_TIER_CONFIRMED', '').lower() == 'true'
    model_supported = env.get('HF_MODEL', MODEL) in (MODEL, ROUTE)
    return {'check_kind': 'launcher_configuration_only',
            'selected': selected if selected in ('demo', 'ollama', 'huggingface') else 'unsupported',
            'token_present': token_present, 'free_tier_confirmed': confirmed,
            'model_supported': model_supported,
            'process_override_keys': [key for key in ('AI_PROVIDER', 'HF_TOKEN', 'HF_MODEL', 'HF_FREE_TIER_CONFIRMED') if key in process_env],
            'blocking_reasons': (['demo_selected'] if selected == 'demo' else
                                 [code for blocked, code in ((not token_present, 'missing_token'),
                                  (not confirmed, 'missing_free_tier_confirmation'),
                                  (not model_supported, 'unsupported_model')) if blocked] if selected == 'huggingface' else []),
            'note': 'Process variables override .env. Existing servers keep their startup configuration until restarted.'}


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-build', action='store_true', help='Serve a previously built Next.js bundle locally')
    parser.add_argument('--test-db', action='store_true', help='Use an isolated ignored browser-test database')
    parser.add_argument('--check-config', action='store_true', help='Print safe effective launcher configuration; no servers or inference calls')
    args = parser.parse_args()
    env = load_local_environment(os.environ.copy(), ROOT / '.env')
    if args.check_config:
        print(json.dumps(configuration_summary(env, os.environ), indent=2))
        return
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise SystemExit('Install Node.js 24 LTS and npm, then run npm ci in frontend/.')
    env['TEACHERLENS_GATEWAY_KEY'] = env.get('TEACHERLENS_GATEWAY_KEY') or secrets.token_urlsafe(48)
    env['TEACHERLENS_BACKEND_URL'] = 'http://127.0.0.1:8000'
    env['TEACHERLENS_FRONTEND_ORIGIN'] = 'http://127.0.0.1:3000'
    if args.test_db:
        env['TEACHERLENS_DB'] = str(ROOT / 'outputs' / 'mvp-browser-tests.sqlite')
        env['TEACHERLENS_PROVIDER'] = 'demo'
        env['AI_PROVIDER'] = 'demo'
        env.pop('HF_TOKEN', None)
    env['NEXT_TELEMETRY_DISABLED'] = '1'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'teacherlens.student.api:create_app',
                                          '--factory', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT, env=env, creationflags=flags))
        processes.append(subprocess.Popen([npm, 'run', 'start' if args.production_build else 'dev'],
                                         cwd=ROOT / 'frontend', env=frontend_environment(env), creationflags=flags))
        print('TeacherLens local synthetic demo: http://127.0.0.1:3000\nPress Ctrl+C to stop both servers.', flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
        raise SystemExit('A local server stopped; inspect the output above. Check that ports 3000 and 8000 are free.')
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    process.terminate()
                process.wait(timeout=15)


if __name__ == '__main__':
    main()
