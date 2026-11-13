# E-commerce PetVila Club · plataforma própria

Implementação do PDR v1.1 (03/11/2026): loja avulsa, assinaturas de kits por cão, ração recorrente,
curadoria assistida por regras com aprovação humana, Minha Vila e painel administrativo.

## Arquitetura

```
                ┌──────────────┐        ┌───────────────────────────┐
 navegador ───► │ frontend     │ /api ► │ backend (Django + DRF)    │ ──► Postgres 16
                │ React + Vite │ /painel│ gunicorn                  │
                │ (nginx)      │        │ painel admin por papel    │ ◄── webhook Asaas
                └──────────────┘        └───────────────────────────┘ ──► API Asaas v3
 app (Expo) ──────────── mesma API REST /api/v1 (JWT) ─────┘
                                         scheduler: rotina diária (mesma imagem)
```

| Pasta | O que é |
| --- | --- |
| `backend/` | Django 5.2 LTS, DRF, JWT (simplejwt), Postgres. Domínios em `backend/apps/*` |
| `frontend/` | React 19 + Vite + TypeScript. Loja, planos, checkout, Minha Vila |
| `mobile/` | Expo SDK 58 (React Native 0.88). Planos, loja, carrinho, assinatura, pagamento e Minha Vila |
| `deploy/` | Caddy (HTTPS automático) e script de backup do Postgres |
| `docker-compose.yml` | Ambiente local completo |
| `docker-compose.prod.yml` | Sobreposição para a VPS |
| raiz (`src/`, Astro) | Landing de pré-lançamento existente, **não alterada** |

Módulos do backend (aplicação modular, sem microsserviços, conforme seção 15 do PDR):

| App | Responsabilidade | Requisitos |
| --- | --- | --- |
| `accounts` | Tutor/equipe, login por e-mail, endereços, consentimento de marketing separado | PET-01, PRV-01, SEG-01 |
| `pets` | Cães com perfil versionado (`DogProfileVersion`), campos obrigatórios configuráveis | PET-01/02/04 |
| `catalog` | Categorias, atributos (ingrediente/material), produtos, SKUs com custo separado do preço | LOJ-01, PET-02 |
| `inventory` | Saldo físico/reservado/avariado/quarentena, lotes e validade, movimentos idempotentes | EST-01/02 |
| `plans` | Planos, ofertas versionadas com aprovação, composições versionadas, modelos de kit | COM-01/02, KIT-01/02/03 |
| `subscriptions` | Assinatura por cão, ração independente, ciclos por cobrança, cancelamento com corte | ASS-01/02/03, RAC-01/02, PET-03 |
| `curation` | Motor de regras determinístico, fila de revisão, aprovação, substituição, congelamento | CUR-01..04, KIT-04 |
| `orders` | Cotação no servidor, preço de assinante, frete por CEP, checkout idempotente | CHK-01/02/03, LOJ-02 |
| `payments` | Cliente Asaas, webhook autenticado e idempotente, estornos com alçada, conciliação | PAG-01/02/03 |
| `logistics` | Separação por cão, conferência, etiqueta única, expedição, ocorrências e reenvio | LOG-01/02/03 |
| `fiscal` | Documento fiscal por expedição (procedimento assistido), bloqueio de expedição | FIS-01/02 |
| `reviews` | Avaliação de SKU realmente entregue, uma por linha, histórico de edição | AVL-01/02 |
| `support` | Solicitações com protocolo e prazo (troca, cancelamento, LGPD) | VIL-03, PRV-02 |
| `core` | Auditoria, alertas operacionais, parâmetros, papéis, indicadores, exportação | ADM-01/02/03, MET-01 |

## Rodar localmente

### Com Docker (recomendado)

```bash
docker compose up --build
```

- Loja: http://localhost:8080
- Painel da equipe: http://localhost:8080/painel/
- API: http://localhost:8080/api/v1/ (saúde em `/api/health/`)

O primeiro `up` migra o banco, cria os papéis e popula dados de demonstração (`SEED_DEMO=1`).

