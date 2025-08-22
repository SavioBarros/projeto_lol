import os
import httpx
from typing import Dict, Any

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not self.bot_token or not self.chat_id:
            print("⚠️  AVISO: Token do Telegram ou Chat ID não configurados!")

    async def notify(self, notification_data: Dict[Any, Any]):
        """
        Envia notificação formatada baseada no tipo (OPENING ou LIVE)
        """
        notification_type = notification_data.get('type', 'UNKNOWN')
        
        if notification_type == 'OPENING':
            message = self._format_opening_message(notification_data)
        elif notification_type == 'LIVE':
            message = self._format_live_message(notification_data)
        else:
            message = self._format_basic_message(notification_data)
        
        await self._send_telegram_message(message)

    def _format_live_message(self, data: Dict) -> str:
        """
        Formata mensagem para oportunidades ao vivo
        """
        match_info = data.get('match', 'Partida Desconhecida')
        league = data.get('league', 'Liga Desconhecida')
        status = data.get('status', 'live').upper()
        opportunities = data.get('odds', {})
        
        # Emoji baseado no status
        status_emoji = {
            'RUNNING': '🔴',
            'RECENT': '🟡', 
            'LIVE': '🔴'
        }.get(status, '⚪')
        
        message_parts = [
            f"{status_emoji} *OPORTUNIDADE {status}* {status_emoji}",
            f"",
            f"🏆 *{league}*",
            f"⚔️ *{match_info}*",
            f"",
            "*📊 Valores Identificados:*"
        ]

        if not opportunities:
            message_parts.append("  • Nenhuma oportunidade específica")
        else:
            for market, details in opportunities.items():
                current = details.get('current', 'N/A')
                fair = details.get('fair', 'N/A') 
                edge = details.get('edge', 0)
                
                # Formatação mais limpa do nome do mercado
                market_display = self._format_market_name(market)
                
                message_parts.extend([
                    f"",
                    f"🎯 *{market_display}*",
                    f"  💰 Odd Atual: `{current}`",
                    f"  📈 Odd Justa: `{fair:.2f}` " if isinstance(fair, (int, float)) else f"  📈 Odd Justa: `{fair}`",
                    f"  ⚡ Edge: *{edge:+.1f}%*"
                ])

        message_parts.extend([
            f"",
            f"⏰ Status: {status}",
            f"",
            "💡 *Analise antes de apostar!*"
        ])

        return "\n".join(message_parts)

    def _format_opening_message(self, data: Dict) -> str:
        """
        Formata mensagem para odds de abertura (formato original melhorado)
        """
        match_info = data.get('match', 'Partida Desconhecida')
        odds_dict = data.get('odds', {})

        message_parts = [
            "🆕 *ABERTURA DE MERCADO* 🆕",
            f"",
            f"⚔️ *{match_info}*",
            f"",
            "*💰 Odds Disponíveis:*"
        ]

        if not odds_dict:
            message_parts.append("  • Nenhuma odd encontrada.")
        else:
            for market, value in odds_dict.items():
                market_name = self._format_market_name(market)
                
                if isinstance(value, dict):
                    # Mercados com múltiplas opções (ML, FirstBlood, etc.)
                    message_parts.append(f"")
                    message_parts.append(f"🎯 *{market_name}:*")
                    for option, odd in value.items():
                        message_parts.append(f"  • {option}: `{odd}`")
                else:
                    # Mercados simples
                    message_parts.append(f"  • {market_name}: `{value}`")

        message_parts.extend([
            f"",
            "📋 Tipo: Abertura de Mercado",
            "💡 *Acompanhe a evolução das odds!*"
        ])

        return "\n".join(message_parts)

    def _format_basic_message(self, data: Dict) -> str:
        """
        Formato básico para compatibilidade com código antigo
        """
        match_info = data.get('match', 'Partida Desconhecida') 
        odds_dict = data.get('odds', {})

        message_parts = [
            "🏆 *Oportunidade LoL* 🏆",
            f"",
            f"*Partida:* {match_info}",
            "*Odds:*"
        ]

        if isinstance(odds_dict, dict):
            for market, value in odds_dict.items():
                market_name = self._format_market_name(market)
                message_parts.append(f"  • {market_name}: *{value}*")
        else:
            message_parts.append(f"  • {odds_dict}")

        return "\n".join(message_parts)

    def _format_market_name(self, market: str) -> str:
        """
        Formata nomes de mercados para exibição mais amigável
        """
        # Dicionário de traduções/formatações
        market_translations = {
            'ML': 'Vencedor (Moneyline)',
            'ML_': 'Vencedor - ',
            'FirstBlood': 'Primeiro Sangue',
            'KillsOver': 'Total Kills Acima de ',
            'KillsUnder': 'Total Kills Abaixo de ',
            'NextDragon': 'Próximo Dragão',
            'FirstTower': 'Primeira Torre',
            'FirstBaron': 'Primeiro Baron'
        }
        
        formatted = market
        for key, translation in market_translations.items():
            if key in formatted:
                formatted = formatted.replace(key, translation)
        
        # Limpar underscores e formatação adicional
        formatted = formatted.replace('_', ' ').replace('  ', ' ').strip()
        
        return formatted

    async def _send_telegram_message(self, message: str):
        """
        Envia mensagem para o Telegram
        """
        if not self.bot_token or not self.chat_id:
            print(f"📱 [TELEGRAM SIMULADO]\n{message}\n")
            return

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                print(f"✅ Notificação enviada com sucesso para o Telegram")
                
        except httpx.HTTPStatusError as e:
            print(f"❌ Erro HTTP ao enviar para Telegram: {e}")
            print(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        except Exception as e:
            print(f"❌ Erro inesperado ao enviar para Telegram: {e}")

    # Método para compatibilidade com código antigo
    def send(self, message: str):
        """
        Método síncrono para compatibilidade (deprecated)
        """
        import asyncio
        try:
            # Tentar usar loop existente se disponível
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Se já há um loop rodando, criar task
                asyncio.create_task(self._send_telegram_message(message))
            else:
                # Se não há loop, executar diretamente
                asyncio.run(self._send_telegram_message(message))
        except Exception:
            # Fallback para execução direta
            asyncio.run(self._send_telegram_message(message))

    async def send_status_update(self, status_message: str):
        """
        Envia atualizações de status do bot
        """
        formatted_message = f"🤖 *Status do Bot*\n\n{status_message}"
        await self._send_telegram_message(formatted_message)

    async def send_error_alert(self, error_message: str):
        """
        Envia alertas de erro
        """
        formatted_message = f"🚨 *ERRO NO BOT*\n\n`{error_message}`\n\nVerifique os logs para mais detalhes."
        await self._send_telegram_message(formatted_message)