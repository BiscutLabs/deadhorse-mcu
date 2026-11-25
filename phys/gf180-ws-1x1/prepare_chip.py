"""Authenticate the template and apply only the documented chip socket binding."""
import argparse, hashlib, json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--simulation',action='store_true');a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build')
    subprocess.run([sys.executable,str(HERE/'prepare_template.py'),'--source',a.source,'--output',a.output],check=True,cwd=ROOT)
    original=json.loads((out/'receipt.json').read_text())
    files=['chip_core.sv','chip_pad_feedback.sv','pad-map.yaml','prepare_chip.py']
    inputs={str((HERE/n).relative_to(ROOT)):sha(HERE/n) for n in files}
    replacements=[]
    target=out/'src/chip_core.sv'
    replacements.append(dict(file='src/chip_core.sv',before=sha(target),after=sha(HERE/'chip_core.sv'),reason='Replace example core with production SoC socket binding'))
    target.write_bytes((HERE/'chip_core.sv').read_bytes())
    (out/'src/chip_pad_feedback.sv').write_bytes((HERE/'chip_pad_feedback.sv').read_bytes())
    defines='`define SLOT_1X1\n`define PAD_gf180mcu_fd_io\n`define SRAM_gf180mcu_ocd_ip_sram\n'
    if a.simulation:
        defines+='`define DEADHORSE_PAD_TEST\n'
        top=out/'src/chip_top.sv';before=sha(top);text=top.read_text()
        # Simulation-only ports reach only the existing named analog models.
        port='    input wire model_lfClock, model_porReference,\n    input wire [11:0] model_supplyMv,\n'
        needle='    inout  wire clk_PAD,';assert text.count(needle)==1;text=text.replace(needle,port+needle)
        needle='        .clk        (clk_PAD2CORE),';assert text.count(needle)==1
        text=text.replace(needle,'        .model_lfClock(model_lfClock), .model_porReference(model_porReference),\n        .model_supplyMv(model_supplyMv),\n'+needle)
        top.write_text(text)
        replacements.append(dict(file='src/chip_top.sv',before=before,after=sha(top),reason='Named simulation fixture only: expose analog-model stimulus, no production pin change'))
    (out/'src/generated_defines.svh').write_text(defines)
    result=dict(status='prepared_not_qualified',simulation=a.simulation,template_receipt=original,
        input_sha256=inputs,patches=replacements,
        artifact_sha256={str(q.relative_to(out)):sha(q) for q in (out/'src').glob('*') if q.is_file()})
    (out/'chip-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS authenticated chip socket preparation; physical fit not claimed')
if __name__=='__main__':main()
