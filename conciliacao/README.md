# Conciliação — Motor de Conciliação de Ativos MSP

Cruza o inventário de dispositivos entre **Milvus**, **TeamViewer** e **Conta Azul**,
gerando um relatório PDF por cliente para conferência mensal de faturamento.

---

## Estrutura

```
conciliacao/
  config/clientes.yaml        # de-para dos clientes nas 3 ferramentas
  .env.example                # template de credenciais
  src/
    sources/
      milvus.py               # adaptador Milvus (dispositivos + agente)
      teamviewer.py           # adaptador TeamViewer (devices, last seen)
      contaazul.py            # adaptador Conta Azul (serviços faturados)
    reconcile.py              # cruzamento + regras de status
    report.py                 # geração de PDF (ReportLab)
    main.py                   # orquestrador
  requirements.txt
  saida/                      # PDFs gerados (criado automaticamente)
```

---

## Pré-requisitos

- Python 3.11+
- `pip`

---

## Configuração

### 1. Criar ambiente virtual e instalar dependências

```bash
cd conciliacao
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar o `.env`

```bash
cp .env.example .env
# Editar .env com suas credenciais reais
```

Variáveis obrigatórias em modo real:

| Variável                  | Descrição                                      |
|---------------------------|------------------------------------------------|
| `MODE`                    | `mock` (padrão) ou `real`                      |
| `MILVUS_BASE_URL`         | URL base da instância Milvus                   |
| `MILVUS_TOKEN`            | Token de API do Milvus                         |
| `TEAMVIEWER_TOKEN`        | Script token do TeamViewer Management Console  |
| `CONTAAZUL_CLIENT_ID`     | Client ID OAuth2 do Conta Azul                 |
| `CONTAAZUL_CLIENT_SECRET` | Client Secret OAuth2 do Conta Azul             |
| `PERIODO`                 | Rótulo do período no PDF (ex.: `Maio/2025`)    |
| `OUTPUT_DIR`              | Diretório de saída (padrão: `saida/`)          |

### 3. Configurar clientes (`config/clientes.yaml`)

Cada cliente precisa dos três IDs preenchidos para ser processado:

```yaml
clientes:
  - nome: "Acme Tecnologia"
    milvus_cliente_id: "CLI-001"
    teamviewer_grupo: "Acme - TI"       # nome exato do grupo no TeamViewer
    contaazul_cliente_id: "CA-10021"
    ativo: true
```

Clientes com qualquer campo vazio ou `ativo: false` são ignorados.

---

## Como rodar

### Modo mock (sem credenciais reais)

```bash
MODE=mock PERIODO="Junho/2025" python -m src.main
```

Gera PDFs de exemplo em `saida/` com cenários intencionais:
- 1 dispositivo **Sem agente** (presente no TeamViewer, ausente no Milvus)
- 1 dispositivo **Sem contato** (last seen > 30 dias)
- 1 caso **Não faturado** (mais dispositivos do que o cobrado no Conta Azul)

### Modo real

```bash
# Garantir que .env tem MODE=real e todas as credenciais
python -m src.main

# Ou explicitamente:
MODE=real PERIODO="Junho/2025" python -m src.main
```

---

## Crontab — exemplos

```cron
# Coleta diária às 06:00 (mantém dados frescos, útil para monitorar sem contato)
0 6 * * * cd /opt/conciliacao && .venv/bin/python -m src.main >> logs/diario.log 2>&1

# Conciliação mensal no dia 25 às 08:00 (antes do fechamento do faturamento)
0 8 25 * * cd /opt/conciliacao && MODE=real PERIODO=$(date +"\%B/\%Y") .venv/bin/python -m src.main >> logs/mensal.log 2>&1
```

---

## Como validar nomes de campo das APIs

Cada adaptador em `src/sources/` tem um bloco `_FIELD_MAP` no topo com os campos
mapeados e comentários `# TODO: confirmar nome do campo`. Para validar:

### Milvus

```bash
curl -H "Authorization: Bearer $MILVUS_TOKEN" \
     "$MILVUS_BASE_URL/dispositivos?cliente_id=CLI-001&page_size=1" | jq .
```

Observe as chaves retornadas e atualize `_FIELD_MAP` em `src/sources/milvus.py`.

### TeamViewer

```bash
# Listar grupos
curl -H "Authorization: Bearer $TEAMVIEWER_TOKEN" \
     https://webapi.teamviewer.com/api/v1/groups | jq .

# Listar dispositivos de um grupo
curl -H "Authorization: Bearer $TEAMVIEWER_TOKEN" \
     "https://webapi.teamviewer.com/api/v1/devices?groupid=<ID_DO_GRUPO>" | jq .
```

Documentação oficial: https://webapi.teamviewer.com/api/v1/docs/index

### Conta Azul

```bash
# Obter token
TOKEN=$(curl -s -X POST https://api.contaazul.com/oauth2/token \
  -d "grant_type=client_credentials&client_id=$CONTAAZUL_CLIENT_ID&client_secret=$CONTAAZUL_CLIENT_SECRET" \
  | jq -r .access_token)

# Consultar vendas de um cliente
curl -H "Authorization: Bearer $TOKEN" \
     "https://api.contaazul.com/v1/sales?customer_id=CA-10021" | jq .
```

Documentação oficial: https://developers.contaazul.com/

---

## Regras de status

| Status        | Critério                                                              |
|---------------|-----------------------------------------------------------------------|
| OK            | Presente no Milvus e no TeamViewer, last seen ≤ 30 dias em ambos     |
| Sem agente    | Presente no TeamViewer, ausente no Milvus                            |
| Sem contato   | last seen > 30 dias em qualquer uma das fontes                       |
| Não faturado  | Qtd. de dispositivos ativos > qtd. cobrada no Conta Azul             |

---

## Nota sobre LGPD

Os dados processados por este sistema incluem informações de equipamentos e
usuários (hostname, usuário logado, endereço MAC, número de série), que podem
ser consideradas **dados pessoais** nos termos da LGPD (Lei 13.709/2018) quando
associados a pessoas identificáveis.

Recomendações:
- Acesso restrito ao diretório `saida/` e ao arquivo `.env` (permissões `600`).
- Tokens de API com **permissão mínima** (somente leitura).
- PDFs gerados contêm dados de colaboradores dos clientes — compartilhamento
  deve ocorrer somente com os responsáveis autorizados de cada empresa.
- Definir política de retenção para os PDFs em `saida/` (ex.: 12 meses).
- Não commitar o arquivo `.env` no repositório (já incluído no `.gitignore`).
