"""
Optimizers (plugins behind core.interfaces.Optimizer): NSGA-II (nsga2.py), random search
(random_search.py). They see only a Problem (variables, objectives to minimise) and a function that
evaluates a list of design vectors to (objectives, violation); they know nothing about machines.
"""
