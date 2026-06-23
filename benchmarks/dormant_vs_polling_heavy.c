/*
 * Benchmark #3: same dormant-vs-polling comparison, but with a REALISTIC
 * per-NPC "full AI logic" cost instead of a 3-comparison toy FSM.
 *
 * Benchmarks #1 and #2 showed dormancy losing to polling because the
 * polling baseline was too cheap to make skipping it worthwhile. This
 * version gives BOTH models the same heavy_logic() cost (simulated
 * line-of-sight raycast + local-grid pathfinding) whenever they actually
 * have to think about an NPC:
 *   - Polling FSM: runs heavy_logic() for every NPC, every tick, always.
 *   - Spikeling:   runs heavy_logic() + the 5-neuron LIF brain only for
 *                  NPCs inside activation range; dormant NPCs pay only
 *                  the distance check, same as before.
 *
 * This isolates the actual variable that matters: how expensive is the
 * thing being skipped? If heavy_logic() is expensive enough (like real
 * game AI), dormancy should start winning.
 *
 * Build: gcc -O2 -o dormant_vs_polling_heavy.exe dormant_vs_polling_heavy.c -lm
 * Run:   ./dormant_vs_polling_heavy.exe
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>

typedef struct { double x, y; } Vec2;

static double distance_check(Vec2 a, Vec2 b) {
    double dx = a.x - b.x, dy = a.y - b.y;
    return sqrt(dx * dx + dy * dy);
}

/* Simulated "real" per-NPC AI cost: a 16-step raycast (line-of-sight) plus
 * an 8x8 local-grid pathfinding pass. Not a real raycaster/pathfinder --
 * deliberately doing comparable FLOP/branch volume to one, so the
 * benchmark reflects realistic AI cost rather than a token FSM. */
static double heavy_logic(Vec2 pos, Vec2 player_pos) {
    double acc = 0.0;
    /* simulated raycast: 16 steps along the line to the player */
    for (int s = 0; s < 16; s++) {
        double t = s / 16.0;
        double sx = pos.x + (player_pos.x - pos.x) * t;
        double sy = pos.y + (player_pos.y - pos.y) * t;
        acc += sin(sx * 0.1) * cos(sy * 0.1);
    }
    /* simulated local-grid pathfinding: 8x8 cost relaxation pass */
    double grid[8][8];
    for (int gy = 0; gy < 8; gy++)
        for (int gx = 0; gx < 8; gx++)
            grid[gy][gx] = fabs((double)gx - (double)gy) + acc * 0.0001;
    double best = 1e9;
    for (int gy = 0; gy < 8; gy++)
        for (int gx = 0; gx < 8; gx++)
            if (grid[gy][gx] < best) best = grid[gy][gx];
    return acc + best;
}

/* ---------- polling FSM NPC: heavy_logic every NPC, every tick ---------- */

typedef struct { Vec2 pos; double health; int state; } PollingNPC;

/* GCC -O2 proved `cost` was dead in the false branch below and legally
 * sank the heavy_logic() call into the true branch -- silently giving the
 * "naive" polling baseline the same dormancy skip Spikeling does on
 * purpose, which corrupted the comparison (timing scaled with active
 * fraction even though this function was supposed to run heavy_logic
 * unconditionally). Forcing the result through a volatile global sink
 * makes it a observable side effect the optimizer can't legally skip,
 * restoring the "actually always pays the cost" baseline this function
 * is meant to represent. */
volatile double g_sink = 0.0;

static void polling_tick(PollingNPC *n, Vec2 player_pos, double activation_range) {
    double dist = distance_check(n->pos, player_pos);
    double cost = heavy_logic(n->pos, player_pos); /* always paid -- now unskippable */
    g_sink = cost;
    if (dist < activation_range) {
        if (n->health < 30.0) n->state = 1;
        else if (cost < 0.0) n->state = 2;
        else n->state = 3;
    } else {
        n->state = 0;
    }
    n->health -= 0.0001;
}

/* ---------- Spikeling dormant LIF NPC ---------- */

typedef struct { double threshold, leak, potential; } LIFNeuron;

static int lif_step(LIFNeuron *neu, double drive) {
    neu->potential += drive;
    neu->potential -= neu->leak;
    if (neu->potential < 0.0) neu->potential = 0.0;
    int fired = neu->potential >= neu->threshold;
    if (fired) neu->potential = 0.0;
    return fired;
}

typedef struct {
    Vec2 pos; double health; int state; LIFNeuron brain[5];
} SpikelingNPC;

