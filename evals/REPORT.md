# Tactical evaluation results

This report is generated from [results.json](results.json). The [experiment notes](README.md) explain what prompted the tests, the separate gameplay win rate, the harness audit, and the limits of these findings.

Requests recorded: **48/48**. Run started: 2026-10-22T00:43:02.427238+00:00.

Environment: macOS 27.0.1, apple-fm-sdk 0.2.1, Python 3.12.11; greedy sampling. The underlying Apple model build was not pinned.

## Overall results

Tactical success means taking an available immediate win, or preventing an immediate opponent win when no winning move is available. These are move-level scores, not full-game win rates.

| Prompt | Tactical successes | Legal responses | Errors | Random expectation |
| --- | --- | --- | --- | --- |
| Rules only | 4/12 (33.3%) | 12/12 | 0 | 20.2% |
| Examples and winning groups | 3/12 (25.0%) | 12/12 | 0 | 20.2% |
| App prompt with strategy guidance | 4/12 (33.3%) | 12/12 | 0 | 20.2% |
| Rules only, broader response schema | 4/12 (33.3%) | 10/12 | 0 | 9.5% |

Random expectation is calculated for uniform selection from legal squares, except for the broader-schema variant, where it uses every board square. These baselines have different action spaces. A legal-only schema enforces legality, so a perfect legal-response score under that constraint does not establish the model's understanding of legality.

## By task

| Prompt | Immediate wins | Prevent immediate loss |
| --- | --- | --- |
| Rules only | 2/7 | 2/5 |
| Examples and winning groups | 1/7 | 2/5 |
| App prompt with strategy guidance | 1/7 | 3/5 |
| Rules only, broader response schema | 1/7 | 3/5 |

## By mode

| Prompt | Classic 3x3 | Big 4x4 | Vanishing 3x3 |
| --- | --- | --- | --- |
| Rules only | 2/4 | 0/4 | 2/4 |
| Examples and winning groups | 1/4 | 0/4 | 2/4 |
| App prompt with strategy guidance | 1/4 | 0/4 | 3/4 |
| Rules only, broader response schema | 1/4 | 0/4 | 3/4 |

## Per-position results

| Case | Task | Acceptable squares | rules_only | examples_and_groups | current | rules_broad_schema |
| --- | --- | --- | --- | --- | --- | --- |
| vanishing_remove_then_block_x | prevent_immediate_loss | [9] | 9 (pass) | 9 (pass) | 9 (pass) | 9 (pass) |
| 4x4_win_o | immediate_win | [8] | 9 (fail) | 9 (fail) | 9 (fail) | 9 (fail) |
| classic_win_o | immediate_win | [6] | 6 (pass) | 6 (pass) | 8 (fail) | 6 (pass) |
| vanishing_block_o | prevent_immediate_loss | [1] | 6 (fail) | 3 (fail) | 1 (pass) | 1 (pass) |
| classic_win_x_rotated | immediate_win | [9] | 9 (pass) | 4 (fail) | 9 (pass) | 5 (fail) |
| vanishing_win_x | immediate_win | [3] | 6 (fail) | 6 (fail) | 7 (fail) | 7 (fail) |
| vanishing_remove_then_block_x_rotated | prevent_immediate_loss | [7] | 7 (pass) | 7 (pass) | 7 (pass) | 7 (pass) |
| 4x4_win_x | immediate_win | [4] | 9 (fail) | 7 (fail) | 9 (fail) | 9 (fail) |
| 4x4_block_o | prevent_immediate_loss | [4] | 7 (fail) | 9 (fail) | 9 (fail) | 7 (fail) |
| classic_win_x | immediate_win | [3] | 6 (fail) | 6 (fail) | 9 (fail) | 9 (fail) |
| classic_block_o | prevent_immediate_loss | [3] | 4 (fail) | 4 (fail) | 9 (fail) | 5 (fail) |
| 4x4_win_x_rotated | immediate_win | [16] | 10 (fail) | 10 (fail) | 10 (fail) | 10 (fail) |

## Method

The suite contains 12 fixed positions: four per mode, including three rotated counterparts of other cases. Each variant gets one greedy request per position in a fresh session. The response format includes both the move and commentary. All requests use a 45-second timeout, with no retries or replacement moves. Variant order rotates across positions.

| Raw variant ID | Assistance supplied |
| --- | --- |
| `rules_only` | Rules, numbered grid, vanishing move history, legal-square list and legal-only enum. |
| `examples_and_groups` | Rules-only input plus generic worked examples and all winning groups. |
| `current` | The app prompt captured for this run: examples, groups and win/block priorities. |
| `rules_broad_schema` | Rules-only input with all board squares allowed by the schema; the legal-square list remains visible. |

A separate evaluator computes acceptable squares solely for scoring. It simulates mark removal before checking vanishing-mode wins. Correct-move labels and board-specific tactical scores are never sent to the model. Errors, timeouts and malformed responses count as unsuccessful requests and are also reported separately.

## Interpretation limits

These are diagnostic positions, including cases used in earlier prompt development, not a held-out benchmark. Rotated cases are related, and there is only one request per position and variant. The results measure immediate tactics, not long-term optimal play, game win rates, or general model capability.

Examples and winning groups were tested together, so their individual effects cannot be separated. All variants use the numbered grid and a legal-square list; this run does not compare the original JSON format or measure completely unassisted action selection. Small differences between totals should not be treated as established effects.

The raw results preserve inputs, schemas, responses, errors, latency, environment metadata and the model.py source hash. See the experiment notes for the independent scorer cross-check and suggested next tests.
