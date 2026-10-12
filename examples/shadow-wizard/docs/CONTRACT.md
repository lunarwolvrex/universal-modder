# Rival ledger boundary (prototype)

There is no live game adapter or interprocess bridge in this build. The Python harness is a synthetic host running the actual Lua rules through Lua 5.4. A later adapter must be validated against the user's Hogwarts Legacy Steam build.

Hogwarts remains authoritative for movement, health, spell hits, missions, enemies, and saves. The ledger owns only rival identity, history, rank, and suggested adaptations. It never supplies movement or combat results. A damage multiplier returned by the ledger is a suggestion until a verified host adapter applies it; the current build does not change damage.

The single-threaded boundary uses named events: observe, begin_encounter, hit, resolve. IDs are stable mod-owned tokens, never raw UObject pointers or recyclable spawn IDs. The adapter must map an eligible ambient enemy to a persistent rival ID and a save-slot-specific profile. This mapping is unresolved. Mission and story actors must be excluded until safe behavior is demonstrated.

Each encounter begins once, records landed spell categories, and resolves once. Death callbacks can be duplicated or delivered during loading: the adapter must deduplicate and gate them before dispatch. Unknown IDs, invalid categories, invalid state transitions and malformed restores fail without mutation. Native player death, actor destruction, level unload and an enemy escaping are different events; destruction alone must not be classified as a kill.

No coordinates, clocks or transport queues cross this boundary. Core calls are synchronous; any future host persistence or worker integration must define its own timing and lifecycle contract. Do not perform blocking disk I/O inside a game callback. Loading another save selects a different profile; profile mismatches fail instead of merging rival history.

Checkpoints use schema 1, profile_id and a sorted rival list. Core snapshot/restore uses detached Lua tables. The harness demonstrates atomic JSON replacement in a mod-only sidecar file, with no access to retail saves. This is test-host persistence, not a verified Hogwarts save integration. A shipping adapter needs a confirmed writable location, single-writer ownership, crash recovery and save/load semantics on Windows.

The first real-game oracle must prove a stable named rival survives a reload, promotion follows an actual player defeat, a remembered category changes only that rival's native combat, and disabling the mod leaves the base game playable. Synthetic success cannot satisfy these checks.
