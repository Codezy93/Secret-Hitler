ITER = 0

PROB_MAP = {
        "FFF":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "FFL":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "FLF":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "LFF":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "FLL":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "LFL":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "LLF":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0},
        "LLL":{"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0}
    }
INIT_PROBABILITES = {"FFF":0, "FFL":0, "FLF":0, "LFF": 0, "FLL":0, "LFL":0, "LLF":0, "LLL":0}
PERMUTATIONS = ["FFF", "FFL", "FLF", "LFF", "FLL", "LFL", "LLF", "LLL"]
curr_sum = 1000000

class Node:
    def __init__(self, liberal_cards, fascist_cards, draw):
        self.liberal_cards = liberal_cards
        self.fascist_cards = fascist_cards
        self.draw = draw
        self.probability = 1
        self.calculate_probability()
        self.children = {
            "FFF":0,
            "FFL":0,
            "FLF":0,
            "LFF":0,
            "FLL":0,
            "LFL":0,
            "LLF":0,
            "LLL":0
            }
        if self.probability != 0:
            for i in self.children:
                self.children[i] = Node(self.liberal_cards, self.fascist_cards, i)
    
    def calculate_probability(self):
        total = self.liberal_cards + self.fascist_cards
        for c in self.draw:
            if c == "F":
                self.probability *= self.fascist_cards/total
                self.fascist_cards -= 1
            else:
                self.probability *= self.liberal_cards/total
                self.liberal_cards -= 1
            total -= 1

probability_tree = Node(6, 11, "FFF")