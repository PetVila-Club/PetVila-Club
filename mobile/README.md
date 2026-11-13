# PetVila Club · app (Expo)

App React Native que usa a mesma API do site (`/api/v1`, JWT). Telas: planos, loja, produto, carrinho e checkout,
assinatura de plano por cão, pagamento (Pix copia e cola, boleto/fatura e cartão na página segura do Asaas) e Minha Vila
(cães, assinaturas com pausa/cancelamento, entregas com avaliação, pedidos).

```bash
npm install
cp .env.example .env    # EXPO_PUBLIC_API_URL apontando para o backend
npx expo start          # abra no Expo Go ou em um emulador
```

- Expo SDK 58. Para novas dependências nativas use `npx expo install <pacote>`.
- Tokens ficam no SecureStore (Keychain/Keystore).
- Cadastro de cães e endereços é feito no site nesta primeira versão; o app lista e usa os cadastrados.
- Builds de loja: configure o EAS (`npx eas build`) com os identificadores `br.com.petvilaclub.app` de `app.json`.
