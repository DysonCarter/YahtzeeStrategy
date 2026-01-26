import random

numeric_scores = {
    "aces" :   1,
    "twos" :   2,
    "threes" : 3,
    "fours" :  4,
    "fives" :  5,
    "sixes" :  6,
}

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

    # Helper to score any choice from top section (1-6)
    def score_top(self, choice):

        if choice not in numeric_scores:
            raise ValueError(f"{choice} not valid option")
        
        if self.score_sheet[choice] is not None:
            raise ValueError(f"{choice} already scored")

        numeric_choice = numeric_scores[choice]
        score = 0
        for d in self.dice:
            if d == numeric_choice:
                score += numeric_choice

        self.score_sheet[choice] = score
        return score
    
    # Mark any choice on scoresheet
    def score(self, choice):
        if choice not in self.score_sheet:
            raise ValueError(f"{choice} not valid option")
        
        if self.score_sheet[choice] is not None:
            raise ValueError(f"{choice} already scored")
        
        if choice in numeric_scores:
            return self.score_top(choice)
        
        if choice == "threekind":
            if not any(self.dice.count(d) >= 3 for d in set(self.dice)):
                self.score_sheet[choice] = 0
                return 0
            
            all_dice = sum(self.dice)
            
            self.score_sheet[choice] = all_dice
            return all_dice
        
        if choice == "fourkind":
            if not any(self.dice.count(d) >= 4 for d in set(self.dice)):
                self.score_sheet[choice] = 0
                return 0
            
            all_dice = sum(self.dice)
            
            self.score_sheet[choice] = all_dice
            return all_dice
        
        if choice == "fullhouse":
            if sorted(self.dice.count(d) for d in set(self.dice)) != [2, 3] or len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 25
            return 25
        
        if choice == "smstraight":
            if not any(seq.issubset(set(self.dice)) for seq in ({1,2,3,4}, {2,3,4,5}, {3,4,5,6})) or len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 30
            return 30
        
        if choice == "lgstraight":
            if set(self.dice) not in ({1,2,3,4,5}, {2,3,4,5,6}) or len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 40
            return 40
        
        if choice == "yahtzee":
            if len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 50
            return 50
            
        if choice == "chance":
            all_dice = sum(self.dice)
            
            self.score_sheet[choice] = all_dice
            return all_dice

        raise ValueError(f"Unhandled category: {choice}")
