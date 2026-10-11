"""Run both loopback-only MVP servers with a shared ephemeral gateway secret."""
import argparse
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-build', action='store_true', help='Serve a previously built Next.js bundle locally')
    parser.add_argument('--test-db', action='store_true', help='Use an isolated ignored browser-test database')
    args = parser.parse_args()
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise SystemExit('Install Node.js 24 LTS and npm, then run npm ci in frontend/.')
    env = os.environ.copy()
    env['TEACHERLENS_GATEWAY_KEY'] = env.get('TEACHERLENS_GATEWAY_KEY') or secrets.token_urlsafe(48)
    env['TEACHERLENS_BACKEND_URL'] = 'http://127.0.0.1:8000'
    env['TEACHERLENS_FRONTEND_ORIGIN'] = 'http://127.0.0.1:3000'
    if args.test_db:
        env['TEACHERLENS_DB'] = str(ROOT / 'outputs' / 'mvp-browser-tests.sqlite')
        env['TEACHERLENS_PROVIDER'] = 'demo'
    env['NEXT_TELEMETRY_DISABLED'] = '1'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'teacherlens.student.api:create_app',
                                          '--factory', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT, env=env, creationflags=flags))
        processes.append(subprocess.Popen([npm, 'run', 'start' if args.production_build else 'dev'],
                                         cwd=ROOT / 'frontend', env=env, creationflags=flags))
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
