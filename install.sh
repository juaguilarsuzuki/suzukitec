#!/bin/bash
# =============================================================================
# Suzuki Tec — Instalador Automático
# Compatível com Ubuntu 20.04, 22.04 e 24.04
# =============================================================================
set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Helpers ───────────────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC}  $*" >&2; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}══ $* ══${NC}"; }
ask()     { echo -e "${YELLOW}$*${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}${BLUE}"
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║         SUZUKI TEC — INSTALADOR AUTOMÁTICO            ║"
echo "  ║         Sistema de Relatórios Mensais                 ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Verificações iniciais ──────────────────────────────────────────────────────
step "Verificando ambiente"

# Permite root (comum em VPS), mas avisa sobre boas práticas
if [[ $EUID -eq 0 ]]; then
    warn "Executando como root. Recomendado usar um usuário comum em produção."
    warn "Continuando mesmo assim..."
    # sudo não é necessário quando já é root
    SUDO=""
else
    SUDO="sudo"
fi

# Garante que sudo existe (necessário apenas quando não é root)
if [[ -n "$SUDO" ]]; then
    command -v sudo >/dev/null || error "sudo não encontrado. Instale-o primeiro."
fi

OS_ID=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
OS_VER=$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
[[ "$OS_ID" != "ubuntu" ]] && warn "Este script foi testado no Ubuntu. Seu SO: $OS_ID $OS_VER"
info "Sistema: Ubuntu $OS_VER — Usuário: $USER"
success "Verificações iniciais OK"

# ── Modo de instalação ─────────────────────────────────────────────────────────
step "Modo de instalação"
echo ""
echo -e "  ${BOLD}1)${NC} Docker ${GREEN}(recomendado — mais simples)${NC}"
echo -e "  ${BOLD}2)${NC} Manual ${YELLOW}(sem Docker — Gunicorn + Nginx + systemd)${NC}"
echo ""
ask "Escolha o modo [1/2]:"
read -r INSTALL_MODE
[[ "$INSTALL_MODE" != "1" && "$INSTALL_MODE" != "2" ]] && error "Opção inválida. Digite 1 ou 2."

# ── Coleta de configurações ────────────────────────────────────────────────────
step "Configurações do sistema"

INSTALL_DIR="/opt/suzukitec"
REPO_URL="https://github.com/juaguilarsuzuki/suzukitec.git"
CURRENT_USER="$USER"

ask "\nDiretório de instalação [${INSTALL_DIR}]:"
read -r INPUT_DIR
INSTALL_DIR="${INPUT_DIR:-$INSTALL_DIR}"

ask "URL ou IP de acesso ao servidor (ex: 192.168.1.10 ou meudominio.com.br):"
read -r SERVER_HOST
[[ -z "$SERVER_HOST" ]] && error "Endereço do servidor é obrigatório."

ask "Nome da empresa [Suzuki Tec]:"
read -r COMPANY_NAME
COMPANY_NAME="${COMPANY_NAME:-Suzuki Tec}"

step "Configurações de e-mail (SMTP)"
ask "Servidor SMTP [smtp.gmail.com]:"
read -r EMAIL_HOST
EMAIL_HOST="${EMAIL_HOST:-smtp.gmail.com}"

ask "Porta SMTP [587]:"
read -r EMAIL_PORT
EMAIL_PORT="${EMAIL_PORT:-587}"

ask "E-mail remetente (usuário SMTP):"
read -r EMAIL_USER
[[ -z "$EMAIL_USER" ]] && error "E-mail é obrigatório."

ask "Senha do e-mail (App Password se Gmail):"
read -rs EMAIL_PASS
echo ""

ask "E-mail de origem para os relatórios [relatorios@suzukitec.com.br]:"
read -r DEFAULT_FROM
DEFAULT_FROM="${DEFAULT_FROM:-relatorios@suzukitec.com.br}"

step "Integrações com ferramentas"

ask "\n[DIGISAC] URL base da API [https://api.digisac.com.br/v1]:"
read -r DIGISAC_URL
DIGISAC_URL="${DIGISAC_URL:-https://api.digisac.com.br/v1}"

ask "[DIGISAC] Token de autenticação:"
read -rs DIGISAC_TOKEN
echo ""

ask "\n[MILVUS] URL base da API [https://api.milvus.com.br/v1]:"
read -r MILVUS_URL
MILVUS_URL="${MILVUS_URL:-https://api.milvus.com.br/v1}"

ask "[MILVUS] Token de autenticação:"
read -rs MILVUS_TOKEN
echo ""

ask "\n[PRTG] URL do servidor PRTG (ex: https://prtg.empresa.com.br):"
read -r PRTG_URL

ask "[PRTG] Usuário:"
read -r PRTG_USER

ask "[PRTG] Passhash (ou deixe em branco para usar senha):"
read -rs PRTG_PASSHASH
echo ""

if [[ -z "$PRTG_PASSHASH" ]]; then
    ask "[PRTG] Senha:"
    read -rs PRTG_PASSWORD
    echo ""
else
    PRTG_PASSWORD=""
fi

# ── Gerar SECRET_KEY ───────────────────────────────────────────────────────────
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || \
             cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 60)

