import random
from difflib import SequenceMatcher

from dataclasses import dataclass

def json_encoder(obj):
    if hasattr(obj, 'as_json'):
        return obj.as_json().copy()
    else:
        return obj.__dict__.copy()

def unique_id():
    alpha = ['a', 'b', 'c',
             'd', 'e', 'f',
             'A', 'B', 'C',
             'D', 'E', 'F',
             'AA', 'AB', 'AC',
             'BA', 'BB', 'BC',
             'CA', 'CB', 'CC',]
    return str(f'{random.choice(alpha)}{random.randint(100, 999)}')

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

@dataclass
class HighlightedMoment:
    position: str = ''
    decibel: float = 0.0
    
    def as_json(self):
        return {
            'position': self.position,
            'decibel': float(self.decibel)
        }