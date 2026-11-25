"""Logical pad inventory/configuration check, including rejection controls."""
import argparse,copy,hashlib,json,pathlib,re,sys,time
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]


def validate(plan,soc,slot):
 expected={(name,lane) for name,pin in soc['pins'].items() if name!='osc_in' for lane in range(pin['width'])}
 observed=[]
 for category,count in [('inputs',12),('bidir',40)]:
  rows=plan[category]
  if len(rows)!=count or {row[0] for row in rows}!=set(range(count)):raise ValueError('Missing/duplicate pad index')
  for index,side,function,lane in rows:
   if (function,lane) not in expected:raise ValueError('Unknown production pin')
   if (category=='inputs') != (soc['pins'][function]['direction']=='input'):raise ValueError('Wrong pad direction')
   # Slot data is configuration, not RTL text. Decode the literal escaped index.
   instance=f'{category}[{index}].pad'
   names={str(s).replace('\\','') for s in slot['PAD_'+side.upper()]}
   if instance not in names:raise ValueError('Wrong pad side')
   observed.append((function,lane))
 if len(observed)!=len(set(observed)) or set(observed)!=expected:raise ValueError('Lost/duplicate production function')
 if plan['dedicated']!={'clk_pad':{'function':'osc_in','side':'south','cell':'gf180mcu_fd_io__in_s'},'rst_n_pad':{'function':'reset_n','side':'south','cell':'gf180mcu_fd_io__in_c'}}:raise ValueError('Dedicated clock/reset binding changed')
 if plan['library']!='gf180mcu_fd_io' or plan['input_cell']!='gf180mcu_fd_io__in_c' or plan['bidir_cell']!='gf180mcu_fd_io__bi_24t' or plan['analog_cell']!='gf180mcu_fd_io__asig_5p0':raise ValueError('Wrong approved pad cell')
 if plan['analog']!=[[0,'north','unassigned'],[1,'north','unassigned']]:raise ValueError('Analog spare assignment changed')
 mux=soc['pad_mux'];aliases=plan['aliases']
 if aliases['boot_mode']!=mux['boot_mode']['pad'] or aliases['aon_gpio']!=mux['aon_gpio']:raise ValueError('Changed strap/AON mux')
 if aliases['aon_spi']!={name:mux['aon_gpio'][index] for name,index in mux['aon_spi'].items()} or aliases['radio_gpio']!=[mux['aon_gpio'][i] for i in mux['radio_gpio']]:raise ValueError('Changed AON SPI/radio mux')
 return dict(digital_spares=0,analog_spares=2,ordinary_inputs=12,bidirectional_or_output=40,dedicated_clock_reset=2)


def main():
 start=time.monotonic();p=argparse.ArgumentParser();p.add_argument('--template',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 here=pathlib.Path(__file__).parent;lock=json.loads((here/'template.lock.json').read_text());source='librelane/slots/slot_1x1.yaml';slotpath=(ROOT/a.template/source).resolve();slotpath.relative_to(ROOT/'build')
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert sha(slotpath)==lock['files'][source]
 paths=[here/'pad-map.yaml',ROOT/'hw/top/reference/soc.yaml',slotpath,here/'template.lock.json',pathlib.Path(__file__)]
 plan,soc,slot=[yaml.safe_load(p.read_text()) for p in paths[:3]];assert plan['template_revision']==lock['revision']
 counts=validate(plan,soc,slot);rejected=[]
 for fault in ('missing-function','duplicate-pad','wrong-side','wrong-direction','wrong-strap'):
  bad=copy.deepcopy(plan)
  if fault=='missing-function':bad['bidir'].pop()
  elif fault=='duplicate-pad':bad['bidir'][1][0]=0
  elif fault=='wrong-side':bad['bidir'][0][1]='north'
  elif fault=='wrong-direction':bad['inputs'][0][2]='osc_en'
  else:bad['aliases']['boot_mode']='gpio2'
  try:validate(bad,soc,slot)
  except ValueError:rejected.append(fault)
  else:raise ValueError('Pad-map fault escaped: '+fault)
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 result=dict(status='logical_inventory_pass',seconds=time.monotonic()-start,counts=counts,negative_controls=rejected,input_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},scope='No pad adapter RTL, electrical, placement or physical fit claim')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS logical pad inventory and five rejected faults; no physical fit claim')

if __name__=='__main__':main()
