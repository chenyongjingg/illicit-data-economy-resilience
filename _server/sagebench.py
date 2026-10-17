import time
import torch
torch.set_num_threads(2)
from torch_geometric.nn import SAGEConv
print("torch_sparse:", end=" ")
try:
    import torch_sparse
    print(torch_sparse.__version__)
except Exception as e:                                          # noqa: BLE001
    print("MISSING", e)
print("torch_scatter:", end=" ")
try:
    import torch_scatter
    print(torch_scatter.__version__)
except Exception as e:                                          # noqa: BLE001
    print("MISSING", e)
for N, E in ((50000, 200000), (822942, 2822983)):
    x = torch.randn(N, 16)
    ei = torch.randint(0, N, (2, E))
    c = SAGEConv(16, 64)
    t = time.time()
    h = c(x, ei)
    print("fwd N=%d E=%d %.2fs" % (N, E, time.time() - t), tuple(h.shape), flush=True)
