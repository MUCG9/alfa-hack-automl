One bounded repair of the saved-pair diagnostic environment.

The first posthoc p0 attempt failed technically: sklearn/joblib import requested
local socket.gethostname metadata. The import-only reproduction, without any
verifier/data/label/probability/score access, hit the same fixed tripwire.
This repair permits only that local hostname metadata event. Actual socket,
DNS, connect, bind, subprocess, model/runtime/provider operations remain denied.
Old p0 failure and original incomplete R4 CV remain unchanged. One new p1 attempt
has the same180/120-second and1024MiB caps. No metric was read for this decision.

Also archived: separately reviewed R2 cachepilot preparation/coordinator/verifier
source. Its only R1 correction checks the gate parent cap after final persistence.
No real cache gate/callback, measured savings, new7200 clock or promotion exists.
