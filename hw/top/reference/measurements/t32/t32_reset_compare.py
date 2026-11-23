import csv,hashlib,json
from pathlib import Path
base=Path('build/t32');out=base/'soc-area-review'
def read(revision,kind):
    p=base/revision/'mapped'/kind/'paths.tsv'
    with p.open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    keyed={(r.get('domain',''),r.get('mode',r.get('polarity')),r['end']):r for r in rows}
    assert len(keyed)==len(rows)
    return p,keyed
checks={}
for kind in ('reset-endpoints-8','sta-screen-8'):
    before,old=read('area04',kind);after,new=read('area06',kind)
    assert old.keys()==new.keys()
    negative_before={k for k,r in old.items() if float(r['slack_ns'])<0}
    negative_after={k for k,r in new.items() if float(r['slack_ns'])<0}
    assert not negative_after-negative_before,'New violating endpoint'
    checks[kind]=dict(rows=len(new),new_violating_endpoints=0,negative_before=len(negative_before),negative_after=len(negative_after),
        worst_before_ns=min(float(r['slack_ns']) for r in old.values()),worst_after_ns=min(float(r['slack_ns']) for r in new.values()),
        changed_rows=sum(old[k]!=new[k] for k in old),negative_rows=[new[k] for k in sorted(negative_after)],
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (before,after)})
receipt=dict(status='matched_screen_no_new_endpoint_violations',checks=checks,
    qualification='Same raw boundary assumptions and ideal clocks; original negative asynchronous removal and unbuffered-clock pulse diagnostics remain unqualified. No CTS/routed/signoff claim.')
(out/'reset-comparison.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:{n:v for n,v in r.items() if n not in ('negative_rows','hashes')} for k,r in checks.items()}))
