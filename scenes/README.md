# Scenes

A file format for cutscenes: NPCs that walk, turn, speak and animate on cue,
with a camera, dialogue and choices. An editor writes a scene; servers and
clients play it. Made for Forest Rift's reoserv server, eoweb client and scene
studio, but nothing in the format is tied to them.

Status: draft, format 1, played by reoserv and eoweb.

| File | What it is |
| --- | --- |
| `README.md` | The format: scenes, the cast, the runner rules, sound, stories (this file) |
| `RUNTIME.md` | Playing scenes in a game: the packets, the payload, progress, checkpoints, instancing, costs |
| `scene.schema.json`, `story.schema.json` | The format, as JSON Schema (draft-07) |
| `net/` | The `Scene` packet family (244), in eolib's protocol.xml form |
| `check_scene.py` | Checks scenes and stories against the schemas and the rules below |
| `examples/` | Small examples of the format, frozen: a guard, a world scene, and the blob story with its two scenes |

A game's own scenes live with its server: Forest Rift's are in reoserv's
`data/scenes`, whose README says how to add one, step by step.

```
pip install jsonschema
python check_scene.py examples/*.eoscene.json examples/*.eostory.json
```

## A scene file

A scene is `<id>.eoscene.json`. Its top level says what the scene is, and
then has two halves:

- **`source`** is what an editor authors: tracks, clips anchored to other
  clips, named markers. Only editors read it, and a scene may leave it out.
- **`compiled`** is what servers and clients run: a flat list of cues, with
  every walk already turned into the tiles it steps on.

The editor does the hard work once, when it saves: it finds paths, resolves
anchors and checks the rules. A runner only has to start each cue when the
cues it waits for are done.

