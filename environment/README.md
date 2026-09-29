# Environment Extension

Packets for a player's surroundings beyond the 0.0.28 protocol: the server's
time of day, for a day-night cycle; the weather; and the request board, where
NPCs post what they need and players take requests on. Made for Forest Rift's
reoserv server and eoweb web client. reoserv sends these packets only to web
clients, which connect over WebSocket. The classic client connects over TCP
and never sees them.

## Changes

### New packet families

| Addition | Value |
|---|---|
| `PacketFamily::Request` | 246 |
| `PacketFamily::Weather` | 247 |
| `PacketFamily::Clock` | 248 |

### New enums

| Enum | Description |
|---|---|
| `WeatherType` | The weather over the world: `Clear` or `Rain` |
| `RequestKind` | What a request asks for: a shortage, a trade run, a hunt, a cull, crafting, or what rain or night brings out |
| `RequestTier` | How hard a request is: `Easy`, `Medium` or `Hard` |
| `RequestHold` | Who holds a request, as the player sees it: nobody, the player, their party, or someone else |

### New structs

| Struct | Description |
|---|---|
| `RequestEntry` | A request on the board: who asked, what for, how many so far, what it pays, how long it has left, and who holds it |

### New server packets

| Packet | Description |
|---|---|
| `ClockReply` | Seconds since midnight on the server's clock, sent on entering the game |
| `WeatherAgree` | The weather, sent on entering the game and to every player whenever it changes |
| `RequestList` | The requests a request board lists for the player, with who holds each. Sent on opening the board, just before `BoardOpen`, which lists the same requests as posts for clients without the extension, and when the player takes or gives up a request there |

### New client packets

| Packet | Description |
|---|---|
| `RequestAccept` | Takes a request from the request board the player has open |
| `RequestRemove` | Gives up a request the player holds |

## The request board

Each map with the request board lists the requests from its region: the maps
nearer that board than any other. It lists a few requests from further away
too, marked `far`, and every request the player holds.

A player who takes a request holds it until they finish it or their time runs
out. Until then, only they and their party can hand it in. It pays the gold it
paid when they took it, instead of rising further. A player can hold only
`max_held` requests at once. After giving one up or running out of time, they
wait `wait_minutes` before taking another. Requests nobody takes for long may be
taken by the world's residents, NPCs who live in its towns.

The server decides how long a hold lasts and how long the wait is. In reoserv
they're settings; by default a hold lasts 1, 2 or 4 hours by tier, plus an hour
for a far request, and the wait is 15 minutes.

## Compatibility

`RequestEntry`'s `hold`, `hold_minutes_left` and `far` come at the end of its
first chunk, and `RequestList`'s `holders`, `max_held` and `wait_minutes` come
after its requests. A client that reads the layout from before players could
take requests skips them, and still shows the board.
