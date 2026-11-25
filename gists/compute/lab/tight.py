#!/usr/bin/env python3
"""tight.py IN.cast OUT.cast [CAP=1.0]: cap every inter-event gap; original untouched."""
import json,sys
cap=float(sys.argv[3]) if len(sys.argv)>3 else 1.0
L=open(sys.argv[1]).read().splitlines(); out=[L[0]]; prev=0; t=0
for l in L[1:]:
    e=json.loads(l); gap=min(e[0]-prev,cap); prev=e[0]; t+=gap; e[0]=round(t,3); out.append(json.dumps(e))
open(sys.argv[2],"w").write("\n".join(out)+"\n"); print(f"{sys.argv[2]}: {t:.1f}s")
