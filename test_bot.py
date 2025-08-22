# test_bot.py - Script para testar o bot expandido

import asyncio
import os
from dotenv import load_dotenv
from src.engine import OpeningEngine

load_dotenv()

async def test_live_monitoring():
    """
    Teste específico para monitoramento ao vivo
    """
    print("🧪 Testando monitoramento ao vivo...")
    
    # Temporariamente forçar MockProvider para testes
    original_provider = os.getenv('ODDS_PROVIDER')
    os.environ['ODDS_PROVIDER'] = 'MOCK'
    
    engine = OpeningEngine()
    
    # Testar busca de odds ao vivo
    if hasattr(engine.provider, 'get_live_odds'):
        live_odds = await engine.provider.get_live_odds()
        print(f"✅ Encontradas {len(live_odds)} partidas ao vivo")
        
        for match in live_odds:
            print(f"  📺 {match['match']} ({match['league']}) - {match['status']}")
            
            # Testar análise de oportunidades
            opportunities = engine.find_value_opportunities(match)
            if opportunities:
                print(f"    💰 {len(opportunities)} oportunidades encontradas")
                for opp_name, details in opportunities.items():
                    edge = details.get('edge', 0)
                    print(f"      • {opp_name}: {edge:+.1f}% edge")
            else:
                print(f"    ⚪ Nenhuma oportunidade de valor")
    
    # Restaurar configuração original
    if original_provider:
        os.environ['ODDS_PROVIDER'] = original_provider
    
    print("✅ Teste concluído!")

async def test_notifications():
    """
    Teste do sistema de notificações
    """
    print("🧪 Testando sistema de notificações...")
    
    from src.notifier import TelegramNotifier
    notifier = TelegramNotifier()
    
    # Teste notificação ao vivo
    await notifier.notify({
        'type': 'LIVE',
        'match': 'T1 vs Gen.G',
        'league': 'LCK Spring',
        'status': 'running',
        'odds': {
            'ML_T1': {
                'current': 2.10,
                'fair': 1.85,
                'edge': 13.5
            },
            'KillsOver28.5_OVER': {
                'current': 1.90,
                'fair': 1.75,
                'edge': 8.6
            }
        }
    })
    
    # Teste notificação de abertura
    await notifier.notify({
        'type': 'OPENING',
        'match': 'BLG vs JDG',
        'odds': {
            'ML': {'BLG': 1.95, 'JDG': 1.85},
            'FirstBlood': {'BLG': 1.90, 'JDG': 1.90}
        }
    })
    
    print("✅ Testes de notificação enviados!")

async def test_pandascore_integration():
    """
    Teste real com PandaScore API (requer token válido)
    """
    if not os.getenv('PANDASCORE_TOKEN'):
        print("⚠️  Pulando teste PandaScore - token não configurado")
        return
        
    print("🧪 Testando integração PandaScore...")
    
    # Forçar PandaScore provider
    os.environ['ODDS_PROVIDER'] = 'PANDASCORE'
    
    from src.providers import PandaScoreProvider
    provider = PandaScoreProvider()
    
    # Testar busca de ligas
    print("📋 Buscando informações das ligas...")
    leagues = await provider.get_leagues_info()
    
    # Testar upcoming matches
    print("🔮 Buscando partidas upcoming...")
    upcoming = await provider.get_upcoming_odds()
    print(f"✅ {len(upcoming)} partidas upcoming encontradas")
    
    # Testar live matches
    print("🔴 Buscando partidas ao vivo...")
    live = await provider.get_live_odds()
    print(f"✅ {len(live)} partidas ao vivo encontradas")
    
    for match in live[:3]:  # Mostrar apenas 3 primeiras
        print(f"  📺 {match['match']} ({match.get('league', 'N/A')})")
        if match.get('odds'):
            print(f"      💰 {len(match['odds'])} mercados disponíveis")

async def run_tests():
    """
    Executar todos os testes
    """
    print("🧪 Iniciando testes do LoL Opening Bot expandido...\n")
    
    await test_live_monitoring()
    print()
    
    await test_notifications()
    print()
    
    await test_pandascore_integration()
    print()
    
    print("🎉 Todos os testes concluídos!")

if __name__ == "__main__":
    asyncio.run(run_tests())