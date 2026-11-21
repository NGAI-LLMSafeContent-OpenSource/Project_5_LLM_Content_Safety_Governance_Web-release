"""Verify a release inventory and run the explicitly declared local checks.

This is release infrastructure, not a replacement for project business code.
Known upstream failures and external-resource checks are reported separately.
"""
import hashlib,json,os,shutil,signal,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=json.loads((ROOT/'release_checks.json').read_text())
alignment=json.loads((ROOT/'SOURCE_ALIGNMENT.json').read_text())
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def tracked_bytes(path):
 if (ROOT/'.git').exists():
  r=subprocess.run(['git','-C',str(ROOT),'show','HEAD:'+path],capture_output=True)
  if r.returncode==0:return r.stdout
 return (ROOT/path).read_bytes()
errors=[]
for path,meta in alignment['source_files'].items():
 if not (ROOT/path).is_file() or blob(tracked_bytes(path))!=meta['git_blob']:errors.append(path)
assert not errors,'Files differ from the pinned original commit: '+str(errors[:8])
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_') and not any(s in k.upper() for s in ['TOKEN','SECRET','PASSWORD','API_KEY']) and k not in ['PYTHONPATH','PYTHONHOME']}
env.update(NO_PROXY='127.0.0.1,localhost,::1',no_proxy='127.0.0.1,localhost,::1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',GRADIO_ANALYTICS_ENABLED='False',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
if env.get('HTTPS_PROXY') or env.get('https_proxy'):env.setdefault('npm_config_https_proxy',env.get('HTTPS_PROXY') or env.get('https_proxy'))
results=[]
with tempfile.TemporaryDirectory(prefix='release-functional-check-') as directory:
 base=Path(directory);work=base/'repo';work.mkdir()
 manifest=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text())
 for path in set(manifest['files'])|{'RELEASE_MANIFEST.json','SHA256SUMS'}:
  source=ROOT/path;dest=work/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
 # Apply only the original project's declared checkout conversions (e.g. CRLF).
 # No source edits or release-specific implementation patches are made.
 if (work/'.gitattributes').exists():
  for args in [['init','-q'],['-c','core.autocrlf=false','add','--all','--force'],['checkout-index','--all','--force']]:
   subprocess.run(['git','-C',str(work),*args],check=True,capture_output=True)
 def expand(argv,port=0):return [str(x).replace('{python}',sys.executable).replace('{root}',str(work)).replace('{temp}',str(base)).replace('{port}',str(port)) for x in argv]
 def environment(item,port=0):
  extra={k:str(v).replace('{root}',str(work)).replace('{temp}',str(base)).replace('{port}',str(port)) for k,v in item.get('env',{}).items()}
  return {**env,**extra}
 for i,item in enumerate(spec.get('commands',[])):
  if any(not os.getenv(k) for k in item.get('requires_env',[])):
   results.append({'name':item['name'],'status':'external_dependency_not_run','requires':item['requires_env']});continue
  args=expand(item['argv']);log=base/('command-'+str(i)+'.log')
  with log.open('wb') as f:
   p=subprocess.Popen(args,cwd=work/item.get('cwd','.'),env=environment(item),stdout=f,stderr=f,start_new_session=True)
   try:rc=p.wait(timeout=item.get('timeout',240))
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();rc=-9
  output=log.read_text(errors='replace');expected=item.get('upstream_failure_contains')
  status='passed' if rc==0 and not expected else 'failed'
  if rc!=0 and expected and expected in output:status='known_upstream_failure'
  result={'name':item['name'],'returncode':rc,'status':status};results.append(result)
  print(json.dumps(result,ensure_ascii=False),flush=True)
  if status=='failed':print(output[-6000:],flush=True)
 def request(port,check):
  body=json.dumps(check['body']).encode() if 'body' in check else None
  req=urllib.request.Request(f'http://127.0.0.1:{port}'+check['path'],data=body,method=check.get('method','GET'),headers={'Content-Type':'application/json'})
  try:
   with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=5) as response:code=response.status;raw=response.read()
  except urllib.error.HTTPError as e:code=e.code;raw=e.read()
  assert code==check.get('status',200),(check['path'],code)
  if 'text_contains' in check:assert check['text_contains'].encode() in raw,check['path']
 for i,item in enumerate(spec.get('servers',[])):
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  log=base/('server-'+str(i)+'.log');result={'name':item['name'],'status':'failed'}
  with log.open('wb') as f:
   p=subprocess.Popen(expand(item['argv'],port),cwd=work/item.get('cwd','.'),env=environment(item,port),stdout=f,stderr=f,start_new_session=True)
   try:
    deadline=time.monotonic()+item.get('startup_timeout',90)
    while True:
     try:request(port,{'path':item.get('ready','/')});break
     except Exception:
      if p.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server did not become ready')
      time.sleep(.2)
    for check in item.get('checks',[{'path':'/'}]):request(port,check)
    result.update(status='passed',http_checks=len(item.get('checks',[{'path':'/'}])))
   except Exception as e:result['error']=str(e)
   finally:
    if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=8)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
  if result['status']=='failed':print(log.read_text(errors='replace')[-6000:],flush=True)
summary={'release_gate_passed':all(r['status']!='failed' for r in results),'source_files_verified':len(alignment['source_files']),'results':results,'scope':spec['scope'],'not_a_full_real_model_acceptance':True}
print(json.dumps(summary,ensure_ascii=False),flush=True)
sys.exit(0 if summary['release_gate_passed'] else 2)
