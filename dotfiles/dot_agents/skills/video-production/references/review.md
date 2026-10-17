# Review

## The packet

```sh
python3 scripts/review_packet.py film.mp4 script.json --out tmp/review/ --brief brief.md --facts facts.md
```

It writes `packet.md` and the frames: two from each scene of 12 s or more (at 45% and 88% of the scene), one from shorter scenes (at 75%), scaled to 1600 px wide. `packet.md` carries the brief, the facts about the cut, the scene table, every caption with its times, and the frame list.

The facts file states what the frames can't show:

- the length, the slot it fills, and where it plays;
- whose voice it is, and whether music plays under it;
- which cards are real screenshots and which scenes are drawn;
- the colour code;
- which numbers are expectations rather than measurements.

## The reviewer

Hand the packet, without your reasoning, to a subagent from a different model family from the one that made the film: your own model shares your blind spots. Read-only: no edits, no shell, no web.

```text
Read <absolute path>/packet.md and view every frame it lists. You are reviewing a finished cut.
Judge it as the audience will see it: once, on a large screen, with no chance to pause.
Return: a one-line verdict; must-fix findings; should-fix findings; and a cut-first list with
timecodes, if it runs long. For each finding, quote the frame or caption it rests on, and say
what would fix it. Flag any claim the film makes that its own frames contradict, any drawn
screen a viewer could take for a captured one, and anything a non-specialist couldn't follow.
List any frame you could not view.
```

Check that it saw every frame. A tool can drop images over its image budget, and an omitted frame is an unseen frame.

## Grading

- Grade claim by claim against the source: valid, partly valid or disputed, each with its evidence (a setting read live, a file, a line of the script).
- Split what you can fix yourself from what is the owner's call: anything that reverses an earlier ruling, cuts runtime, or changes the message.
- Present the owner a numbered list, so the answer can be the numbers.
- The reviewer can't hear. Pace, balance, false starts and pronunciation need a human listen, on speakers and on headphones.

## Iterating

Owner feedback arrives as `scene: change`. Apply a round in one pass, re-render, re-run the checks, and report a short changelog with the new version number. Record every ruling in the versioned list, with what it supersedes.
