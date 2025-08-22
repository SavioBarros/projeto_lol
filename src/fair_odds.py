import math

class FairOddsEngine:
    def __init__(self):
        pass

    def poisson_prob(self, lam, k):
        return (lam**k * math.exp(-lam)) / math.factorial(k)

    def fair_odds(self, avg_value, line):
        prob_over = 1 - sum(self.poisson_prob(avg_value, k) for k in range(int(line)+1))
        prob_under = 1 - prob_over
        return { "over": 1/prob_over if prob_over > 0 else None,
                 "under": 1/prob_under if prob_under > 0 else None }
