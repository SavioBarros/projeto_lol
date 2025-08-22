import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from src.engine import OpeningEngine

# Carregar variáveis do arquivo .env
load_dotenv()

def setup_logging():
    """Configurar sistema de logging"""
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configurar handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configurar handler para arquivo (se especificado)
    handlers = [console_handler]
    log_file = os.getenv('LOG_FILE')
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=log_level,
        handlers=handlers
    )

def validate_config():
    """Validar configurações críticas"""
    errors = []
    warnings = []
    
    # Verificar provedor de odds
    provider = os.getenv('ODDS_PROVIDER')
    if provider == 'PANDASCORE':
        token = os.getenv('PANDASCORE_TOKEN')
        if not token:
            errors.append("PANDASCORE_TOKEN não configurado")
        elif len(token) < 20:
            warnings.append("Token PandaScore parece inválido (muito curto)")
    
    # Verificar Telegram
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
    
    if not telegram_token:
        warnings.append("TELEGRAM_BOT_TOKEN não configurado - modo simulação ativo")
    if not telegram_chat:
        warnings.append("TELEGRAM_CHAT_ID não configurado - modo simulação ativo")
    
    # Verificar configurações numéricas
    try:
        edge_threshold = float(os.getenv('EDGE_THRESHOLD', '0.05'))
        if edge_threshold <= 0 or edge_threshold >= 1:
            warnings.append("EDGE_THRESHOLD deve estar entre 0 e 1")
    except ValueError:
        errors.append("EDGE_THRESHOLD deve ser um número válido")
    
    try:
        poll_interval = int(os.getenv('POLL_INTERVAL_SECONDS', '60'))
        if poll_interval < 10:
            warnings.append("POLL_INTERVAL_SECONDS muito baixo - pode causar rate limiting")
    except ValueError:
        errors.append("POLL_INTERVAL_SECONDS deve ser um número inteiro")
    
    # Verificar diretório Oracle
    oracle_dir = os.getenv('ORACLE_DATA_DIR', './oracle_csvs')
    if not os.path.exists(oracle_dir):
        try:
            os.makedirs(oracle_dir, exist_ok=True)
            warnings.append(f"Diretório {oracle_dir} criado automaticamente")
        except Exception as e:
            errors.append(f"Não foi possível criar diretório Oracle: {e}")
    
    return errors, warnings

def print_banner():
    """Imprimir banner do bot"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    🚀 LoL Opening Bot v2.0                   ║
║              Monitoramento Inteligente de Odds               ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def print_config():
    """Imprimir configurações do bot"""
    config_info = f"""
📊 CONFIGURAÇÕES ATIVAS:
{'='*60}
📡 Provedor: {os.getenv('ODDS_PROVIDER', 'MOCK')}
🏆 Ligas: {os.getenv('MONITORED_LEAGUES', 'Todas')}
📈 Mercados: {os.getenv('MARKET_TYPES', 'Padrão')}
⚡ Edge mínimo: {float(os.getenv('EDGE_THRESHOLD', '0.05'))*100:.1f}%
⏰ Intervalo abertura: {os.getenv('POLL_INTERVAL_SECONDS', '60')}s
🔴 Intervalo ao vivo: {os.getenv('LIVE_POLL_INTERVAL_SECONDS', '30')}s
📅 Lookahead: {os.getenv('OPENING_LOOKAHEAD_DAYS', '14')} dias
🔔 Max notificações/partida: {os.getenv('MAX_NOTIFICATIONS_PER_MATCH', '3')}
⏳ Cooldown notificações: {os.getenv('NOTIFICATION_COOLDOWN_MINUTES', '10')}min
"""
    print(config_info)

async def main():
    """
    Ponto de entrada principal do bot
    """
    print_banner()
    
    # Configurar logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Validar configurações
    logger.info("Validando configurações...")
    errors, warnings = validate_config()
    
    # Tratar erros críticos
    if errors:
        logger.error("❌ ERROS CRÍTICOS ENCONTRADOS:")
        for error in errors:
            logger.error(f"  • {error}")
        logger.error("Bot não pode continuar. Corrija os erros acima.")
        return 1
    
    # Mostrar warnings
    if warnings:
        logger.warning("⚠️  AVISOS:")
        for warning in warnings:
            logger.warning(f"  • {warning}")
        
        # Aguardar confirmação se há muitos warnings
        if len(warnings) > 2:
            try:
                response = input("\nContinuar mesmo assim? (s/N): ")
                if response.lower() not in ['s', 'sim', 'y', 'yes']:
                    print("Execução cancelada pelo usuário.")
                    return 0
            except KeyboardInterrupt:
                print("\nExecução cancelada pelo usuário.")
                return 0
    
    print_config()
    
    # Verificar token PandaScore
    if os.getenv('ODDS_PROVIDER') == 'PANDASCORE':
        token = os.getenv('PANDASCORE_TOKEN')
        if token:
            logger.info(f"✅ Token PandaScore: {token[:8]}...{token[-4:]}")
        else:
            logger.warning("⚠️  Token PandaScore não encontrado!")
    
    # Verificar Telegram
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
    
    if telegram_token and telegram_chat:
        logger.info("✅ Telegram configurado")
    else:
        logger.warning("⚠️  Telegram não configurado - usando modo simulação")
    
    print("\n" + "="*60)
    print("🤖 Bot iniciado! Pressione Ctrl+C para parar")
    print(f"🕒 Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    try:
        # Inicializar e executar o engine
        logger.info("Inicializando engine...")
        engine = OpeningEngine()
        
        # Executar engine com tratamento de exceções
        await engine.run()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot interrompido pelo usuário")
        return 0
    except Exception as e:
        logger.error(f"\n❌ Erro crítico: {e}")
        logger.exception("Detalhes do erro:")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        print("\n🛑 Execução interrompida")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Erro fatal: {e}")
        sys.exit(1)