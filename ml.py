import numpy as np
from sklearn.neural_network import MLPClassifier
from collections import Counter
import random
import os
import pickle
import warnings

from yahtzee_game import YahtzeeGame
from utils import calculate_score

warnings.filterwarnings('ignore')

#-----------------------------
# CONSTANTS
#-----------------------------

CATEGORIES = [
    "aces", "twos", "threes", "fours", "fives", "sixes",
    "threekind", "fourkind", "fullhouse", "smstraight", 
    "lgstraight", "yahtzee", "chance"
]

UPPER_CATEGORIES = ["aces", "twos", "threes", "fours", "fives", "sixes"]

NUM_REROLL_ACTIONS = 32
NUM_SCORE_ACTIONS = 13
NUM_ACTIONS = 45

#-----------------------------
# FEATURE EXTRACTION
#-----------------------------

def extract_features(dice, score_sheet, rolls_remaining):
    """Extract features from game state."""
    features = []
    counts = Counter(dice)
    dice_sum = sum(dice)
    unique = set(dice)
    
    # Dice Features (18)
    for face in range(1, 7):
        features.append(counts.get(face, 0) / 5.0)
    features.append(dice_sum / 30.0)
    features.append(max(counts.values()) / 5.0)
    features.append(len(unique) / 5.0)
    
    unique_sorted = sorted(unique)
    longest_run = 1
    current_run = 1
    for i in range(1, len(unique_sorted)):
        if unique_sorted[i] == unique_sorted[i-1] + 1:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    features.append(longest_run / 5.0)
    
    sm_straights = [{1,2,3,4}, {2,3,4,5}, {3,4,5,6}]
    features.append(1.0 if any(s.issubset(unique) for s in sm_straights) else 0.0)
    
    lg_straights = [{1,2,3,4,5}, {2,3,4,5,6}]
    features.append(1.0 if any(s == unique for s in lg_straights) else 0.0)
    
    sorted_counts = sorted(counts.values(), reverse=True)
    features.append(1.0 if sorted_counts == [3, 2] or sorted_counts == [5] else 0.0)
    features.append(1.0 if len(unique) == 1 else 0.0)
    
    for d in dice:
        features.append(d / 6.0)
    
    # Scoresheet Features (26)
    for cat in CATEGORIES:
        features.append(1.0 if score_sheet[cat] is not None else 0.0)
    
    max_scores = {
        "aces": 5, "twos": 10, "threes": 15, "fours": 20, "fives": 25, "sixes": 30,
        "threekind": 30, "fourkind": 30, "fullhouse": 25, "smstraight": 30,
        "lgstraight": 40, "yahtzee": 50, "chance": 30
    }
    for cat in CATEGORIES:
        if score_sheet[cat] is None:
            features.append(calculate_score(dice, cat) / max_scores[cat])
        else:
            features.append(0.0)
    
    # Strategic Features (8)
    features.append(rolls_remaining / 2.0)
    upper_total = sum(score_sheet[cat] for cat in UPPER_CATEGORIES if score_sheet[cat] is not None)
    features.append(upper_total / 63.0)
    upper_filled = sum(1 for cat in UPPER_CATEGORIES if score_sheet[cat] is not None)
    features.append(upper_filled / 6.0)
    total_filled = sum(1 for cat in CATEGORIES if score_sheet[cat] is not None)
    features.append(total_filled / 13.0)
    features.append(1.0 if score_sheet["yahtzee"] is not None else 0.0)
    expected_upper = upper_filled * 10.5
    features.append(1.0 if upper_total >= expected_upper * 0.9 else 0.0)
    best_available = max((calculate_score(dice, cat) for cat in CATEGORIES if score_sheet[cat] is None), default=0)
    features.append(best_available / 50.0)
    features.append(total_filled / 13.0)
    
    return np.array(features, dtype=np.float32)


def get_legal_mask(score_sheet, rolls_remaining):
    """Returns boolean mask of legal actions."""
    legal = np.zeros(NUM_ACTIONS, dtype=bool)
    if rolls_remaining > 0:
        legal[0:32] = True
    for i, cat in enumerate(CATEGORIES):
        if score_sheet[cat] is None:
            legal[32 + i] = True
    return legal


def action_to_reroll_mask(action):
    return [1 if ((action >> i) & 1) else 0 for i in range(5)]


def action_to_category(action):
    return CATEGORIES[action - 32]


def category_to_action(cat):
    return 32 + CATEGORIES.index(cat)


#-----------------------------
# ML BOT
#-----------------------------

