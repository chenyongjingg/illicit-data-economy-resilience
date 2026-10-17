#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53b_tgn_smoke.py -- cost + correctness smoke test at E5p's real sizes.

Three things can go wrong here and none of them announces itself:

1. `TGNMemory` writes its memory buffer with an IN-PLACE index assignment
   (`self.memory[n_id] = memory`) inside `update_state`. Doing that under
   autograd, repeatedly, is the classic way to get a version-counter error on
   step 3 -- or, worse, silently dead gradients on step 1 while the loss still
   falls (because the readout head alone can fit the training labels). So the
   test ASSERTS that a non-trivial gradient reaches the GRU and the time encoder
   on the first, second, third and last step, not merely that training ran.

   Note on where the parameters are: with the canonical `IdentityMessage` the
   message module has NO parameters at all -- it is a concat. The learnable
   state transition is the GRUCell plus `TimeEncoder`. Checking
   `msg_module.parameters()` therefore checks nothing, and returns `max() arg is
   an empty sequence` if you ask it for a gradient (this is how the first
   version of this file failed). The check below is written against the
   parameters that exist.

2. `reset_state()` builds a per-node message-store dict of `num_nodes` entries.
   At 822,942 nodes that allocation happens once per epoch and must be cheap.

3. Per-step wall time over ~58k events (TGN) and ~2.8M-edge snapshots
   (GraphSAGE) decides whether 49 steps x N epochs fits at all. Timed here
   rather than extrapolated from a toy that would flatter it.
