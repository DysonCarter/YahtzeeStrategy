import random

# Solo game
class YahtzeeGame:
    def __init__(self):
        self.dice = [0,0,0,0,0]
        self.reroll_count = 0

        self.score_sheet = {
            "aces":       None,
            "twos":       None,
            "threes":     None,
            "fours":      None,
            "fives":      None,
            "sixes":      None,
            "threekind":  None,
            "fourkind":   None,
            "fullhouse":  None,
            "smstraight": None,
            "lgstraight": None,
            "yahtzee":    None,
            "chance":     None,
        }

        # For Yahtzee Bonus
        self.yahtzee_count = 0

    #---------------------------------------
    #   Controls
    #_______________________________________

    def roll_die(self):
        return random.randint(1, 6)
    
    def roll_dice(self):
        for i in range(len(self.dice)):
            self.dice[i] = self.roll_die()

    # Mask len 5 of which dice to reroll
    # dice_mask = [1,0,0,1,0] -> reroll die 0 and die 3
    def reroll_dice(self, dice_mask):
        for i, reroll in enumerate(dice_mask):
            if reroll:
                self.dice[i] = self.roll_die()

    #---------------------------------------
    #   Scoring
    #_______________________________________
    