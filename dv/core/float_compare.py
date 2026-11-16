"""Independent architectural effects and RV32IMFC retirement comparison."""
import copy

from lockstep import BASE, architectural_effect, completion_window, normalize


def effect(insn, regs, floats):
    """Return X destination, F destination or None, F sources, memory access.

    Instruction fields follow the ISA, not the candidate's integer proxy decode.
    Results come exclusively from the pinned QEMU snapshots.
    """
    opcode=insn&127
    if insn==0x30200073: return 0,None,{},None # MRET has no GPR destination.
    if insn&3!=3:
        quadrant,kind=insn&3,insn>>13
        if quadrant in (0,2) and kind in (3,7):
            rd,access=architectural_effect(insn^(1<<13),regs)
            write,address,width,_=access
            source=(8+((insn>>2)&7)) if quadrant==0 else ((insn>>2)&31)
            return 0,None if write else rd,{2:source} if write else {},(
                write,address,width,floats[source] if write else 0)
    elif opcode in (7,0x27):
        if (insn>>12)&7!=2: raise ValueError('Unsupported FP memory encoding')
        rd,access=architectural_effect(insn^4,regs)
        write,address,width,_=access
        source=(insn>>20)&31
        return 0,None if write else rd,{2:source} if write else {},(
            write,address,width,floats[source] if write else 0)
    elif opcode in (0x43,0x47,0x4b,0x4f):
        if (insn>>25)&3: raise ValueError('Non-single fused instruction')
        return 0,(insn>>7)&31,{1:(insn>>15)&31,2:(insn>>20)&31,3:insn>>27},None
    elif opcode==0x53:
        function=insn>>25; rd=(insn>>7)&31; rs1=(insn>>15)&31; rs2=(insn>>20)&31
        if function in (0,4,8,12,16,20): return 0,rd,{1:rs1,2:rs2},None
        if function==44: return 0,rd,{1:rs1},None
        if function==80: return rd,None,{1:rs1,2:rs2},None
        if function in (96,112): return rd,None,{1:rs1},None
        if function in (104,120): return 0,rd,{},None
        raise ValueError('Unknown F arithmetic encoding')
    rd,access=architectural_effect(insn,regs)
    return rd,None,{},access


def compare(rows, iss, binary, base=BASE, require_probes=False):
    iss=completion_window(iss,binary,base,allow_compressed_store=True)
    if not rows or len(rows)+1!=len(iss):
        raise ValueError(f'Floating retirement count: RTL={len(rows)} ISS={len(iss)}')
    memory={base+i:b for i,b in enumerate(binary)}
    known=set(); flags_checked=0; float_writes=0; floating=0
    def instruction(pc):
        if pc not in memory or pc+1 not in memory: raise ValueError('Instruction outside image')
        size=4 if memory[pc]&3==3 else 2
        return sum(memory.get(pc+i,0)<<(8*i) for i in range(size))
    expected_fcsr=0; expected_interrupt=False; interrupts=0
    for n,(raw,before,after) in enumerate(zip(rows,iss,iss[1:])):
        got=normalize(raw); pc=before['pc']; insn=instruction(pc)
        def need(condition,reason):
            if not condition: raise ValueError(f'{reason} at retirement {n}, PC {pc:08x}, instruction {insn:08x}')
        need(got['order']==n+1 and not got['trap'] and not got['halt'] and
             bool(got['intr'])==expected_interrupt and got['mode']==3 and got['ixl']==1,'retirement control')
        need(got['pc_rdata']==pc and got['insn']==insn,'instruction/PC')
        irq_entry=(before['mstatus']&8 and not after['mstatus']&8 and
                   after.get('mcause')==0x80000003 and after.get('mtvec',0)&3==1 and
                   after['pc']==(after['mtvec']&~3)+12)
        need(got['pc_wdata']==(after['mepc'] if irq_entry else after['pc']),'next PC / precise IRQ boundary')
        expected_interrupt=bool(irq_entry)
        if irq_entry: interrupts+=1
        rd,fd,sources,access=effect(insn,before['regs'],before['fregs'])
        need(got['rd_addr']==rd,'integer destination')
        expected=dict(before['regs'])
        if rd:
            need(got['rd_wdata']==after['regs'][rd],'integer result')
            expected[rd]=got['rd_wdata']
        need(expected==after['regs'],'integer state')
        for rs in ('rs1','rs2'):
            need(got[rs+'_rdata']==before['regs'][got[rs+'_addr']],rs+' operand')
        need(got['frs_en']==sum(1<<(i-1) for i in sources),'floating source enables')
        for index,address in sources.items():
            need(got[f'frs{index}_addr']==address,'floating source address')
            need(got[f'frs{index}_rdata']==before['fregs'][address],'floating operand')
        need(bool(got['frd_wen'])==(fd is not None),'floating destination enable')
        if fd is not None:
            need(got['frd_addr']==fd and got['frd_wdata']==after['fregs'][fd],'floating result')
            known.add(fd); float_writes+=1
        for index in known:
            need(got['fregs'][index]==after['fregs'][index],'floating register state')
        need(got['ext_fs']==((after['mstatus']>>13)&3),'FS state')
        if access:
            write,address,width,value=access; mask=(1<<width)-1; data_mask=(1<<(8*width))-1
            need(got['mem_addr']==address and got['mem_wmask' if write else 'mem_rmask']==mask,'memory address/mask')
            if write:
                need(got['mem_wdata']&data_mask==value&data_mask,'store value')
                for i in range(width): memory[(address+i)&0xffffffff]=(value>>(8*i))&255
            else:
                value=sum(memory.get((address+i)&0xffffffff,0)<<(8*i) for i in range(width))
                need(got['mem_rdata']&data_mask==value,'load value')
        if not access or not access[0]: need(got['mem_wmask']==0,'spurious store')
        is_float=bool(sources) or fd is not None or insn&127==0x53
        arithmetic=insn&3==3 and insn&127 in (0x43,0x47,0x4b,0x4f,0x53)
        csr=insn&127==0x73 and (insn>>12)&7 and insn>>20 in (1,2,3)
        if is_float: floating+=1
        # QEMU's text trace omits fcsr. The fixtures insert an architectural
        # CSRR x28,fcsr after each FP operation; use its ISS result, never RTL.
        probe=(n+2<len(iss) and instruction(after['pc'])==0x00302e73)
        if probe:
            expected_fcsr=iss[n+2]['regs'][28]
            need(got['ext_fcsr']==expected_fcsr,'exception flags/rounding CSR')
            flags_checked+=1
        elif arithmetic or csr:
            if require_probes and insn!=0x00302e73:
                raise ValueError('Missing architectural FCSR probe')
            # An uninstrumented flight build still compares FP values at every
            # retirement; its flags are only checked when a real CSR read occurs.
            if insn!=0x00302e73: expected_fcsr=None
        if insn==0x00302e73:
            expected_fcsr=after['regs'][28]
            need(got['ext_fcsr']==expected_fcsr,'FCSR read')
        elif expected_fcsr is not None and not (arithmetic or csr):
            need(got['ext_fcsr']==expected_fcsr,'unexpected FCSR change')
    last=normalize(rows[-1])
    if not(last['mem_addr']==0x100000 and last['mem_wmask']==15 and last['mem_wdata']==0x5555):
        raise ValueError('Missing success finisher')
    return dict(retirements=len(rows),floating_instructions=floating,float_writes=float_writes,interrupts=interrupts,
                fcsr_probes=flags_checked,initialized_fregs=len(known))