static void spikeling_init(SpikelingNPC *n, Vec2 pos) {
    n->pos = pos; n->health = 100.0; n->state = 0;
    for (int i = 0; i < 5; i++) { n->brain[i].threshold = 1.0; n->brain[i].leak = 0.05; n->brain[i].potential = 0.0; }
}

static void spikeling_tick(SpikelingNPC *n, Vec2 player_pos, double activation_range) {
    double dist = distance_check(n->pos, player_pos); /* always paid, cheap */
    if (dist >= activation_range) {
        n->state = 0;
        return; /* heavy_logic() AND the brain are both skipped */
    }
    double cost = heavy_logic(n->pos, player_pos); /* only active NPCs pay this */
    double sight_drive = 1.0 - dist / activation_range;
    if (sight_drive < 0.0) sight_drive = 0.0;
    sight_drive += cost * 0.0; /* keep cost "used" so compiler can't dead-code it away */
    int fired[5];
    for (int i = 0; i < 5; i++) fired[i] = lif_step(&n->brain[i], sight_drive);
    if (fired[1]) n->state = 1;
    else if (fired[4]) n->state = 2;
    else if (fired[2]) n->state = 3;
    else n->state = 4;
    n->health -= 0.0001;
}

/* ---------- benchmark harness ---------- */

static double frand(double lo, double hi) { return lo + (hi - lo) * ((double)rand() / RAND_MAX); }

static double run_polling(int npc_count, double active_fraction, int ticks) {
    double activation_range = 50.0;
    Vec2 player_pos = {0.0, 0.0};
    PollingNPC *npcs = malloc(sizeof(PollingNPC) * npc_count);
    int n_active = (int)(npc_count * active_fraction);
    for (int i = 0; i < npc_count; i++) {
        double r = (i < n_active) ? frand(0, activation_range * 0.8) : frand(activation_range * 1.5, activation_range * 5);
        double angle = frand(0, 2 * M_PI);
        npcs[i].pos.x = r * cos(angle); npcs[i].pos.y = r * sin(angle);
        npcs[i].health = 100.0; npcs[i].state = 0;
    }
    clock_t start = clock();
    for (int t = 0; t < ticks; t++)
        for (int i = 0; i < npc_count; i++)
            polling_tick(&npcs[i], player_pos, activation_range);
    double elapsed = (double)(clock() - start) / CLOCKS_PER_SEC;
    free(npcs);
    return elapsed;
}

static double run_spikeling(int npc_count, double active_fraction, int ticks) {
    double activation_range = 50.0;
    Vec2 player_pos = {0.0, 0.0};
    SpikelingNPC *npcs = malloc(sizeof(SpikelingNPC) * npc_count);
    int n_active = (int)(npc_count * active_fraction);
    for (int i = 0; i < npc_count; i++) {
        double r = (i < n_active) ? frand(0, activation_range * 0.8) : frand(activation_range * 1.5, activation_range * 5);
        double angle = frand(0, 2 * M_PI);
        Vec2 pos = { r * cos(angle), r * sin(angle) };
        spikeling_init(&npcs[i], pos);
    }
    clock_t start = clock();
    for (int t = 0; t < ticks; t++)
        for (int i = 0; i < npc_count; i++)
            spikeling_tick(&npcs[i], player_pos, activation_range);
    double elapsed = (double)(clock() - start) / CLOCKS_PER_SEC;
    free(npcs);
    return elapsed;
}

int main(void) {
    srand(42);
    int ticks = 2000;
    int npc_counts[] = {50, 200, 1000};
    double fractions[] = {0.05, 0.20, 0.50, 1.00};

    printf("%6s %8s %17s %19s %9s\n", "NPCs", "%active", "Polling FSM (s)", "Spikeling LIF (s)", "Speedup");
    for (size_t ci = 0; ci < sizeof(npc_counts)/sizeof(int); ci++) {
        for (size_t fi = 0; fi < sizeof(fractions)/sizeof(double); fi++) {
            int n = npc_counts[ci]; double f = fractions[fi];
            double t_poll = run_polling(n, f, ticks);
            double t_spike = run_spikeling(n, f, ticks);
            double speedup = t_spike > 0 ? t_poll / t_spike : 0.0;
            printf("%6d %7.0f%% %17.4f %19.4f %8.2fx\n", n, f*100, t_poll, t_spike, speedup);
        }
        printf("\n");
    }
    return 0;
}
