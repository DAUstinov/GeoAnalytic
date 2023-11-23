import re
import math
import string
from collections import Counter
import requests
import pandas as pd

df = pd.read_csv('data/all_data.csv', sep=';')
df = df.astype({'addr:street':'str'})

def autocorrector(df, city, input_string):
    def tokens(text):
        return re.findall(r'[А-яё-]+', text)

    df = df[df['city'] == city]
    input_string = input_string.title()
    TEXT_1 = ' '.join(df['city'])
    TEXT_2 = ' '.join(df['addr:street'])
    TEXT = TEXT_1 + TEXT_2
    TEXT = re.sub('ё', 'е', TEXT)
    WORDS = tokens(TEXT)
    COUNTS = Counter(WORDS)



    alphabet = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя'

    def known(words):
        return {w for w in words if w in COUNTS}

    def splits(word):
        return [(word[:i], word[i:])
                for i in range(len(word)+1)]

    def edits0(word):
        return {word}

    def edits1(word):
        pairs = splits(word)
        deletes = [a+b[1:] for (a, b) in pairs if b]
        transposes = [a+b[1]+b[0]+b[2:] for (a, b) in pairs if len(b) > 1]
        replaces = [a+c+b[1:] for (a, b) in pairs for c in alphabet if b]
        inserts = [a+c+b for (a, b) in pairs for c in alphabet]
        return set(deletes + transposes + replaces + inserts)

    def edits2(word):
        return {e2 for e1 in edits1(word) for e2 in edits1(e1)}

    def correct(word):
        candidates = (known(edits0(word)) or
                      known(edits1(word)) or
                      known(edits2(word)) or
                      [word])
        return max(candidates, key=COUNTS.get)

    return (list(map(correct, tokens(input_string))))