| Usuário | Senha | Papel |
| --- | --- | --- |
| `admin@petvila.local` | `petvila123` | superusuário |
| `gestor@`, `curador@`, `operacao@`, `atendimento@`, `financeiro@petvila.local` | `petvila123` | papel do mesmo nome |
| `tutor@petvila.local` | `petvila123` | tutora com 2 cães (Paçoca: restrição frango; Thor: restrição látex) |

Sem `ASAAS_API_KEY`, o backend usa um **provedor simulado**: Pix, boleto e fatura são falsos e as telas de
pagamento mostram botões "Simular pagamento aprovado/vencido", que passam pelo mesmo processamento do webhook real.

Para zerar os dados: `docker compose down -v`.

### Sem Docker

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # ajuste DATABASE_URL para o seu Postgres
set -a; . ./.env; set +a
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --demo-approve
.venv/bin/python manage.py runserver
```

```bash
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxy para :8000)
```

```bash
cd mobile && npm install && cp .env.example .env && npx expo start
```

### Testes

```bash
cd backend && .venv/bin/pytest          # 41 testes, cobrindo os casos H01–H13
cd frontend && npm run typecheck && npm run build
cd mobile && npm run typecheck
```

## Asaas

1. Crie a conta sandbox em https://sandbox.asaas.com e gere a chave em *Integrações*.
2. Configure `ASAAS_API_KEY`, `ASAAS_ENV=sandbox` e um `ASAAS_WEBHOOK_TOKEN` longo e aleatório.
3. No painel Asaas, em *Integrações > Webhooks*, cadastre:
   - URL: `https://SEU-DOMINIO/api/v1/payments/asaas/webhook/`
   - Token de autenticação: o mesmo `ASAAS_WEBHOOK_TOKEN` (chega no header `asaas-access-token`)
   - Eventos de cobrança (`PAYMENT_*`).
4. Em produção, troque para a chave de produção e `ASAAS_ENV=production`.

Como a integração cumpre o PDR:

- **Meios aceitos** (regra de 13/11/2026): assinaturas de plano e ração recorrente só no **cartão de crédito**;
  compra avulsa da loja no **cartão de crédito ou Pix**. Boleto não é oferecido. O backend recusa outros meios
  com `billing_not_allowed`.
- **Cartão** é pago na fatura hospedada pelo Asaas (`invoiceUrl`): a PetVila nunca recebe nem guarda dados de cartão.
- **Assinaturas**: uma assinatura Asaas por cão (`cycle=MONTHLY`; ração `MONTHLY`/`BIMONTHLY`). Cada cobrança
  gerada vira um `Cycle` único (chave: ID da cobrança), então evento repetido não cria dois pedidos.
- **Webhook**: autenticado pelo token, deduplicado pelo ID do evento, nunca regride estado (evento atrasado é
  registrado e ignorado), liberação única com `SELECT FOR UPDATE`. Falhas viram alerta e podem ser
  reprocessadas no painel (*Eventos do provedor > Reprocessar*). O endpoint sempre responde 200 para eventos
  autênticos, para não travar a fila do Asaas.
- **Divergência de valor**, cobrança desconhecida, pagamento de pedido já cancelado e contestação viram itens na
  fila *Alertas operacionais* (tipo "Divergência financeira").
- **Estorno**: idempotente, limitado ao valor capturado, só papéis financeiro/gestor, com alçada configurável.
- **Cancelamento** antes do corte cancela a assinatura no Asaas; depois do corte define `endDate` para que o ciclo já
  processado seja cobrado e entregue, sem cobranças posteriores.
- **Pausa**: tenta inativar a assinatura no Asaas; se o provedor recusar, a pausa vira controle assistido com alerta
  para o operador (seção 7 do PDR). Precisa ser homologado no sandbox.

## Painel administrativo (`/painel/`)

Django Admin com a identidade da marca e ações próprias. Nenhuma tarefa usual exige editar código ou banco.

