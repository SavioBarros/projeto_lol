import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import httpx
from dataclasses import dataclass

# Configurar logger
logger = logging.getLogger(__name__)

@dataclass
class MatchData:
    """Classe para estruturar dados de partida"""
    match_id: str
    team1: str
    team2: str
    league: str
    league_slug: str
    status: str
    begin_at: Optional[str]
    odds: Dict
    tournament: Optional[str] = None
    
    @property
    def match_name(self) -> str:
        return f"{self.team1} vs {self.team2}"

class RateLimiter:
    """Classe para controlar rate limiting"""
    
    def __init__(self, max_requests: int = 30, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    async def acquire(self):
        """Aguarda até que seja seguro fazer uma nova requisição"""
        now = datetime.now()
        
        # Remove requisições antigas
        self.requests = [req_time for req_time in self.requests 
                        if (now - req_time).seconds < self.time_window]
        
        # Se atingiu o limite, aguarda
        if len(self.requests) >= self.max_requests:
            wait_time = self.time_window - (now - self.requests[0]).seconds + 1
            if wait_time > 0:
                logger.info(f"⏳ Rate limit atingido, aguardando {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        self.requests.append(now)

class MockProvider:
    """Provider simulado para testes e desenvolvimento"""
    
    def __init__(self):
        logger.info("🧪 Inicializando MockProvider")
        self.name = "MOCK"
        
    def get_odds_for_matches(self):
        """Método original para compatibilidade"""
        return asyncio.run(self.get_upcoming_odds())
    
    async def get_upcoming_odds(self) -> List[Dict]:
        """Retorna dados simulados para jogos upcoming"""
        logger.info("🧪 Gerando odds simuladas para partidas upcoming...")
        await asyncio.sleep(0.2)  # Simular latência de API
        
        # Dados mais realistas com variação
        import random
        
        matches = [
            {
                'match_id': 'mock_001',
                'match': 'T1 vs Gen.G',
                'league': 'LCK Spring',
                'league_slug': 'lck',
                'status': 'upcoming',
                'begin_at': (datetime.now() + timedelta(hours=2)).isoformat(),
                'odds': {
                    'ML': {
                        'T1': round(random.uniform(1.70, 2.20), 2),
                        'Gen.G': round(random.uniform(1.70, 2.20), 2)
                    },
                    'FirstBlood': {
                        'T1': round(random.uniform(1.85, 2.05), 2),
                        'Gen.G': round(random.uniform(1.85, 2.05), 2)
                    },
                    'KillsOver28.5': {
                        'over': round(random.uniform(1.80, 2.10), 2),
                        'under': round(random.uniform(1.80, 2.10), 2)
                    }
                }
            },
            {
                'match_id': 'mock_002',
                'match': 'JDG vs BLG',
                'league': 'LPL Spring',
                'league_slug': 'lpl',
                'status': 'upcoming',
                'begin_at': (datetime.now() + timedelta(hours=4)).isoformat(),
                'odds': {
                    'ML': {
                        'JDG': round(random.uniform(1.60, 1.90), 2),
                        'BLG': round(random.uniform(2.00, 2.40), 2)
                    },
                    'FirstTower': {
                        'JDG': round(random.uniform(1.75, 2.00), 2),
                        'BLG': round(random.uniform(1.90, 2.15), 2)
                    }
                }
            }
        ]
        
        return matches
    
    async def get_live_odds(self) -> List[Dict]:
        """Retorna dados simulados para jogos ao vivo"""
        logger.info("🔴 Gerando odds simuladas para partidas ao vivo...")
        await asyncio.sleep(0.1)
        
        import random
        
        if random.random() < 0.7:  # 70% chance de ter partidas ao vivo
            return [
                {
                    'match_id': 'mock_live_001',
                    'match': 'G2 vs FNC',
                    'league': 'LEC Spring',
                    'league_slug': 'lec',
                    'status': 'running',
                    'begin_at': (datetime.now() - timedelta(minutes=25)).isoformat(),
                    'odds': {
                        'ML': {
                            'G2': round(random.uniform(1.50, 2.50), 2),
                            'FNC': round(random.uniform(1.50, 2.50), 2)
                        },
                        'NextDragon': {
                            'G2': round(random.uniform(1.70, 2.30), 2),
                            'FNC': round(random.uniform(1.70, 2.30), 2)
                        }
                    }
                }
            ]
        
        return []

class PandaScoreProvider:
    """Provider para PandaScore API com funcionalidades avançadas"""
    
    def __init__(self):
        self.api_token = os.getenv("PANDASCORE_TOKEN")
        self.base_url = os.getenv("PANDASCORE_BASE", "https://api.pandascore.co")
        self.game = os.getenv("PANDASCORE_GAME", "lol")
        self.name = "PANDASCORE"
        
        # Configurações avançadas
        self.timeout = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
        self.max_retries = int(os.getenv("MAX_REQUEST_RETRIES", "3"))
        self.per_page = int(os.getenv("API_RESULTS_PER_PAGE", "25"))
        
        # Rate limiter
        rate_limit = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "30"))
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=60)
        
        # Configurar ligas monitoradas
        leagues_config = os.getenv("MONITORED_LEAGUES", "")
        if leagues_config.strip():
            self.monitored_leagues = [l.strip().lower() for l in leagues_config.split(",")]
            logger.info(f"🏆 Ligas monitoradas: {self.monitored_leagues}")
        else:
            self.monitored_leagues = []
            logger.info("🏆 Monitorando todas as ligas disponíveis")
            
        # Configurar tipos de mercado
        markets_config = os.getenv("MARKET_TYPES", "")
        if markets_config.strip():
            self.monitored_markets = [m.strip().lower() for m in markets_config.split(",")]
        else:
            self.monitored_markets = []
        
        # Validar configuração
        self._validate_config()
        
        logger.info(f"✅ PandaScoreProvider inicializado - Token: {self.api_token[:8] if self.api_token else 'NENHUM'}...")
    
    def _validate_config(self):
        """Validar configurações do provider"""
        if not self.api_token:
            logger.error("❌ PANDASCORE_TOKEN não configurado!")
            raise ValueError("Token PandaScore obrigatório")
            
        if len(self.api_token) < 20:
            logger.warning("⚠️  Token PandaScore parece inválido (muito curto)")
    
    def get_odds_for_matches(self):
        """Método original para compatibilidade - agora usa async internamente"""
        return asyncio.run(self.get_upcoming_odds())

    async def get_upcoming_odds(self) -> List[Dict]:
        """Busca odds para partidas upcoming (futuras)"""
        logger.info("🔮 Buscando odds para partidas upcoming...")
        return await self._fetch_matches_by_status("upcoming")

    async def get_live_odds(self) -> List[Dict]:
        """Busca odds para partidas running (ao vivo)"""
        logger.info("🔴 Buscando odds para partidas ao vivo...")
        live_matches = await self._fetch_matches_by_status("running")
        
        # Filtrar apenas partidas com odds ativas
        active_matches = [match for match in live_matches if match.get('odds')]
        logger.info(f"📊 {len(active_matches)} partidas ao vivo com odds ativas")
        
        return active_matches

    async def get_recent_matches(self) -> List[Dict]:
        """Busca partidas recentes (útil para análise pós-jogo)"""
        logger.info("📅 Buscando partidas recentes...")
        return await self._fetch_matches_by_status("finished")

    async def _fetch_matches_by_status(self, status: str, retries: int = 0) -> List[Dict]:
        """Busca partidas por status específico com retry automático"""
        
        # Aplicar rate limiting
        await self.rate_limiter.acquire()
        
        # Construir URL e parâmetros
        url = f"{self.base_url}/{self.game}/matches/{status}"
        params = self._build_request_params()
        
        logger.debug(f"🔍 Fazendo requisição: {url} com params: {params}")
        
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers()
            ) as client:
                
                response = await client.get(url, params=params)
                
                # Log detalhado
                logger.debug(f"📡 Status: {response.status_code}, URL: {response.url}")
                
                # Tratamento de erros específicos
                if response.status_code == 400:
                    logger.error(f"❌ Erro 400 - Parâmetros inválidos: {response.text[:300]}")
                    return []
                elif response.status_code == 401:
                    logger.error(f"❌ Erro 401 - Token inválido ou expirado")
                    return []
                elif response.status_code == 403:
                    logger.error(f"❌ Erro 403 - Acesso negado. Verifique permissões do token")
                    return []
                elif response.status_code == 404:
                    logger.warning(f"⚠️  Endpoint não encontrado para status '{status}'")
                    return []
                elif response.status_code == 429:
                    logger.warning(f"⚠️  Rate limit atingido. Aguardando...")
                    await asyncio.sleep(60)  # Aguardar 1 minuto
                    if retries < self.max_retries:
                        return await self._fetch_matches_by_status(status, retries + 1)
                    return []
                
                response.raise_for_status()
                matches_data = response.json()
                
                if not isinstance(matches_data, list):
                    logger.error(f"❌ Formato de resposta inesperado: {type(matches_data)}")
                    return []
                
                logger.info(f"✅ Encontradas {len(matches_data)} partidas {status}")
                formatted_matches = self._format_matches(matches_data, status)
                
                logger.info(f"📊 {len(formatted_matches)} partidas após filtragem")
                return formatted_matches
                
        except httpx.TimeoutException:
            logger.warning(f"⏰ Timeout na requisição para status '{status}'")
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)  # Backoff exponencial
                return await self._fetch_matches_by_status(status, retries + 1)
            return []
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erro HTTP {e.response.status_code}: {e}")
            if retries < self.max_retries and e.response.status_code >= 500:
                await asyncio.sleep(2 ** retries)
                return await self._fetch_matches_by_status(status, retries + 1)
            return []
            
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao buscar partidas {status}: {e}")
            return []
    
    def _get_headers(self) -> Dict[str, str]:
        """Construir headers para requisições"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "User-Agent": "LoL-Opening-Bot/2.0"
        }
    
    def _build_request_params(self) -> Dict[str, str]:
        """Construir parâmetros da requisição"""
        params = {
            "sort": "begin_at",
            "per_page": str(self.per_page)
        }
        
        # Filtrar por ligas se especificado
        if self.monitored_leagues:
            # PandaScore aceita slugs separados por vírgula
            params["filter[league_slug]"] = ",".join(self.monitored_leagues)
        
        # Adicionar filtro temporal para upcoming
        # if status == "upcoming":
        #     future_date = (datetime.now() + timedelta(days=int(os.getenv('OPENING_LOOKAHEAD_DAYS', '14')))).isoformat()
        #     params["filter[begin_at]"] = f"<{future_date}"
        
        return params

    def _format_matches(self, matches: List[Dict], status: str) -> List[Dict]:
        """Formata dados das partidas para o formato padrão do bot"""
        formatted_matches = []
        
        for match_data in matches:
            try:
                formatted_match = self._format_single_match(match_data, status)
                if formatted_match:
                    formatted_matches.append(formatted_match)
            except Exception as e:
                logger.warning(f"⚠️  Erro ao formatar partida: {e}")
                continue
        
        return formatted_matches
    
    def _format_single_match(self, match: Dict, status: str) -> Optional[Dict]:
        """Formata uma única partida"""
        # Validar estrutura básica
        if not match.get('opponents') or len(match['opponents']) < 2:
            return None
            
        # Extrair times
        team1_data = match['opponents'][0].get('opponent', {})
        team2_data = match['opponents'][1].get('opponent', {})
        
        if not team1_data or not team2_data:
            return None
        
        team1 = team1_data.get('name', team1_data.get('slug', 'Team A'))
        team2 = team2_data.get('name', team2_data.get('slug', 'Team B'))
        
        # Informações da liga
        league_info = match.get('league', {})
        league_name = league_info.get('name', 'Unknown League')
        league_slug = league_info.get('slug', '').lower()
        
        # Pular se não for liga monitorada
        if self.monitored_leagues and league_slug not in self.monitored_leagues:
            return None
        
        # Extrair odds
        odds_data = self._extract_odds(match.get('odds', []))
        
        # Para partidas upcoming, incluir mesmo sem odds
        # Para outras, só incluir se tiver odds
        if not odds_data and status != "upcoming":
            return None
        
        # Informações do torneio
        tournament_info = match.get('tournament', {})
        tournament_name = tournament_info.get('name')
        
        return {
            'match_id': str(match.get('id', '')),
            'match': f"{team1} vs {team2}",
            'team1': team1,
            'team2': team2,
            'league': league_name,
            'league_slug': league_slug,
            'tournament': tournament_name,
            'status': status,
            'begin_at': match.get('begin_at'),
            'odds': odds_data
        }

    def _extract_odds(self, odds_list: List[Dict]) -> Dict:
        """Extrai e organiza as odds dos diferentes mercados"""
        odds_data = {}
        
        if not odds_list:
            return odds_data
        
        for odd in odds_list:
            try:
                market_name = odd.get('market_name', '').lower()
                results = odd.get('results', [])
                
                if not results:
                    continue
                
                # Filtrar mercados se especificado
                if self.monitored_markets and not any(
                    market_type in market_name for market_type in self.monitored_markets
                ):
                    continue
                
                # Processar diferentes tipos de mercado
                self._process_market_odds(market_name, results, odds_data)
                
            except Exception as e:
                logger.debug(f"Erro ao processar odds de mercado: {e}")
                continue
        
        return odds_data
    
    def _process_market_odds(self, market_name: str, results: List[Dict], odds_data: Dict):
        """Processa odds de um mercado específico"""
        
        # Match Winner / Moneyline
        if 'winner' in market_name and ('2-way' in market_name or 'match' in market_name):
            if len(results) >= 2:
                # Verificar se tem names dos times
                if all(result.get('name') for result in results[:2]):
                    team1_name = results[0]['name']
                    team2_name = results[1]['name']
                    odds_data['ML'] = {
                        team1_name: results[0].get('odds'),
                        team2_name: results[1].get('odds')
                    }
                else:
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
        
        # First Tower
        elif 'first tower' in market_name or 'first turret' in market_name:
            if len(results) >= 2:
                odds_data['FirstTower'] = {
                    'team1': results[0].get('odds'),
                    'team2': results[1].get('odds')
                }
        
        # Total Kills (Over/Under)
        elif 'kill' in market_name and ('total' in market_name or 'over' in market_name or 'under' in market_name):
            line_match = re.search(r'(\d+\.?\d*)', market_name)
            if line_match and len(results) >= 2:
                line = line_match.group(1)
                market_key = f"KillsO/U{line}"
                
                # Identificar Over/Under pelos nomes ou ordem
                over_result = under_result = None
                
                for result in results:
                    result_name = result.get('name', '').lower()
                    if 'over' in result_name:
                        over_result = result
                    elif 'under' in result_name:
                        under_result = result
                
                # Se não encontrou pelos nomes, usar ordem padrão
                if not over_result and not under_result:
                    over_result = results[0]
                    under_result = results[1] if len(results) > 1 else None
                
                if over_result and under_result:
                    odds_data[market_key] = {
                        'over': over_result.get('odds'),
                        'under': under_result.get('odds')
                    }
        
        # Dragon/Baron markets
        elif any(keyword in market_name for keyword in ['dragon', 'baron', 'inhibitor']):
            market_key = self._clean_market_name(market_name)
            
            if len(results) >= 2:
                odds_data[market_key] = {
                    'team1': results[0].get('odds'),
                    'team2': results[1].get('odds')
                }
            elif len(results) == 1:
                odds_data[market_key] = results[0].get('odds')
    
    def _clean_market_name(self, market_name: str) -> str:
        """Limpa nome do mercado para usar como chave"""
        # Remove caracteres especiais e converte para CamelCase
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', market_name)
        words = cleaned.split()
        return ''.join(word.capitalize() for word in words)

    async def get_leagues_info(self) -> List[Dict]:
        """Busca informações das ligas disponíveis"""
        logger.info("🏆 Buscando informações das ligas...")
        
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{self.game}/leagues"
        params = {"per_page": "100"}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, 
                    params=params, 
                    headers=self._get_headers()
                )
                response.raise_for_status()
                leagues = response.json()
                
                logger.info(f"✅ Encontradas {len(leagues)} ligas")
                
                # Log das ligas para debugging
                if logger.isEnabledFor(logging.DEBUG):
                    for league in leagues[:10]:
                        logger.debug(f"  - {league.get('name')} (slug: {league.get('slug')})")
                
                return leagues
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar ligas: {e}")
            return []

    async def test_connection(self) -> Tuple[bool, str]:
        """Testa conexão com a API"""
        logger.info("🔌 Testando conexão com PandaScore API...")
        
        try:
            leagues = await self.get_leagues_info()
            if leagues:
                return True, f"Conexão OK - {len(leagues)} ligas disponíveis"
            else:
                return False, "Nenhuma liga encontrada"
        except Exception as e:
            return False, f"Erro na conexão: {e}"

# Factory function para criar provider baseado na configuração
def create_provider():
    """Factory function para criar o provider correto"""
    provider_type = os.getenv('ODDS_PROVIDER', 'MOCK').upper()
    
    if provider_type == 'PANDASCORE':
        return PandaScoreProvider()
    elif provider_type == 'MOCK':
        return MockProvider()
    else:
        logger.warning(f"⚠️  Provider desconhecido '{provider_type}', usando MOCK")
        return MockProvider()