def interrupt_reentry(records,binary,base=BASE):
    """Pinned QEMU MMIO reentry at the exact MSIP-clear/CSR-read boundary.

    Keep every architectural instruction. A repeated identical snapshot of
    CSRR mcause at the same PC after an MSIP clear is an execution-loop reentry,
    not another retired CSR (which must advance PC). No generic deduplication.
    """
    result=[]; duplicates=[]
    def instruction(row):
        offset=row['pc']-base
        return int.from_bytes(binary[offset:offset+4],'little') if 0<=offset<=len(binary)-4 else 0
    for index,record in enumerate(records):
        if len(result)>=2 and record==result[-1]:
            previous=result[-2]; store=instruction(previous)
            if (store&0x707f==0x2023 and instruction(record)==0x34202c73 and
                    record['pc']==previous['pc']+4 and record.get('mcause')==0x80000003 and
                    not record['mstatus']&8 and record['pc']==(record['mtvec']&~3)+16):
                _,access=architectural_effect(store,previous['regs'])
                if access==(True,0x02000000,4,0) and previous['regs']==record['regs'] and previous['fregs']==record['fregs']:
                    duplicates.append(dict(raw_index=index,store_pc=previous['pc'],csr_pc=record['pc']))
                    continue
        result.append(record)
    return result,duplicates


def negative_controls(rows,iss,binary,base=BASE):
    failures={}
    fp=next(i for i,r in enumerate(rows) if r['frd_wen'] and r['frd_addr']==0)
    source=next(i for i,r in enumerate(rows) if r['frs_en'])
    store=next(i for i,r in enumerate(rows) if r['mem_wmask'] and r['mem_addr']!=0x100000)
    for name in ('f0-result','f0-hidden-write','source','flags','fs','integer-result','store','missing-retirement'):
        bad=copy.deepcopy(rows)
        if name=='f0-result': bad[fp]['frd_wdata']^=1
        elif name=='f0-hidden-write': bad[fp]['fregs'][0]^=1
        elif name=='source': bad[source]['frs1_rdata']^=1
        elif name=='flags': bad[fp]['ext_fcsr']^=1
        elif name=='fs': bad[fp]['ext_fs']^=1
        elif name=='store': bad[store]['mem_wdata']^=1
        elif name=='integer-result': next(r for r in bad if r['rd_addr'])['rd_wdata']^=1
        else: bad.pop(fp)
        try: compare(bad,iss,binary,base)
        except ValueError as exc: failures[name]=str(exc)
        else: raise ValueError('Escaped floating checker fault: '+name)
    return failures
