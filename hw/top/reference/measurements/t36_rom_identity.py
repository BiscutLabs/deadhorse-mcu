"""Authenticate the initialized production ROM before mapping any constants."""
import hashlib
import re
from pathlib import Path

def authenticate(design, item, image, emitted):
    words=image.read_text().split()
    if len(words)!=16384 or any(not re.fullmatch(r"[0-9a-fA-F]{8}",w) for w in words):
        raise ValueError("ROM image must contain exactly 16384 initialized words")
    p=item["parameters"]
    if (p["SIZE"],p["WIDTH"],p["WR_PORTS"],p["ABITS"])!=(16384,32,0,14):
        raise ValueError("Unexpected production ROM shape or write port")
    cell=design["modules"][item["module"]]["cells"][item["name"]]
    expected="".join(f"{int(w,16):032b}" for w in reversed(words))
    if cell["parameters"]["INIT"]!=expected:
        raise ValueError("ROM INIT differs from authenticated image or is uninitialized")
    loads=[]
    for path in emitted:
        for name in re.findall(r'\$readmemh\("([^"\n]+)"\s*,',path.read_text()):
            loads.append(name)
    if len(loads)!=1 or Path(loads[0]).resolve()!=image.resolve():
        raise ValueError("Production emission does not bind this exact ROM file once")
    return dict(status="authenticated",image=str(image),
        image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        initialized_bits_sha256=hashlib.sha256(expected.encode()).hexdigest(),
        words_measured=len(words),bytes_measured=len(words)*4,
        identity="Every initialized word matches the sole read-only production ROM")
