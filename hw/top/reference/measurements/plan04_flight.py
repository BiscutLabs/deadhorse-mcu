"""Compatibility entry point for the retained flight/wake campaign after PLAN05.

The old lite-owned oscillator/loader fixture is retired under E1-E3.
The production benchmark retains the workloads, limits, checksums and faults.
"""
from plan05_flight import main
if __name__=='__main__':main()
