# Attention and interaction

Rules for interfaces people work in: apps, dashboards, status lines, review pages. Evidence and
sources: the wiki note `00-inbox/research-interaction-patterns/findings-attention-and-patterns.md`.

## Exception-based attention

The owner's rule (2026-10-25): attention goes only to what is important; "if nothing is shown
(example no checkmark), it should mean things are ok". Process control says the same: "a good HMI is mostly gray, and color
means something is wrong" ([ISA-101 guide](https://hmilibrary.com/standards/isa-101.html)).

- A normal state is quiet or absent: no green tick for success, no badge for "all fine".
- Colour, motion, sound, badges and notifications go only to what needs the person: a failure, a
  question, a stall, a cost, a step that cannot be undone.
- Before adding anything that draws the eye, say why it matters. If it would not be missed, leave
  it out.
- A cost is never shown in the colour of "fine".

Where it does not apply, and what to do instead:

- **The person's own action.** Show that it worked (a sent message appears, a saved setting holds).
- **Silence could mean the monitor died.** Keep a liveness signal: when each source last answered,
  on request or quietly; a stale source is itself an exception.
- **A newcomer must learn what normal looks like.** Keep status reachable on request, by shape,
  position or text; never by colour alone.
- **Automation the person supervises.** Its state and recent actions stay one click away, and every
  exception links to them, so the person does not fall out of the loop.

## Patterns

| Pattern | Rule | Source |
| --- | --- | --- |
| Progressive disclosure | Show what most visits need; defer the rest one click away; at most two levels; label the way to the second | [NN/g](https://www.nngroup.com/articles/progressive-disclosure/) |
| Answer first | Status text and summaries lead with the state and what needs the person; detail after | [NN/g](https://www.nngroup.com/articles/inverted-pyramid/) |
| Indicator or notification | A state of one item is an indicator beside it; interrupt only when the person must act now | [NN/g](https://www.nngroup.com/articles/indicators-validations-notifications/) |
| Progress by wait | Nothing under a second; a spinner for 2 to 10 seconds; beyond that, steps or progress and a Stop | [NN/g](https://www.nngroup.com/articles/progress-indicators/) |
| Undo over confirm | Reversible routine actions get undo; confirm only the irreversible or costly, and say what will happen | [Raskin](https://alistapart.com/article/neveruseawarning/), [NN/g](https://www.nngroup.com/articles/confirmation-dialog/) |
| Recognition over recall | Offer the commands, names and values instead of asking the person to remember them; shortcuts for experts alongside | [NN/g](https://www.nngroup.com/articles/recognition-and-recall/) |
| Resizable panes | A side panel whose content varies gets a window splitter: arrow keys move it, Enter collapses and restores, its size is kept | [WAI-ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/) |

## Check before calling a screen done

- [ ] Every coloured or moving element is an exception someone must act on or know about.
- [ ] With everything fine, the screen is calm: no success marks, no idle badges.
- [ ] Each exception says what happened and offers the next step.
- [ ] A quiet source can be told apart from a dead one.
