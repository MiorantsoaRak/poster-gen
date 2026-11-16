**Verdict: APPROVE WITH FIXES.** The admission/debit model fits the current code. The remaining fixes concern payment validation, restore instructions and browser recovery.

1. **P2 — Amount fixes can erase or negate a payment.**  
   D-005 permits a bought grant of 1,000 Ar followed by `correct … 0 --amount-ar -2000`: receipts become −1,000 Ar, while the credits remain. Require the corrected payment total to stay positive.

   The trigger’s stronger claim also needs correction: [design:150](docs/project/designs/prepaid-balance.md:150) sums **all other shops together**. A negative balance of ariary in one shop can conceal a positive payment in another. Use `EXISTS` over per-shop groups with `HAVING SUM(amount_ar) > 0`. The command-level checks prevent the round-2 duplication sequence; the SQL does not independently guarantee everything claimed.

2. **P2 — Restore must replay operations globally, not shop by shop.**  
   D-005’s [per-shop ordering](docs/project/designs/prepaid-balance.md:539) does not preserve dependencies in A→B→C. Processing B first can print B→C before A→B; following those commands leaves the payment in the wrong shop after refusals.

   Print all missing-shop creations first, then operations in the kept ledger’s global insertion order. Pair each move once, suppress its component grant/correction, and test a chain whose shop order opposes its movement order. Retain the new repayment classification.

3. **P2 — Restore silently changes payment dates.**  
   Reconciliation prints ordinary grant/correction commands, whose contracts provide no original timestamp. Replaying a payment from last month therefore records it this month. The dashboard seam explicitly totals ariary by `created_at` ([design:632](docs/project/designs/prepaid-balance.md:632)).

   Preserve the original effective date during reconciliation and test period totals before and after restore. This consequence is not currently addressed.

4. **P2 — Exempt both replay buttons from credit and blocking gates.**  
   D-006 exempts « Reprendre » at zero, but does not clearly exempt « Réessayer », or either button during a service/day block. Both resend the same stored request ([ChatView.vue:324](frontend/src/ChatView.vue:324)); the distinction is presentation state ([chat.ts:249](frontend/src/chat.ts:249)).

   An accepted request can consume the last credit/reservation before its answer is lost. Its replay still succeeds because [store.py:47](backend/src/affiche/posters/store.py:47) returns the stored answer before admission checks. Gate **new requests** only; keep both replays available at zero and while blocked. Test that case.

5. **P2 — Specify shell-safe printed commands.**  
   D-005 prints `--name "<name>"`. Shop names are editable and accept shell metacharacters ([models.py:11](backend/src/affiche/posters/models.py:11), [store.py:137](backend/src/affiche/posters/store.py:137)); double quotes still allow command substitution.

   Require `shlex.join` for the complete argument list, including names, references and notes. Test quotes, newlines and literal `$()` without executing the printed command.

**Round-2 disposition**

| Finding | Status |
|---|---|
| Payment funds two shops | **CLOSED** through the specified commands; schema/amount validation needs fix 1 |
| Restore repayment classification | **CLOSED**; restore ordering and dates are separate remaining defects |
| Scene estimate disables textures | **CLOSED** |
| History omits returned credits | **CLOSED** |
| Cached cancellation exposes dollars | **CLOSED** as specified, including the historical replay test |

**P3 — Small corrections before implementation**

- T-BALANCE-003 also needs to replace the `/api/usage` assertions at [test_api.py:100](backend/tests/test_api.py:100).
- Append the returned-credit sentence in the common terminal-job branch: `interrupted` currently bypasses `jobFailure` ([App.vue:1250](frontend/src/App.vue:1250)).
- The headroom example warns although **8.40 < 8.80**; remove its warning or change its numbers.

Keep the seven-task order and the derived balance. The pilot’s temporary zero balance matches the owner’s decision and the actual release sequence. A→B→C preserves totals through the specified commands; moving back, or moving after an amount fix, is explicitly refused. Keeping amount fixes is useful only with the positive-total rule above.

The seven remaining owner decisions still need resolution. In particular, textures amend ADR-107, and choosing a monthly cap adds a separate task. Apply the listed requirements amendments before implementation.

No files changed; no tests or network, device, production, paid or store-writing commands run. SQLite 3.40.1 and restore execution remain unverified.