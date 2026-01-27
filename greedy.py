from yahtzee_game import YahtzeeGame
from itertools import product
from functools import lru_cache
import time

class GreedyBot:
    def __init__(self):
        self._categories = list(YahtzeeGame().score_sheet.keys())

    def intmask_to_listmask(self, reroll_mask_int):
        # bit i = 1 means reroll die i
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]

    # Choose the best dice mask i.e. the best dice to reroll
    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(dice)
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)

        @lru_cache(maxsize=None)
        def best_category_value(dice_state):
            g = YahtzeeGame()
            g.dice = list(dice_state)
            g.score_sheet = {
                cat: (None if avail else 0)
                for cat, avail in zip(self._categories, avail_t)
            }
            best = float("-inf")
            for cat in self._categories:
                s = g.get_score(cat)
                if s > best:
                    best = s
            return best

        @lru_cache(maxsize=None)
        def best_ev(dice_state, r_left):
            if r_left == 0:
                return best_category_value(dice_state)
            return max(ev_if_reroll_mask(dice_state, m, r_left) for m in range(1 << 5))

        @lru_cache(maxsize=None)
        def ev_if_reroll_mask(dice_state, m, r_left):
            reroll_idxs = [i for i in range(5) if ((m >> i) & 1) == 1]
            k = len(reroll_idxs)

            if k == 0:
                return best_category_value(dice_state)

            total = 0.0
            p_each = (1.0 / 6.0) ** k
            for outcome in product(range(1, 7), repeat=k):
                new_dice = list(dice_state)
                for idx, val in zip(reroll_idxs, outcome):
                    new_dice[idx] = val
                total += p_each * best_ev(tuple(new_dice), r_left - 1)
            return total

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

            v = ev_if_reroll_mask(dice_t, m, rolls_left)
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
        dice_t = tuple(dice)
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)

        @lru_cache(maxsize=None)
        def best_category_value(dice_state):
            g = YahtzeeGame()
            g.dice = list(dice_state)
            # Mark unavailable categories as non-None so get_score returns -1 for them
            g.score_sheet = {
                cat: (None if avail else 0)
                for cat, avail in zip(self._categories, avail_t)
            }
            best = float("-inf")
            for cat in self._categories:
                s = g.get_score(cat)
                if s > best:
                    best = s
            return best

        @lru_cache(maxsize=None)
        def best_ev(dice_state, r_left):
            # Best EV from this state with r_left rerolls remaining
            if r_left == 0:
                return best_category_value(dice_state)

            best = float("-inf")
            for m in range(1 << 5):
                val = ev_if_reroll_mask(dice_state, m, r_left)
                if val > best:
                    best = val
            return best

        @lru_cache(maxsize=None)
        def ev_if_reroll_mask(dice_state, m, r_left):
            # Expected value if we apply mask m right now (consumes 1 reroll)
            reroll_idxs = [i for i in range(5) if ((m >> i) & 1) == 1]  # 1 means reroll
            k = len(reroll_idxs)

            # Enumerate all outcomes for rerolled dice
            total = 0.0
            p_each = (1.0 / 6.0) ** k

            if k == 0:
                # "Reroll nothing" -> dice unchanged but still consumes a reroll
                return best_category_value(dice_state)

            for outcome in product(range(1, 7), repeat=k):
                new_dice = list(dice_state)
                for idx, val in zip(reroll_idxs, outcome):
                    new_dice[idx] = val
                total += p_each * best_ev(tuple(new_dice), r_left - 1)

            return total

        # We are evaluating the EV of taking *this specific* mask now
        if rolls_left == 0:
            return best_category_value(dice_t)

        return ev_if_reroll_mask(dice_t, reroll_mask, rolls_left)
    
    def choose_best_category(self, dice, score_sheet):
        """
        When rolls_left == 0, pick the best available category for these dice.
        """
        g = YahtzeeGame()
        g.dice = list(dice)
        g.score_sheet = dict(score_sheet)  # preserve availability
        best_cat = None
        best_score = float("-inf")
        for cat in self._categories:
            s = g.get_score(cat)
            if s > best_score:
                best_score = s
                best_cat = cat
        return best_cat
