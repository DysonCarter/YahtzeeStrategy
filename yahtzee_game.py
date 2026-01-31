import random
from utils import calculate_score

numeric_scores = {
    "aces" :   1,
    "twos" :   2,
    "threes" : 3,
    "fours" :  4,
    "fives" :  5,
    "sixes" :  6,
}

upper_by_face = {1: "aces", 2: "twos", 3: "threes", 4: "fours", 5: "fives", 6: "sixes"}

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
        self.dice.sort()

    # Mask len 5 of which dice to reroll
    # dice_mask = [1,0,0,1,0] -> reroll die 0 and die 3
    def reroll_dice(self, dice_mask):
        for i, reroll in enumerate(dice_mask):
            if reroll:
                self.dice[i] = self.roll_die()
        self.dice.sort()

    #---------------------------------------
    #   Helpers
    #_______________________________________

    def _is_yahtzee(self):
        return len(set(self.dice)) == 1

    # Get Potential Scores
    # -1 for invalid choices
    def get_score(self, choice):
        if choice not in self.score_sheet:
            raise ValueError(f"{choice} not valid option")
        if self.score_sheet[choice] is not None:
            raise ValueError(f"{choice} already scored")

        apply_joker = self._is_yahtzee() and (self.score_sheet["yahtzee"] == 50)

        if apply_joker:
            face = self.dice[0]
            forced_upper = upper_by_face[face]
            upper_open = (self.score_sheet[forced_upper] is None)

            lower_open_exists = any(
                self.score_sheet[c] is None
                for c in ("threekind", "fourkind", "fullhouse", "smstraight", "lgstraight", "yahtzee", "chance")
            )

            if upper_open and choice != forced_upper:
                raise ValueError(f"{choice} not valid option")

            if (not upper_open) and lower_open_exists and (choice in numeric_scores):
                raise ValueError(f"{choice} not valid option")

            if not upper_open:
                if choice == "fullhouse":
                    return 25
                if choice == "smstraight":
                    return 30
                if choice == "lgstraight":
                    return 40

        return calculate_score(self.dice, choice)
    
    # Gets the total score so far of aces through sixes
    # For bonus strategy calculation
    def get_top_total(self):
        total = 0
        for cat in numeric_scores:
            if self.score_sheet[cat] is not None:
                total += self.score_sheet[cat]
        return total
    
    #---------------------------------------
    #   Scoring
    #_______________________________________
    
    # Mark any choice on scoresheet
    def score(self, choice):
        bonus_awarded = self._is_yahtzee() and (self.score_sheet["yahtzee"] == 50)

        points = self.get_score(choice)
        self.score_sheet[choice] = points

        if bonus_awarded:
            self.yahtzee_count += 1

        return points
