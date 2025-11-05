import statistics

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