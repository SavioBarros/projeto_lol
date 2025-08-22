import os
import asyncio
from src.providers import MockProvider, PandaScoreProvider
from src.fair_odds import FairOddsEngine
from src.notifier import TelegramNotifier

class OpeningEngine:
    def __init__(self):
        self.provider = (MockProvider() if os.getenv("ODDS_PROVIDER") == "MOCK"
                          else PandaScoreProvider())
        self.fair = FairOddsEngine()
        self.notifier = TelegramNotifier()
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
        self.live_poll_interval = int(os.getenv("LIVE_POLL_INTERVAL_SECONDS", 30))
        self.edge_threshold = float(os.getenv("EDGE_THRESHOLD", 0.05))
        
        # Ligas para monitorar (configurável via .env)
        leagues = os.getenv("MONITORED_LEAGUES", "lck,lpl,lec,lcs")
        self.monitored_leagues = [l.strip().lower() for l in leagues.split(",")]
        
        # Cache para evitar notificações duplicadas
        self.notified_opportunities = set()

    async def run(self):
        """Executa ambos os monitores: abertura e tempo real"""
        await asyncio.gather(
            self.monitor_opening_odds(),
            self.monitor_live_odds()
        )

    async def monitor_opening_odds(self):
        """Monitor original para odds de abertura"""
        while True:
            try:
                print("🔍 Verificando odds de abertura...")
                odds = await self.provider.get_upcoming_odds()
                
                for match_data in odds:
                    # Aplicar lógica de fair odds aqui se necessário
                    opportunities = self.analyze_opportunities(match_data)
                    
                    if opportunities:
                        await self.notifier.notify({
                            'match': match_data['match'],
                            'odds': opportunities,
                            'type': 'OPENING'
                        })
                        
            except Exception as e:
                print(f"❌ Erro no monitor de abertura: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def monitor_live_odds(self):
        """Novo monitor para odds em tempo real"""
        while True:
            try:
                print("🔴 Verificando odds ao vivo...")
                
                # Buscar partidas running + recent (ainda com odds ativas)
                live_matches = await self.provider.get_live_odds()
                
                for match_data in live_matches:
                    opportunities = self.find_value_opportunities(match_data)
                    
                    if opportunities:
                        # Criar ID único para evitar spam
                        opportunity_id = f"{match_data['match']}_{hash(str(opportunities))}"
                        
                        if opportunity_id not in self.notified_opportunities:
                            await self.notifier.notify({
                                'match': match_data['match'],
                                'odds': opportunities,
                                'type': 'LIVE',
                                'league': match_data.get('league', 'Unknown'),
                                'status': match_data.get('status', 'live')
                            })
                            
                            self.notified_opportunities.add(opportunity_id)
                            
                            # Limpar cache antigo (manter apenas últimas 100)
                            if len(self.notified_opportunities) > 100:
                                self.notified_opportunities = set(list(self.notified_opportunities)[-50:])
                                
            except Exception as e:
                print(f"❌ Erro no monitor ao vivo: {e}")
                
            await asyncio.sleep(self.live_poll_interval)

    def find_value_opportunities(self, match_data):
        """
        Encontra oportunidades de valor comparando odds do mercado vs fair odds
        """
        opportunities = {}
        market_odds = match_data.get('odds', {})
        
        # Para cada mercado disponível
        for market_name, odds_info in market_odds.items():
            
            if market_name == 'ML' and isinstance(odds_info, dict):
                # Moneyline - comparar com histórico dos times
                fair_ml = self.calculate_fair_moneyline(match_data)
                if fair_ml:
                    for team, current_odd in odds_info.items():
                        fair_odd = fair_ml.get(team)
                        if fair_odd and self.has_edge(current_odd, fair_odd):
                            opportunities[f"ML_{team}"] = {
                                'current': current_odd,
                                'fair': fair_odd,
                                'edge': self.calculate_edge(current_odd, fair_odd)
                            }
            
            elif 'kills' in market_name.lower():
                # Mercados de kills - usar modelo Poisson
                line = self.extract_line_from_market(market_name)
                if line:
                    avg_kills = self.estimate_avg_kills(match_data)
                    fair_odds = self.fair.fair_odds(avg_kills, line)
                    
                    if fair_odds['over'] and self.has_edge(odds_info, fair_odds['over']):
                        opportunities[f"{market_name}_OVER"] = {
                            'current': odds_info,
                            'fair': fair_odds['over'],
                            'edge': self.calculate_edge(odds_info, fair_odds['over'])
                        }
        
        return opportunities

    def calculate_fair_moneyline(self, match_data):
        """
        Calcula odds justas para moneyline baseado em dados históricos
        (Implementação simplificada - você pode melhorar com dados do Oracle)
        """
        teams = self.extract_teams(match_data['match'])
        if len(teams) != 2:
            return None
            
        # Por enquanto, usar probabilidade baseada na liga
        # Você pode melhorar isso integrando com dados do Oracle's Elixir
        league = match_data.get('league', '').lower()
        
        # Probabilidades estimadas (você pode refinar isso)
        base_prob = 0.5  # 50/50 por padrão
        
        # Ajustar baseado na liga (times mais fortes em certas ligas)
        if league in ['lck', 'lpl']:
            # Ligas mais competitivas - menos previsíveis
            base_prob = 0.52
        elif league in ['lec', 'lcs']:
            base_prob = 0.48
            
        return {
            teams[0]: 1 / base_prob,
            teams[1]: 1 / (1 - base_prob)
        }

    def estimate_avg_kills(self, match_data):
        """
        Estima média de kills baseado na liga e times
        (Implementação simplificada)
        """
        league = match_data.get('league', '').lower()
        
        # Médias por liga (você pode refinar com dados reais)
        league_averages = {
            'lck': 28.5,
            'lpl': 32.0,
            'lec': 26.5,
            'lcs': 25.0,
            'worlds': 30.0
        }
        
        return league_averages.get(league, 27.0)  # Default global

    def extract_line_from_market(self, market_name):
        """Extrai a linha numérica do nome do mercado"""
        import re
        match = re.search(r'(\d+\.?\d*)', market_name)
        return float(match.group(1)) if match else None

    def extract_teams(self, match_string):
        """Extrai nomes dos times da string da partida"""
        return [team.strip() for team in match_string.split(' vs ')]

    def has_edge(self, market_odd, fair_odd):
        """Verifica se há edge suficiente"""
        if not market_odd or not fair_odd:
            return False
        return (market_odd - fair_odd) / fair_odd > self.edge_threshold

    def calculate_edge(self, market_odd, fair_odd):
        """Calcula a porcentagem de edge"""
        return round(((market_odd - fair_odd) / fair_odd) * 100, 2)

    def analyze_opportunities(self, match_data):
        """Análise básica para odds de abertura (compatibilidade com código atual)"""
        return match_data.get('odds', {})