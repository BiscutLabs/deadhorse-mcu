"""Measured flattened-cell area attributed to exclusive endpoint cones plus shared glue."""
import collections,hashlib,json,re,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_boundary import groups
base=root/'build/t32/area06/mapped'
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',body)[1]) for n,body in groups(lib.read_text(),'cell')}
for mhz in (8,):
    out=base/f'map-{mhz}';m=json.loads((out/'canonical.json').read_text())['modules']['DeadhorseSoc']
    original=json.loads((out/'bound-hier.json').read_text())['modules']
    top=original['DeadhorseSoc'];sub=original['SocI1Peripherals$DeadhorseSoc.subsystem']
    blocks={n:c['type'].split('$')[0] for n,c in top['cells'].items() if c['type'] in original and n!='subsystem'}
    blocks.update({'subsystem.'+n:c['type'].split('$')[0] for n,c in sub['cells'].items() if c['type'] in original})
    def labels(alias):return {p for p in blocks if alias==p or alias.startswith(p+'.')}
    aliases=collections.defaultdict(set)
    for n,v in m['netnames'].items():
        for b in v['bits']:
            if isinstance(b,int):aliases[b].update(labels(n))
    # A source filename can recover a pruned private state alias only when all
    # occurrences of that emitted module belong to the same production block.
    src_blocks=collections.defaultdict(set)
    for n,mod in original.items():
        path=n.split('$',1)[-1].removeprefix('DeadhorseSoc.')
        src=mod.get('attributes',{}).get('src','').split(':')[0]
        if src:src_blocks[src].update(labels(path))
    cells=m['cells'];drivers={};seq={};owners={};domains={}
    for n,c in cells.items():
        for pin,direction in c['port_directions'].items():
            if direction=='output':
                for b in c['connections'][pin]:
                    if isinstance(b,int):assert b not in drivers;drivers[b]=n
    clock_roots={m['ports'][p]['bits'][0]:d for p,d in [('mainClock','main'),('i1_aonClock','aon'),('i1_usbClock','usb'),('i1_inactive_jtagTck','tck')]}
    def clock_domain(bit,seen=()):
        if bit in clock_roots:return clock_roots[bit]
        assert bit not in seen and bit in drivers
        c=cells[drivers[bit]]
        if '__icgtp_' in c['type']:return clock_domain(c['connections']['CLK'][0],(*seen,bit))
        assert '__buf_' in c['type'] or '__clkbuf_' in c['type'] or '__inv_' in c['type']
        return clock_domain(c['connections']['I'][0],(*seen,bit))
    for n,c in cells.items():
        clock_pins=[p for p in ('CLK','CLKN') if p in c['connections']]
        if not clock_pins:continue
        assert len(clock_pins)==1
        seq[n]=c;domain=clock_domain(c['connections'][clock_pins[0]][0]);domains[n]={domain}
        found=set().union(*(aliases[b] for b in c['connections'].get('Q',[])))
        if not found:found=src_blocks[c.get('attributes',{}).get('src','').split(':')[0]]
        if n.startswith(('subsystem.usb.','usb_enable_replica_')):found={'subsystem.usb'}
        owners[n]=found or {'unattributed state'}
    def propagate(initial):
        result={n:set(v) for n,v in initial.items()};queue=collections.deque(initial)
        while queue:
            n=queue.popleft();c=cells[n]
            for pin,direction in c['port_directions'].items():
                if direction!='input' or pin in ('CLK','CLKN'):continue
                for b in c['connections'][pin]:
                    upstream=drivers.get(b)
                    if upstream is None or upstream in seq:continue
                    before=result.setdefault(upstream,set());extra=result[n]-before
                    if extra:before.update(extra);queue.append(upstream)
        return result
    cone_owners=propagate(owners);cone_domains=propagate(domains)
    rows={};domain_rows={};assignments={}
    for n,c in cells.items():
        a=areas[c['type']];bs=cone_owners.get(n,set());ds=cone_domains.get(n,set())
        # Do not charge a shared cone in full to multiple blocks/domains.
        block=next(iter(bs)) if len(bs)==1 else 'shared inter-block glue' if bs else 'output-only/unattributed glue'
        domain=next(iter(ds)) if len(ds)==1 else 'shared clock/reset/domain glue' if ds else 'output-only/unattributed glue'
        for group,key in [(rows,block),(domain_rows,domain)]:
            row=group.setdefault(key,dict(area_um2=0,cells=0,sequential_cells=0))
            row['area_um2']+=a;row['cells']+=1;row['sequential_cells']+=int(n in seq)
        assignments[n]=dict(block=block,domain=domain,area_um2=a)
    total=sum(v['area_um2'] for v in rows.values())
    stat=float(re.findall(r'Chip area.*?:\s*([\d.]+)',(out/'area.txt').read_text())[-1])
    assert abs(total-stat)<.00001 and abs(total-sum(v['area_um2'] for v in domain_rows.values()))<.00001
    (out/'area-partition.json').write_text(json.dumps(dict(status='measured',area_um2=total,
      by_block=rows,by_domain=domain_rows,block_types=blocks,cells=assignments,
      method='Exclusive backward endpoint cones on actual flattened cells; stop at every sequential output; shared cones counted once in explicit shared rows; output-only/unattributed glue retained separately. This is an allocation of mapped cells, not a sum of standalone block estimates.',
      limitations='Includes RVFI observation logic and USB packet RAM standard cells; excludes six SRAM/ROM sockets and physical routing/CTS/pads. Shared/unattributed rows prevent claiming a uniquely measurable intrinsic block area.',
      hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'canonical.json',out/'bound-hier.json',out/'area.txt',lib,Path(__file__)]}),indent=2)+'\n')
    print(mhz,'area mm2',total/1e6,'domain allocations',domain_rows,flush=True)
