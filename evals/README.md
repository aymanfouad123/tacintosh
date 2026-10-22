# What I learned from tic-tac-toe

Tacintosh started with a simple question: how well could Apple's on-device
language model play tic-tac-toe if it chose every move itself? During casual
play, it kept losing. That raised a more useful question: was the model
struggling with the game, or was I making the board and rules hard to understand?

I tried clearer inputs, then checked whether the extra help actually improved
its decisions. The result was mixed: more detailed instructions did not increase
the overall tactical score in this run, and legal-move constraints hid mistakes
that appeared when I relaxed them.

## What prompted the experiment

The initial request used compact JSON: the model's mark, board rows, empty
squares, and a short goal such as "3 in a row." It also asked for a playful
remark alongside the move. I replaced that board representation with a numbered
text grid, made turns and winning conditions explicit, and explained each mode's
rules. Vanishing mode also included each player's marks in placement order,
because removing the oldest mark can change whether a move wins.

When early spot checks still missed immediate wins, I added worked rule
examples, a list of every winning group, and a strategy priority: win now,
otherwise prevent an immediate loss, otherwise build a line.

That introduced a second question: was I observing the model's game reasoning,
or the benefit of a more helpful harness? I kept the resulting app prompt and
compared versions with parts of that assistance removed.

The formal run compares those assistance levels using the same numbered grid.
It does **not** compare the original compact JSON with the grid, so it cannot
establish which board representation works best.

## Two different measures of performance

### Informal gameplay: 0 wins in 9 completed games

The [saved gameplay snapshot](gameplay_snapshot.json) aggregates the app's local
completed-game log at the time of this write-up:

| Mode | Completed games | Model wins | Model losses | Draws |
| --- | ---: | ---: | ---: | ---: |
| Classic 3×3 | 5 | 0 | 4 | 1 |
| Big 4×4 | 1 | 0 | 1 | 0 |
| Vanishing 3×3 | 3 | 0 | 3 | 0 |
| **Total** | **9** | **0** | **8** | **1** |

The observed model win rate was **0/9 (0%)**. This describes those games,
not an estimated win rate against other players. The log does not record prompt
versions, who moved first, player skill, or model builds. The prompt changed
during development, and unfinished games are not recorded. I cannot use this
history to attribute wins or losses to a particular prompt or harness.

### Controlled tactical checks: 48 requests

I tested 12 fixed positions under four input variants. Four positions came
from each mode; three positions were rotated counterparts of other cases.
Seven positions offered an immediate win, and five required preventing an
immediate opponent win. Every position had one acceptable square under that
scoring rule.

Each request used a fresh session, greedy sampling, the same move-plus-remark
response format, and a 45-second timeout. Request order rotated across variants.
There were no retries, replacement moves, errors, or timeouts.

| Variant | What the model received | Tactical success | Legal responses |
| --- | --- | ---: | ---: |
| Rules only (`rules_only`) | Rules, numbered board, move history where needed, legal-square list, and legal-only response schema | 4/12 (33.3%) | 12/12 |
| Examples and groups (`examples_and_groups`) | Rules-only input plus worked rule examples and all winning groups | 3/12 (25.0%) | 12/12 |
| App prompt (`current`) | Examples-and-groups input plus explicit win/block priorities | 4/12 (33.3%) | 12/12 |
| Broader schema (`rules_broad_schema`) | Rules-only input, but the response schema allowed every board square, including occupied ones | 4/12 (33.3%) | 10/12 |

Here, **tactical success** means taking an immediate win when available;
otherwise, choosing a move that leaves the opponent no immediate winning reply.
It does not measure longer-term optimal play or full-game win rate. A separate
evaluator simulates each move, including vanishing-mode removal, to score it.
Those answers are never sent to the model.

See the [generated report](REPORT.md) for every position and the
[raw results](results.json) for exact prompts, schemas, responses, latency, and
environment metadata. `current` names the app prompt captured for this run.

## What stood out

**More guidance did not improve the total.** Rules-only and the app prompt both
scored 4/12. Adding examples and winning groups scored 3/12. This is no evidence
of an overall gain in this run; it does not establish that guidance never helps.
Examples and winning groups were bundled, so their individual effects remain unknown.

