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
        self._idx_yahtzee = self._cat_to_idx.get("yahtzee")
        self._idx_fullhouse = self._cat_to_idx.get("fullhouse")
        self._idx_smstraight = self._cat_to_idx.get("smstraight")
        self._idx_lgstraight = self._cat_to_idx.get("lgstraight")

        # face value -> corresponding upper category index
        self._upper_idx_by_face = {
            1: self._cat_to_idx["aces"],
            2: self._cat_to_idx["twos"],
            3: self._cat_to_idx["threes"],
            4: self._cat_to_idx["fours"],
            5: self._cat_to_idx["fives"],
            6: self._cat_to_idx["sixes"],
        }

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

        # NOTE: calculate_score MUST be "standard" category scoring (no Joker baked in),
        # because Joker overrides are handled in _best_category_value / choose_best_category.
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
    def _get_future_ev(self, avail_mask, upper_total, y_bonus_enabled):
        """
        EV of the rest of the game given available categories (bitmask),
        assuming a fresh roll of 5 dice. upper_total capped to 63.
        """
        if avail_mask == 0:
            return 35.0 if upper_total >= 63 else 0.0

        total_ev = 0.0
        for sid, prob in self._first_roll:
            total_ev += prob * self._best_ev(sid, 2, avail_mask, upper_total, y_bonus_enabled)
        return total_ev

    @lru_cache(maxsize=None)
    def _best_category_value(self, state_id, avail_mask, upper_total, y_bonus_enabled):
        """
        max over legal available categories of (immediate score + yahtzee bonus (if any) + future EV),
        including Joker legality + overrides.
        """
        dice = self._dice_states[state_id]  # sorted 5-tuple

        # --- Joker / Yahtzee bonus detection
        is_yahtzee_roll = (dice[0] == dice[4])
        yahtzee_open = bool(avail_mask & (1 << self._idx_yahtzee)) if self._idx_yahtzee is not None else False
        apply_joker = is_yahtzee_roll and (not yahtzee_open) and y_bonus_enabled

        immediate_bonus = 100.0 if apply_joker else 0.0

        # If Joker applies and the corresponding upper slot is open, you MUST use it.
        forced_upper = None
        if apply_joker:
            upper_idx = self._upper_idx_by_face[dice[0]]
            if avail_mask & (1 << upper_idx):
                forced_upper = upper_idx

        # If Joker applies and you're NOT forced into the corresponding upper slot,
        # you must play in the lower section if any lower category is available.
        lower_avail = (avail_mask & ~self._upper_mask) != 0

        best = float("-inf")

        for ci in range(self._n_cat):
            if not (avail_mask & (1 << ci)):
                continue

            # enforce joker forced-upper constraint
            if forced_upper is not None and ci != forced_upper:
                continue

            # enforce "must play lower if possible" when Joker applies and not forced into upper
            if apply_joker and forced_upper is None and lower_avail and (self._upper_mask & (1 << ci)):
                continue

            # base score from precomputed table
            score = self._score_table[state_id][ci]

            # joker scoring overrides (only when forced upper is NOT open)
            if apply_joker and forced_upper is None:
                if ci == self._idx_fullhouse:
                    score = 25
                elif ci == self._idx_smstraight:
                    score = 30
                elif ci == self._idx_lgstraight:
                    score = 40

            # update upper total
            new_upper_total = upper_total
            if self._upper_mask & (1 << ci):
                s = upper_total + score
                new_upper_total = 63 if s >= 63 else s

            new_avail = avail_mask & ~(1 << ci)

            # enable future yahtzee bonuses iff we scored Yahtzee category with 50
            new_y_bonus = y_bonus_enabled
            if ci == self._idx_yahtzee and score == 50:
                new_y_bonus = True

            future_val = self._get_future_ev(new_avail, new_upper_total, new_y_bonus)
            total_val = immediate_bonus + score + future_val

            if total_val > best:
                best = total_val

        return best

    @lru_cache(maxsize=None)
    def _best_ev(self, state_id, r_left, avail_mask, upper_total, y_bonus_enabled):
        """
        Best EV from this dice state with r_left rerolls remaining in the turn.
        """
        if r_left == 0:
            return self._best_category_value(state_id, avail_mask, upper_total, y_bonus_enabled)

        # Option: stop early and score now (equivalent to rerolling 0 dice)
        best = self._best_category_value(state_id, avail_mask, upper_total, y_bonus_enabled)

        dice = self._dice_states[state_id]
        for m in range(1, 32):
            k = m.bit_count()
            kept = tuple(dice[i] for i in range(5) if not ((m >> i) & 1))
            v = self._ev_after_reroll(kept, k, r_left, avail_mask, upper_total, y_bonus_enabled)
            if v > best:
                best = v

        return best

    @lru_cache(maxsize=None)
    def _ev_after_reroll(self, kept, k, r_left, avail_mask, upper_total, y_bonus_enabled):
        """
        Expected value if we reroll k dice (consuming 1 reroll), keeping 'kept' (sorted tuple).
        Distribution is over unique multisets of k dice with multinomial probabilities.
        """
        total = 0.0
        for outcome, prob in self._roll_outcomes_by_k[k]:
            new_dice = self._merge_sorted(kept, outcome)
            new_sid = self._state_to_id[new_dice]
            total += prob * self._best_ev(new_sid, r_left - 1, avail_mask, upper_total, y_bonus_enabled)
        return total

    # --- Public API

    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(sorted(dice))
        state_id = self._state_to_id[dice_t]
        avail_mask = self._make_avail_mask(score_sheet)
        upper_total = self._get_upper_total(score_sheet)
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

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
                v = self._best_category_value(state_id, avail_mask, upper_total, y_bonus_enabled)
            else:
                k = m.bit_count()
                kept = tuple(dice_t[i] for i in range(5) if not ((m >> i) & 1))
                v = self._ev_after_reroll(kept, k, rolls_left, avail_mask, upper_total, y_bonus_enabled)

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
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

        if rolls_left == 0 or reroll_mask == 0:
            return self._best_category_value(state_id, avail_mask, upper_total, y_bonus_enabled)

        k = reroll_mask.bit_count()
        kept = tuple(dice_t[i] for i in range(5) if not ((reroll_mask >> i) & 1))
        return self._ev_after_reroll(kept, k, rolls_left, avail_mask, upper_total, y_bonus_enabled)

    def choose_best_category(self, dice, score_sheet):
        dice_t = tuple(sorted(dice))
        state_id = self._state_to_id[dice_t]
        avail_mask = self._make_avail_mask(score_sheet)
        upper_total = self._get_upper_total(score_sheet)
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

        # --- Joker / Yahtzee bonus detection
        is_yahtzee_roll = (dice_t[0] == dice_t[4])
        yahtzee_open = bool(avail_mask & (1 << self._idx_yahtzee)) if self._idx_yahtzee is not None else False
        apply_joker = is_yahtzee_roll and (not yahtzee_open) and y_bonus_enabled

        immediate_bonus = 100.0 if apply_joker else 0.0

        forced_upper = None
        if apply_joker:
            upper_idx = self._upper_idx_by_face[dice_t[0]]
            if avail_mask & (1 << upper_idx):
                forced_upper = upper_idx

        # If Joker applies and we are NOT forced into upper,
        # play in lower section if any lower category is still open.
        lower_avail = (avail_mask & ~self._upper_mask) != 0

        best_cat = None
        best_total_val = float("-inf")

        for ci in range(self._n_cat):
            if not (avail_mask & (1 << ci)):
                continue

            if forced_upper is not None and ci != forced_upper:
                continue

            if apply_joker and forced_upper is None and lower_avail and (self._upper_mask & (1 << ci)):
                continue

            s = self._score_table[state_id][ci]

            # Joker scoring overrides (only when not forced into upper)
            if apply_joker and forced_upper is None:
                if ci == self._idx_fullhouse:
                    s = 25
                elif ci == self._idx_smstraight:
                    s = 30
                elif ci == self._idx_lgstraight:
                    s = 40

            new_upper_total = upper_total
            if self._upper_mask & (1 << ci):
                t = upper_total + s
                new_upper_total = 63 if t >= 63 else t

            new_avail = avail_mask & ~(1 << ci)

            new_y_bonus = y_bonus_enabled
            if ci == self._idx_yahtzee and s == 50:
                new_y_bonus = True

            f_ev = self._get_future_ev(new_avail, new_upper_total, new_y_bonus)
            total_val = immediate_bonus + s + f_ev

            if total_val > best_total_val:
                best_total_val = total_val
                best_cat = self._categories[ci]

        return best_cat

    def reset_cache(self):
        self._get_future_ev.cache_clear()
        self._best_category_value.cache_clear()
        self._best_ev.cache_clear()
        self._ev_after_reroll.cache_clear()
