from typing import List


def parse_values(raw_input: str) -> List[float]:
    """
    Szöveges input feldolgozása számlistává
    """
    return [float(x.strip()) for x in raw_input.split(",")]


def calculate_mean(values: List[float]) -> float:
    return sum(values) / len(values)


def calculate_min(values: List[float]) -> float:
    return min(values)


def calculate_max(values: List[float]) -> float:
    return max(values)


def normalize(values: List[float]) -> List[float]:
    min_val = calculate_min(values)
    max_val = calculate_max(values)
    return [(v - min_val) / (max_val - min_val) for v in values]


def estimate_slope(values: List[float]) -> float:
    """
    Egyszerű meredekség becslés (utolsó - első)
    """
    return (values[-1] - values[0]) / (len(values) - 1)

