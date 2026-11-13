# PetVila Club

Este repositório tem duas partes:

- **E-commerce (plataforma própria)**: `backend/` (Django + Postgres + Asaas), `frontend/` (React), `mobile/` (React Native/Expo).
  Rodar com `docker compose up --build` e abrir http://localhost:8080. Guia completo: [`docs/ecommerce.md`](docs/ecommerce.md).
- **Landing de pré-lançamento** (Astro), descrita abaixo.

---

## Landing Page de pré-lançamento

Astro 7 + TypeScript, sem biblioteca de animação. Página estática com funções
serverless para o cadastro "Primeiros da Vila" (`/api/leads`) e o webhook do WhatsApp
(`/api/webhooks/whatsapp`).

Decisões, pendências e diagnóstico de domínio: [`docs/primeira-entrega.md`](docs/primeira-entrega.md).

## Rodar localmente

Requer Node 22.12+.

```sh
npm install
cp .env.example .env
npm run dev        # http://localhost:4321
```

Sem planilha configurada, os cadastros feitos em desenvolvimento vão para `.data/leads.jsonl`, e o CRM local (`/crm`, com `CRM_PASSWORD` no `.env`) lê esse arquivo.

## Scripts

| Comando | O que faz |
| --- | --- |
| `npm run dev` | Servidor de desenvolvimento |
| `npm run build` | Build de produção (saída em `.vercel/output`) |
| `npm run preview` | Serve o build localmente |
| `npm run check` | Checagem de tipos e de templates |
| `npm test` | Testes (Vitest) |

## Variáveis de ambiente

Veja `.env.example`. Prefixo `PUBLIC_` vai para o navegador; o resto fica só no servidor.
Em produção, configure no painel da hospedagem (nunca no repositório):

- `PUBLIC_APP_ENV=production` (fora disso a página sai com `noindex` e o robots bloqueia tudo)
- `PUBLIC_SITE_URL=https://petvilaclub.com.br`
- `LEADS_SHEETS_URL` e `LEADS_SHEETS_TOKEN` (planilha Google; instalação em `docs/primeira-entrega.md`, seção 12)
- `CRM_PASSWORD` e `CRM_SESSION_SECRET` (acesso a `/crm`)
- `WHATSAPP_*` (boas-vindas e webhook do WhatsApp; desligado com `WHATSAPP_ENABLED=false`). Veja [`docs/whatsapp.md`](docs/whatsapp.md)
- `PUBLIC_GA4_ID`, `PUBLIC_META_PIXEL_ID` (opcionais; só carregam depois que o visitante aceita o banner de cookies)

## Onde mexer

- Copy: `src/content/copy.ts`
- Instagram, contato, razão social: `src/config/site.ts`
- Logo oficial: salve em `src/assets/brand/logo-petvila.svg` (troca automática)
- Cores e fontes: `src/styles/global.css`
- Destino dos leads: `src/lib/leads/store.ts` e `integrations/google-sheets/Code.gs`
- CRM: `src/pages/crm/index.astro` e `src/scripts/crm.ts`
- Fotos provisórias: `src/content/photos.ts`
- Eventos de tracking: `src/lib/tracking.ts`
- WhatsApp (envio, webhook, status): `src/lib/whatsapp/` e `src/pages/api/webhooks/whatsapp.ts`
- Assets pendentes: procure por `<Placeholder` nos componentes

## Deploy (Vercel)

1. Importe o repositório na Vercel (framework detectado: Astro).
2. Configure as variáveis acima em Production e Preview.
3. Adicione os domínios; os redirects para `https://petvilaclub.com.br` já estão em `vercel.json`.
4. Altere o DNS na GoDaddy conforme a seção 11 do documento de entrega, **preservando os registros de e-mail do `.com`**.
