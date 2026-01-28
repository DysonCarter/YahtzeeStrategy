def calculate_score(dice, category):
    """
    Pure scoring function. Returns the score for the given dice and category.
    dice: list or tuple of 5 ints
    category: string
    """
    numeric_scores = {
        "aces": 1, "twos": 2, "threes": 3, 
        "fours": 4, "fives": 5, "sixes": 6,
    }
    
    if category in numeric_scores:
        n = numeric_scores[category]
        return sum(d for d in dice if d == n)
    
    s = sum(dice)
    uniq = set(dice)
    
    if category == "threekind":
        return s if any(dice.count(d) >= 3 for d in uniq) else 0
    
    if category == "fourkind":
        return s if any(dice.count(d) >= 4 for d in uniq) else 0
    
    if category == "fullhouse":
        counts = sorted(dice.count(d) for d in uniq)
        if counts == [2, 3] or len(uniq) == 1:
            return 25
        return 0
    
    if category == "smstraight":
        if any(seq.issubset(uniq) for seq in ({1,2,3,4}, {2,3,4,5}, {3,4,5,6})) or len(uniq) == 1:
            return 30
        return 0
    
    if category == "lgstraight":
        if uniq in ({1,2,3,4,5}, {2,3,4,5,6}) or len(uniq) == 1:
            return 40
        return 0
    
    if category == "yahtzee":
        return 50 if len(uniq) == 1 else 0
    
    if category == "chance":
        return s
    
    raise ValueError(f"Unknown category: {category}")