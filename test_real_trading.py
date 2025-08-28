#!/usr/bin/env python3
"""
Teste do Trading Real com OCO Orders
Verifica se o sistema está enviando ordens reais ao mercado
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent))

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_real_trading():
    """Testa envio de ordem real"""
    
    print("\n" + "="*60)
    print("TESTE DE TRADING REAL - OCO Orders")
    print("="*60)
    
    # Verificar se trading está habilitado
    enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
    
    if not enable_trading:
        print("\n⚠️  ATENÇÃO: Trading NÃO está habilitado!")
        print("Para ativar trading real, edite .env.production:")
        print("  ENABLE_TRADING=true")
        print("\nAbortando teste...")
        return False
    
    print("\n✅ Trading habilitado em .env.production")
    print("⚠️  AVISO: Este teste ENVIARÁ uma ordem REAL ao mercado!")
    
    response = input("\nDeseja continuar? (sim/não): ").lower()
    if response not in ['sim', 's', 'yes', 'y']:
        print("Teste cancelado.")
        return False
    
    # Importar connection manager
    from src.connection_manager_working import ConnectionManagerWorking
    
    print("\nConectando ao ProfitDLL...")
    conn = ConnectionManagerWorking()
    
    if not conn.connect():
        print("❌ Erro ao conectar!")
        return False
    
    print("✅ Conectado com sucesso")
    
    # Subscrever ao símbolo
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    print(f"\nSubscrevendo ao símbolo {symbol}...")
    conn.subscribe_symbol(symbol)
    
    # Aguardar dados
    print("Aguardando dados de mercado...")
    for i in range(10):
        prices = conn.get_current_prices()
        if prices['bid'] > 0 and prices['ask'] > 0:
            print(f"✅ Dados recebidos - Bid: R$ {prices['bid']:.2f}, Ask: R$ {prices['ask']:.2f}")
            break
        time.sleep(1)
    else:
        print("❌ Timeout aguardando dados de mercado")
        return False
    
    # Preparar ordem de teste
    print("\n" + "="*60)
    print("CONFIGURAÇÃO DA ORDEM DE TESTE")
    print("="*60)
    
    # Usar valores conservadores para teste
    current_price = prices['mid']
    stop_loss = current_price - 50  # Stop 50 pontos abaixo
    take_profit = current_price + 100  # Take 100 pontos acima
    
    print(f"Símbolo: {symbol}")
    print(f"Lado: BUY (Compra)")
    print(f"Quantidade: 1 contrato")
    print(f"Entrada: A MERCADO")
    print(f"Stop Loss: R$ {stop_loss:.2f}")
    print(f"Take Profit: R$ {take_profit:.2f}")
    
    print("\n⚠️  ÚLTIMA CONFIRMAÇÃO")
    print("Esta ordem será REALMENTE enviada ao mercado!")
    
    response = input("\nConfirmar envio? (sim/não): ").lower()
    if response not in ['sim', 's', 'yes', 'y']:
        print("Ordem cancelada.")
        return False
    
    # Enviar ordem
    print("\n🚀 Enviando ordem...")
    result = conn.send_order_with_bracket(
        symbol=symbol,
        side="BUY",
        quantity=1,
        entry_price=0,  # Mercado
        stop_price=stop_loss,
        take_price=take_profit
    )
    
    if result and 'main_order' in result:
        print("\n" + "="*60)
        print("✅ ORDEM ENVIADA COM SUCESSO!")
        print("="*60)
        print(f"Order ID Principal: {result.get('main_order')}")
        print(f"Stop Loss ID: {result.get('stop_order')}")
        print(f"Take Profit ID: {result.get('take_order')}")
        print("="*60)
        
        # Aguardar 5 segundos
        print("\nAguardando 5 segundos antes de cancelar...")
        time.sleep(5)
        
        # Oferecer cancelamento
        response = input("\nDeseja CANCELAR as ordens? (sim/não): ").lower()
        if response in ['sim', 's', 'yes', 'y']:
            print("Cancelando ordens...")
            if conn.cancel_bracket_orders(result['main_order']):
                print("✅ Ordens canceladas com sucesso")
            else:
                print("⚠️  Falha ao cancelar algumas ordens")
    else:
        print("\n❌ Falha ao enviar ordem")
        print(f"Resultado: {result}")
        return False
    
    # Desconectar
    conn.disconnect()
    print("\nTeste concluído!")
    return True

if __name__ == "__main__":
    try:
        test_real_trading()
    except KeyboardInterrupt:
        print("\n\nTeste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()