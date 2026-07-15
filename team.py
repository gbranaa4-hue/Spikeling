"""
Spike's agent team -- 10 pillar-specialist agents that work the AAA roadmap
(vault/AAA_Roadmap_Tribe.md) through the SAME verified pipeline every other
agent task uses: clarify -> pre-register -> implement -> independent peer
review -> one correction pass -> honest vault ledger (see do_agent_task in
voice_commands.py).

HONEST DESIGN NOTE -- why this is a coordinated crew, not 10 parallel workers:
running many agents concurrently on ONE game's files clobbers shared files
(tribemember.gd, project.godot, main.tscn) with no locking, producing merge
corruption and an un-reviewable blob -- the opposite of the quality bar it's
meant to raise. So the team works a QUEUE: each agent takes one task, runs the
full pipeline to a reviewable diff, and the batch stops for human Godot review
before the next. The "10 agents" are 10 SPECIALISTS (one per AAA pillar), which
is where the real leverage is -- focused expertise per task -- not raw
parallelism. Each agent folds its specialty framing into the task so the
implementer and reviewer both work from that lens.
"""
import sys
import voice_commands as vc

# One specialist per AAA pillar (see the roadmap). name + the lens each brings.
TEAM = [
    {"name": "Juno",  "pillar": "Game Feel & Juice",      "lens": "game feel and juice -- impact, weight, screen shake, hit flash, knockback, particles, hitstop"},
    {"name": "Echo",  "pillar": "Audio",                  "lens": "audio -- layered reactive sound effects, ambience, music buses, positional falloff"},
    {"name": "Pixel", "pillar": "UI / UX & Menus",        "lens": "UI/UX -- clean menus, settings, HUD, control legends, consistency and clarity"},
    {"name": "Lux",   "pillar": "Visual Fidelity",        "lens": "visual fidelity -- lighting, WorldEnvironment, materials, post-processing, the expensive look"},
    {"name": "Sway",  "pillar": "Animation & Character",  "lens": "character animation -- believable movement, smooth transitions, poses, no snapping"},
    {"name": "Vera",  "pillar": "Camera",                 "lens": "camera work -- smoothing, framing, FOV kicks, shake hooks, cinematic transitions"},
    {"name": "Sage",  "pillar": "Onboarding & Tutorial",  "lens": "onboarding -- teaching without a manual, contextual prompts, fading hints"},
    {"name": "Dex",   "pillar": "Systems Depth & Balance","lens": "systems depth and balance -- tunable constants, progression, economy, readable numbers"},
    {"name": "Bolt",  "pillar": "Performance & Technical","lens": "performance and tech -- framerate, LOD, pooling, save/load, defensive null guards"},
    {"name": "Finch", "pillar": "Content, Polish & Edge Cases", "lens": "content and polish -- variety, win/lose screens, persistence, edge-case handling"},
]
TEAM_BY_NAME = {a["name"]: a for a in TEAM}


def roster():
    return "\n".join(f"  {a['name']:6} -- {a['pillar']}" for a in TEAM)


def dispatch(agent, task):
    """Run ONE task through the full pipeline under a given specialist's lens.
    The lens is folded into the task text so the implementer AND the peer
    reviewer both reason from that expertise. Returns the pipeline's result
    string. `task` should already carry its project prefix (e.g. 'tribe: ...')."""
    # Insert the lens right after the project prefix so resolve_project() still
    # sees the project name first.
    if ":" in task:
        proj, rest = task.split(":", 1)
        framed = f"{proj}: (you are {agent['name']}, the {agent['lens']} specialist) {rest.strip()}"
    else:
        framed = f"(you are {agent['name']}, the {agent['lens']} specialist) {task}"
    print(f"\n=== {agent['name']} [{agent['pillar']}] working ===", flush=True)
    result = vc.do_agent_task(framed)
    print(result, flush=True)
    return result


def run_batch(assignments):
    """assignments: list of (agent_name, task). Serialized -- one at a time,
    each to a reviewable diff -- so nothing clobbers a shared file mid-edit.
    Prints a [i/total] progress line per task so a background run shows where
    it is. Returns a list of (agent_name, task, result)."""
    out = []
    total = len(assignments)
    import time as _t
    t0 = _t.time()
    for i, (name, task) in enumerate(assignments, 1):
        agent = TEAM_BY_NAME.get(name)
        if not agent:
            print(f"(no such agent: {name})", flush=True)
            continue
        bar = "#" * i + "-" * (total - i)
        print(f"\n[{bar}] task {i}/{total} -- dispatching {name} ({int(_t.time()-t0)}s elapsed)", flush=True)
        out.append((name, task, dispatch(agent, task)))
        print(f"[{bar}] task {i}/{total} done ({int(_t.time()-t0)}s elapsed)", flush=True)
    print(f"\n=== BATCH COMPLETE ({total}/{total}, {int(_t.time()-t0)}s total) -- review the diff in Godot ===", flush=True)
    return out


if __name__ == "__main__":
    print("Spike agent team:\n" + roster(), flush=True)