| Field | Meaning |
| --- | --- |
| `format` | `1`. A runner refuses a format it doesn't know. |
| `id` | The scene's name, as EQF's `PlayScene` and `$scene` use it |
| `title` | Optional: its name for people |
| `summary` | Optional: what happens in it, in a sentence or two, for the [story](#stories) it's in and whoever writes the next scene |
| `kind` | `personal` or `world` (below) |
| `map` | The map it plays on |
| `timeOfDay` | Optional: the time of day it plays at, as `"22:00"` (below) |
| `footsteps` | Optional: the surface walks sound on (see [Sound](#sound)) |
| `duck` | Optional: how loud the music stays under lines and choices, 0 to 1 (see [Sound](#sound)) |
| `cast` | Everyone in it, by name |

Units: tiles are `[x, y]`, times are milliseconds, directions are `down`,
`left`, `up` and `right`.

## Personal and world scenes

A **personal** scene plays for one player. It can lock them, move the camera,
take them to other maps, show a letterbox and dialogue boxes, and ask them to
choose. NPCs from the map
appear as stand-ins on that player's screen only: their client hides the real
NPC for the scene and shows a copy at the cast's `at`. It also hides the
map's other NPCs, the ones not in the cast, until the scene ends, so an NPC
that should be in the picture is cast. Nobody else sees anything.

A personal scene with `"instanced": true` also takes the player out of the
world while it plays: other players don't see them, nothing can attack them,
and a map cue moves them unseen. Use it when the scene takes the player
somewhere (an intro, a memory, a dream). Without it, others see them standing
where they are, held. The watcher always sees only the cast: other players are
hidden on their screen too. See RUNTIME.md, "Instanced scenes".

A **world** scene plays on the map for everyone in range. The server directs
the real NPCs, and extras are temporary NPCs everyone sees. A world scene
can't lock, use the camera or the screen, ask a choice, or speak in dialogue
boxes: its lines are timed balloons.

## The cast

| Role | Is | Fields |
| --- | --- | --- |
| `npc` | An NPC already on the map | `spawn` (the map file's spawn entry, from 0) or `npc` (an ENF id), and `at`, where the scene expects it |
| `extra` | An NPC made for the scene | `npc` (the ENF id to show), `at`, `facing`, and `hidden` if it waits for an `appear` cue |
| `player` | The player watching | `at` and `facing`, where the trigger expects them, and `wears` |

An actor with `map` starts on that map rather than the scene's; see
[Changing maps](#changing-maps).

Any actor can have a `label`: the name the dialogue box shows over its
lines, instead of the NPC's own name (or "You" for the player). Two NPCs the
game calls "Blob" can speak as "Mr Blob A" and "Mr Blob B".

**The player in the scene.** The player can walk, turn, emote, swing
(`pose: attack`) and speak like anyone else, on their own screen only: the
server hasn't moved them, so when the scene ends the runner puts them back
where the server has them (a turn alone stays). A `map` cue moves them for
real. `wears` dresses them for the scene, by EIF item id: a weapon, shield,
armour, hat and boots. Armour is made for one gender, so list one of each
and each player wears theirs: `[27, 144, 151]` is the Small Sword with the
Peasant Suit for men and Peasant Clothes for women. Their own gear comes
back when the scene ends.

## Running compiled cues

Each cue is waiting, running, done or skipped. A cue's `id` is its place in
`cues`. `after` lists the cues it waits for, and they always come earlier in
the list, so one pass in order is enough.

1. At the start, and whenever a cue finishes, start every waiting cue:
   - that isn't in an unpicked branch, and
   - whose `after` cues are all done.
2. A cue with no `after` starts as soon as its branch does: at the start of
   the scene, or when its option is picked.
3. The scene ends when every cue is done or skipped.

When each cue is done:

| Cue | Done when |
| --- | --- |
| `walk` | The last step lands: one step per `stepMs` along `path` |
| `say` | `wait: click`: the player closes it. `wait: time`: after `ms`. |
| `choice` | An option is picked and every cue in its branch is done |
| `camera` | After `ms` |
| `screen` | `fade` and `title`: after `ms`. `letterbox`: at once. |
| `pose` | `loop: false`: when the animation ends. Otherwise at once. |
| `wait` | After `ms` |
| `map` | The player has arrived: after the fade, or at once for `how: cut` |
| `lock`, `unlock`, `face`, `emote`, `sound`, `music`, `effect`, `quake`, `appear`, `leave` | At once |

A `quake` shakes the view for 1 s, by up to `strength` × 2 pixels, dying
away, so it stays in the shot it's in. (A map's own quake effect shakes for
3 × strength + 10 ticks at full strength: over 2 s at strength 3, long
enough to carry into the next shot.)

When the scene ends, the runner:

- unlocks the player;
- takes the camera home and the letterbox away;
- removes extras still on the map, with a fade;
- hands real NPCs back to their usual behaviour;
- fades out the scene's music still playing, over 1.5 s, and brings the
  map's own music back.

### Branches

A cue with `branch: [c, k]` belongs to option `k` of choice cue `c`.

- **Starting:** it can't start until that option is picked, and it may only
  wait for cues in the same branch.
- **Unpicked branches:** when choice `c` resolves to option `k`, every cue in
  another option of `c` is skipped. So is every cue in a branch of a skipped
  choice.
- **After the choice:** cues that come after `c` wait for the whole picked
  branch, because `c` is done only when its branch is.

The pick is also the scene's outcome for EQF: `SceneChoice(scene, k)`.

### Walking

- **Legal tiles:** a `walk` steps from `from` along `path`, one tile per
  `stepMs`. Paths are baked on tiles every server lets NPCs walk: never a warp
  or a wall, chair, chest, bank vault, edge, board, jukebox or NPC boundary.
- **Animation:** while moving, the NPC loops `pose` (default `walk`, the
  sprite's four-frame walk cycle, one cycle per step).
- **Arriving:** the NPC faces `face` if given, then loops `idle` (default
  `idle`).
- **Speed:** `stepMs` is at least 400. EO clients animate faster steps badly.
- **Someone in the way:** that's for the runner to decide. It may wait, go
  round and rejoin the path, or give up on the cue. It never skips tiles.
- **Wrong starting tile:** if an NPC isn't at `from` when its walk starts, the
  runner walks it there first if it can find a way. Otherwise it starts from
  where the NPC is.

### Leaving by a door

`leave` with a `door` names the warp next to the actor. A server that sends
NPCs through warps, as reoserv does with its residents, sends it through.
Others take it off the map.

### Changing maps

A personal scene can move to another map part way through: a cutscene that
follows the player through a door, or cuts to somewhere else.

- **`map`** takes the player to `map`, at `at`, facing `facing` (default
  down). With `how: fade` (the default), the screen fades out, the player is
  warped, and it fades back in. `how: cut` warps at once. The camera goes
  home to the player, and the scene carries on there.
- **Actors on other maps:** an actor with `map` starts on that map. The
  runner sets it up (a stand-in, or the real NPC claimed) when the scene
  first arrives on that map, not before.
- **Travelling with the player:** an actor goes to another map with `leave`
  on the old one, then `appear` with `map` and `at` on the new one.
- **Ending elsewhere:** when a scene ends on another map, the player stays
  there. The trigger that played the scene decides what happens next.

### Time of day

A scene with `timeOfDay` plays at that time, whatever the server's clock
says: `"22:00"` puts it at night, with the lamps lit and the windows
glowing. A client that lights maps by the server's clock (the
[environment extension](../environment/README.md)'s `ClockReply`) lights
the scene by this time instead while it plays, and goes back to the clock
when it ends. Without it, a scene plays at whatever time it is.

Only a personal scene changes the sky. A world scene plays for everyone in
range, so runners leave their sky alone and ignore its `timeOfDay`.

### Sound

A scene's own music and sounds live beside its files, in `audio/`:

- `audio/music/<name>.ogg` (or `.wav`): songs. A `<name>.json` beside one
  can say where it loops, `{"loop": [start, end]}` in seconds: the first
  time through plays from the start, then it goes round between the two.
  Without it, the whole song loops.
- `audio/sounds/<name>.wav` (or `.ogg`): sounds. Files named `<name>-1`,
  `<name>-2` and on make a set, `<name>`: each time it plays, one is picked.
  Footsteps on a surface are the set `<surface>-step`.

A number in `song` or `sfx` is the game's own: its MIDI `mfxNNN.mid` or its
`sfxNNN.wav`. A name is the scene's.

**Music** plays one song at a time:

- `song` starts it, rising from silence to `volume` (default 1) over `ms`.
  Whatever was playing fades out over the same `ms` as it comes in.
- `stop` fades the song out over `ms`.
- A cue with only `volume` takes the song to that volume over `ms`.
- A song loops unless `loop` is false; then it plays once.
- While a personal scene's song plays, the map's own music is silent for
  that player; it comes back when the scene ends. A world scene's music is
  heard by everyone in range.
- With the scene's `duck`, the music dips to that much of its volume while
  a line is shown or a choice is up, over a quarter of a second each way.

**Sounds:** a `sound` cue plays its `sfx` once at `volume` (default 1).
With an `actor` or `at`, it comes from there: at full volume within 3 tiles
of the camera (the player, in a world scene), fading to nothing at 16, and
panned toward the side of the screen it's on.

**Footsteps:** a walk with `steps` plays a footstep for each tile, 30% of the
way into the step, from the walker, as a sound would be. Each is a take from
the set picked at random but not the one just played, at 55% volume (times
the walk's `stepVolume`) with a little variation, and up to 5% higher or
lower in pitch. The compiler settles `steps` and `stepVolume` from the walk,
its actor and the scene's `footsteps`, so a runner only reads the walk's.

A song's `<name>.json` can also give `"crossfade"`: the seconds over which
the end of the loop blends into what leads up to its start (equal power),
so going round doesn't jump. Pick loop points on downbeats, a whole number
of phrases apart, where the music sounds alike.

The player's own volume settings scale all of it: music by their music
volume, sounds and footsteps by their effects volume.

## Game state stays in quests

A scene doesn't give items, set flags or change quests: it shows things.
What a player has seen and picked is the server's to keep (see RUNTIME.md,
"Progress"), and what follows from it is the quests'. An EQF quest starts a
scene with the action `PlayScene(name)`. Two rules would let quests follow
a scene, and aren't built yet:

- `SceneDone(name)`: holds once the scene has ended;
- `SceneChoice(name, option)`: holds if that option was picked.

Until they are, a scene leads to a quest by where it leaves the player: the
intro ends beside Haldor, whose quest takes it from there.

## Classic clients

The 0.0.28 client sees only what 0.0.28 packets carry. A runner shows it the
rest as follows:

| Cue | On the classic client |
| --- | --- |
| `walk`, `say` as a balloon, `sound`, `music`, `effect`, `quake` | As normal |
| `lock`, `unlock` | As normal, through `Walk_Close` and `Walk_Open` |
| `say` in a box | A balloon. A click-wait waits `ms` instead. |
| `choice` | Not shown. The first option is picked. |
| `face` | Seen on the NPC's next step |
| `pose`, `emote` on NPCs, `camera`, `screen`, `timeOfDay` | Not shown |
| `appear`, `leave` | The NPC appears or is removed, without a fade |
| `map` | An ordinary warp |

Stand-ins need a client that can draw its own NPCs, so a classic player in a
personal scene sees only the cues above.

## Rules beyond the schema

`check_scene.py` checks these as well as the schema:

- **Cues:**
  - a cue's `id` is its index;
  - `after` names only earlier cues, in the same branch;
  - `branch` names an earlier `choice` cue, and one of its options.
- **Cast:**
  - every `actor` and `follow` is in the cast;
  - only a personal scene has a `player`, and only one.
- **World scenes:** no `lock`, `unlock`, `camera`, `screen`, `choice` or
  `map`, and their lines are timed balloons.
- **Walks:**
  - each step is next to the one before;
  - a walk starts where the actor last stood.
- **The whole file:**
  - `compiled.uses` lists exactly the cue types used;
  - the file is named `<id>.eoscene.json`.
- **Source:**
  - clip ids are unique;
  - anchors name real clips;
  - markers exist;
  - branches belong to a choice.

Checking that paths are NPC-legal needs the map, so editors do that when they
compile.

## Source, for editors

`source` holds the scene as it was authored:

- **`markers`:** named tiles, such as `inn-door`.
- **`tracks`:** the editor's rows, top to bottom.
- **`clips`:** the blocks on those rows.
- **`editor`:** the editor's own state.

A clip has the same fields as the cue it becomes, with three differences:

- **A walk uses `to` and `via`, not a path.** `to` is `{ "marker": … }`,
  `{ "tile": … }` or `{ "near": actor }`: the free tile beside that cast
  member, wherever they stand by then, on the walker's side of them. `via`
  lists tiles the path must pass through. The editor bakes the path when it
  compiles.
- **Facing someone.** A `walk` or `face` clip with `toward: actor` turns to
  face that cast member, wherever they stand by then. The editor works out
  the direction.
- **A clip is anchored, not listed.** `start` is one of:
  - `{ "at": ms }`: from the start of the scene, or of the clip's branch;
  - `{ "after": clip }`: once that clip is done;
  - `{ "with": clip }`: when that clip starts.

  Each can add an `offset` in ms. The compiler turns offsets into `wait` cues.
- **A branch clip names its option.** It carries `branch` with an option's
  name from a choice clip's `options`, instead of a cue index.

## Stories

A scene often belongs to a bigger one: the blobs plot when a player first
reaches Frosthollow, and when the player later talks to Ingrid, the blobs try
to win them over. A **story** puts scenes in the order a player meets them,
and says what plays each: `<id>.eostory.json`, beside the scenes.

```json
{
  "format": 1,
  "id": "the-blob-uprising",
  "title": "The blob uprising",
  "characters": { "ingrid": { "npc": 311, "about": "Adores the blobs." } },
  "beats": [
    { "scene": "blobs-plot", "when": { "enterMap": { "map": 19 } } },
    { "scene": "blobs-recruit", "when": { "talkedToNpc": { "npc": 311 } }, "after": ["blobs-plot"] }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `characters` | The story's recurring people: an ENF id and a note on who they are, so each scene casts and voices them the same way |
| `beats` | Scenes, in order. Each has a `scene`, the checkpoint `when` that plays it, and optionally `after`, `once` (default true) and a `note` |
| `after` | Scenes that must have played first: ids, or `{ "scene": id, "choice": branch }` for a scene where the player picked that option |

A beat's `when` is one checkpoint, named as reoserv's quest rules are:

| `when` | Plays when the player |
| --- | --- |
| `{ "start": {} }` | can: as soon as the beats it's `after` have played |
| `{ "newCharacter": {} }` | comes into the world for the first time: a new character's first login, before anything else |
| `{ "enterMap": { "map": N } }` | arrives on a map |
| `{ "enterCoord": { "map": N, "at": [x, y] } }` | steps on a tile |
| `{ "leaveMap": { "map": N } }` | leaves a map |
| `{ "talkedToNpc": { "npc": id } }` | talks to an NPC |
| `{ "killedNpcs": { "npc": id, "amount": n } }` | has killed that many |
| `{ "gotItems": { "item": id, "amount": n } }` | holds that many of an item |
| `{ "afterScene": { "scene": id, "choice": branch } }` | has just watched a scene (and picked that option) |

A beat plays when its checkpoint is met, everything it's `after` has
played, and the player stands on the scene's map (a `leaveMap` beat's scene
plays on the map ahead). Each plays once per character unless it says
`"once": false`. A server keeps an index from each checkpoint to the beats
waiting for it, so a checkpoint costs one lookup (RUNTIME.md,
"Checkpoints"). Beats that wait on each other never play, and
`check_scene.py` says so.