# ── Resumo ─────────────────────────────────────────────────────────────────────
step "Resumo da instalação"
echo ""
echo -e "  Diretório:    ${BOLD}$INSTALL_DIR${NC}"
echo -e "  Modo:         ${BOLD}$([ "$INSTALL_MODE" = "1" ] && echo "Docker" || echo "Manual")${NC}"
echo -e "  Servidor:     ${BOLD}$SERVER_HOST${NC}"
echo -e "  Empresa:      ${BOLD}$COMPANY_NAME${NC}"
echo -e "  E-mail SMTP:  ${BOLD}$EMAIL_USER${NC}"
echo ""
ask "Confirmar instalação? [s/N]:"
read -r CONFIRM
[[ "${CONFIRM,,}" != "s" && "${CONFIRM,,}" != "sim" ]] && { info "Instalação cancelada."; exit 0; }

# =============================================================================
# FUNÇÕES DE INSTALAÇÃO
# =============================================================================

write_env_file() {
    local ENV_FILE="$1"
    cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${SERVER_HOST},localhost,127.0.0.1
DATABASE_URL=${2:-sqlite:///db.sqlite3}
REDIS_URL=${3:-redis://localhost:6379/0}
DJANGO_SETTINGS_MODULE=config.settings.production

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=${EMAIL_HOST}
EMAIL_PORT=${EMAIL_PORT}
EMAIL_USE_TLS=True
EMAIL_HOST_USER=${EMAIL_USER}
EMAIL_HOST_PASSWORD=${EMAIL_PASS}
DEFAULT_FROM_EMAIL=${DEFAULT_FROM}

DIGISAC_BASE_URL=${DIGISAC_URL}
DIGISAC_TOKEN=${DIGISAC_TOKEN}

MILVUS_BASE_URL=${MILVUS_URL}
MILVUS_TOKEN=${MILVUS_TOKEN}

PRTG_BASE_URL=${PRTG_URL}
PRTG_USERNAME=${PRTG_USER}
PRTG_PASSHASH=${PRTG_PASSHASH}
PRTG_PASSWORD=${PRTG_PASSWORD}

COMPANY_NAME=${COMPANY_NAME}
COMPANY_LOGO_URL=
EOF
    chmod 600 "$ENV_FILE"
    success "Arquivo .env criado"
}

clone_repo() {
    step "Clonando repositório"
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        warn "Repositório já existe — atualizando..."
        git -C "$INSTALL_DIR" pull
    else
        $SUDO mkdir -p "$INSTALL_DIR"
        $SUDO chown "$CURRENT_USER":"$CURRENT_USER" "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
    success "Repositório pronto em $INSTALL_DIR"
}

# =============================================================================
# INSTALAÇÃO VIA DOCKER
# =============================================================================
install_docker_mode() {

    step "Instalando Docker"
    if command -v docker &>/dev/null; then
        success "Docker já instalado: $(docker --version)"
    else
        info "Baixando e instalando Docker..."
        curl -fsSL https://get.docker.com | $SUDO sh
        $SUDO usermod -aG docker "$CURRENT_USER"
        success "Docker instalado"
    fi

    if ! docker compose version &>/dev/null; then
        info "Instalando Docker Compose plugin..."
        $SUDO apt-get install -y docker-compose-plugin
        success "Docker Compose instalado"
    else
        success "Docker Compose já disponível: $(docker compose version --short)"
    fi

    clone_repo
    cd "$INSTALL_DIR"

    step "Criando arquivo .env"
    write_env_file ".env" \
        "postgres://suzuki:suzuki@db:5432/suzukitec" \
        "redis://redis:6379/0"

    step "Iniciando containers"
    # Garantir que o grupo docker seja aplicado nesta sessão
    sg docker -c "docker compose up -d --build" 2>/dev/null || \
        $SUDO docker compose up -d --build

    info "Aguardando containers ficarem prontos..."
    sleep 15

    step "Configurando banco de dados"
    sg docker -c "docker compose exec web python manage.py migrate --noinput" 2>/dev/null || \
        $SUDO docker compose exec web python manage.py migrate --noinput

    step "Coletando arquivos estáticos"
    sg docker -c "docker compose exec web python manage.py collectstatic --noinput" 2>/dev/null || \
        $SUDO docker compose exec web python manage.py collectstatic --noinput

    step "Criando superusuário administrador"
    echo ""
    warn "Você precisará criar um usuário administrador para acessar o painel."
    sg docker -c "docker compose exec -it web python manage.py createsuperuser" 2>/dev/null || \
        $SUDO docker compose exec -it web python manage.py createsuperuser
}

# =============================================================================
# INSTALAÇÃO MANUAL
# =============================================================================
install_manual_mode() {

    step "Instalando dependências do sistema"
    $SUDO apt-get update -qq
    $SUDO apt-get install -y \
        python3 python3-pip python3-venv \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
        libffi-dev libcairo2 libgdk-pixbuf2.0-0 \
        fonts-liberation fonts-noto \
        redis-server postgresql postgresql-contrib \
        nginx git curl
    success "Dependências instaladas"

    step "Configurando Redis"
    $SUDO systemctl enable redis-server
    $SUDO systemctl start redis-server
    success "Redis ativo"

    step "Configurando PostgreSQL"
    DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    $SUDO -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'suzuki') THEN
    CREATE USER suzuki WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;
CREATE DATABASE suzukitec OWNER suzuki;
GRANT ALL PRIVILEGES ON DATABASE suzukitec TO suzuki;
SQL
    success "Banco PostgreSQL configurado (usuário: suzuki)"

    clone_repo
    cd "$INSTALL_DIR"

    step "Criando ambiente virtual Python"
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    success "Dependências Python instaladas"

    step "Criando arquivo .env"
    write_env_file ".env" \
        "postgres://suzuki:${DB_PASS}@localhost:5432/suzukitec" \
        "redis://localhost:6379/0"

    step "Migrando banco de dados"
    python manage.py migrate --noinput --settings=config.settings.production
    success "Migrations aplicadas"

    step "Coletando arquivos estáticos"
    python manage.py collectstatic --noinput --settings=config.settings.production
    success "Estáticos coletados"

    step "Criando superusuário administrador"
    warn "Crie o usuário administrador para acessar o painel:"
    python manage.py createsuperuser --settings=config.settings.production

    deactivate

    # ── Serviços systemd ──────────────────────────────────────────────────────
    step "Configurando serviços systemd"

    # Gunicorn (Django)
    $SUDO tee /etc/systemd/system/suzukitec.service > /dev/null <<EOF
[Unit]
Description=Suzuki Tec - Django/Gunicorn
After=network.target postgresql.service redis.service

[Service]
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn config.wsgi:application \\
    --bind 127.0.0.1:8000 --workers 3 --timeout 120
EnvironmentFile=${INSTALL_DIR}/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Celery Worker
    $SUDO tee /etc/systemd/system/suzukitec-worker.service > /dev/null <<EOF
[Unit]
Description=Suzuki Tec - Celery Worker
After=network.target redis.service suzukitec.service

[Service]
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/celery -A config worker \\
    --loglevel=info --concurrency=4
EnvironmentFile=${INSTALL_DIR}/.env
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Celery Beat
    $SUDO tee /etc/systemd/system/suzukitec-beat.service > /dev/null <<EOF
[Unit]
Description=Suzuki Tec - Celery Beat (Agendador)
After=network.target redis.service suzukitec.service

[Service]
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/celery -A config beat \\
    --loglevel=info \\
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
EnvironmentFile=${INSTALL_DIR}/.env
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    $SUDO systemctl daemon-reload
    $SUDO systemctl enable suzukitec suzukitec-worker suzukitec-beat
    $SUDO systemctl start suzukitec suzukitec-worker suzukitec-beat
    success "Serviços systemd ativos"

    # ── Nginx ──────────────────────────────────────────────────────────────────
    step "Configurando Nginx"
    $SUDO tee /etc/nginx/sites-available/suzukitec > /dev/null <<EOF
server {
    listen 80;
    server_name ${SERVER_HOST};
    client_max_body_size 20M;

    location /static/ {
        alias ${INSTALL_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias ${INSTALL_DIR}/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
    }
}
EOF

    $SUDO ln -sf /etc/nginx/sites-available/suzukitec /etc/nginx/sites-enabled/
    $SUDO rm -f /etc/nginx/sites-enabled/default
    $SUDO nginx -t
    $SUDO systemctl restart nginx
    success "Nginx configurado"

    # ── Let's Encrypt (opcional) ───────────────────────────────────────────────
    echo ""
    ask "Deseja instalar certificado SSL gratuito (Let's Encrypt)? Requer domínio apontado para este servidor. [s/N]:"
    read -r INSTALL_SSL
    if [[ "${INSTALL_SSL,,}" == "s" || "${INSTALL_SSL,,}" == "sim" ]]; then
        $SUDO apt-get install -y certbot python3-certbot-nginx
        $SUDO certbot --nginx -d "$SERVER_HOST" --non-interactive --agree-tos -m "$EMAIL_USER" || \
            warn "SSL não configurado automaticamente. Execute manualmente: sudo certbot --nginx -d $SERVER_HOST"
    fi
}

# =============================================================================
# EXECUÇÃO
# =============================================================================
if [[ "$INSTALL_MODE" == "1" ]]; then
    install_docker_mode
else
    install_manual_mode
fi

# =============================================================================
# RESUMO FINAL
# =============================================================================
step "Instalação concluída!"
echo ""
echo -e "${GREEN}${BOLD}  ✔ Sistema instalado com sucesso!${NC}"
echo ""
echo -e "${BOLD}  Acesso ao sistema:${NC}"
echo -e "    Dashboard:  ${CYAN}http://${SERVER_HOST}/${NC}"
echo -e "    Admin:      ${CYAN}http://${SERVER_HOST}/admin/${NC}"
echo ""
echo -e "${BOLD}  Próximos passos no painel admin:${NC}"
echo -e "    1. Acesse ${CYAN}http://${SERVER_HOST}/admin/${NC}"
echo -e "    2. Vá em ${BOLD}Clientes → Adicionar Cliente${NC}"
echo -e "    3. Preencha nome, e-mail e configure as integrações (Digisac ID, Milvus ID, PRTG Group ID)"
echo -e "    4. Os relatórios serão gerados automaticamente todo dia 1 às 06h"
echo ""
if [[ "$INSTALL_MODE" == "2" ]]; then
    echo -e "${BOLD}  Comandos úteis:${NC}"
    echo -e "    Ver logs Django:  ${YELLOW}sudo journalctl -u suzukitec -f${NC}"
    echo -e "    Ver logs Worker:  ${YELLOW}sudo journalctl -u suzukitec-worker -f${NC}"
    echo -e "    Reiniciar tudo:   ${YELLOW}sudo systemctl restart suzukitec suzukitec-worker suzukitec-beat${NC}"
    echo -e "    Gerar relatório agora (manual):"
    echo -e "      ${YELLOW}cd ${INSTALL_DIR} && source venv/bin/activate${NC}"
    echo -e "      ${YELLOW}python manage.py shell -c \"from apps.reports.tasks import generate_all_monthly_reports; generate_all_monthly_reports.delay()\"${NC}"
else
    echo -e "${BOLD}  Comandos úteis (Docker):${NC}"
    echo -e "    Ver logs:         ${YELLOW}cd ${INSTALL_DIR} && docker compose logs -f${NC}"
    echo -e "    Reiniciar:        ${YELLOW}docker compose restart${NC}"
    echo -e "    Parar tudo:       ${YELLOW}docker compose down${NC}"
    echo -e "    Gerar relatório agora (manual):"
    echo -e "      ${YELLOW}docker compose exec web python manage.py shell -c \"from apps.reports.tasks import generate_all_monthly_reports; generate_all_monthly_reports.delay()\"${NC}"
fi
echo ""
echo -e "  ${BOLD}Arquivo de configuração:${NC} ${INSTALL_DIR}/.env"
echo ""