"""
import json
import sys
import time

import numpy as np
import torch

from torch_geometric.nn.models.tgn import (TGNMemory, IdentityMessage,
                                           LastAggregator)
from torch_geometric.nn import SAGEConv

N_NODES = 822942
EV = 57612
E_FULL = 2822983
STEPS = 49
MEM_DIM = 64
TIME_DIM = 16
RAW_DIM = 3
HID = 64


def time_tgn(r, eval_mode, tag):
    """`t` must be LONG: TGNMemory scatters it into its long `last_update`
    buffer, and a float `t` raises
        RuntimeError: Index put requires the source and destination dtypes match
    The first version of this file passed a float tensor and never got past step
    1. Recorded because the error names dtypes, not the argument.
    """
    torch.manual_seed(12345)
    g = torch.Generator().manual_seed(999)
    t = time.time()
    mem = TGNMemory(num_nodes=N_NODES, raw_msg_dim=RAW_DIM, memory_dim=MEM_DIM,
                    time_dim=TIME_DIM,
                    message_module=IdentityMessage(RAW_DIM, MEM_DIM, TIME_DIM),
                    aggregator_module=LastAggregator())
    r["tgn_construct_s"] = round(time.time() - t, 2)
    r["tgn_n_message_params"] = sum(p.numel()
                                    for p in mem.msg_s_module.parameters())
    r["tgn_n_gru_params"] = sum(p.numel() for p in mem.gru.parameters())
    r["tgn_n_timeenc_params"] = sum(p.numel() for p in mem.time_enc.parameters())

    t = time.time()
    mem.reset_state()
    r["tgn_reset_state_s"] = round(time.time() - t, 2)

    # eval_mode: update_state applies the stored messages to `memory`
    # IMMEDIATELY (it stores first, then updates). train mode does the opposite:
    # it applies whatever was stored by the PREVIOUS call and only then stores
    # this call's messages -- i.e. the committed memory lags one event batch
    # behind, and reading it needs `forward()`, which re-applies the store over
    # whatever node set you hand it. E5p needs the memory state AT t0 for every
    # node in the graph (to feed a SAGEConv readout), so the eval-mode ordering
    # is the one that makes `mem.memory` itself the correct snapshot, and makes
    # `mem.memory` a plain tensor rather than a per-call recomputation.
    if eval_mode:
        with torch.no_grad():
            mem.train(False)

    head = torch.nn.Sequential(torch.nn.Linear(MEM_DIM, 64), torch.nn.ReLU(),
                               torch.nn.Linear(64, 1))
    opt = torch.optim.Adam(list(mem.parameters()) + list(head.parameters()),
                           lr=1e-3)
    step_times, grad_ok = [], {}
    for T in range(1, STEPS + 1):
        t0 = time.time()
        src = torch.randint(0, N_NODES, (EV,), generator=g)
        dst = torch.randint(0, N_NODES, (EV,), generator=g)
        tt = torch.full((EV,), T, dtype=torch.long)
        raw = torch.ones((EV, RAW_DIM))
        mem.update_state(src, dst, tt, raw)

        idx = torch.randint(0, N_NODES, (5400,), generator=g)
        if eval_mode:
            m = mem.memory[idx]          # cheap gather of the committed state
        else:
            m, _ = mem(idx)
        logit = head(m).squeeze(-1)
        y = torch.randint(0, 2, (5400,)).float()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logit, y)
        opt.zero_grad()
        loss.backward()

        def gsum(mod):
            ps = [p for p in mod.parameters() if p.grad is not None]
            if not ps:
                return None
            return float(sum(float(p.grad.abs().sum()) for p in ps))

        if T in (1, 2, 3, STEPS):
            grad_ok["step_%d" % T] = dict(
                gru=gsum(mem.gru), time_enc=gsum(mem.time_enc), head=gsum(head),
                memory_requires_grad=bool(mem.memory.requires_grad),
                loss=float(loss))
        opt.step()
        mem.detach()
        step_times.append(time.time() - t0)
    r["tgn_grad_sums"] = grad_ok
    r["tgn_grad_all_positive"] = all(
        (v["gru"] or 0) > 0 and (v["time_enc"] or 0) > 0 and (v["head"] or 0) > 0
        for v in grad_ok.values())
    r["tgn_step_s_mean"] = round(float(np.mean(step_times)), 3)
    r["tgn_step_s_first"] = round(step_times[0], 3)
    r["tgn_step_s_last"] = round(step_times[-1], 3)
    r["tgn_epoch_s"] = round(float(np.sum(step_times)), 1)
    r["tgn_memory_MB"] = round(mem.memory.numel() * 4 / 1e6, 1)
    # A memory that never moves would make every downstream readout identical
    # and a "trained" TGN indistinguishable from an untrained one.
    r["tgn_memory_absmean_end"] = round(float(mem.memory.abs().mean()), 5)
    r["tgn_memory_norm_changed"] = bool(float(mem.memory.abs().sum()) > 0)
    return r


def time_sage(r):
    """One forward+backward on a snapshot graph the size of the full window."""
    torch.manual_seed(7)
    torch.set_num_threads(8)
    x = torch.randn(N_NODES, 16)
    ei = torch.randint(0, N_NODES, (2, E_FULL))
    conv1 = SAGEConv(16, HID)
    conv2 = SAGEConv(HID, HID)
    head = torch.nn.Linear(HID, 1)
    opt = torch.optim.Adam(list(conv1.parameters()) + list(conv2.parameters())
                           + list(head.parameters()), lr=1e-3)
    idx = torch.randint(0, N_NODES, (5400,))
    y = torch.randint(0, 2, (5400,)).float()
    times = []
    for _ in range(3):
        t0 = time.time()
        h = conv1(x, ei).relu()
        h = conv2(h, ei).relu()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(
            head(h[idx]).squeeze(-1), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
        times.append(time.time() - t0)
    r["sage_full_snapshot_fwdbwd_s"] = [round(v, 3) for v in times]
    r["sage_estimated_epoch_s"] = round(float(np.mean(times)) * STEPS / 2, 1)
    r["sage_note"] = ("per-step cost is ~half the full graph on average, so the "
                      "49-step epoch estimate is mean_snapshot * 49 / 2")
    return r


def main():
    torch.set_num_threads(8)
    r = {}
    for eval_mode, tag in ((False, "train_mode"), (True, "eval_mode")):
        out = {}
        try:
            out = time_tgn(out, eval_mode, tag)
            # re-key so both variants sit side by side
            r["tgn_" + tag] = dict(out, mode=tag, eval_mode=eval_mode,
                                   error=None)
        except Exception as exc:                                # noqa: BLE001
            r["tgn_" + tag] = dict(mode=tag, eval_mode=eval_mode,
                                   error="%s: %s" % (type(exc).__name__, exc),
                                   grad_all_positive=False)
    try:
        r = time_sage(r)
        r["sage_error"] = None
    except Exception as exc:                                    # noqa: BLE001
        r["sage_error"] = "%s: %s" % (type(exc).__name__, exc)
    a = r["tgn_train_mode"]
    b = r["tgn_eval_mode"]
    r["ok"] = bool(a.get("grad_all_positive") and b.get("grad_all_positive")
                   and not r.get("sage_error"))
    with open("/root/cis/results/53b_smoke.json", "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=2)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
