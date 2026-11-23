import hashlib,json,re,subprocess
from pathlib import Path
p=Path('build/t19/sram-catalog-review-01/gf180mcu_ocd_ip_sram.tar.zst')
digest=hashlib.sha256(p.read_bytes()).hexdigest()
assert digest=='62c12904ac105fe68fc7ebd91214d6f59b3126edc5c87c4f3238c29bf2fdf6d0'
members=subprocess.check_output(['tar','--zstd','-tf',str(p)],text=True).splitlines();rows=[]
for member in members:
    if not member.endswith('.lef'):continue
    raw=subprocess.check_output(['tar','--zstd','-xOf',str(p),member]);body=raw.decode()
    for name,w,h in re.findall(r'MACRO\s+(\S+).*?SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s*;',body,re.S):
        rows.append(dict(name=name,width_um_measured=float(w),height_um_measured=float(h),area_mm2_estimated=float(w)*float(h)/1e6,lef_sha256=hashlib.sha256(raw).hexdigest()))
out=Path('build/t32/soc-area-review');out.mkdir(exist_ok=True)
(out/'sram.json').write_text(json.dumps(dict(archive_sha256=digest,macros=rows,command='python scratch/t32_sram_review.py'),indent=2)+'\n')
print(json.dumps(rows))
