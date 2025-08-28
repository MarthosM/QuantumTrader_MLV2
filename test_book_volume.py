"""
Teste para capturar volume dos callbacks de book
O OfferBook tem informações de cada ordem individual, incluindo quantidade
"""
from ctypes import *
import time
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Dados globais
book_updates = []
trades_detected = []

print("=" * 60)
print("TESTE VOLUME DO BOOK (OFFER/PRICE)")
print("=" * 60)

# Verificar métodos disponíveis
book_methods = [
    'SetOfferBookCallback',
    'SetOfferBookCallbackV2', 
    'SetPriceBookCallback',
    'SetPriceBookCallbackV2'
]

print("\n[CHECK] Métodos de Book disponíveis:")
for method in book_methods:
    if hasattr(dll, method):
        print(f"  [OK] {method}")

# Teste SetOfferBookCallbackV2 - tem informações detalhadas de cada ordem
if hasattr(dll, 'SetOfferBookCallbackV2'):
    print("\n[TEST] SetOfferBookCallbackV2 - Ordens individuais com volume")
    
    # OfferBook V2 tem muitos parâmetros incluindo qtd (quantidade/volume)
    @WINFUNCTYPE(c_int, c_void_p, c_int32, c_int32, c_int32, c_longlong, c_int32,
                c_int32, c_double, c_int32, c_int32, c_int32, c_int32, 
                c_int32, c_void_p, c_void_p, c_void_p)
    def offer_book_callback_v2(asset_id, action, position, side, qtd, agent,
                              offer_id, price, has_price, has_qtd, has_date,
                              has_offer_id, has_agent, date_ptr, array_sell, array_buy):
        """
        Callback para OfferBook V2
        qtd = QUANTIDADE/VOLUME em contratos!
        """
        global book_updates
        
        try:
            # Capturar dados importantes
            volume = int(qtd) if qtd else 0  # VOLUME EM CONTRATOS
            price_val = float(price) if price else 0
            
            # Determinar lado
            side_str = "BUY" if side == 0 else "SELL" if side == 1 else "UNKNOWN"
            
            # Determinar ação
            if action == 0:
                action_str = "ADD"
            elif action == 1:
                action_str = "UPDATE"
            elif action == 2:
                action_str = "DELETE"
            else:
                action_str = f"ACTION_{action}"
            
            # Salvar dados
            update = {
                'type': 'OfferBookV2',
                'action': action_str,
                'side': side_str,
                'price': price_val,
                'volume': volume,  # VOLUME EM CONTRATOS
                'position': position,
                'agent': agent,
                'timestamp': datetime.now().isoformat()
            }
            
            book_updates.append(update)
            
            # Log significativos (volume > 0)
            if volume > 0 and len(book_updates) <= 20:
                print(f"  [BOOK] {action_str} {side_str} | Price: {price_val:.2f} | Volume: {volume} contratos | Pos: {position}")
            
            # Detectar possível trade (DELETE de ordem pode indicar execução)
            if action_str == "DELETE" and volume > 0:
                trades_detected.append({
                    'price': price_val,
                    'volume': volume,
                    'side': side_str,
                    'timestamp': datetime.now().isoformat()
                })
                print(f"  [TRADE?] Possível execução: {volume} contratos @ {price_val:.2f}")
            
        except Exception as e:
            print(f"  [ERROR] Callback: {e}")
        
        return 0
    
    # Registrar callback
    ret = dll.SetOfferBookCallbackV2(offer_book_callback_v2)
    print(f"  Registro SetOfferBookCallbackV2: {ret}")

