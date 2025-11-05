import statistics
import numpy as np

def calculate_stats(temperatures: list[float]) -> dict:
    if not temperatures:
        return {
            'mean': 0.0,
            'min': 0.0,
            'max': 0.0,
            'std': 0.0,
            'count': 0
        }
    
    return {
        'mean': statistics.mean(temperatures),
        'min': min(temperatures),
        'max': max(temperatures),
        'std': statistics.stdev(temperatures) if len(temperatures) > 1 else 0.0,
        'count': len(temperatures)
    }

def calculate_trend_slope(times: list[float], temperatures: list[float], n: int) -> float:
    if len(temperatures) < 2 or n < 2:
        return 0.0
    # Take last min(n, len) values
    num = min(n, len(temperatures))
    t = times[-num:]
    temp = temperatures[-num:]
    # Linear regression slope
    if len(t) > 1:
        slope = np.polyfit(t, temp, 1)[0]
        return slope
    return 0.0