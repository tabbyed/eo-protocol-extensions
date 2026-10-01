# Running scenes in a game

How a server and a client play the scenes and stories in this folder. A
scene file is authored once (in EO Scene Studio, or by hand) and played by
any server and client that follow this. reoserv and eoweb are the first.

## Who does what

```
 author            server (authority)                     client (presentation)
 ──────            ──────────────────                     ─────────────────────
 studio ──save──▶  data/scenes/*.eoscene.json ─┐
                   data/scenes/*.eostory.json ─┼─ catalog: payloads, trigger index
                   data/scenes/audio/**        ─┘     (built once, on load and change)
                                │
 player walks, talks, kills ──▶ trigger index ──▶ Scene_Open {payload} ──▶ runner
                                                                            │ cues, stand-ins,
                                                                            │ camera, boxes,
 progress table ◀── seen, choice ◀── Scene_Accept / Scene_Close ◀───────────┘ music, sounds
                                     Scene_Use (map cue) ──▶ warp
                                                                fetches audio/** over HTTP
```

- **The server is the authority.** It decides when a scene plays (the
  stories' checkpoints), what the player picked, and where the player
  ends up. It keeps what each character has seen.
- **The client presents a personal scene.** It plays the compiled cues
  itself: stand-ins for the cast, the camera, boxes and choices, music and
  sounds. The real map goes on underneath, hidden for the scene's length.
  The server sends the scene and hears back only the choices, the map cues
  and the end.
- **A world scene is directed by the server.** It plays for everyone in
  range, moving real NPCs and extras as the `actors` extension does. That's
  phase two; personal scenes come first.
- **Hand-written quests can play scenes too:** the EQF action
  `PlayScene("id")` starts one as a checkpoint would.

## Packets (family `Scene`, 244)

| Packet | Way | Fields | |
| --- | --- | --- | --- |
| `Scene_Open` | server → client | `payload` | Play this personal scene now (below) |
| `Scene_Close` | server → client | | Stop the scene playing, if any: the player was warped, killed or kicked |
| `Scene_Remove` | server → client | `player_id` | Another player in range has stepped into an instanced scene: stop drawing them |
| `Scene_Agree` | server → client | `nearby` | They're back, where the scene left them (the same body as `Players_Agree`) |
| `Scene_Accept` | client → server | `choice_cue`, `option` | The player picked an option of a choice cue |
| `Scene_Use` | client → server | `cue` | A `map` cue is due: take the player there |
| `Scene_Close` | client → server | | The scene has ended, or the player skipped it |

Talking to an NPC is reported with the game's own `Quest_Use`, which web
clients send for friendly NPCs as well as quest NPCs.

## The payload

`Scene_Open` carries the scene as compact JSON, in ASCII (anything else is
written `\uXXXX`), so it passes through EO's 8-bit strings. A scene of 66
cues is about 7 KB. It holds only what a client needs:

```json
{
  "id": "blobs-recruit", "kind": "personal", "map": 19,
  "timeOfDay": "18:30", "duck": 0.45,
  "cast": { "ingrid": { "role": "npc", "npc": 311, "at": [39, 9], "facing": "down" }, ... },
  "cues": [ ...the compiled cues... ],
  "audio": {
    "music":  { "shady-dealings": { "url": "music/shady-dealings.ogg", "loop": [5.46, 27.785], "crossfade": 0.2 } },
    "sounds": { "snow-step": ["sounds/snow-step-1.wav", "..."], "ice-crack": ["..."] }
  }
}
```

- `cast` gives every actor's ENF id: for an `npc` cast by `spawn`, the
  server looks it up in the map file.
- `audio` lists only the songs and sounds the scene uses, so the client
  never has to list a folder over HTTP. `url`s are relative to the client's
  `/scenes/audio/`, which serves the server's `data/scenes/audio/`.

## Progress: the schema

```sql
CREATE TABLE IF NOT EXISTS `character_scenes` (
    `character_id` INTEGER NOT NULL,
    `scene` VARCHAR(64) NOT NULL,
    `choices` VARCHAR(255) NOT NULL DEFAULT '',  -- branches picked, comma-separated
    `plays` INTEGER NOT NULL DEFAULT 1,
    `played_at` DATETIME NOT NULL,
    PRIMARY KEY (`character_id`, `scene`),
    FOREIGN KEY (`character_id`) REFERENCES `characters` (`id`) ON DELETE CASCADE
);
```

- One row per scene a character has finished. That's all a story needs:
  a beat is ready when the scenes in its `after` have rows (with the
  choice, where it names one), and a `once` beat is done when its own scene
  has one.
- Read with the character, as its quest progress is; written when the
  character is saved, only the rows that changed.
- The primary key leads with `character_id`, so loading a character's rows
  is one index range.
- Compiled choice cues carry each option's `branch`, so the server records
  the names the stories use, not option numbers.

## Checkpoints: the trigger index

The catalog files every beat under its checkpoint, by key:

| Checkpoint | Key | Checked when |
| --- | --- | --- |
| `enterMap` | map | the character arrives on a map |
| `enterCoord` | (map, x, y) | the character steps onto a tile |
| `leaveMap` | map | the character leaves a map |
| `talkedToNpc` | ENF id | the character talks to an NPC (`Quest_Use`) |
| `killedNpcs` | ENF id | the character kills one; counted from when the beat is ready |
| `gotItems` | item id | the character's inventory gains that item |
| `afterScene` | scene | the character finishes that scene |
| `start` | each scene in `after`; none: login | the beats it waits for have played |

A step, a kill or an item is one hash lookup that usually finds nothing.
The few beats it finds are checked against the character's progress, a hash
lookup for each scene in their `after`. A map with no `enterCoord` beats
isn't looked at per step at all.

## Costs

| What | Cost |
| --- | --- |
| Loading the catalog | O(file bytes + beats), once, again only when a file changes |
| A payload | built once per scene at load; sending it shares the bytes, O(1) |
| A checkpoint | O(1) expected, plus O(b·a) for the b beats under that key (a: their `after` length), almost always 0 or 1 beat |
| A character's progress | O(rows) to load and save, one indexed query each way |
| The client running a scene | O(cues + dependencies) in all: each cue waits on a count of the cues before it, and finishing one counts down its dependents (Kahn's order), so no cue is looked at twice |
| A frame of a scene | O(cues playing + cast) |

## Locks and safety

- While a personal scene plays, the server drops the character's walking,
  attacks and spells if the scene has a `lock` cue, and starts no second
  scene. It forgets the scene on `Scene_Close`, on a warp it didn't ask for,
  on death and on logout.
- A choice is taken only if it names a choice cue of the playing scene and
  an option it has. A map cue is taken only if it's a `map` cue of the
  playing scene, and only once.
- A scene counts as seen when the client closes it, so a player who
  disconnects mid-scene sees it again next time.
- A save while a scene plays keeps the player where the scene found them,
  before its first map step took them away. A player who leaves mid-scene
  comes back there, and the scene can play again.

## Instanced scenes

A personal scene with `"instanced": true` takes the player out of the world
while it plays, for an intro or a dream: other players don't see them, and
nothing reaches them.

- **Others:** when it starts, the server tells the players in range
  (`Scene_Remove`, or `Avatar_Remove` for a classic client). From then on
  it leaves them out of what anyone is told: nearby lists, arrivals on a
  map (a map cue doesn't announce them), coming into range, their emotes,
  chat and equipment, trades and party requests. When it ends, however it
  ends, the players in range see them again where it left them
  (`Scene_Agree`, or `Players_Agree`).
- **Safety:** NPCs, spells, spikes and map drain pass them by.
- **It isn't an admin's hide:** that's a moderator's power, kept with the
  character. An instanced scene lasts only while it plays and is never
  saved; a server keeps the two apart (reoserv: `Character::out_of_sight`
  is either).
- **On the watcher's own screen**, every personal scene shows only its
  cast: the map's other NPCs and other players aren't drawn until it ends.

