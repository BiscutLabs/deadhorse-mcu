"""Compare prepared and executed MCPs without accepting extra timing overrides."""
import re
from tools.timing.usb_qualification import applied_pairs


def envelope(prepared,applied):
    def lines(text,kind):
        text=re.sub(r'\\\r?\n\s*',' ',text)
        found=[s.strip() for s in text.splitlines() if s.strip().startswith(kind+' ')]
        found=[s.replace('[get_ports clk_PAD]','[get_ports {clk_PAD}]') for s in found]
        if kind=='create_clock':found=[re.sub(r'-period \S+','-period PERIOD',s) for s in found]
        return sorted(found)
    for kind in ('create_clock','create_generated_clock','set_case_analysis'):
        assert lines(prepared,kind)==lines(applied,kind),'Changed '+kind
    names=re.findall(r'^create_(?:generated_)?clock -name (\w+) ',prepared,re.M)
    expected=sorted('set_propagated_clock [get_clocks {'+n+'}]' for n in names)
    assert lines(applied,'set_propagated_clock')==expected,'Clock propagation changed'


def pairs(text):
    text=re.sub(r'\\\r?\n\s*',' ',text)
    allowed={'current_design','create_clock','create_generated_clock','set_case_analysis',
             'set_clock_transition','set_clock_uncertainty','set_propagated_clock',
             'set_timing_derate','set_max_transition','set_max_fanout','set_input_transition',
             'set_load','set_input_delay','set_output_delay','set_multicycle_path'}
    result=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        command=line.split()[0]
        if command not in allowed:raise ValueError('Unexpected timing override: '+command)
        if command!='set_multicycle_path':continue
        match=re.fullmatch(r'set_multicycle_path (\d+) -(setup|hold) -from \[get_pins \{([^{}]+)\}\] -to \[get_pins \{([^{}]+)\}\]',line)
        if match:
            def pins(value):
                names=value.split()
                if len(names)!=len(set(names)):raise ValueError('Duplicate prepared exception pin')
                return '[list '+' '.join('[get_pins {'+n+'}]' for n in names)+']'
            line=f'set_multicycle_path -{match[2]} -from {pins(match[3])} -to {pins(match[4])} {match[1]}'
        result.append(line)
    return applied_pairs('\n'.join(result))
