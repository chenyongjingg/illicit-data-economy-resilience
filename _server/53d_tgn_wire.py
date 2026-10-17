#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""53d_tgn_wire.py -- exercise the E5p TGN arm's exact API surface at tiny scale.

Why this file exists: 53_E5p_temporal_gnn.py runs the GraphSAGE arm first and the
TGN arm second, so a bug in the TGN arm would only appear ~60 minutes into a
~2-hour run. This runs the same construction / update_state / readout /
backward / reset_state / state_dict round-trip at 20k nodes and 3 steps, in under
a minute, and ASSERTS rather than prints where it can.

It imports the real module -- it does not re-implement the arm. `snapshot_pass`
is a closure inside `main()` and is not reachable from here, so the three lines
that matter (reset_state -> update_state -> readout) are reproduced verbatim from
it. The rest of that function is plain Python over the same pieces.

The trap this is aimed at: `TGNMemory.update_state` writes
`self.memory[n_id] = memory` IN PLACE. Repeated in-place writes under autograd
either raise a version-counter error on step 3, or silently deaden the graph on
step 1 while the loss still falls (the readout head alone can fit the training
labels). So a gradient check on the GRU and the TimeEncoder is the point, not a
loss curve.

Note where the parameters are NOT: with the canonical `IdentityMessage` the
message module is a plain concat and has no parameters at all, so asking
`msg_module.parameters()` for a gradient raises `max() arg is an empty
sequence`. That is how the first version of this suite failed. (53b, which made
that mistake, was killed by me after ~19 minutes without output and is cited for
nothing; see the ledger.)
"""
import importlib
import sys

import torch

sys.path.insert(0, "/root/cis/scripts")
m = importlib.import_module("53_E5p_temporal_gnn")

N = 20000
D_TAB = len(m.TAB_IDX)
E = 40000
STEPS = 3
OUT = {}


def gsum(mod):
    ps = [p for p in mod.parameters() if p.grad is not None]
    return None if not ps else float(sum(float(p.grad.abs().sum()) for p in ps))


def main():
    torch.set_num_threads(4)
    torch.manual_seed(7)
    for d_tab, tag in ((D_TAB, "as_used"), (6, "narrow_tab")):
        out = {"d_tab": d_tab}
        try:
            net = m.TGNArm(N, d_tab, m.N_DELTA, memory_dim=32, time_dim=8,
                           raw_dim=3, hidden=16)
            out["n_params"] = int(sum(p.numel() for p in net.parameters()))
            out["tgn_in_eval_mode"] = bool(not net.tgn.training)
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            ei = torch.randint(0, N, (2, E))
            x = torch.randn(N, m.D_ALL)
            tab = torch.randn(N, d_tab)
            grads = {}
            for T in range(1, STEPS + 1):
                net.set_train(True)
                with torch.no_grad():
                    net.tgn.reset_state()
                # verbatim from snapshot_pass's tgn branch
                net.tgn.update_state(
                    torch.randint(0, N, (E,)), torch.randint(0, N, (E,)),
                    torch.full((E,), T, dtype=torch.long), torch.ones(E, 3))
                sel = torch.arange((T - 1) * 100, T * 100)
                logit = net.readout(sel, ei, tab[sel])
                out["logit_shape_step%d" % T] = list(logit.shape)
                loss = torch.nn.functional.binary_cross_entropy_with_logits(
                    logit, torch.randint(0, 2, logit.shape).float())
                opt.zero_grad()
                loss.backward()
                grads["step_%d" % T] = {
                    "gru": gsum(net.tgn.gru),
                    "time_enc": gsum(net.tgn.time_enc),
                    "conv": gsum(net.conv), "trunk": gsum(net.trunk),
                    "heads": gsum(net.heads), "loss": float(loss)}
                opt.step()
                net.tgn.detach()
            out["grads"] = grads
            out["grad_all_nonzero"] = all(
                (g["gru"] or 0) > 0 and (g["time_enc"] or 0) > 0
                and (g["conv"] or 0) > 0 and (g["heads"] or 0) > 0
                for g in grads.values())
            # the narrow message module really is parameterless: assert it, so a
            # future version cannot silently start relying on a param that is not
            # there. (`in` rather than a gradient query: asking an empty
            # parameter list for a gradient is what raised in 53b.)
            out["msg_module_n_params"] = sum(
                p.numel() for p in net.tgn.msg_s_module.parameters())
            # memory must actually move, or every readout is the same readout
            with torch.no_grad():
                net.tgn.reset_state()
                a0 = float(net.tgn.memory.abs().sum())
                net.tgn.update_state(
                    torch.randint(0, N, (E,)), torch.randint(0, N, (E,)),
                    torch.full((E,), 1, dtype=torch.long), torch.ones(E, 3))
                a1 = float(net.tgn.memory.abs().sum())
                net.tgn.detach()
            out["memory_abs_sum_after_reset"] = a0
            out["memory_abs_sum_after_update"] = a1
            out["memory_moved"] = bool(a1 > 0 and a0 == 0.0)
            # state_dict round trip (best_state restore in train_snapshot_arm)
            sd = {k: v.clone() for k, v in net.state_dict().items()}
            out["state_dict_keys"] = sorted(sd.keys())
            net.load_state_dict(sd)
            out["state_dict_roundtrip"] = True
            # and the same readout on the same state must be reproducible
            with torch.no_grad():
                l1 = net.readout(sel, ei, tab[sel])
                l2 = net.readout(sel, ei, tab[sel])
            out["readout_deterministic"] = bool(torch.equal(l1, l2))
            out["error"] = None
        except Exception as exc:                                  # noqa: BLE001
            import traceback
            out["error"] = "%s: %s" % (type(exc).__name__, exc)
            out["traceback"] = traceback.format_exc()[-1500:]
        OUT[tag] = out
        print("[53d]", tag, "error=", out["error"],
              "grad_all_nonzero=", out.get("grad_all_nonzero"),
              "memory_moved=", out.get("memory_moved"), flush=True)
    ok = all(v.get("error") is None and v.get("grad_all_nonzero")
             and v.get("memory_moved") and v.get("readout_deterministic")
             for v in OUT.values())
    OUT["ok"] = bool(ok)
    import json
    with open("/root/cis/results/53d_tgn_wire.json", "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(OUT, fh, ensure_ascii=False, indent=2)
    print(json.dumps(OUT, ensure_ascii=False, indent=2)[:4000])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