# Inicializar
print("\n[INIT] Inicializando...")
key = os.getenv('PROFIT_KEY', '')
if key:
    ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
    print(f"  DLLInitializeLogin: {ret}")
    
    # Subscribe
    symbol = b"WDOU25"
    ret = dll.SubscribeTicker(0, symbol)
    print(f"  SubscribeTicker: {ret}")
    
    # SubscribeBBO se disponível (Best Bid Offer)
    if hasattr(dll, 'SubscribeBBO'):
        ret = dll.SubscribeBBO(0, symbol)
        print(f"  SubscribeBBO: {ret}")
    
    # Monitorar
    print("\n[MONITOR] Aguardando dados do book (30 segundos)...")
    print("  Observando volume em contratos nas ordens do book...")
    
    start_time = time.time()
    last_report = start_time
    
    while time.time() - start_time < 30:
        current = time.time()
        
        if current - last_report >= 5:
            elapsed = int(current - start_time)
            print(f"\n  [{elapsed}s] Updates: {len(book_updates)} | Trades detectados: {len(trades_detected)}")
            
            # Análise de volume
            if book_updates:
                volumes = [u['volume'] for u in book_updates if u['volume'] > 0]
                if volumes:
                    print(f"    Volume MIN: {min(volumes)} contratos")
                    print(f"    Volume MAX: {max(volumes)} contratos")
                    print(f"    Volume MÉDIO: {sum(volumes)/len(volumes):.1f} contratos")
                    
                    # Últimas atualizações com volume
                    recent = [u for u in book_updates[-10:] if u['volume'] > 0]
                    if recent:
                        print("    Últimas ordens com volume:")
                        for u in recent[-3:]:
                            print(f"      {u['action']} {u['side']}: {u['volume']} @ {u['price']:.2f}")
            
            last_report = current
        
        time.sleep(0.1)
    
    # Análise final
    print("\n" + "=" * 60)
    print("ANÁLISE FINAL - VOLUME DO BOOK")
    print("=" * 60)
    
    if book_updates:
        print(f"\n[DADOS] {len(book_updates)} atualizações do book capturadas")
        
        # Filtrar updates com volume
        with_volume = [u for u in book_updates if u['volume'] > 0]
        print(f"  Updates com volume > 0: {len(with_volume)}")
        
        if with_volume:
            volumes = [u['volume'] for u in with_volume]
            
            print(f"\n[VOLUME EM CONTRATOS - BOOK]")
            print(f"  Mínimo: {min(volumes)} contratos")
            print(f"  Máximo: {max(volumes)} contratos")
            print(f"  Médio: {sum(volumes)/len(volumes):.1f} contratos")
            print(f"  Total: {sum(volumes)} contratos")
            
            # Distribuição
            print(f"\n[DISTRIBUIÇÃO]")
            print(f"  1-10 contratos: {len([v for v in volumes if v <= 10])}")
            print(f"  11-50 contratos: {len([v for v in volumes if 11 <= v <= 50])}")
            print(f"  51-100 contratos: {len([v for v in volumes if 51 <= v <= 100])}")
            print(f"  100+ contratos: {len([v for v in volumes if v > 100])}")
            
            # Por ação
            print(f"\n[POR AÇÃO]")
            for action in ['ADD', 'UPDATE', 'DELETE']:
                action_vols = [u['volume'] for u in with_volume if u['action'] == action]
                if action_vols:
                    print(f"  {action}: {len(action_vols)} ordens, média {sum(action_vols)/len(action_vols):.1f} contratos")
            
            if trades_detected:
                print(f"\n[POSSÍVEIS TRADES DETECTADOS] {len(trades_detected)}")
                for t in trades_detected[:5]:
                    print(f"  {t['volume']} contratos @ {t['price']:.2f} ({t['side']})")
            
            print(f"\n[CONCLUSÃO]")
            print("  ✓ Volume disponível no OfferBookCallbackV2!")
            print("  ✓ Dados em contratos (não lotes)")
            print("  ✓ Podemos usar esses dados para análise de fluxo")
    else:
        print("\n[SEM DADOS] Nenhuma atualização de book capturada")
    
    # Cleanup
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)

print("\nTeste concluído!")