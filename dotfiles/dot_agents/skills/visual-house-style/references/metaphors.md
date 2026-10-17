# Metaphor catalogue

For the metaphor-led approach in [SKILL.md](../SKILL.md).

## Building a mapping

1. List the system parts the audience must tell apart, and the one mechanism the picture must carry.
2. Give each part one picture element and each property one visual variable (size, colour, shape,
   position). Write the legend before drawing.
3. Check every element on every panel against the legend. A decorative element that resembles a
   legend entry reads as that entry.
4. Prefer a picture the field already draws, because it needs no explanation.
5. Put the plain system strip beneath each picture so an architect can check the mapping.

## Traffic: shared capacity, contention, throttling and queues

First used for a database write-pressure story told to non-technical readers and architects
together (2026-10). Microsoft's own explanation of SQL Server insert flow control uses the same
picture: a single-lane bottleneck that backs traffic up, and "the traffic lights on a highway
on-ramp" ([Behind the Scenes on OPTIMIZE_FOR_SEQUENTIAL_KEY](https://techcommunity.microsoft.com/blog/sqlserver/behind-the-scenes-on-optimize_for_sequential_key/806888)).

| System part                      | Picture                                       | Holds only if                                                              |
| -------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------- |
| Shared server                    | A bridge                                      | Strain shows in the bridge, never as cars crossing lanes                   |
| Separate databases on it         | Separate roads on the bridge                  | Each workload stays on its own road                                        |
| Insert hot spot                  | A single-file merge bay                       | Everyone needs the same slot                                               |
| Page splits                      | Roadworks narrowing the bay                   | Shown as occasional, not constant                                          |
| Many writers at once             | A crowded funnel of cars                      | Set against a few spaced cars moving faster                                |
| Batching                         | A bus                                         | It is the only large vehicle anywhere                                      |
| Fixed throttle or quota          | A speed-limit gate                            | The limit is the same whatever the traffic                                 |
| Adaptive throttle                | An on-ramp light with a sensor on the road    | The light reacts to the road, not to a timer                               |
| Queue or backlog                 | A waiting area before the ramp                | The queue keeps everything; check retention and compaction first           |