**The failures shifted rather than simply disappearing.** Rules-only found 2/7
immediate wins and handled 2/5 defensive positions. The app prompt found 1/7 wins
and handled 3/5 defensive positions. Equal totals concealed different choices.
With so few cases, the results cannot establish that strategy guidance caused that tradeoff.

**Every variant missed all four 4×4 positions.** These included immediate wins
for both X and O, a required block, and a rotated winning position. Listing all
winning groups was still insufficient on these cases. This is a finding about
the tested positions, not proof that the model can never play 4×4 successfully.

**Equivalent boards could produce different outcomes.** Rules-only missed the
classic top-row win at square 3 but found its rotated counterpart at square 9.
The app prompt did the same:

```text
Original                 Rotated 90 degrees
X | X | .                . | O | X
O | O | .                . | O | X
. | . | .                . | . | .

X can win at square 3    X can win at square 9
App chose square 9       App chose square 9
```

Squares are numbered left to right, then top to bottom. This makes board orientation and square numbering
useful things to vary in future tests; this run does not isolate the cause.

**Legal moves were partly a property of the harness.** All legal-only variants
returned legal moves on all 12 positions. With occupied squares allowed in the
schema, the model selected occupied square 5 twice, despite still receiving the
legal-square list. The constraint helped enforce legality, but its perfect legal
rate was not evidence that the model understood that rule unaided.

Uniform random selection from legal squares would have an expected tactical
success rate of **20.2%** on these fixtures. For the broader-schema variant,
uniform selection from every board square would give **9.5%**. These are
calculated expectations with different action spaces, not sampled opponents.
This small, correlated suite cannot establish a reliable advantage over random play.

## How much did the harness help?

There are several kinds of help in this setup, and they affect what the results can demonstrate:

| Component | What it supplies |
| --- | --- |
| Rules, board, current player, vanishing move history | The task definition and observable game state. |
| Worked examples | Demonstrations of how to apply the rules. |
| All winning groups | A static expansion of rows, columns, and diagonals into square numbers. |
| Win/block priorities | Explicit strategy coaching. |
| Legal-square list | Precomputed available actions. |
| Legal-only response schema | A decoding constraint that prevents occupied-square responses. |
| Runtime validation | Enforcement of game legality after generation. |

The app leaves move selection to the model: it supplies no board-specific winning
or blocking recommendation and runs no game solver. Still, the current setup is
**prompt-guided model play with constrained legal actions**. Calling it unaided
strategic ability would overlook the assistance above.

In this run, the richer prompt showed no overall tactical improvement. The
legal-only schema did enforce a behavior the model violated when it had the
freedom to choose occupied squares. That distinction is the most useful harness
observation: reliable game behavior and demonstrated model understanding are
separate things to measure.

## What I'd test next

Use fresh positions, more board symmetries, and repeated runs. Separate worked
examples, winning-group lists, and strategy instructions into their own variants.
Compare compact JSON and a grid directly, and test whether generating commentary
alongside the move changes decisions. For full-game win rates, fix the opponent,
balance who moves first, and record the prompt and model version for each game.

Keep legality and tactical quality as separate scores. A rules-and-state baseline
without a precomputed legal-square list would further test the model's ability
to derive available moves. Runtime validation should remain in the game, with
rejected moves counted as evaluation failures rather than silently repaired.

## Reproduce and interpret the run

From the project root:

```sh
.venv/bin/python -B evals/run.py --dry-run
.venv/bin/python -B -u evals/run.py
```

The dry run validates and lists fixtures without model requests. The real run
needs access to Apple's local model service. Results are checkpointed after every
request; rerunning resumes without retries. Once all 48 records exist, the runner
regenerates the report without additional model requests. Preserve or relocate
`results.json` before starting a fresh run. Changed request inputs cannot be
silently appended to an existing run.

The completed run used macOS 27.0.1, `apple-fm-sdk` 0.2.1, and Python 3.12.11,
starting at 2026-10-22 00:43 UTC. The underlying Apple model build was not pinned.
The independent scorer was checked against the game engine on 2,622 candidate
moves across the three modes.

These are diagnostic results from one request per position and variant. Some
positions were used in earlier prompt development, and rotated cases are related,
so this is not a held-out benchmark or a general assessment of Apple's models.
The prompts, responses, and source hash are retained so the observations remain
traceable to the setup I actually tested.
