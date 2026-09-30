# Actors Extension

Packets for NPCs the server directs, rather than leaving to wander: the
residents who live their days in a world's towns, and later the NPCs in a
cutscene. Made for Forest Rift's reoserv server and eoweb web client. reoserv
sends these packets only to web clients, which connect over WebSocket. The
classic client connects over TCP and never sees them.

## Changes

### New packet families

| Addition | Value |
|---|---|
| `PacketFamily::Actor` | 245 |

### New server packets

| Packet | Description |
|---|---|
| `ActorRemove` | An NPC leaves the map by a warp. The client takes it off the map as it goes, not as a death |
| `ActorReply` | An NPC strikes another NPC: who strikes whom, which way it faces, the damage, what's left of the target's HP, and whether it died |
| `ActorUse` | An NPC uses an item on itself, as a hurt resident drinks a potion: the item, the HP it gained, and its HP after |

## Travelling between maps

A resident may walk from one map to another, as a player does: it walks onto
a warp, and comes out where the warp leads. Nothing in the 0.0.28 protocol
takes an NPC off a map except its death, so the server sends `ActorRemove`
to the players in range of the warp.

Arriving needs nothing new. The server sends `Npc_Agree` for the NPC to the
players in range of where it comes out, as for any NPC a client doesn't know
yet.

## Fighting

A resident who takes on a request for what a monster drops goes to where the
monster lives and hunts it. The 0.0.28 protocol has an NPC strike only a
player, and an NPC take damage only from a player, so the server sends
`ActorReply` for each strike to the players in range of the target. The
client plays the attacker's attack and the target's health bar, and a death
if the strike killed it.

A monster a resident strikes fights back, with `ActorReply` the other way
round, so the resident's health bar shows what it takes. A hurt resident
drinks one of the potions it took out hunting, and the server sends
`ActorUse`, which shows the heal. With its potions gone, it gives up the
request and heads home. A resident struck down is carried home, where it
appears again, and the request goes back on the board.

A kill by an NPC drops nothing and gives no player experience. The monster
comes back as it would after any death.

## Compatibility

The classic client never sees `ActorRemove`. reoserv sends it `Npc_Junk` for
the NPC's id instead, which takes every NPC of that id off its map, as a boss's
children are when the boss dies. A resident's NPC is the only one of its id,
so only it goes.

The classic client never sees `ActorReply` or `ActorUse` either. reoserv
sends it no strikes or heals, but for a kill it sends `Npc_Spec` with no
killer and no drop, so the NPC dies on its map too.
