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
        
        # CORREÇÃO: Configurar ligas monitoradas com validação
        self.monitored_leagues = self._parse_monitored_leagues()
        
        # Configurar tipos de mercado
        markets_config = os.getenv("MARKET_TYPES", "")
        if markets_config.strip():
            self.monitored_markets = [m.strip().lower() for m in markets_config.split(",")]
        else:
            self.monitored_markets = []
        
        # Validar configuração
        self._validate_config()
        
        logger.info(f"✅ PandaScoreProvider inicializado - Token: {self.api_token[:8] if self.api_token else 'NENHUM'}...")
    
    def _parse_monitored_leagues(self) -> List[str]:
        """CORREÇÃO: Parse mais robusto das ligas monitoradas"""
        leagues_config = os.getenv("MONITORED_LEAGUES", "").strip()
        
        if not leagues_config:
            logger.info("🏆 Nenhuma liga específica configurada - monitorando todas")
            return []
        
        # Parse e validação dos slugs
        raw_leagues = [l.strip().lower() for l in leagues_config.split(",")]
        valid_leagues = []
        
        # Slugs conhecidos válidos para LoL
        known_valid_slugs = {
            'lck', 'lpl', 'lec', 'lcs', 'worlds', 'msi', 'cblol',
            'lck-spring', 'lpl-spring', 'lec-spring', 'lcs-spring',
            'lck-summer', 'lpl-summer', 'lec-summer', 'lcs-summer',
            'worlds-2024', 'msi-2024'
        }
        
        for league in raw_leagues:
            if not league:
                continue
            
            # Validar formato básico do slug
            if re.match(r'^[a-z0-9-]+$', league) and len(league) >= 3:
                valid_leagues.append(league)
                if league not in known_valid_slugs:
                    logger.warning(f"⚠️ Liga '{league}' não está na lista de slugs conhecidos")
            else:
                logger.warning(f"⚠️ Slug inválido ignorado: '{league}'")
        
        if valid_leagues:
            logger.info(f"🏆 Ligas monitoradas: {valid_leagues}")
        else:
            logger.warning("⚠️ Nenhuma liga válida encontrada - monitorando todas")
        
        return valid_leagues
    
    def _validate_config(self):
        """Validar configurações do provider"""
        if not self.api_token:
            logger.error("❌ PANDASCORE_TOKEN não configurado!")
            raise ValueError("Token PandaScore obrigatório")
            
        if len(self.api_token) < 20:
            logger.warning("⚠️ Token PandaScore parece inválido (muito curto)")
        
        # Validar formato básico do token
        if not re.match(r'^[a-zA-Z0-9_-]{20,}$', self.api_token):
            logger.warning("⚠️ Formato do token PandaScore pode estar incorreto")
    
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
        """CORREÇÃO: Busca partidas por status específico com fallback"""
        
        # Aplicar rate limiting
        await self.rate_limiter.acquire()
        
        # Tentar primeiro com filtros (se configurados)
        if self.monitored_leagues:
            matches = await self._fetch_with_league_filter(status, retries)
            if matches is not None:  # None indica erro, lista vazia é válida
                return matches
        
        # Fallback: buscar sem filtros
        logger.info(f"🔄 Buscando {status} matches sem filtros como fallback...")
        return await self._fetch_without_filters(status, retries)
    
    async def _fetch_with_league_filter(self, status: str, retries: int = 0) -> Optional[List[Dict]]:
        """Busca partidas com filtro de liga"""
        url = f"{self.base_url}/{self.game}/matches/{status}"
        params = {
            "sort": "begin_at",
            "per_page": str(self.per_page),
            "filter[league_slug]": ",".join(self.monitored_leagues)
        }
        
        try:
            result = await self._make_request(url, params)
            if result:
                logger.info(f"✅ {len(result)} partidas {status} encontradas com filtros")
                return self._format_matches(result, status)
            return []
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.warning(f"⚠️ Erro 400 com filtros - tentando fallback sem filtros")
                return None  # Sinaliza para tentar fallback
            else:
                raise
    
    async def _fetch_without_filters(self, status: str, retries: int = 0) -> List[Dict]:
        """Busca partidas sem filtros de liga"""
        url = f"{self.base_url}/{self.game}/matches/{status}"
        params = {
            "sort": "begin_at", 
            "per_page": str(self.per_page)
        }
        
        try:
            result = await self._make_request(url, params)
            if result:
                formatted = self._format_matches(result, status)
                # Aplicar filtro manual se necessário
                if self.monitored_leagues:
                    filtered = [m for m in formatted if m.get('league_slug') in self.monitored_leagues]
                    logger.info(f"📊 {len(filtered)} partidas após filtro manual de {len(formatted)}")
                    return filtered
                return formatted
            return []
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar sem filtros: {e}")
            return []
    
    async def _make_request(self, url: str, params: Dict, retries: int = 0) -> Optional[List[Dict]]:
        """Faz requisição HTTP com retry automático"""
        logger.debug(f"🔗 Fazendo requisição: {url} com params: {params}")
        
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers()
            ) as client:
                
                response = await client.get(url, params=params)
                
                # Log detalhado
                logger.debug(f"📡 Status: {response.status_code}, URL: {response.url}")
                
                # Tratamento de erros específicos
                await self._handle_response_errors(response)
                
                response.raise_for_status()
                matches_data = response.json()
                
                if not isinstance(matches_data, list):
                    logger.error(f"❌ Formato de resposta inesperado: {type(matches_data)}")
                    return []
                
                return matches_data
                
        except httpx.TimeoutException:
            logger.warning(f"⏰ Timeout na requisição")
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)  # Backoff exponencial
                return await self._make_request(url, params, retries + 1)
            return []
            
        except httpx.HTTPStatusError as e:
            if retries < self.max_retries and e.response.status_code >= 500:
                await asyncio.sleep(2 ** retries)
                return await self._make_request(url, params, retries + 1)
            raise
    
    async def _handle_response_errors(self, response: httpx.Response):
        """CORREÇÃO: Tratamento melhorado de erros de resposta"""
        if response.status_code == 400:
            try:
                error_data = response.json()
                logger.error(f"❌ Erro 400 - Parâmetros inválidos: {error_data}")
            except:
                logger.error(f"❌ Erro 400 - Parâmetros inválidos: {response.text[:300]}")
        elif response.status_code == 401:
            logger.error(f"❌ Erro 401 - Token inválido ou expirado")
        elif response.status_code == 403:
            logger.error(f"❌ Erro 403 - Acesso negado. Verifique permissões do token")
        elif response.status_code == 404:
            logger.warning(f"⚠️ Erro 404 - Endpoint não encontrado")
        elif response.status_code == 429:
            logger.warning(f"⚠️ Rate limit atingido. Aguardando...")
            await asyncio.sleep(60)  # Aguardar 1 minuto
            raise httpx.HTTPStatusError("Rate limit", request=response.request, response=response)
    
    def _get_headers(self) -> Dict[str, str]:
        """Construir headers para requisições"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "User-Agent": "LoL-Opening-Bot/2.0"
        }

    def _format_matches(self, matches: List[Dict], status: str) -> List[Dict]:
        """Formata dados das partidas para o formato padrão do bot"""
        formatted_matches = []
        
        for match_data in matches:
            try:
                formatted_match = self._format_single_match(match_data, status)
                if formatted_match:
                    formatted_matches.append(formatted_match)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao formatar partida: {e}")
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
            result = await self._make_request(url, params)
            if result:
                logger.info(f"✅ Encontradas {len(result)} ligas")
                
                # Log das ligas para debugging
                if logger.isEnabledFor(logging.DEBUG):
                    for league in result[:10]:
                        logger.debug(f"  - {league.get('name')} (slug: {league.get('slug')})")
                
                return result
            return []
                
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
    
    async def validate_api_access(self) -> bool:
        """NOVO: Valida acesso à API com requisição de teste"""
        try:
            leagues = await self.get_leagues_info()
            if not leagues:
                logger.error("❌ Token válido, mas sem acesso a ligas")
                return False
            
            logger.info(f"✅ API acessível - {len(leagues)} ligas encontradas")
            
            # Validar se ligas monitoradas existem
            if self.monitored_leagues:
                available_slugs = {league.get('slug', '').lower() for league in leagues}
                invalid_leagues = [l for l in self.monitored_leagues if l not in available_slugs]
                
                if invalid_leagues:
                    logger.warning(f"⚠️ Ligas configuradas não encontradas: {invalid_leagues}")
                    logger.info(f"💡 Ligas disponíveis: {sorted(list(available_slugs))[:20]}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Erro na validação da API: {e}")
            return False

# Factory function para criar provider baseado na configuração
def create_provider():
    """Factory function para criar o provider correto"""
    provider_type = os.getenv('ODDS_PROVIDER', 'MOCK').upper()
    
    if provider_type == 'PANDASCORE':
        return PandaScoreProvider()
    elif provider_type == 'MOCK':
        return MockProvider()
    else:
        logger.warning(f"⚠️ Provider desconhecido '{provider_type}', usando MOCK")
        return MockProvider()
