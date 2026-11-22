import hashlib,json,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_qualification import audit_exceptions
mhz=int(sys.argv[1]);base=root/'build/plan03/production-measure06'
cert=json.loads((base/f'certificate09-{mhz}/proof/result.json').read_text())
sdc=base/f'classes-{mhz}/applied.sdc'
counts=audit_exceptions(sdc.read_text(),cert)
bad=sdc.read_text().replace(' 4\n',' 5\n',1)
assert bad!=sdc.read_text()
try:audit_exceptions(bad,cert)
except ValueError:pass
else:raise AssertionError('Wrong setup multiplier escaped')
result=dict(status='pass',counts=counts,wrong_multiplier='rejected',
  sdc_sha256=hashlib.sha256(sdc.read_bytes()).hexdigest(),
  certificate_sha256=hashlib.sha256((base/f'certificate09-{mhz}/proof/result.json').read_bytes()).hexdigest(),
  scope='Exact applied pair inventory; register screen, no new delay-fault qualification or signoff claim')
(base/f'classes-{mhz}/exception-audit02.json').write_text(json.dumps(result,indent=2)+'\n')
print(mhz,result)
