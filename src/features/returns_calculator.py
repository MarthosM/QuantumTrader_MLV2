"""
Correção para cálculo de returns com dados reais
"""

def calculate_returns_from_prices(prices, periods=[1, 5, 10, 20]):
    """
    Calcula returns a partir de lista de preços
    
    Args:
        prices: Lista ou array de preços
        periods: Períodos para calcular returns
        
    Returns:
        Dict com returns calculados
    """
    import numpy as np
    
    returns = {}
    prices = np.array(prices)
    
    for period in periods:
        key = f"returns_{period}"
        if len(prices) > period:
            # Calcular retorno percentual
            current = prices[-1]
            past = prices[-(period+1)]
            if past > 0:
                returns[key] = (current - past) / past
            else:
                returns[key] = 0.0
        else:
            returns[key] = 0.0
    
    return returns

def calculate_volatility_from_returns(returns_series, periods=[10, 20, 50]):
    """
    Calcula volatilidade a partir de série de returns
    
    Args:
        returns_series: Série de returns
        periods: Períodos para calcular volatilidade
        
    Returns:
        Dict com volatilidades calculadas
    """
    import numpy as np
    
    volatilities = {}
    returns_series = np.array(returns_series)
    
    for period in periods:
        key = f"volatility_{period}"
        if len(returns_series) >= period:
            # Calcular desvio padrão dos últimos N returns
            recent_returns = returns_series[-period:]
            volatilities[key] = np.std(recent_returns)
        else:
            volatilities[key] = 0.0
    
    return volatilities
