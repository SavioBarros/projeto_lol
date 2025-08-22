# LoL Opening Bot

Bot para monitorar odds de abertura no League of Legends e identificar valor em mercados específicos.

## Estrutura do Projeto

```
lol_opening_bot/
│── main.py                # Ponto de entrada
│── .env                   # Configurações de ambiente
│── requirements.txt       # Dependências
│── README.md              # Guia de uso
│── oracle_csvs/           # CSVs do Oracles Elixir (se ORACLE_ENABLE_DOWNLOAD=false)
│── src/
│   ├── db.py
│   ├── models.py
│   ├── oracle.py
│   ├── providers.py
│   ├── fair_odds.py
│   ├── notifier.py
│   └── engine.py
```

## Configuração

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure o arquivo `.env`:
   ```ini
   DATABASE_URL=sqlite:///lol_openings.db
   ODDS_PROVIDER=PANDASCORE
   PANDASCORE_TOKEN=SEU_TOKEN_AQUI
   PANDASCORE_BASE=https://api.pandascore.co
   PANDASCORE_GAME=lol

   ORACLE_DATA_DIR=./oracle_csvs
   ORACLE_ENABLE_DOWNLOAD=false

   TELEGRAM_BOT_TOKEN=SEU_BOT_TOKEN
   TELEGRAM_CHAT_ID=SEU_CHAT_ID

   POLL_INTERVAL_SECONDS=60
   OPENING_LOOKAHEAD_DAYS=14
   EDGE_THRESHOLD=0.05
   ```

3. Se `ORACLE_ENABLE_DOWNLOAD=false`, baixe manualmente o CSV do Oracles Elixir e coloque em `oracle_csvs/`.

4. Se `ORACLE_ENABLE_DOWNLOAD=true`, o bot tentará baixar automaticamente a versão mais recente do Oracles Elixir.

## Execução

```bash
python main.py
```

O bot então:
- Consulta odds de abertura (via PandaScore ou mock).
- Carrega estatísticas da Oracle’s Elixir.
- Calcula odds justas (modelo de Poisson).
- Envia notificações via Telegram para odds desreguladas.

