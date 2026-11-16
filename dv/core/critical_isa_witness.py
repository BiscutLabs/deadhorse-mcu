"""Validate concrete lw/C.ADD activity at the original check-cycle predicate."""

def active_witness(text,instruction,fault):
    wanted={'reset':'checker_inst.reset','check':'checker_inst.check','spec_valid':'checker_inst.spec_valid',
        'valid':'rvfi_valid','instruction':'rvfi_insn','trap':'rvfi_trap','result':'rvfi_rd_wdata',
        'expected':'checker_inst.spec_rd_wdata'}
    names={};values={};scope=[];found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in wanted):return
        raw={n:values[names[n]] for n in wanted}
        if any(set(v)-set('01') for v in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()};insn=d['instruction']
        matches=(insn&0x707f==0x2003) if instruction=='lw' else (insn>>16==0 and insn&0xf003==0x9002 and (insn>>2)&31!=0)
        if d['reset'] or not d['check'] or not d['valid'] or not d['spec_valid'] or not matches:return
        if not fault and d['trap']:return
        expected=0 if d['trap'] else d['expected']
        if d['result']!=(expected^1 if fault else expected):return
        found.append(dict(time=time,values=d,expected=expected))
    for line in text.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='$scope':scope.append(parts[2])
        elif parts[0]=='$upscope':scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for key,suffix in wanted.items():
                if full=='rvfi_testbench.'+suffix:names[key]=parts[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2:values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No concrete checked '+instruction+' '+('result-bit fault' if fault else 'cover'))
    return found[0]
