# Interface feedback

Rejected actions retain `outcome.action_error`, with structured details in
`outcome.action_feedback`. Communication uses `communication_error` and
`communication_feedback`. Existing invalid-action metrics remain compatible.

Feedback contains `status`, `code`, `category`, `phase`, `field`, `message`,
`hint`, and `details`. Known validation errors distinguish formatting, resource
shortages, permissions, visibility, stale state and capacity. Numeric shortages
use the acting member's own actual available balance, including fractional
amounts. Invalid quantities explain integer versus decimal requirements and the
public interface maximum.

Examples:

| Trigger | Code | Correction |
|---|---|---|
| Two entries for A | `DUPLICATE_MATERIAL` | Merge quantities into one entry; check the quantity limit and available balance. |
| Transfer 1 A while holding 0.991868839 A | `INSUFFICIENT_ASSETS` | Returns required, available and shortfall; do not round upward. |
| Accept your own material offer | `ITEM_OFFER_PERMISSION` | Only an eligible buyer can accept. |
| Send to a chat before joining | `CHAT_NOT_JOINED` | Accept a visible invitation and wait for the updated view. |
| Use a chat ID as a game ID | `GAME_UNAVAILABLE` | Use an existing visible game, not a chat identifier. |
| Start a game from ordinary text | `GAME_WORK_KIND` | Use an executable `game_xml` or `game_python` work. |
| Sell another author's work | `WORK_AUTHOR_ONLY` | Reading permission does not confer authorship. |
| Use an undiscovered function | `FUNCTION_NOT_DISCOVERED` | Use only your own privately unlocked interface. |

A legally executed experiment yielding nothing receives `feedback.status =
executed_no_output` and `code = NO_OUTPUT` in its settlement/discovery record.
This is an observed result, not an interface rejection or proof that the input
could never produce anything under other conditions.

Feedback does not inspect hidden recipes, coefficients, other members' private
inventories, unseen chats or undiscovered combinations. Unrecognized exception
strings are not forwarded to the member. Failed actions remain rejected: hints
never rewrite or execute a corrected action, transfer resources, or waive costs.

The paid 2026-10-12 comparison keeps its frozen engine and old feedback. This
change applies to new runs; it must be treated as an interface intervention when
comparing future trajectories. Historical outcomes are not rewritten.

Validation: `tests/test_interface_feedback.py`, plus the material, social-content
and pre-action communication regression suites. All checks use offline/mock
calls and incur no API charge.
