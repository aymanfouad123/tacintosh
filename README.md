# tacintosh

tic-tac-toe in the terminal, powered by apple foundation models.

turns out your mac comes with a [local 3b-parameter language model](https://developer.apple.com/documentation/foundationmodels) that you can try by running `fm`! i wanted to see how it would hold up at tic-tac-toe, so i built a way to play against it.

![Tacintosh terminal gameplay demo](tacintosh.gif)

## to try it

you’ll need an apple intelligence–compatible mac, macos 26+, python 3.12+, xcode set up for `apple-fm-sdk`, and `uv`.

to check out `fm` on your mac:

```bash
fm --help
```

then run tacintosh:

```bash
uv sync
uv run tacintosh
```

the model gets a numbered text grid, explicit rules for the selected mode, all winning groups, and a list of legal squares. the prompt asks it to prioritize winning, then preventing an immediate loss. it picks its own move and returns structured json.

the code only enforces legality, wins, and vanishing-mode removal — no board-specific win/block hints or solver.

the sdk connects directly to the on-device model. no api key or separate model server needed.

## modes

| mode          | what it is                                                            |
| ------------- | --------------------------------------------------------------------- |
| classic 3×3   | standard tic-tac-toe                                                  |
| big 4×4       | four in a row wins                                                    |
| vanishing 3×3 | each player keeps only their three newest marks (no full-board draws) |

in vanishing mode, place on an empty square first, then remove your oldest mark if you now have four. wins are checked after removal. repeated positions do not end the round, so a game can run indefinitely.

## keys

**menu:** ↑↓ mode · ←→ first · enter play · q quit

**game:** arrows select · enter / 1–9 place · a–g for squares 10–16 on 4×4 · n new round · m menu · r retry · q quit

## layout

```
tacintosh/
  main.py         entry point
  game.py         modes, board rules, and move validation
  model.py        prompts and apple fm requests
  stats.py        saved game results
  app.py          textual menu, board, and turn flow
  style.tcss      terminal layout and colors
```

## what i noticed

the model kept losing during casual play, which made me wonder whether it was struggling with tic-tac-toe or just with how i was presenting the board. the first prompt used compact json and a short goal. i switched to a numbered grid, spelled out the rules, and added examples, winning groups, and win/block priorities. then i wanted to check whether that extra help was actually helping.

the local completed-game log recorded **0 model wins, 8 losses, and 1 draw across 9 games** — an observed **0% win rate**. those were informal human games while the prompt was changing, so they don't establish which prompt played better.

i also ran **48 tactical checks**: the same 12 positions under four prompt variants, across all three modes.

| input | correct tactical moves | legal moves |
| --- | ---: | ---: |
| rules and board, with legal-only responses | 4/12 (33.3%) | 12/12 |
| add rule examples and all winning groups | 3/12 (25.0%) | 12/12 |
| add win/block strategy guidance — the app prompt | 4/12 (33.3%) | 12/12 |
| rules and board, allowing occupied-square responses | 4/12 (33.3%) | 10/12 |

a correct tactical move meant taking an immediate win, or preventing an immediate loss when no win was available. these percentages are **tactical success rates**, separate from the game win rate above. all variants received a legal-square list; the last variant relaxed only the response schema.

some interesting observations:

- **more guidance didn't improve the total in this run.** rules-only and the app prompt both scored 4/12, but succeeded on different positions. the app prompt found fewer immediate wins and handled more defensive positions.
- **every variant scored 0/4 on the tested 4×4 positions**, even with every winning group listed.
- **equivalent boards produced different outcomes.** rules-only and the app prompt missed a classic top-row win but found its rotated counterpart.
- **the harness helped enforce legality.** allowing occupied squares in the response schema exposed two occupied-square choices. guaranteed legal moves aren't the same as demonstrated rule understanding.

it's a small diagnostic run with related positions and one request per variant per position. it doesn't establish a general capability score or prove that extra guidance never helps. i also haven't directly compared the original json format against the grid. the app still leaves every move to the model, with prompt guidance and legal-action constraints.

the [full experiment notes](evals/README.md) cover what prompted the tests, the harness choices, limits, and next questions. the [score report](evals/REPORT.md), [raw requests and responses](evals/results.json), and [gameplay snapshot](evals/gameplay_snapshot.json) keep the findings inspectable.
