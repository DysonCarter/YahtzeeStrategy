from yahtzee_game import YahtzeeGame
from utils import calculate_score
from itertools import combinations_with_replacement
from functools import lru_cache
import time


class DynamicProgrammingBot:
    def __init__(self):
        self._categories = list(YahtzeeGame().score_sheet.keys())
        self._n_cat = len(self._categories)

        self._numeric_scores = {
            "aces": 1, "twos": 2, "threes": 3, "fours": 4, "fives": 5, "sixes": 6,
        }
        self._upper_categories = set(self._numeric_scores.keys())

        # --- category indices + upper mask (bit i = category i is upper section)
        self._cat_to_idx = {c: i for i, c in enumerate(self._categories)}
        self._upper_mask = 0
        for c in self._upper_categories:
            if c in self._cat_to_idx:
                self._upper_mask |= (1 << self._cat_to_idx[c])

        # --- all 252 dice multisets, interned to ids (0..251)
        self._dice_states = list(combinations_with_replacement(range(1, 7), 5))  # each is a sorted 5-tuple
        self._state_to_id = {s: i for i, s in enumerate(self._dice_states)}

        # --- small factorials 0..5
        self._fact = [1] * 6
        for i in range(1, 6):
            self._fact[i] = self._fact[i - 1] * i

        # --- precompute multinomial-weighted outcomes for rolling k dice (k=0..5)
        # Each entry: list of (sorted_tuple_of_len_k, prob)
        self._roll_outcomes_by_k = [[] for _ in range(6)]
        self._roll_outcomes_by_k[0] = [((), 1.0)]
        for k in range(1, 6):
            denom_pow = 6 ** k
            fk = self._fact[k]
            outs = []
            for outcome in combinations_with_replacement(range(1, 7), k):
                counts = [0] * 6
                for v in outcome:
                    counts[v - 1] += 1
                denom = 1
                for c in counts:
                    denom *= self._fact[c]
                prob = (fk / denom) / denom_pow
                outs.append((outcome, prob))
            self._roll_outcomes_by_k[k] = outs

        # --- precompute first-roll distribution as (state_id, prob)
        self._first_roll = [(self._state_to_id[out], p) for (out, p) in self._roll_outcomes_by_k[5]]

        # --- precompute score table: score_table[state_id][cat_idx]
        self._score_table = [[0] * self._n_cat for _ in range(len(self._dice_states))]
        for sid, dice in enumerate(self._dice_states):
            for ci, cat in enumerate(self._categories):
                self._score_table[sid][ci] = calculate_score(dice, cat)

    def intmask_to_listmask(self, reroll_mask_int):
        # bit i = 1 means reroll die i
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]

    @staticmethod
    def _merge_sorted(a, b):
        """Merge two sorted tuples into one sorted tuple."""
        i = j = 0
        la, lb = len(a), len(b)
        res = []
        while i < la and j < lb:
            if a[i] <= b[j]:
                res.append(a[i]); i += 1
            else:
                res.append(b[j]); j += 1
        if i < la:
            res.extend(a[i:])
        if j < lb:
            res.extend(b[j:])
        return tuple(res)

    def _make_avail_mask(self, score_sheet):
        """bit i=1 means category i is available"""
        m = 0
        for i, cat in enumerate(self._categories):
            if score_sheet[cat] is None:
                m |= (1 << i)
        return m

    def _get_upper_total(self, score_sheet):
        """Calculate current upper section total from score sheet (cap at 63)."""
        total = 0
        for cat in self._upper_categories:
            if cat in score_sheet and score_sheet[cat] is not None:
                total += score_sheet[cat]
        return 63 if total >= 63 else total

    @lru_cache(maxsize=None)
    def _get_future_ev(self, avail_mask, upper_total):
        """
        EV of the rest of the game given available categories (bitmask),
        assuming a fresh roll of 5 dice. upper_total capped to 63.
        """
        if avail_mask == 0:
            return 35.0 if upper_total >= 63 else 0.0

        total_ev = 0.0
        for sid, prob in self._first_roll:
            total_ev += prob * self._best_ev(sid, 2, avail_mask, upper_total)
        return total_ev

    @lru_cache(maxsize=None)
    def _best_category_value(self, state_id, avail_mask, upper_total):
        """
        max over available categories of (immediate score + future EV)
        """
        best = float("-inf")

        for ci in range(self._n_cat):
            if not (avail_mask & (1 << ci)):
                continue

            current_score = self._score_table[state_id][ci]

            new_upper_total = upper_total
            if self._upper_mask & (1 << ci):
                s = upper_total + current_score
                new_upper_total = 63 if s >= 63 else s

            new_avail = avail_mask & ~(1 << ci)
            future_val = self._get_future_ev(new_avail, new_upper_total)

            total_val = current_score + future_val
            if total_val > best:
                best = total_val

        return best

    @lru_cache(maxsize=None)
    def _best_ev(self, state_id, r_left, avail_mask, upper_total):
        """
        Best EV from this dice state with r_left rerolls remaining in the turn.
        """
        if r_left == 0:
            return self._best_category_value(state_id, avail_mask, upper_total)

        # Option: stop early and score now (equivalent to rerolling 0 dice)
        best = self._best_category_value(state_id, avail_mask, upper_total)

        dice = self._dice_states[state_id]
        # Try rerolling some dice (m=1..31). This is where we avoid 6^k.
        for m in range(1, 32):
            k = m.bit_count()
            kept = tuple(dice[i] for i in range(5) if not ((m >> i) & 1))
            v = self._ev_after_reroll(kept, k, r_left, avail_mask, upper_total)
            if v > best:
                best = v

        return best

    @lru_cache(maxsize=None)
    def _ev_after_reroll(self, kept, k, r_left, avail_mask, upper_total):
        """
        Expected value if we reroll k dice (consuming 1 reroll), keeping 'kept' (sorted tuple).
        Distribution is over unique multisets of k dice with multinomial probabilities.
        """
        total = 0.0
        for outcome, prob in self._roll_outcomes_by_k[k]:
            new_dice = self._merge_sorted(kept, outcome)  # sorted 5-tuple
            new_sid = self._state_to_id[new_dice]
            total += prob * self._best_ev(new_sid, r_left - 1, avail_mask, upper_total)
        return total

    # --- Public API

    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(sorted(dice))
        state_id = self._state_to_id[dice_t]
        avail_mask = self._make_avail_mask(score_sheet)
        upper_total = self._get_upper_total(score_sheet)

        if rolls_left == 0:
            return 0

        best_mask = 0
        best_val = float("-inf")

        if debug:
            print(f"    [bot] evaluating 32 masks for dice={list(dice_t)} rolls_left={rolls_left}", flush=True)

        t_start = time.perf_counter()
        for m in range(32):
            if debug and (m % 4 == 0):
                elapsed = time.perf_counter() - t_start
                print(f"    [bot] mask {m:2d}/31 (elapsed {elapsed:.2f}s) best={best_val:.3f}", flush=True)

            if m == 0:
                v = self._best_category_value(state_id, avail_mask, upper_total)
            else:
                k = m.bit_count()
                kept = tuple(dice_t[i] for i in range(5) if not ((m >> i) & 1))
                v = self._ev_after_reroll(kept, k, rolls_left, avail_mask, upper_total)

            if v > best_val:
                best_val = v
                best_mask = m

        if debug:
            elapsed = time.perf_counter() - t_start
            print(f"    [bot] done in {elapsed:.2f}s best_mask={best_mask:05b} ev={best_val:.3f}", flush=True)

        return best_mask

    def expected_turn_value(self, dice, reroll_mask, rolls_left, score_sheet):
        dice_t = tuple(sorted(dice))
        state_id = self._state_to_id[dice_t]
        avail_mask = self._make_avail_mask(score_sheet)
        upper_total = self._get_upper_total(score_sheet)

        if rolls_left == 0 or reroll_mask == 0:
            return self._best_category_value(state_id, avail_mask, upper_total)

        k = reroll_mask.bit_count()
        kept = tuple(dice_t[i] for i in range(5) if not ((reroll_mask >> i) & 1))
        return self._ev_after_reroll(kept, k, rolls_left, avail_mask, upper_total)

    def choose_best_category(self, dice, score_sheet):
        dice_t = tuple(sorted(dice))
        state_id = self._state_to_id[dice_t]
        avail_mask = self._make_avail_mask(score_sheet)
        upper_total = self._get_upper_total(score_sheet)

        best_cat = None
        best_total_val = float("-inf")

        for ci in range(self._n_cat):
            if not (avail_mask & (1 << ci)):
                continue

            s = self._score_table[state_id][ci]

            new_upper_total = upper_total
            if self._upper_mask & (1 << ci):
                t = upper_total + s
                new_upper_total = 63 if t >= 63 else t

            new_avail = avail_mask & ~(1 << ci)
            f_ev = self._get_future_ev(new_avail, new_upper_total)

            total_val = s + f_ev
            if total_val > best_total_val:
                best_total_val = total_val
                best_cat = self._categories[ci]

        return best_cat

    def reset_cache(self):
        self._get_future_ev.cache_clear()
        self._best_category_value.cache_clear()
        self._best_ev.cache_clear()
        self._ev_after_reroll.cache_clear()
