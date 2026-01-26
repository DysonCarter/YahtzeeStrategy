import random

def roll_die():
    return random.randint(1, 6)

# Solo game
class YahtzeeGame:
    def __init__(self):
        self.dice = [0,0,0,0,0,0]

        self.score_sheet = {
            "aces":       0,
            "twos":       0,
            "threes":     0,
            "fours":      0,
            "fives":      0,
            "sixes":      0,
            "threekind":  0,
            "fourkind":   0,
            "fullhouse":  0,
            "smstraight": 0,
            "lgstraight": 0,
            "yahtzee":    0,
            "chance":     0,
        }

        # For Yahtzee Bonus
        self.yahtzee_count = 0