from yahtzee_game import YahtzeeGame
from utils import calculate_score
from itertools import product, combinations_with_replacement
from functools import lru_cache
from math import factorial
import time

class DynamicProgrammingBot:
    def __init__(self):
        self._categories = list(YahtzeeGame().score_sheet.keys())
        self._numeric_scores = {
            "aces": 1, "twos": 2, "threes": 3, "fours": 4, "fives": 5, "sixes": 6,
        }
        self._upper_categories = set(self._numeric_scores.keys())

    def intmask_to_listmask(self, reroll_mask_int):
        # bit i = 1 means reroll die i
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]

    @lru_cache(maxsize=None)
    def _score_category(self, dice_state, cat):
        return calculate_score(dice_state, cat)

    @lru_cache(maxsize=None)
    def _get_future_ev(self, avail_t, upper_total):
        """
        Calculates the Expected Value (EV) of the rest of the game 
        given the available categories (avail_t), assuming a fresh roll of 5 dice.
        upper_total: current sum of upper section scores (capped at 63 for state space)
        """
        # Base case: No categories left, game over.
        if not any(avail_t):
            # Add 35 bonus if upper section total >= 63
            return 35.0 if upper_total >= 63 else 0.0

        total_ev = 0.0
        # Iterate over all unique sorted outcomes of rolling 5 dice (252 combinations)
        # We weigh them by their probability of occurring.
        for outcome in combinations_with_replacement(range(1, 7), 5):
            # Calculate probability of this specific outcome (Multinomial distribution)
            counts = [outcome.count(i) for i in range(1, 7)]
            denom = 1
            for c in counts:
                denom *= factorial(c)
            # Probability = (5! / (c1! * ... * c6!)) * (1/6)^5
            prob = (factorial(5) / denom) / (6**5)
            
            # Add weighted EV. 
            # A new turn starts with 2 rerolls allowed (after the initial roll).
            total_ev += prob * self._best_ev(outcome, 2, avail_t, upper_total)
            
        return total_ev

    @lru_cache(maxsize=None)
    def _best_category_value(self, dice_state, avail_t, upper_total):
        """
        Returns max(Score + FutureEV) for the current dice state.
        """
        dice_state = tuple(sorted(dice_state))
        best = float("-inf")
        
        # We need indices to construct the next state tuple
        for i, (cat, avail) in enumerate(zip(self._categories, avail_t)):
            if not avail:
                continue
            
            # 1. Immediate Score
            current_score = self._score_category(dice_state, cat)
            
            # 2. Calculate new upper_total if this is an upper section category
            new_upper_total = upper_total
            if cat in self._upper_categories:
                # Cap at 63 to limit state space (anything >= 63 is equivalent)
                new_upper_total = min(63, upper_total + current_score)
            
            # 3. Future Expected Value (DP step)
            # Create new mask with this category used (False)
            new_avail = list(avail_t)
            new_avail[i] = False
            future_val = self._get_future_ev(tuple(new_avail), new_upper_total)
            
            total_val = current_score + future_val
            
            if total_val > best:
                best = total_val
        return best

    @lru_cache(maxsize=None)
    def _best_ev(self, dice_state, r_left, avail_t, upper_total):
        dice_state = tuple(sorted(dice_state))
        if r_left == 0:
            return self._best_category_value(dice_state, avail_t, upper_total)
        return max(self._ev_if_reroll_mask(dice_state, m, r_left, avail_t, upper_total) for m in range(1 << 5))

    @lru_cache(maxsize=None)
    def _ev_if_reroll_mask(self, dice_state, m, r_left, avail_t, upper_total):
        reroll_idxs = [i for i in range(5) if ((m >> i) & 1) == 1]
        k = len(reroll_idxs)

        if k == 0:
            return self._best_category_value(dice_state, avail_t, upper_total)

        total = 0.0
        p_each = (1.0 / 6.0) ** k
        for outcome in product(range(1, 7), repeat=k):
            new_dice = list(dice_state)
            for idx, val in zip(reroll_idxs, outcome):
                new_dice[idx] = val
            new_state = tuple(sorted(new_dice)) # For canonization
            total += p_each * self._best_ev(new_state, r_left - 1, avail_t, upper_total)
        return total

    def _get_upper_total(self, score_sheet):
        """Calculate current upper section total from score sheet."""
        total = 0
        for cat in self._upper_categories:
            if score_sheet[cat] is not None:
                total += score_sheet[cat]
        return min(63, total)  # Cap at 63

    # Choose the best dice mask i.e. the best dice to reroll
    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        upper_total = self._get_upper_total(score_sheet)

        if rolls_left == 0:
            return 0  

        best_mask = 0
        best_val = float("-inf")

        if debug:
            print(f"    [bot] evaluating 32 masks for dice={list(dice_t)} rolls_left={rolls_left}", flush=True)

        t_start = time.perf_counter()
        for m in range(1 << 5):
            if debug and (m % 4 == 0):
                elapsed = time.perf_counter() - t_start
                print(f"    [bot] mask {m:2d}/31 (elapsed {elapsed:.2f}s) best={best_val:.3f}", flush=True)
                
            v = self._ev_if_reroll_mask(dice_t, m, rolls_left, avail_t, upper_total)
            if v > best_val:
                best_val = v
                best_mask = m

        if debug:
            elapsed = time.perf_counter() - t_start
            print(f"    [bot] done in {elapsed:.2f}s best_mask={best_mask:05b} ev={best_val:.3f}", flush=True)

        return best_mask

    def expected_turn_value(self, dice, reroll_mask, rolls_left, score_sheet):
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        upper_total = self._get_upper_total(score_sheet)

        if rolls_left == 0:
            return self._best_category_value(dice_t, avail_t, upper_total)

        return self._ev_if_reroll_mask(dice_t, reroll_mask, rolls_left, avail_t, upper_total)
    
    def choose_best_category(self, dice, score_sheet):
        """
        Picks the category that maximizes (Immediate Score + Future EV).
        """
        dice_t = tuple(sorted(dice))
        avail_t = tuple(score_sheet[cat] is None for cat in self._categories)
        upper_total = self._get_upper_total(score_sheet)

        best_cat = None
        best_total_val = float("-inf")
        
        for i, (cat, avail) in enumerate(zip(self._categories, avail_t)):
            if not avail:
                continue
            
            # Score for this specific category
            s = self._score_category(dice_t, cat)
            
            # Calculate new upper_total if this is an upper section category
            new_upper_total = upper_total
            if cat in self._upper_categories:
                new_upper_total = min(63, upper_total + s)
            
            # Future EV if we consume this category
            new_avail = list(avail_t)
            new_avail[i] = False
            f_ev = self._get_future_ev(tuple(new_avail), new_upper_total)
            
            total_val = s + f_ev
            
            if total_val > best_total_val:
                best_total_val = total_val
                best_cat = cat
                
        return best_cat

    def reset_cache(self):
        self._score_category.cache_clear()
        self._best_category_value.cache_clear()
        self._best_ev.cache_clear()
        self._ev_if_reroll_mask.cache_clear()
        self._get_future_ev.cache_clear()