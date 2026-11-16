"""Strict timing of the emitted production core, RF and ASIC clock gate."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import local,measure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    emitted=local(args.emitted)
    result=measure('DeadhorsePerfCore',[str(p) for p in sorted(emitted.glob('*.sv'))],
                   'clk_i',args.output)
    return int(result['status']!='pass')


if __name__=='__main__': sys.exit(main())
