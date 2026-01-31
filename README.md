# Yahtzee Strategy Comparison

This repository explores **optimal decision-making in Yahtzee** using three different approaches:

* **Dynamic Programming (DP)** — full game-theoretic planning
* **Greedy Search** — optimal play within a single turn
* **Machine Learning (ML)** — policy learning via self-play

---

## Overview

Yahtzee is a stochastic, sequential decision problem with:

* Hidden future outcomes (dice rolls)
* Long-term dependencies (upper bonus, multiple Yahtzee bonus)
* Large branching factors

This repo implements and compares three agents that solve the problem at different levels of foresight.

---

## Bots

### 1. DynamicProgrammingBot (`dynamic_programming.py`)

**Gold standard / oracle agent**

* Performs full expected-value optimization over:

  * reroll decisions
  * category selection
  * remaining game state
* Correctly models:

  * Upper section bonus
  * Yahtzee bonus (+100)
  * Joker rules (forced upper / lower logic)
* Computationally expensive

  * To play a full game will take extremely long
  * You can run this when there are less categories available

Perfectly Optimized - Maximized Expected Value

---

### 2. GreedyBot (`greedy.py`)

**Strong baseline**

* Computes exact expected value **within a single turn**
* Optimizes rerolls + final category choice for the current turn only
* Does **not** reason about future turns or category scarcity

Very strong, but some small flaws (e.g. greedy will never sacrifice a small category for the chance at a huge future turn)
---

### 3. MLBot (`ml.py`)

**Learned policy via self-play**

* Uses an `MLPClassifier` trained on state–action pairs
* Input features include:

  * Dice statistics
  * Scoresheet availability
  * Upper-section progress
  * Strategic indicators (straights, sets, etc.)
* Actions:

  * 32 reroll masks
  * 13 scoring actions
* Trained using **reward-weighted self-play**
* Falls back to random policy if no model is loaded

The ML agent is a generalist and currently underperforms DP and Greedy in late-game precision.

---

## Joker Rule & Scoring

The implementation follows **official Yahtzee rules**:

* First Yahtzee scores **50**
* Subsequent Yahtzees score **+100 bonus** if the Yahtzee category was filled with 50
* Joker rules:

  * If the corresponding upper category is open → **must score there**
  * Otherwise → must score in the lower section if possible
  * Full house / straights score their fixed values under Joker

All bots are aligned to the same scoring logic via `utils.calculate_score`.

---

## Experiments

### Late-Game Comparison (Notebook)

The main comparison notebook evaluates bots on:

* **100 random game states**
* **≤5 categories remaining** (for the sake of speed)
* Identical dice sequences across bots

Metrics:

* Final total score after playing out the remaining game
* Distribution shown via boxplots

**Observed ordering:**

```
Dynamic Programming > Greedy >> ML
```

This clean separation highlights the difference between:

* Planning (DP)
* Local optimization (Greedy)
* Pattern learning (ML)

---

## Repository Structure

```
.
├── dynamic_programming.py   # Full-game DP agent
├── greedy.py                # Turn-level EV agent
├── ml.py                    # ML agent + training code
├── yahtzee_game.py          # Game state & rules
├── utils.py                 # Scoring logic
├── comparison.ipynb         # Analysis & plots
├── yahtzee_ml_model.pkl     # Trained ML model (optional)
└── README.md
```

---

## Usage

### Load and compare bots

```python
from greedy import GreedyBot
from dynamic_programming import DynamicProgrammingBot
from ml import MLBot

greedy = GreedyBot()
dp = DynamicProgrammingBot()
ml = MLBot(model_path="yahtzee_ml_model.pkl") # Train using train_self_play()
```

### Run experiments

Use the provided notebook or create custom evaluation scripts by:

* Sampling small game states
* Playing out remaining turns
* Comparing final scores

---

## Key Takeaways

* **DP** is optimal but expensive — best used as a benchmark
* **Greedy** is fast and nearly optimal in short horizons
* **ML** not ideal

The project demonstrates how **planning depth directly translates to score**, especially under constrained decision spaces.
