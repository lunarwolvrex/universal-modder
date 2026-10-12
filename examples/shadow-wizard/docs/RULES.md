# Rival-memory rules

This is an original greybox mechanic inspired by memorable, persistent rivals in
*Middle-earth: Shadow of War*. These rules and numbers are synthetic starting
values. They were not extracted from the native Nemesis system, and they do not
claim to reproduce its behavior. Hogwarts Legacy remains the intended host; this
standalone module has no Hogwarts hooks and does not change either game.

## First-slice behavior

1. A profile observes a rival under a stable ID. New rivals start at rank 1 and
   remain available until an encounter begins.
2. `begin_encounter(id)` opens exactly one encounter for that rival and resets
   its landed-hit counters. Its presentation lists remembered spell categories
   and the illustrative damage multiplier for each category.
3. `hit(id, category)` records one landed hit, rather than a spell cast. Categories
   are `fire`, `control`, `force`, and `curse`. The future host adapter must supply
   the actual spell classification and landed-hit evidence.
4. `resolve(id, outcome)` closes that encounter exactly once. When the rival
   survives through `player_defeated`, `enemy_escaped`, or `enemy_spared`, at least
   three total landed hits permit learning the most-used category. Ties use the
   fixed order fire, control, force, curse. Only that category is considered; an
   already-known dominant category does not cause learning a less-used category.
5. A rival remembers at most two categories. Each has a damage multiplier of
   `0.75`: an illustrative 25% reduction, never immunity. At most one new category
   can be learned per completed encounter. Repeated learning does not stack.
6. Only `player_defeated` promotes a rival, by one rank up to rank 5. A survivor
   becomes available for a later encounter. The core does not spawn that encounter
   or schedule a return in the game world.
7. `enemy_killed` is terminal. The rival gains neither rank nor a new adaptation.
   Existing memory remains in its record for inspection. The same ID cannot start
   another encounter, even if observed again.

The multiplier is presentation data. This simulation records memory; an eventual
verified host adapter would have to apply and validate damage changes in the
actual game. The present build makes no claim about game damage or control effects.

## Public Lua API

```lua
local core = require("rival_core")
local ledger = core.new("steam_lab_profile") -- optional validated snapshot second
ledger:observe("ash_01", "Ash the Persistent")
local introduction = ledger:begin_encounter("ash_01")
ledger:hit("ash_01", "fire")
ledger:hit("ash_01", "fire")
ledger:hit("ash_01", "control")
local result = ledger:resolve("ash_01", "enemy_escaped")
local checkpoint = ledger:snapshot()
local reloaded = core.new("steam_lab_profile", checkpoint)
```

`observe`, `hit`, and `resolve` return a detached rival record. Observing an
existing ID refreshes its display name without reviving it or changing its memory.
`get(id)` returns a detached rival record, or `nil` for an unknown valid ID.
`begin_encounter` returns `{id, display_name, rank, remembered_categories,
damage_multipliers}`. Remembered categories use the same fixed category order;
unremembered categories have multiplier `1`.

Invalid operations raise a Lua error before authoritative state changes. Hits and
resolution require an active encounter; repeated resolution and nested starts are
invalid. Different rivals may have concurrent active encounters. Callers should
use `pcall` at an external event boundary and keep the last successful checkpoint.

## State contract and bounds

A snapshot is a plain Lua table with schema version `1`, its exact `profile_id`,
and a dense `rivals` array. Every rival has these fields:

| Field | Meaning and constraint |
| --- | --- |
| `id` | Unique stable token, 1–128 bytes, `[A-Za-z0-9_-]` only |
| `display_name` | Nonblank valid UTF-8, 1–128 bytes, no ASCII control characters |
| `rank` | Integer 1–5, equal to `min(1 + player_defeats, 5)` |
| `status` | `available`, `in_encounter`, or `dead` |
| `encounters` | Started encounter count, integer 0–1,000,000 |
| `player_defeats` | Completed `player_defeated` count, integer 0–1,000,000 |
| `adaptations` | Dense array of at most two distinct category strings |
| `spell_counts` | All four category keys with integer counts 0–1,000,000 each |
| `last_outcome` | Most recent resolved outcome; omitted before any resolution |

Profile IDs use the same token constraints as rival IDs. A profile holds at most
128 rivals. Capacity failures preserve its existing state. Reaching the rank cap
does not stop the recorded player-defeat counter from increasing. Counts outside
an active encounter are zero. A dead status must agree with `enemy_killed`;
completed-encounter counts, last outcome, promotion, and adaptation counts must
agree. Unknown fields, categories, duplicate IDs, sparse arrays, metatables,
nonfinite numbers, and snapshots for another profile are rejected.

Snapshots contain no file paths, game objects, handles, or timestamps. Input rival
arrays may be unsorted; output arrays are always sorted lexicographically by ID.
Adaptation arrays always use fire, control, force, curse order. Their multiplier
is the fixed rule value `0.75`, supplied through encounter presentation.
Construction validates and copies the complete input before accepting it.
Snapshots and reads contain fresh nested tables: changing them cannot mutate the
live ledger, and later encounters cannot change an earlier checkpoint. The copies
are ordinary writable Lua tables; they are immutable with respect to the core's
future changes, rather than enforced read-only objects.

Serialization, durable file replacement, corrupt-file handling, save/profile
mapping, and stable host identity are adapter responsibilities. The core performs
no file I/O, launches no guest game, and has no IPC service or invented host hooks.
