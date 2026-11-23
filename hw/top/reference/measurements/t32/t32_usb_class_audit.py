from pathlib import Path
import hashlib,json,sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from tools.timing.check import screening_limit
out=ROOT/'build/t32/area07/mapped/usb-class-screen02'
p=out/'result.json';r=json.loads(p.read_text())
for name,row in r['classes'].items():
    domain,kind=name.split('.')
    original={'usb':'usbClock','main':'appClock','aon':'aonClock','tck':'tck'}[domain]+'.'+kind
    period={'usb':1000/48,'main':125,'aon':1000,'tck':10000}[domain]
    limit=screening_limit('Usb',original,row['budget_ns'],period,'usb-48mhz')
    delay=row['worst']['delay_ns']
    row.update(failure_limit_ns=limit,classification='fail' if delay>limit else 'warning' if delay>row['budget_ns'] else 'pass',
               scope='Same-domain integrated unchanged USB island; existing D59 policy, FP remains strict 12.5 ns; mandatory post-placement recheck')
r['metadata_correction']='Use maintained screening_limit; prior diagnostic prose generalized D59 too broadly to FP. All numeric path results unchanged.'
r['source_result_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'result03.json').write_text(json.dumps(r,indent=2)+'\n')
print({n:(v['classification'],v['failure_limit_ns']) for n,v in r['classes'].items()})