class MLBot:
    def __init__(self, model_path=None):
        self._categories = CATEGORIES
        self.model = None
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def intmask_to_listmask(self, reroll_mask_int):
        return [1 if ((reroll_mask_int >> i) & 1) else 0 for i in range(5)]
    
    def _get_action_probs(self, features, legal_mask):
        """Get action probabilities, handling exploration."""
        if self.model is None:
            # Random policy if no model
            probs = np.zeros(NUM_ACTIONS)
            probs[legal_mask] = 1.0 / legal_mask.sum()
            return probs
        
        # Get model probabilities
        model_probs = self.model.predict_proba([features])[0]
        
        full_probs = np.zeros(NUM_ACTIONS)
        for i, cls in enumerate(self.model.classes_):
            full_probs[cls] = model_probs[i]
        
        # Zero out illegal actions and renormalize
        full_probs[~legal_mask] = 0
        if full_probs.sum() > 0:
            full_probs /= full_probs.sum()
        else:
            # Fallback to uniform over legal actions
            full_probs[legal_mask] = 1.0 / legal_mask.sum()
        
        return full_probs
    
    def sample_action(self, dice, score_sheet, rolls_remaining, temperature=1.0):
        """
        Sample an action using the current policy.
        Temperature controls exploration:
          - temperature=0: always pick best action (greedy)
          - temperature=1: sample proportional to probabilities
          - temperature>1: more random exploration
        """
        features = extract_features(dice, score_sheet, rolls_remaining)
        legal = get_legal_mask(score_sheet, rolls_remaining)
        
        probs = self._get_action_probs(features, legal)
        
        if temperature == 0:
            return int(np.argmax(probs))
        
        # Apply temperature
        if temperature != 1.0:
            probs = np.power(probs + 1e-10, 1.0 / temperature)
            probs /= probs.sum()
        
        return int(np.random.choice(NUM_ACTIONS, p=probs))
    
    def choose_best_keep(self, dice, rolls_left, score_sheet, debug=False):
        """Greedy action selection for evaluation."""
        if rolls_left == 0:
            return 0
        
        features = extract_features(dice, score_sheet, rolls_left)
        legal = get_legal_mask(score_sheet, rolls_left)
        legal[32:] = False  # Only reroll actions
        
        probs = self._get_action_probs(features, legal)
        best_action = int(np.argmax(probs))
        
        if debug:
            print(f"    [ml] dice={dice} rolls_left={rolls_left} -> mask={best_action:05b}")
        
        return best_action
    
    def choose_best_category(self, dice, score_sheet, debug=False):
        """Greedy category selection for evaluation."""
        features = extract_features(dice, score_sheet, rolls_remaining=0)
        legal = get_legal_mask(score_sheet, rolls_remaining=0)
        legal[0:32] = False  # Only score actions
        
        probs = self._get_action_probs(features, legal)
        best_action = int(np.argmax(probs))
        
        if debug:
            print(f"    [ml] dice={dice} -> category={action_to_category(best_action)}")
        
        return action_to_category(best_action)
    
    def save_model(self, path):
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)
    
    def load_model(self, path):
        with open(path, 'rb') as f:
            self.model = pickle.load(f)
    
    def reset_cache(self):
        pass


# =============================================================================
# GAME SIMULATION
# =============================================================================

def calculate_final_score(game):
    """Calculate final score for a completed game."""
    upper_score = sum(game.score_sheet[cat] for cat in UPPER_CATEGORIES)
    upper_bonus = 35 if upper_score >= 63 else 0
    lower_score = sum(v for k, v in game.score_sheet.items() if k not in UPPER_CATEGORIES)
    bonus_points = game.yahtzee_count * 100
    return upper_score + upper_bonus + lower_score + bonus_points


