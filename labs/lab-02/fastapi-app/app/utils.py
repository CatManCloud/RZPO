def calculate(expression: str):
    # УЯЗВИМОСТЬ (Bandit B307): eval на пользовательском вводе -> RCE
    return eval(expression)