| Tarefa | Onde | Quem |
| --- | --- | --- |
| Criar/aprovar/publicar oferta (preço) | Planos e kits > Ofertas | gestor |
| Editar composição (rascunho → revisão → aprovada → publicada) | Planos e kits > Composições | operação prepara, curador aprova, gestor publica |
| Modelos de kit (até 5 ativos por plano, configurável) | Planos e kits > Modelos | curador/operação |
| Gerar sugestões, revisar, aprovar, rejeitar, reprocessar | Curadoria > Kits dos ciclos | curador |
| Substituir SKU (ruptura) | Curadoria > Linhas do kit | curador/operação |
| Fechar e reservar estoque | Curadoria > Kits dos ciclos | operação |
| Separar, conferir, etiqueta, expedir, entrega, ocorrência, devolução | Expedição | operação |
| Documento fiscal (procedimento assistido) | Expedição (inline) ou Fiscal | financeiro |
| Estorno | Pagamentos > Cobranças | financeiro (alçada) / gestor |
| Entrada, ajuste e inspeção de estoque | Estoque > Saldos | operação |
| Atendimento e LGPD | Atendimento > Solicitações | atendimento |
| Parâmetros (corte, janela de variedade, alçadas…) | Núcleo > Parâmetros operacionais | gestor |
| Auditoria e alertas | Núcleo | todos (leitura) |

A página inicial do painel mostra a rotina do dia (curadorias pendentes, kits a fechar, expedições abertas, alertas,
assinaturas ativas e receita recorrente). Exportação aberta com versão do esquema:
`GET /api/v1/ops/export/` (gestor/financeiro, auditada) ou `python manage.py export_operations --out arquivo.json`.

## Deploy na VPS

Requisitos: Docker + Docker Compose, portas 80/443 liberadas e DNS do domínio apontando para a VPS.

```bash
git clone <repo> /opt/petvila && cd /opt/petvila
cp .env.docker.example .env   # preencha DOMAIN, DJANGO_SECRET_KEY, POSTGRES_PASSWORD, ASAAS_*
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend python manage.py createsuperuser
```

- O Caddy emite e renova o certificado HTTPS do `DOMAIN` automaticamente.
- Em produção o backend recusa subir sem `DJANGO_SECRET_KEY` e sem `ASAAS_API_KEY` (não existe provedor simulado em produção).
- Backup diário: agende `deploy/backup.sh` no cron (mantém 14 dias em `backups/`). Ensaiar a restauração antes do
  lançamento (QAL-01): `gunzip -c backups/ARQUIVO.sql.gz | docker compose exec -T db psql -U petvila petvila`.
- Atualizar: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
  (migrações rodam na subida do backend).
- A rotina diária (pedidos expirados, cancelamentos agendados, sugestões de curadoria) roda no serviço `scheduler`.

## O que continua pendente (decisões de negócio do PDR)

O código implementa os comportamentos, mas não inventa regras comerciais. Antes de vender:

- **P01**: preço do Essential (a oferta v1 está sem preço e a publicação é bloqueada). O R$ 209,90 do Care é
  referência não oficial; só o seed com `--demo-approve` (ambiente local) o publica.
- **P02/P03/P10**: periodicidade final, fidelidade, data de corte (parâmetro `cutoff_days_before_billing`, hoje 5),
  frete, cupons, preço familiar, regras de preço de assinante. Carrinho misto: no MVP, loja, kit e ração são
  fluxos e cobranças separados.
- **P04**: campos obrigatórios do perfil (parâmetro `dog_required_fields`), janela de variedade (`variety_window_cycles`).
- **P07/P08**: homologar no sandbox Asaas os cenários aprovado, recusado, pendente, vencido, cancelado, estorno,
  pausa e cancelamento de recorrência. Emissão fiscal está como procedimento assistido.
- **P09**: transportadoras e regiões. As regiões de entrega são cadastradas no painel (seed: Grande São Paulo).
  Etiqueta e rastreio são registrados manualmente até a integração com transportador.
- Textos de privacidade e termos são bases para revisão jurídica.
- O PDR lista aplicativo nativo como fora da primeira entrega; o app em `mobile/` foi incluído a pedido e usa a
  mesma API.