def play_game_and_record(bot, temperature=1.0):
    """
    Play a full game, recording all (state, action) pairs.
    Returns: (trajectory, final_score)
    """
    game = YahtzeeGame()
    trajectory = []
    
    for turn in range(13):
        game.roll_dice()
        
        # Up to 2 rerolls
        for roll in range(2):
            rolls_left = 2 - roll
            features = extract_features(game.dice, game.score_sheet, rolls_left)
            legal = get_legal_mask(game.score_sheet, rolls_left)
            
            action = bot.sample_action(game.dice, game.score_sheet, rolls_left, temperature)
            
            # Only record if it's a legal reroll action
            if action < 32 and legal[action]:
                trajectory.append((features.copy(), action))
                if action == 0:
                    break  # Keep all
                game.reroll_dice(action_to_reroll_mask(action))
            else:
                break
        
        # Scoring
        features = extract_features(game.dice, game.score_sheet, 0)
        action = bot.sample_action(game.dice, game.score_sheet, 0, temperature)
        
        # Ensure we pick a valid scoring action
        if action >= 32:
            category = action_to_category(action)
            if game.score_sheet[category] is None:
                trajectory.append((features.copy(), action))
                game.score(category)
                continue
        
        # Fallback: pick best available
        available = [cat for cat in CATEGORIES if game.score_sheet[cat] is None]
        category = available[0]
        action = category_to_action(category)
        trajectory.append((features.copy(), action))
        game.score(category)
    
    return trajectory, calculate_final_score(game)


# =============================================================================
# SELF-PLAY TRAINING
# =============================================================================

def train_self_play(
    num_iterations=20,
    games_per_iteration=500,
    top_percentile=30,
    temperature_start=2.0,
    temperature_end=0.5,
    model_path="yahtzee_ml_model.pkl"
):
    """
    Train using self-play with reward-weighted learning.
    
    Algorithm:
    1. Play many games with current policy (with exploration)
    2. Keep only the top-scoring games
    3. Train on (state, action) pairs from those good games
    4. Repeat with decreasing temperature (less exploration over time)
    """
    
    print("=" * 60)
    print("Yahtzee ML Bot - Self-Play Training")
    print("=" * 60)
    
    bot = MLBot()
    best_mean_score = 0
    
    for iteration in range(num_iterations):
        # Anneal temperature
        progress = iteration / max(num_iterations - 1, 1)
        temperature = temperature_start + progress * (temperature_end - temperature_start)
        
        print(f"\n{'='*60}")
        print(f"Iteration {iteration + 1}/{num_iterations} | Temperature: {temperature:.2f}")
        print(f"{'='*60}")
        
        # Play games
        print(f"Playing {games_per_iteration} games...")
        all_games = []
        
        for g in range(games_per_iteration):
            if (g + 1) % 100 == 0:
                print(f"  Game {g + 1}/{games_per_iteration}")
            trajectory, score = play_game_and_record(bot, temperature)
            all_games.append((trajectory, score))
        
        scores = [s for _, s in all_games]
        print(f"Scores: mean={np.mean(scores):.1f}, std={np.std(scores):.1f}, "
              f"min={np.min(scores)}, max={np.max(scores)}")
        
        # Select top games
        threshold = np.percentile(scores, 100 - top_percentile)
        top_games = [(t, s) for t, s in all_games if s >= threshold]
        print(f"Selected {len(top_games)} games with score >= {threshold:.0f}")
        
        # Build training data
        states = []
        actions = []
        weights = []
        
        top_scores = [s for _, s in top_games]
        min_score = min(top_scores)
        max_score = max(top_scores)
        score_range = max(max_score - min_score, 1)
        
        for trajectory, score in top_games:
            weight = 1.0 + (score - min_score) / score_range
            for features, action in trajectory:
                states.append(features)
                actions.append(action)
                weights.append(weight)
        
        states = np.array(states)
        actions = np.array(actions)
        weights = np.array(weights)
        
        print(f"Training on {len(states)} state-action pairs...")
        
        # Train model
        model = MLPClassifier(
            hidden_layer_sizes=(128, 64),
            activation='relu',
            solver='adam',
            alpha=0.0001,
            batch_size=64,
            learning_rate='adaptive',
            learning_rate_init=0.001,
            max_iter=100,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
            verbose=False,
            random_state=iteration
        )
        
        # Oversample high-weight examples
        indices = np.random.choice(
            len(states), 
            size=len(states), 
            replace=True, 
            p=weights / weights.sum()
        )
        
        model.fit(states[indices], actions[indices])
        bot.model = model
        
        # Evaluate
        print("Evaluating...")
        eval_scores = [play_game_and_record(bot, temperature=0)[1] for _ in range(100)]
        mean_score = np.mean(eval_scores)
        
        print(f"Evaluation: mean={mean_score:.1f}, std={np.std(eval_scores):.1f}")
        
        if mean_score > best_mean_score:
            best_mean_score = mean_score
            bot.save_model(model_path)
            print(f"*** New best! Saved to {model_path} ***")
    
    print(f"\n{'='*60}")
    print(f"Training complete! Best mean score: {best_mean_score:.1f}")
    print(f"{'='*60}")
    
    bot.load_model(model_path)
    return bot