class Card:
    def __init__(self, rank, suit):
        self.suit = suit
        self.rank = rank
        self.hard, self.soft = self._points()

class NumberCard( Card ):
    def _points(self):
        return int(self.rank), int(self.rank)
    
class AceCard( Card ):
    def _points(self):
        return 1, 11

nc=NumberCard(11,12)
print(nc)