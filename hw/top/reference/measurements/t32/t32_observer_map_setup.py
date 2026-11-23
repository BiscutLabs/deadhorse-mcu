from pathlib import Path
p=Path('scratch/t32_area03_map.py').read_text()
p=p.replace("base=root/'build/t32/area03/mapped'","base=root/'build/t32/area04/mapped'")
needle="    (out/'cut.json').write_text(json.dumps(projected))"
insert='''    # Physical boundary excludes only verification retirement observation ports.
    physical=copy.deepcopy(projected)
    removed_observers={n:p for n,p in physical['modules']['DeadhorseSoc']['ports'].items() if n.startswith('rvfi_')}
    assert removed_observers and all(p['direction']=='output' for p in removed_observers.values())
    for name in removed_observers:del physical['modules']['DeadhorseSoc']['ports'][name]
    undo=copy.deepcopy(physical);undo['modules']['DeadhorseSoc']['ports'].update(removed_observers)
    assert undo==projected,'Observer boundary changed functional logic/ports'
    (out/'observer-boundary.json').write_text(json.dumps(dict(removed_ports=removed_observers,
      verification='Exact restoration recovers full instrumented hierarchy; no input or functional output or cell changed'),indent=2)+'\\n')
    projected=physical
'''
assert needle in p;p=p.replace(needle,insert+needle)
Path('scratch/t32_area04_map.py').write_text(p,encoding='utf-8')
for name in ('partition','budget'):
    Path(f'scratch/t32_area04_{name}.py').write_text(Path(f'scratch/t32_area03_{name}.py').read_text().replace('build/t32/area03','build/t32/area04'),encoding='utf-8')
Path('build/t32/area04').mkdir(exist_ok=True)
