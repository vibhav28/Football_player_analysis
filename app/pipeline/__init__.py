"""Must run before torch/ultralytics or scikit-learn are imported anywhere
in this package — see the two `os.environ` lines below.

On macOS, `torch` (via `ultralytics`) bundles its own `libomp.dylib`, while
`scikit-learn` dynamically links the separate Homebrew-installed
`libomp.dylib`. When a single pipeline run uses both (YOLO detection, then
K-Means team-color classification), two different OpenMP runtimes end up
loaded in the same process. Under concurrent thread-pool use this crashes
the whole process with SIGSEGV inside libomp — visible as a macOS "Python
quit unexpectedly" crash reporter popup, not a catchable Python exception,
which is why it kills the entire backend rather than just failing one job.

KMP_DUPLICATE_LIB_OK is the standard, widely-used escape hatch for exactly
this "two OpenMP runtimes in one process" conflict (see PyTorch/scikit-learn
issue trackers for the same crash signature on macOS). OMP_NUM_THREADS=1
additionally minimizes actual concurrent OpenMP execution, since the
env var alone silences the safety check without removing the underlying
duplication. Neither is a full fix (a matched build of both libraries
against one shared libomp would be) but both are safe, low-cost, and
sufficient to stop the crash. `setdefault` so an operator can still
override at the shell if needed.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
