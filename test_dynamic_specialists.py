#!/usr/bin/env python
"""
test_dynamic_specialists.py — verifies the real pipeline's live-specialist-
spawning capability (spiking_orchestrator.py's _maybe_spawn_specialist),
wired on top of the self-growing-network mechanism proven in
test_self_growing_network.py.

Four checks, each with an explicit prediction:
  1. SPAWN HAPPENS   -- a task whose Implementer output requests
                         "NEEDS_SPECIALIST: DBMigrator: ..." actually spawns
                         a DBMigrator neuron that fires and appears in `fired`.
  2. GETS REVIEWED    -- the spawned specialist is wired into Reviewer, so
                         Reviewer fires again after it (visible as a second
                         Reviewer entry in `fired`).
  3. DEDUPE           -- requesting the SAME name twice in one run spawns it
                         only once.
  4. GROWTH CAP HOLDS -- a run that requests MORE than MAX_DYNAMIC_SPECIALISTS
                         distinct names only spawns up to the cap, never more
                         (the DRIVE_FLOOR-style guardrail actually works).

    python test_dynamic_specialists.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spiking_orchestrator as so   # noqa: E402


def check_1_spawn_happens() -> bool:
    p = so.SpikingPipeline(
        "rename the fire_rate variable to shot_delay",
        dry_run=True,
        spawn_request=("Implementer", "DBMigrator", "write the schema migration"),
    )
    res = p.run()
    ok = "DBMigrator" in res["fired"] and "DBMigrator" in p._dynamic_specialists
    print(f"  [{'PASS' if ok else 'FAIL'}] 1. spawn happens: fired={res['fired']}")
    return ok


def check_2_gets_reviewed() -> bool:
    p = so.SpikingPipeline(
        "rename the fire_rate variable to shot_delay",
        dry_run=True,
        spawn_request=("Implementer", "DBMigrator", "write the schema migration"),
    )
    res = p.run()
    reviewer_count = res["fired"].count("Reviewer")
    # Implementer -> Reviewer (first pass) -> DBMigrator spawned off Implementer's
    # output -> DBMigrator -> Reviewer again (second pass, reviewing the new work)
    ok = reviewer_count >= 2
    print(f"  [{'PASS' if ok else 'FAIL'}] 2. spawned specialist gets reviewed: "
          f"Reviewer fired {reviewer_count}x, fired={res['fired']}")
    return ok


def check_3_dedupe() -> bool:
    # simulate the SAME request coming from two different sources by
    # calling _maybe_spawn_specialist directly twice with the same name
    p = so.SpikingPipeline("rename x to y", dry_run=True)
    p.rt  # ensure built
    p._maybe_spawn_specialist("Implementer", "NEEDS_SPECIALIST: Foo: do a thing")
    p._maybe_spawn_specialist("Reviewer", "NEEDS_SPECIALIST: Foo: do it again")
    ok = p._dynamic_specialists.count("Foo") == 1
    print(f"  [{'PASS' if ok else 'FAIL'}] 3. dedupe: dynamic_specialists={p._dynamic_specialists}")
    return ok


def check_4_growth_cap_holds() -> bool:
    p = so.SpikingPipeline("rename x to y", dry_run=True)
    p.rt
    names = ["A", "B", "C", "D", "E"]   # 5 requests, cap is MAX_DYNAMIC_SPECIALISTS=2
    for n in names:
        p._maybe_spawn_specialist("Implementer", f"NEEDS_SPECIALIST: {n}: task for {n}")
    ok = (len(p._dynamic_specialists) == so.MAX_DYNAMIC_SPECIALISTS
          and len(p._dynamic_specialists) < len(names))
    print(f"  [{'PASS' if ok else 'FAIL'}] 4. growth cap holds: requested {len(names)}, "
          f"spawned {len(p._dynamic_specialists)} (cap={so.MAX_DYNAMIC_SPECIALISTS})")
    return ok


def check_5_multi_spawn_one_output() -> bool:
    # a single agent turn listing TWO genuinely distinct needs -- both
    # should spawn (cap is 2, so this exactly saturates it); a THIRD in the
    # same output must be dropped, not queued for later.
    p = so.SpikingPipeline("rename x to y", dry_run=True)
    p.rt
    p._maybe_spawn_specialist(
        "Implementer",
        "NEEDS_SPECIALIST: DBMigrator: write the schema migration\n"
        "NEEDS_SPECIALIST: SecurityReview: check the new auth path\n"
        "NEEDS_SPECIALIST: Overflow: this one should be dropped by the cap"
    )
    ok = (p._dynamic_specialists == ["DBMigrator", "SecurityReview"]
          and "Overflow" not in p._dynamic_specialists)
    print(f"  [{'PASS' if ok else 'FAIL'}] 5. multi-spawn from one output "
          f"(3rd correctly dropped by cap): dynamic_specialists={p._dynamic_specialists}")
    return ok


def check_6_non_implementer_source() -> bool:
    # the mechanism is wired generically into EVERY handler -- confirm a
    # spawn triggered by Reviewer (not Implementer) works identically.
    p = so.SpikingPipeline("rename x to y", dry_run=True)
    p.rt
    p._maybe_spawn_specialist("Reviewer", "NEEDS_SPECIALIST: LoadTester: stress-test the endpoint")
    ok = "LoadTester" in p._dynamic_specialists and "LoadTester" in p._specialists
    print(f"  [{'PASS' if ok else 'FAIL'}] 6. non-Implementer source (Reviewer) can spawn: "
          f"dynamic_specialists={p._dynamic_specialists}")
    return ok


def run() -> None:
    print("=" * 74)
    print("  DYNAMIC SPECIALISTS -- wired into the real pipeline")
    print("=" * 74)
    results = [
        check_1_spawn_happens(),
        check_2_gets_reviewed(),
        check_3_dedupe(),
        check_4_growth_cap_holds(),
        check_5_multi_spawn_one_output(),
        check_6_non_implementer_source(),
    ]
    print()
    if all(results):
        print(f"  ALL {len(results)} CHECKS PASS: a specialist can spawn an unanticipated "
              f"sub-specialist live, mid-task, and it's reviewed like any other -- capped "
              f"and deduped so it can't run away.")
    else:
        print(f"  {results.count(False)}/{len(results)} CHECKS FAILED -- do not trust this "
              f"capability until resolved.")


if __name__ == "__main__":
    run()
