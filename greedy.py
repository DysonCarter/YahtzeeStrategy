from yahtzee_game import YahtzeeGame
from utils import calculate_score
from itertools import product
from functools import lru_cache
import time

class GreedyBot:
    def __init__(self):
        self._categories = list(YahtzeeGame().score_sheet.keys())
        self._numeric_scores = {
            "aces": 1, "twos": 2, "threes": 3, "fours": 4, "fives": 5, "sixes": 6,
        }

        self._cat_to_idx = {c: i for i, c in enumerate(self._categories)}
        self._idx_yahtzee = self._cat_to_idx.get("yahtzee")
        self._idx_fullhouse = self._cat_to_idx.get("fullhouse")
        self._idx_smstraight = self._cat_to_idx.get("smstraight")
        self._idx_lgstraight = self._cat_to_idx.get("lgstraight")

        self._upper_idxs = {self._cat_to_idx[c] for c in self._numeric_scores.keys()}
        self._lower_idxs = {i for i in range(len(self._categories)) if i not in self._upper_idxs}

        self._upper_idx_by_face = {
            1: self._cat_to_idx["aces"],
            2: self._cat_to_idx["twos"],
            3: self._cat_to_idx["threes"],
            4: self._cat_to_idx["fours"],
            5: self._cat_to_idx["fives"],
            6: self._cat_to_idx["sixes"],
        }

    def intmask_to_listmask(self, reroll_mask_int):
        # bit i = 1 means reroll die i
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]

    @lru_cache(maxsize=None)
    def _score_category(self, dice_state, cat):
        return calculate_score(dice_state, cat)

    @lru_cache(maxsize=None)
    def _best_category_value(self, dice_state, avail_t, y_bonus_enabled):
        is_yahtzee_roll = (dice_state[0] == dice_state[4])
        yahtzee_open = bool(avail_t[self._idx_yahtzee]) if self._idx_yahtzee is not None else False
        apply_joker = is_yahtzee_roll and (not yahtzee_open) and y_bonus_enabled

        immediate_bonus = 100.0 if apply_joker else 0.0

        forced_upper = None
        if apply_joker:
            upper_idx = self._upper_idx_by_face[dice_state[0]]
            if avail_t[upper_idx]:
                forced_upper = upper_idx

        lower_avail = any(avail_t[i] for i in self._lower_idxs)

        best = float("-inf")
        for ci, (cat, avail) in enumerate(zip(self._categories, avail_t)):
            if not avail:
                continue

            if forced_upper is not None and ci != forced_upper:
                continue

            if apply_joker and forced_upper is None and lower_avail and (ci in self._upper_idxs):
                continue

            score = self._score_category(dice_state, cat)

            if apply_joker and forced_upper is None:
                if ci == self._idx_fullhouse:
                    score = 25
                elif ci == self._idx_smstraight:
                    score = 30
                elif ci == self._idx_lgstraight:
                    score = 40

            val = immediate_bonus + score
            if val > best:
                best = val

        return best

    @lru_cache(maxsize=None)
    def _best_ev(self, dice_state, r_left, avail_t, y_bonus_enabled):
        if r_left == 0:
            return self._best_category_value(dice_state, avail_t, y_bonus_enabled)
        return max(self._ev_if_reroll_mask(dice_state, m, r_left, avail_t, y_bonus_enabled) for m in range(1 << 5))

    @lru_cache(maxsize=None)
    def _ev_if_reroll_mask(self, dice_state, m, r_left, avail_t, y_bonus_enabled):
        reroll_idxs = [i for i in range(5) if ((m >> i) & 1) == 1]
        k = len(reroll_idxs)

        if k == 0:
            return self._best_category_value(dice_state, avail_t, y_bonus_enabled)

        total = 0.0
        p_each = (1.0 / 6.0) ** k
        for outcome in product(range(1, 7), repeat=k):
            new_dice = list(dice_state)
            for idx, val in zip(reroll_idxs, outcome):
                new_dice[idx] = val

            new_state = tuple(sorted(new_dice)) # Canonize
            total += p_each * self._best_ev(new_state, r_left - 1, avail_t, y_bonus_enabled)
        return total

    # Choose the best dice mask i.e. the best dice to reroll
    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

        # pick best mask using the *same* cache
        if rolls_left == 0:
            return 0  # no rerolls possible

        best_mask = 0
        best_val = float("-inf")

        if debug:
            print(f"    [bot] evaluating 32 masks for dice={list(dice_t)} rolls_left={rolls_left}", flush=True)

        t_start = time.perf_counter()
        for m in range(1 << 5):
            if debug and (m % 4 == 0):
                elapsed = time.perf_counter() - t_start
                print(f"    [bot] mask {m:2d}/31 (elapsed {elapsed:.2f}s) best={best_val:.3f}", flush=True)

            v = self._ev_if_reroll_mask(dice_t, m, rolls_left, avail_t, y_bonus_enabled)
            if v > best_val:
                best_val = v
                best_mask = m

        if debug:
            elapsed = time.perf_counter() - t_start
            print(f"    [bot] done in {elapsed:.2f}s best_mask={best_mask:05b} ev={best_val:.3f}", flush=True)

        return best_mask

    def expected_turn_value(self, dice, reroll_mask, rolls_left, score_sheet):
        """
        True expected value for the REST of this turn if you apply reroll_mask now,
        then play optimally (choose best reroll mask) on remaining rerolls,
        then choose best available category to score at the end.

        Mask semantics
          - bit 1 => reroll that die
          - bit 0 => keep that die
        """
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

        # We are evaluating the EV of taking *this specific* mask now
        if rolls_left == 0:
            return self._best_category_value(dice_t, avail_t, y_bonus_enabled)

        return self._ev_if_reroll_mask(dice_t, reroll_mask, rolls_left, avail_t, y_bonus_enabled)
    
    def choose_best_category(self, dice, score_sheet):
        """
        When rolls_left == 0, pick the best available category for these dice.
        """
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        y_bonus_enabled = (score_sheet.get("yahtzee") == 50)

        is_yahtzee_roll = (dice_t[0] == dice_t[4])
        yahtzee_open = bool(avail_t[self._idx_yahtzee]) if self._idx_yahtzee is not None else False
        apply_joker = is_yahtzee_roll and (not yahtzee_open) and y_bonus_enabled

        forced_upper = None
        if apply_joker:
            upper_idx = self._upper_idx_by_face[dice_t[0]]
            if avail_t[upper_idx]:
                forced_upper = upper_idx

        lower_avail = any(avail_t[i] for i in self._lower_idxs)

        best_cat = None
        best_val = float("-inf")
        for ci, (cat, avail) in enumerate(zip(self._categories, avail_t)):
            if not avail:
                continue

            if forced_upper is not None and ci != forced_upper:
                continue

            if apply_joker and forced_upper is None and lower_avail and (ci in self._upper_idxs):
                continue

            s = self._score_category(dice_t, cat)

            if apply_joker and forced_upper is None:
                if ci == self._idx_fullhouse:
                    s = 25
                elif ci == self._idx_smstraight:
                    s = 30
                elif ci == self._idx_lgstraight:
                    s = 40

            if s > best_val:
                best_val = s
                best_cat = cat

        return best_cat

    def reset_cache(self):
        self._score_category.cache_clear()
        self._best_category_value.cache_clear()
        self._best_ev.cache_clear()
        self._ev_if_reroll_mask.cache_clear()
