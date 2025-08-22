import os
import httpx
import asyncio
from typing import List, Dict

class MockProvider:
    def get_odds_for_matches(self):
        """Método original para compatibilidade"""
        return self.get_upcoming_odds()
    
    async def get_upcoming_odds(self):
        """
        Retorna dados de teste para jogos upcoming
        """
        print("🧪 Usando MockProvider para odds de abertura...")
        await asyncio.sleep(0.1)  # Simular latência
        return [
            {
                'match': 'T1 vs Gen.G',
                'league': 'LCK',
                'status': 'upcoming',
                'odds': {
                    'ML': {'T1': 1.85, 'Gen.G': 1.95},
                    'KillsOver28.5': 2.0,
                    'FirstBlood': {'T1': 1.90, 'Gen.G': 1.90}
                }
            }
        ]
    
    async def get_live_odds(self):
        """
        Retorna dados de teste para jogos ao vivo
        """
        print("🔴 Usando MockProvider para odds ao vivo...")
        await asyncio.sleep(0.1)
        return [
            {
                'match': 'BLG vs JDG',
                'league': 'LPL',
                'status': 'running',
                'odds': {
                    'ML': {'BLG': 2.10, 'JDG': 1.75},
                    'KillsOver30.5': 1.90,
                    'NextDragon': {'BLG': 1.80, 'JDG': 2.00}
                }
            },
            {
                'match': 'G2 vs FNC',
                'league': 'LEC',
                'status': 'running', 
                'odds': {
                    'ML': {'G2': 1.65, 'FNC': 2.25},
                    'KillsOver25.5': 1.85
                }
            }
        ]

