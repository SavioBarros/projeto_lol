#!/usr/bin/env python3
"""
Script para testar as correções do LoL Opening Bot
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

async def test_mock_provider():
    """Teste com MockProvider"""
    print("🧪 TESTANDO MOCK PROVIDER")
    print("=" * 50)
    
    # Forçar MockProvider
    original_provider = os.environ.get('ODDS_PROVIDER')
    os.environ['ODDS_PROVIDER'] = 'MOCK'
    
    try:
        from src.providers import create_provider
        provider = create_provider()
        
        # Testar upcoming odds
        print("📮 Testando upcoming odds...")
        upcoming = await provider.get_upcoming_odds()
        print(f"✅ {len(upcoming)} partidas upcoming encontradas")
        
        for match in upcoming:
            print(f"  ⚔️ {match['match']} ({match['league']})")
            odds = match.get('odds', {})
            print(f"    💰 {len(odds)} mercados disponíveis")
        
        # Testar live odds
        print("\n🔴 Testando live odds...")
        live = await provider.get_live_odds()
        print(f"✅ {len(live)} partidas ao vivo encontradas")
        
        for match in live:
            print(f"  📺 {match['match']} ({match['league']})")
        
        print("\n✅ MockProvider funcionando corretamente!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no MockProvider: {e}")
        return False
    finally:
        # Restaurar configuração original
        if original_provider:
            os.environ['ODDS_PROVIDER'] = original_provider
        elif 'ODDS_PROVIDER' in os.environ:
            del os.environ['ODDS_PROVIDER']

async def test_pandascore_provider():
    """Teste com PandaScoreProvider"""
    print("\n🏆 TESTANDO PANDASCORE PROVIDER")
    print("=" * 50)
    
    token = os.getenv('PANDASCORE_TOKEN')
    if not token:
        print("⚠️ PANDASCORE_TOKEN não configurado - pulando teste")
        return False
    
    print(f"🔑 Token: {token[:8]}...{token[-4:]}")
    
    # Forçar PandaScoreProvider
    os.environ['ODDS_PROVIDER'] = 'PANDASCORE'
    
    try:
        from src.providers import create_provider
        provider = create_provider()
        
        # Teste de conexão
        print("🔌 Testando conexão...")
        success, message = await provider.test_connection()
        print(f"{'✅' if success else '❌'} {message}")
        
        if not success:
            return False
        
        # Validar acesso à API
        print("🔍 Validando acesso à API...")
        valid = await provider.validate_api_access()
        print(f"{'✅' if valid else '❌'} Validação: {'OK' if valid else 'FALHOU'}")
        
        if not valid:
            return False
        
        # Testar busca de partidas upcoming
        print("📮 Testando upcoming matches...")
        upcoming = await provider.get_upcoming_odds()
        print(f"✅ {len(upcoming)} partidas upcoming encontradas")
        
        for match in upcoming[:3]:  # Mostrar apenas 3
            print(f"  ⚔️ {match['match']} ({match.get('league', 'N/A')})")
            odds = match.get('odds', {})
            if odds:
                print(f"    💰 {len(odds)} mercados: {list(odds.keys())}")
        
        # Testar busca de partidas ao vivo
        print("\n🔴 Testando live matches...")
        live = await provider.get_live_odds()
        print(f"✅ {len(live)} partidas ao vivo encontradas")
        
        for match in live[:2]:  # Mostrar apenas 2
            print(f"  📺 {match['match']} ({match.get('league', 'N/A')})")
            odds = match.get('odds', {})
            if odds:
                print(f"    💰 {len(odds)} mercados: {list(odds.keys())}")
        
        print("\n✅ PandaScoreProvider funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no PandaScoreProvider: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_engine_integration():
    """Teste da integração com o engine"""
    print("\n🤖 TESTANDO INTEGRAÇÃO COM ENGINE")
    print("=" * 50)
    
    try:
        from src.engine import OpeningEngine
        
        engine = OpeningEngine()
        print(f"✅ Engine inicializado com provider: {engine.provider.name}")
        
        # Testar análise de oportunidades (com dados mock)
        sample_match = {
            'match': 'T1 vs Gen.G',
            'league': 'LCK',
            'odds': {
                'ML': {'T1': 1.85, 'Gen.G': 2.10}
            }
        }
        
        opportunities = engine.find_value_opportunities(sample_match)
        print(f"🎯 Oportunidades encontradas: {len(opportunities)}")
        
        for name, details in opportunities.items():
            print(f"  💎 {name}: {details}")
        
        print("✅ Engine funcionando corretamente!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no Engine: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_notifier():
    """Teste do sistema de notificações"""
    print("\n📱 TESTANDO SISTEMA DE NOTIFICAÇÕES")
    print("=" * 50)
    
    try:
        from src.notifier import TelegramNotifier
        
        notifier = TelegramNotifier()
        
        # Teste notificação de abertura
        await notifier.notify({
            'type': 'OPENING',
            'match': 'T1 vs Gen.G',
            'odds': {
                'ML': {'T1': 1.85, 'Gen.G': 2.10},
                'FirstBlood': {'T1': 1.90, 'Gen.G': 1.90}
            }
        })
        print("✅ Notificação de abertura enviada")
        
        # Teste notificação ao vivo
        await notifier.notify({
            'type': 'LIVE',
            'match': 'BLG vs JDG',
            'league': 'LPL',
            'status': 'running',
            'odds': {
                'ML_BLG': {
                    'current': 2.10,
                    'fair': 1.85,
                    'edge': 13.5
                }
            }
        })
        print("✅ Notificação ao vivo enviada")
        
        print("✅ Sistema de notificações OK!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no Notifier: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_config_status():
    """Mostra status da configuração"""
    print("⚙️ CONFIGURAÇÃO ATUAL")
    print("=" * 50)
    
    config_items = [
        ("ODDS_PROVIDER", os.getenv('ODDS_PROVIDER', 'MOCK')),
        ("PANDASCORE_TOKEN", f"{os.getenv('PANDASCORE_TOKEN', 'NÃO CONFIGURADO')[:8]}..." if os.getenv('PANDASCORE_TOKEN') else 'NÃO CONFIGURADO'),
        ("MONITORED_LEAGUES", os.getenv('MONITORED_LEAGUES', 'TODAS')),
        ("TELEGRAM_BOT_TOKEN", "CONFIGURADO" if os.getenv('TELEGRAM_BOT_TOKEN') else "NÃO CONFIGURADO"),
        ("TELEGRAM_CHAT_ID", "CONFIGURADO" if os.getenv('TELEGRAM_CHAT_ID') else "NÃO CONFIGURADO"),
        ("EDGE_THRESHOLD", f"{float(os.getenv('EDGE_THRESHOLD', '0.05')) * 100:.1f}%"),
        ("POLL_INTERVAL_SECONDS", f"{os.getenv('POLL_INTERVAL_SECONDS', '60')}s"),
    ]
    
    for key, value in config_items:
        print(f"  {key}: {value}")

async def main():
    """Função principal de teste"""
    print("🚀 INICIANDO TESTES DAS CORREÇÕES")
    print("=" * 60)
    
    print_config_status()
    
    results = []
    
    # Teste MockProvider (sempre deve funcionar)
    results.append(await test_mock_provider())
    
    # Teste PandaScore (se configurado)
    if os.getenv('PANDASCORE_TOKEN'):
        results.append(await test_pandascore_provider())
    else:
        print("\n⏭️ Pulando teste PandaScore (token não configurado)")
        results.append(True)  # Não contar como falha
    
    # Teste Engine
    results.append(await test_engine_integration())
    
    # Teste Notifier
    results.append(await test_notifier())
    
    # Resultado final
    print("\n" + "=" * 60)
    success_count = sum(results)
    total_tests = len(results)
    
    if success_count == total_tests:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Bot está funcionando corretamente")
    else:
        print(f"⚠️ {success_count}/{total_tests} TESTES PASSARAM")
        print("❌ Há problemas que precisam ser corrigidos")
    
    print(f"\n💡 Próximos passos:")
    if os.getenv('ODDS_PROVIDER') == 'MOCK' or not os.getenv('PANDASCORE_TOKEN'):
        print("  1. Configure PANDASCORE_TOKEN no .env")
        print("  2. Configure ODDS_PROVIDER=PANDASCORE no .env")
    print("  3. Execute: python main.py")
    print("  4. Monitore os logs para identificar outros problemas")

if __name__ == "__main__":
    # Adicionar diretório src ao Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n💥 Erro fatal no teste: {e}")
        import traceback
        traceback.print_exc()
