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
    #   Getters
    #_______________________________________

    # Get Potential Scores
    # -1 for invalid choices
    def get_score_top(self, choice):

        if choice not in numeric_scores:
            return -1
        
        if self.score_sheet[choice] is not None:
            return -1

        numeric_choice = numeric_scores[choice]
        score = 0
        for d in self.dice:
            if d == numeric_choice:
                score += numeric_choice

        return score
    
    def get_score(self, choice):
        if choice not in self.score_sheet:
            raise ValueError(f"{choice} not valid option")
        
        if self.score_sheet[choice] is not None:
            return -1
        
        if choice in numeric_scores:
            return self.score_top(choice)
        
        if choice == "threekind":
            if not any(self.dice.count(d) >= 3 for d in set(self.dice)):
                return 0
            
            all_dice = sum(self.dice)
            return all_dice
        
        if choice == "fourkind":
            if not any(self.dice.count(d) >= 4 for d in set(self.dice)):
                return 0
            
            all_dice = sum(self.dice)
            return all_dice
        
        if choice == "fullhouse":
            if sorted(self.dice.count(d) for d in set(self.dice)) != [2, 3] and len(set(self.dice)) != 1:
                return 0
            
            return 25
        
        if choice == "smstraight":
            if not any(seq.issubset(set(self.dice)) for seq in ({1,2,3,4}, {2,3,4,5}, {3,4,5,6})) and len(set(self.dice)) != 1:
                return 0
            
            return 30
        
        if choice == "lgstraight":
            if set(self.dice) not in ({1,2,3,4,5}, {2,3,4,5,6}) and len(set(self.dice)) != 1:
                return 0
            
            return 40
        
        if choice == "yahtzee":
            if len(set(self.dice)) != 1:
                return 0
            
            return 50
            
        if choice == "chance":
            all_dice = sum(self.dice)
            
            return all_dice

        raise ValueError(f"Unhandled category: {choice}")
    
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

    # Helper to score any choice from top section (1-6)
    # Marks scoresheet
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
            if sorted(self.dice.count(d) for d in set(self.dice)) != [2, 3] and len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 25
            return 25
        
        if choice == "smstraight":
            if not any(seq.issubset(set(self.dice)) for seq in ({1,2,3,4}, {2,3,4,5}, {3,4,5,6})) and len(set(self.dice)) != 1:
                self.score_sheet[choice] = 0
                return 0
            
            self.score_sheet[choice] = 30
            return 30
        
        if choice == "lgstraight":
            if set(self.dice) not in ({1,2,3,4,5}, {2,3,4,5,6}) and len(set(self.dice)) != 1:
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
    
    #---------------------------------------
    #   Menu
    #_______________________________________

    def solo_menu(self):
        print("--- Welcome to Solo Yahtzee ---")
        
        # A standard game has 13 rounds to fill the 13 categories
        for turn in range(1, 14):
            print(f"\nTurn {turn} of 13")
            self.roll_dice()
            
            # Up to 2 rerolls allowed (3 rolls total)
            for r in range(2):
                print(f"Current Dice: {self.dice}")
                print("Enter die positions to REROLL (1-5) separated by commas (e.g., 1,2,5), or 'k' to keep:")
                user_input = input("> ").strip().lower()
                
                if user_input == 'k':
                    break
                
                # Convert user input (1-5) into the [1,0,0,1,0] mask your function expects
                mask = [0, 0, 0, 0, 0]
                try:
                    # Subtract 1 because users think 1-5, but indices are 0-4
                    indices = [int(i.strip()) - 1 for i in user_input.split(',')]
                    for idx in indices:
                        if 0 <= idx < 5:
                            mask[idx] = 1
                    self.reroll_dice(mask)
                except ValueError:
                    print("Invalid input. Keeping current dice.")
                    break

            print(f"Final Dice for this turn: {self.dice}")
            
            # Show available scoring options
            available = [cat for cat, val in self.score_sheet.items() if val is None]
            print(f"Available Categories: {', '.join(available)}")
            
            while True:
                choice = input("Select category to score: ").strip().lower()
                try:
                    # Handle Yahtzee Bonus logic before scoring
                    # (If it's a Yahtzee and the slot is already filled with 50)
                    if len(set(self.dice)) == 1 and self.score_sheet["yahtzee"] == 50:
                        self.yahtzee_count += 1
                        print("Yahtzee Bonus! +100 points added.")

                    points = self.score(choice)
                    print(f"Scored {points} points in {choice}!")
                    break
                except ValueError as e:
                    print(f"Error: {e}. Please try again.")

        # Final Scoring Calculation
        upper_score = sum(self.score_sheet[cat] for cat in numeric_scores)
        upper_bonus = 35 if upper_score >= 63 else 0
        lower_score = sum(val for cat, val in self.score_sheet.items() if cat not in numeric_scores)
        bonus_points = self.yahtzee_count * 100
        
        total = upper_score + upper_bonus + lower_score + bonus_points

        print("\n" + "="*20)
        print("      GAME OVER      ")
        print("="*20)
        print(f"Upper Section: {upper_score}")
        if upper_bonus: print(f"Upper Bonus:   {upper_bonus}")
        print(f"Lower Section: {lower_score}")
        if bonus_points: print(f"Yahtzee Bonus: {bonus_points}")
        print("-" * 20)
        print(f"TOTAL SCORE:   {total}")
        print("="*20)

Yahtzee = YahtzeeGame()
Yahtzee.solo_menu()