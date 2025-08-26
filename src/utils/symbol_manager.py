"""
Gerenciador de Símbolos do WDO
Atualiza automaticamente o símbolo baseado no mês/ano atual
"""

from datetime import datetime
import logging

logger = logging.getLogger('SymbolManager')

class SymbolManager:
    """Gerencia a atualização automática de símbolos de contratos futuros"""
    
    # Mapeamento de meses para códigos de vencimento do WDO
    # WDOU25 = contrato de Setembro/2025
    MONTH_CODES = {
        1: 'G',   # Janeiro
        2: 'G',   # Fevereiro (usa vencimento de Fevereiro - G)
        3: 'J',   # Março (usa vencimento de Abril - J)
        4: 'J',   # Abril
        5: 'M',   # Maio (usa vencimento de Junho - M)
        6: 'M',   # Junho
        7: 'N',   # Julho (usa vencimento de Agosto - N)
        8: 'U',   # Agosto (usa vencimento de Setembro - U)
        9: 'U',   # Setembro (U)
        10: 'V',  # Outubro (usa vencimento de Novembro - V)
        11: 'V',  # Novembro
        12: 'Z',  # Dezembro (Z)
    }
    
    # Meses de vencimento reais (contratos vencem nestes meses)
    EXPIRY_MONTHS = {
        'G': 2,   # Fevereiro
        'J': 4,   # Abril
        'M': 6,   # Junho
        'N': 8,   # Agosto
        'U': 9,   # Setembro (WDOU)
        'Q': 10,  # Outubro
        'V': 11,  # Novembro
        'Z': 12,  # Dezembro
    }
    
    @staticmethod
    def get_current_wdo_symbol():
        """
        Retorna o símbolo atual do WDO baseado no mês/ano
        
        Returns:
            str: Símbolo atual (ex: 'WDOU25' para Setembro de 2025)
        """
        now = datetime.now()
        month = now.month
        year = now.year % 100  # Últimos 2 dígitos do ano
        
        # Obter código do mês
        month_code = SymbolManager.MONTH_CODES.get(month, 'U')
        
        # Se estamos após o dia 15 do mês de vencimento, usar próximo vencimento
        # Vencimentos ocorrem em: Fev(G), Abr(J), Jun(M), Ago(N), Set(U), Out(Q), Nov(V), Dez(Z)
        vencimento_months = {2: 'G', 4: 'J', 6: 'M', 8: 'N', 9: 'U', 10: 'Q', 11: 'V', 12: 'Z'}
        
        # Se estamos em um mês de vencimento E após o dia 15, usar próximo vencimento
        if month in vencimento_months and now.day > 15:
            # Definir próximo vencimento
            if month == 2:
                month_code = 'J'  # Abril
            elif month == 4:
                month_code = 'M'  # Junho
            elif month == 6:
                month_code = 'N'  # Agosto
            elif month == 8:
                month_code = 'U'  # Setembro - NÃO mudar pois ainda estamos em Agosto!
            elif month == 9:
                month_code = 'Q'  # Outubro
            elif month == 10:
                month_code = 'V'  # Novembro
            elif month == 11:
                month_code = 'Z'  # Dezembro
            elif month == 12:
                month_code = 'G'  # Fevereiro do próximo ano
                year += 1
        
        symbol = f"WDO{month_code}{year:02d}"
        return symbol
    
    @staticmethod
    def get_next_wdo_symbol():
        """
        Retorna o próximo símbolo do WDO (próximo vencimento)
        
        Returns:
            str: Próximo símbolo (ex: 'WDOV25')
        """
        current = SymbolManager.get_current_wdo_symbol()
        
        # Extrair código do mês atual
        current_code = current[3]
        current_year = int(current[4:6])
        
        # Mapear para próximo vencimento
        next_codes = {
            'G': 'J',  # Fev -> Abr
            'J': 'M',  # Abr -> Jun
            'M': 'N',  # Jun -> Ago
            'N': 'Q',  # Ago -> Out
            'Q': 'V',  # Out -> Dez
            'V': 'G',  # Dez -> Fev (próximo ano)
            'U': 'Q',  # Set -> Out
            'Z': 'G',  # Dez -> Fev (próximo ano)
        }
        
        next_code = next_codes.get(current_code, 'G')
        next_year = current_year
        
        # Se voltou para G (Janeiro/Fevereiro), incrementar ano
        if current_code in ['V', 'Z'] and next_code == 'G':
            next_year += 1
            if next_year > 99:
                next_year = 0
        
        symbol = f"WDO{next_code}{next_year:02d}"
        return symbol
    
    @staticmethod
    def is_near_expiry(days_before=5):
        """
        Verifica se estamos próximos do vencimento do contrato atual
        
        Args:
            days_before: Quantos dias antes do vencimento considerar "próximo"
            
        Returns:
            bool: True se próximo do vencimento
        """
        now = datetime.now()
        current_symbol = SymbolManager.get_current_wdo_symbol()
        month_code = current_symbol[3]
        
        # Obter mês de vencimento
        expiry_month = SymbolManager.EXPIRY_MONTHS.get(month_code, 0)
        
        # WDO vence na segunda sexta-feira do mês de vencimento
        if now.month == expiry_month:
            # Calcular segunda sexta-feira
            first_day = datetime(now.year, now.month, 1)
            first_friday = first_day
            
            # Encontrar primeira sexta-feira
            while first_friday.weekday() != 4:  # 4 = Friday
                first_friday = datetime(now.year, now.month, first_friday.day + 1)
            
            # Segunda sexta-feira é 7 dias depois
            second_friday = datetime(now.year, now.month, first_friday.day + 7)
            
            # Verificar se estamos próximos
            days_to_expiry = (second_friday - now).days
            
            if days_to_expiry <= days_before:
                logger.warning(f"[SYMBOL] Próximo do vencimento! {days_to_expiry} dias restantes")
                return True
        
        return False
    
    @staticmethod
    def should_roll_contract():
        """
        Determina se deve rolar para o próximo contrato
        
        Returns:
            bool: True se deve rolar para próximo vencimento
        """
        # Rolar 3 dias antes do vencimento
        return SymbolManager.is_near_expiry(days_before=3)
    
    @staticmethod
    def get_symbol_info(symbol=None):
        """
        Retorna informações detalhadas sobre um símbolo
        
        Args:
            symbol: Símbolo para analisar (None = símbolo atual)
            
        Returns:
            dict: Informações do símbolo
        """
        if not symbol:
            symbol = SymbolManager.get_current_wdo_symbol()
        
        if not symbol.startswith('WDO') or len(symbol) != 6:
            return None
        
        month_code = symbol[3]
        year = int(symbol[4:6])
        
        # Determinar ano completo
        current_year = datetime.now().year
        current_century = (current_year // 100) * 100
        full_year = current_century + year
        
        # Se o ano parece estar no passado, assumir próximo século
        if full_year < current_year - 1:
            full_year += 100
        
        expiry_month = SymbolManager.EXPIRY_MONTHS.get(month_code, 0)
        
        return {
            'symbol': symbol,
            'asset': 'WDO',
            'month_code': month_code,
            'year': full_year,
            'expiry_month': expiry_month,
            'expiry_month_name': datetime(2000, expiry_month, 1).strftime('%B') if expiry_month else 'Unknown',
            'is_current': symbol == SymbolManager.get_current_wdo_symbol(),
            'is_next': symbol == SymbolManager.get_next_wdo_symbol(),
            'near_expiry': SymbolManager.is_near_expiry() if symbol == SymbolManager.get_current_wdo_symbol() else False
        }


def update_symbol_if_needed(current_symbol):
    """
    Verifica e atualiza o símbolo se necessário
    
    Args:
        current_symbol: Símbolo atualmente em uso
        
    Returns:
        tuple: (novo_símbolo, mudou)
    """
    correct_symbol = SymbolManager.get_current_wdo_symbol()
    
    if current_symbol != correct_symbol:
        logger.warning(f"[SYMBOL] Símbolo desatualizado! Atual: {current_symbol} -> Correto: {correct_symbol}")
        
        # Se deve rolar contrato
        if SymbolManager.should_roll_contract():
            next_symbol = SymbolManager.get_next_wdo_symbol()
            logger.warning(f"[SYMBOL] Próximo do vencimento! Considere rolar para: {next_symbol}")
        
        return correct_symbol, True
    
    # Verificar se próximo do vencimento mesmo com símbolo correto
    if SymbolManager.is_near_expiry():
        next_symbol = SymbolManager.get_next_wdo_symbol()
        logger.info(f"[SYMBOL] Alerta: Próximo do vencimento. Próximo contrato: {next_symbol}")
    
    return current_symbol, False


# Teste rápido ao importar
if __name__ == "__main__":
    print("=== Symbol Manager Test ===")
    current = SymbolManager.get_current_wdo_symbol()
    next_sym = SymbolManager.get_next_wdo_symbol()
    info = SymbolManager.get_symbol_info()
    
    print(f"Símbolo Atual: {current}")
    print(f"Próximo Símbolo: {next_sym}")
    print(f"Informações: {info}")
    print(f"Próximo do vencimento? {SymbolManager.is_near_expiry()}")
    print(f"Deve rolar contrato? {SymbolManager.should_roll_contract()}")