class PandaScoreProvider:
    def __init__(self):
        self.api_token = os.getenv("PANDASCORE_TOKEN")
        self.base_url = os.getenv("PANDASCORE_BASE")
        self.game = os.getenv("PANDASCORE_GAME", "lol")
        
        # Configurar ligas monitoradas
        leagues = os.getenv("MONITORED_LEAGUES", "lck,lpl,lec,lcs")
        self.monitored_leagues = [l.strip().lower() for l in leagues.split(",")]

    def get_odds_for_matches(self):
        """Método original para compatibilidade - agora usa async internamente"""
        return asyncio.run(self.get_upcoming_odds())

    async def get_upcoming_odds(self):
        """
        Busca odds para partidas upcoming (futuras)
        """
        return await self._fetch_matches_by_status("upcoming")

    async def get_live_odds(self):
        """
        Busca odds para partidas running (ao vivo) e recent (recém-finalizadas)
        """
        live_matches = await self._fetch_matches_by_status("running")
        recent_matches = await self._fetch_matches_by_status("recent")
        
        # Combinar e filtrar apenas partidas com odds ativas
        all_matches = live_matches + recent_matches
        return [match for match in all_matches if match.get('odds')]

    async def _fetch_matches_by_status(self, status: str) -> List[Dict]:
        """
        Busca partidas por status específico
        """
        url = f"{self.base_url}/{self.game}/matches/{status}"
        
        # Parâmetros básicos
        params = {
            "sort": "begin_at",
            "per_page": 25,  # Reduzir para evitar timeouts
            "token": self.api_token
        }
        
        # Adicionar filtro de ligas apenas se especificado e não vazio
        if self.monitored_leagues:
            # PandaScore usa formato específico para filtros
            leagues_filter = ",".join(self.monitored_leagues)
            params["filter[league_slug]"] = leagues_filter
        
        print(f"🔍 Buscando partidas {status} em: {url}")
        print(f"📋 Parâmetros: {params}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                # Log detalhado para debugging
                print(f"📡 Status: {response.status_code}")
                print(f"🔗 URL Final: {response.url}")
                
                if response.status_code == 400:
                    print(f"❌ Erro 400 - Parâmetros inválidos")
                    print(f"Response: {response.text[:500]}")
                    return []
                elif response.status_code == 403:
                    print(f"❌ Erro 403 - Token inválido ou sem permissão")
                    print(f"Token usado: {self.api_token[:10] if self.api_token else 'NENHUM'}...")
                    return []
                elif response.status_code == 404:
                    print(f"⚠️  Endpoint não encontrado para status '{status}'")
                    return []
                
                response.raise_for_status()
                matches = response.json()
                
                print(f"✅ Encontradas {len(matches)} partidas {status}")
                return self._format_matches(matches, status)
                
        except httpx.HTTPStatusError as e:
            print(f"❌ Erro HTTP ao buscar partidas {status}: {e}")
            print(f"Response: {e.response.text[:500] if hasattr(e, 'response') else 'N/A'}")
            return []
        except httpx.TimeoutException:
            print(f"⏰ Timeout ao buscar partidas {status}")
            return []
        except Exception as e:
            print(f"❌ Erro inesperado ao buscar partidas {status}: {e}")
            return []

    def _format_matches(self, matches: List[Dict], status: str) -> List[Dict]:
        """
        Formata dados das partidas para o formato padrão do bot
        """
        formatted_matches = []
        
        for match in matches:
            # Extrair informações básicas
            if not match.get('opponents') or len(match['opponents']) < 2:
                continue
                
            team1_data = match['opponents'][0].get('opponent', {})
            team2_data = match['opponents'][1].get('opponent', {})
            
            team1 = team1_data.get('name', 'Time A')
            team2 = team2_data.get('name', 'Time B')
            
            # Informações da liga
            league_info = match.get('league', {})
            league_name = league_info.get('name', 'Unknown League')
            league_slug = league_info.get('slug', '').lower()
            
            # Pular se não for liga monitorada
            if self.monitored_leagues and league_slug not in self.monitored_leagues:
                continue
            
            # Extrair odds se disponíveis
            odds_data = self._extract_odds(match.get('odds', []))
            
            # Só adicionar se tiver odds ou se for status upcoming
            if odds_data or status == "upcoming":
                formatted_match = {
                    'match': f"{team1} vs {team2}",
                    'league': league_name,
                    'league_slug': league_slug,
                    'status': status,
                    'begin_at': match.get('begin_at'),
                    'odds': odds_data
                }
                
                formatted_matches.append(formatted_match)
        
        return formatted_matches

    def _extract_odds(self, odds_list: List[Dict]) -> Dict:
        """
        Extrai e organiza as odds dos diferentes mercados
        """
        odds_data = {}
        
        for odd in odds_list:
            market_name = odd.get('market_name', '').lower()
            results = odd.get('results', [])
            
            if not results:
                continue
            
            # Moneyline (Winner 2-way)
            if 'winner' in market_name and '2-way' in market_name:
                if len(results) >= 2:
                    # Assumir que results[0] é team1 e results[1] é team2
                    odds_data['ML'] = {
                        'team1': results[0].get('odds'),
                        'team2': results[1].get('odds')
                    }
            
            # First Blood
            elif 'first blood' in market_name:
                if len(results) >= 2:
                    odds_data['FirstBlood'] = {
                        'team1': results[0].get('odds'),
                        'team2': results[1].get('odds')
                    }
            
            # Mercados de Kills (Over/Under)
            elif 'kills' in market_name or 'kill' in market_name:
                # Extrair linha se possível
                import re
                line_match = re.search(r'(\d+\.?\d*)', market_name)
                if line_match:
                    line = line_match.group(1)
                    market_key = f"Kills{market_name.replace(' ', '').title()}"
                    
                    if len(results) >= 2:
                        # Geralmente Over é primeiro, Under segundo
                        odds_data[market_key] = {
                            'over': results[0].get('odds'),
                            'under': results[1].get('odds')
                        }
            
            # Outros mercados específicos do LoL
            elif any(keyword in market_name for keyword in ['tower', 'dragon', 'baron', 'inhibitor']):
                market_key = market_name.replace(' ', '').replace('-', '').title()
                if len(results) >= 2:
                    odds_data[market_key] = {
                        'team1': results[0].get('odds'),
                        'team2': results[1].get('odds')
                    }
                elif len(results) == 1:
                    odds_data[market_key] = results[0].get('odds')
        
        return odds_data

    async def get_leagues_info(self):
        """
        Busca informações das ligas disponíveis (útil para debugging)
        """
        url = f"{self.base_url}/{self.game}/leagues"
        params = {"token": self.api_token, "per_page": 100}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                leagues = response.json()
                
                print("🏆 Ligas disponíveis:")
                for league in leagues[:10]:  # Mostrar apenas primeiras 10
                    print(f"  - {league.get('name')} (slug: {league.get('slug')})")
                
                return leagues
        except Exception as e:
            print(f"❌ Erro ao buscar ligas: {e}")
            return []