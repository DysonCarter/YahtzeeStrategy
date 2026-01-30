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

    def intmask_to_listmask(self, reroll_mask_int):
        # bit i = 1 means reroll die i
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]

    @lru_cache(maxsize=None)
    def _score_category(self, dice_state, cat):
        return calculate_score(dice_state, cat)

    @lru_cache(maxsize=None)
    def _best_category_value(self, dice_state, avail_t):
        best = float("-inf")
        for cat, avail in zip(self._categories, avail_t):
            if not avail:
                continue
            val = self._score_category(dice_state, cat)
            if val > best:
                best = val
        return best

    @lru_cache(maxsize=None)
    def _best_ev(self, dice_state, r_left, avail_t):
        if r_left == 0:
            return self._best_category_value(dice_state, avail_t)
        return max(self._ev_if_reroll_mask(dice_state, m, r_left, avail_t) for m in range(1 << 5))

    @lru_cache(maxsize=None)
    def _ev_if_reroll_mask(self, dice_state, m, r_left, avail_t):
        reroll_idxs = [i for i in range(5) if ((m >> i) & 1) == 1]
        k = len(reroll_idxs)

        if k == 0:
            return self._best_category_value(dice_state, avail_t)

        total = 0.0
        p_each = (1.0 / 6.0) ** k
        for outcome in product(range(1, 7), repeat=k):
            new_dice = list(dice_state)
            for idx, val in zip(reroll_idxs, outcome):
                new_dice[idx] = val

            new_state = tuple(sorted(new_dice)) # Canonize
            total += p_each * self._best_ev(new_state, r_left - 1, avail_t)
        return total

    # Choose the best dice mask i.e. the best dice to reroll
    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)

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

            v = self._ev_if_reroll_mask(dice_t, m, rolls_left, avail_t)
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

        # We are evaluating the EV of taking *this specific* mask now
        if rolls_left == 0:
            return self._best_category_value(dice_t, avail_t)

        return self._ev_if_reroll_mask(dice_t, reroll_mask, rolls_left, avail_t)
    
    def choose_best_category(self, dice, score_sheet):
        """
        When rolls_left == 0, pick the best available category for these dice.
        """
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)

        best_cat = None
        best_score = float("-inf")
        for cat, avail in zip(self._categories, avail_t):
            if not avail:
                continue
            s = self._score_category(dice_t, cat)
            if s > best_score:
                best_score = s
                best_cat = cat
        return best_cat

    def reset_cache(self):
        self._score_category.cache_clear()
        self._best_category_value.cache_clear()
        self._best_ev.cache_clear()
        self._ev_if_reroll_mask.cache_clear()
