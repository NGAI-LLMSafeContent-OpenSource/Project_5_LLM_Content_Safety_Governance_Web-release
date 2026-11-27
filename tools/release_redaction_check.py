"""Check release inventory, approved address redactions, and source provenance."""
from pathlib import Path
import hashlib,ipaddress,json,re
root=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
proof=json.loads((root/'RELEASE_MANIFEST.json').read_text())
alignment=json.loads((root/'SOURCE_ALIGNMENT.json').read_text())
for path,meta in proof['files'].items():
 data=(root/path).read_bytes()
 assert sha(data)==meta['sha256'],path
 assert bool((root/path).stat().st_mode & 0o111)==(meta['mode']=='100755'),path
for path,meta in alignment['source_files'].items():
 assert blob((root/path).read_bytes())==meta['git_blob'],path
for path,meta in alignment.get('authorized_address_redactions',{}).items():
 assert blob((root/path).read_bytes())==meta['release_git_blob'],path
expected=''.join(sha((root/path).read_bytes())+'  '+path+'\n' for path in sorted(set(proof['files'])|{'RELEASE_MANIFEST.json'}))
assert (root/'SHA256SUMS').read_text()==expected,'SHA256SUMS'
networks=[ipaddress.ip_network(n) for n in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']]
for path in proof['files']:
 if Path(path).name in ['requirements.txt','requirement.txt']:continue
 text=(root/path).read_bytes().decode('utf-8',errors='replace')
 # Ignore network range definitions in this checker itself.
 if path=='tools/release_redaction_check.py':continue
 for m in re.finditer(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])',text):
  try:address=ipaddress.ip_address(m.group())
  except ValueError:continue
  assert not any(address in network for network in networks),path
print(json.dumps({'passed':True,'files':len(proof['files'])+2,'authorized_redactions':len(alignment.get('authorized_address_redactions',{})),'checks':['inventory_sha256','file_modes','source_provenance','redaction_hashes','checksum_list','private_ipv4_literals']},sort_keys=True))
