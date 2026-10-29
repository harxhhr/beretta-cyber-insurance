"""Behavioural UML figures, gathered from the b_*.py modules."""
import importlib

FIGURES = []
for _name in ("b_usecase", "b_state", "b_sequence", "b_activity", "b_dfd", "b_timing"):
    try:
        FIGURES += importlib.import_module(_name).FIGURES
    except ModuleNotFoundError as exc:
        if exc.name != _name:
            raise
