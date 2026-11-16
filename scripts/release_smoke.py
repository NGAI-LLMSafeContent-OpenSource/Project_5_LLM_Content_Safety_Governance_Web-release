"""Build and exercise the minimal release in disposable environments."""
from pathlib import Path
import functools
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import venv

ROOT = Path(__file__).resolve().parents[1]
# Local checks must not traverse a caller's HTTP proxy.
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def main():
    if sys.version_info < (3, 11):
        raise RuntimeError('Python >=3.11 is required')
    for tool in ['node', 'pnpm']:
        if not shutil.which(tool):
            raise RuntimeError('Missing '+tool+'; install Node.js 20/22 and pnpm 9 first')
    # No inherited application configuration, model keys or development import paths.
    env = {k:v for k,v in os.environ.items() if k in ['PATH','HOME','SYSTEMROOT','SystemRoot','WINDIR','TEMP','TMP','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR']}
    def run(argv, cwd=ROOT):
        subprocess.run([str(x) for x in argv],cwd=cwd,env=env,check=True,timeout=900)
    with tempfile.TemporaryDirectory(prefix='topic5-release-smoke-') as tmp:
        tmp=Path(tmp);venv_dir=tmp/'venv'
        venv.EnvBuilder(with_pip=False).create(venv_dir)
        python=venv_dir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        # The caller needs pip; --python installs into the isolated environment.
        run([sys.executable,'-m','pip','--isolated','--python',python,'install','--no-cache-dir','-r',ROOT/'web/backend/requirements.txt'])
        backend=ROOT/'web/backend'
        run([python,'-B','-m','pytest','tests/test_health.py','tests/test_governance_sessions.py','-q'],backend)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        service_env=dict(env,DATABASE_URL='sqlite+aiosqlite:///'+(tmp/'empty.sqlite').as_posix(),GOVERNANCE_ASSISTANT_PROVIDER='stub',GOVERNANCE_SKILL_RUNTIME_MODE='off',TOPIC1_VALUE_QA_AUTO_ENSURE='false',TOPIC2_RISK_DETECT_METHOD='keyword',BENCHMARK_ARTIFACT_ROOT=str(tmp/'artifacts'))
        with (tmp/'server.log').open('w+b') as log:
            process=subprocess.Popen([str(python),'-B','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=backend,env=service_env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+45;healthy=False
                while time.monotonic()<deadline and process.poll() is None:
                    try:
                        with LOCAL_HTTP.open('http://127.0.0.1:'+str(port)+'/health',timeout=1) as response:
                            data=json.load(response)
                            healthy=response.status==200 and data.get('code')==0 and data.get('data',{}).get('status')=='ok'
                        if healthy:break
                    except OSError:time.sleep(.2)
                if not healthy:
                    log.seek(0);raise RuntimeError('Empty database HTTP startup failed:\n'+log.read().decode(errors='replace')[-6000:])
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        front=ROOT/'web/frontend'
        run(['pnpm','install','--frozen-lockfile','--ignore-scripts','--store-dir',str(tmp/'pnpm-store')],front)
        run(['pnpm','build'],front)
        handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(front/'dist'))
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with LOCAL_HTTP.open('http://127.0.0.1:'+str(server.server_port)+'/',timeout=5) as response:
                html=response.read().decode()
                if response.status!=200 or '<html' not in html.lower() or '/assets/' not in html:
                    raise RuntimeError('Built frontend page check failed')
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
        # Exercise the exact production entry, including SPA refresh and 404 boundaries.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        deploy_env=dict(service_env,PORT=str(port),STUDIO_DATA_DIR=str(tmp/'studio-data'))
        with (tmp/'production.log').open('w+b') as log:
            process=subprocess.Popen([str(python),'-B',str(ROOT/'deploy/serve.py')],cwd=ROOT,env=deploy_env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+45
                while time.monotonic()<deadline and process.poll() is None:
                    try:
                        with LOCAL_HTTP.open(f'http://127.0.0.1:{port}/health',timeout=1) as response:
                            if json.load(response).get('data',{}).get('status')=='ok':break
                    except OSError:time.sleep(.2)
                else:
                    log.seek(0);raise RuntimeError('Production entry failed: '+log.read().decode(errors='replace')[-4000:])
                for path in ['/', '/governance', '/studio/deep/link']:
                    with LOCAL_HTTP.open(f'http://127.0.0.1:{port}'+path,timeout=5) as response:
                        assert response.status==200 and b'/assets/' in response.read(),path
                for path in ['/api/no-such-endpoint','/assets/missing.js']:
                    try:LOCAL_HTTP.open(f'http://127.0.0.1:{port}'+path,timeout=5)
                    except urllib.error.HTTPError as exc:assert exc.code==404
                    else:raise RuntimeError('Missing endpoint became HTML: '+path)
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        print(json.dumps({'passed':True,'backend':'pytest plus empty-database HTTP health','frontend':'frozen install, production build and HTTP page'},ensure_ascii=False))

if __name__=='__main__':main()
