# PCA assistente: como usar

O PCA assistente busca no SIPAC as requisições de um grupo de material e monta a planilha do PCA no
Google Sheets. Ele **só lê** o SIPAC e **só escreve** na planilha do grupo. Antes de gravar, ele mostra
o que vai mudar e faz uma cópia de segurança.

## 1. Instalar (ou atualizar)
1. Extraia o arquivo `PCA-assistente-instalador.zip` numa pasta qualquer (botão direito → *Extrair tudo*).
2. Abra a pasta e clique duas vezes em **`instalar.cmd`**.
3. Aparece o atalho **PCA assistente** na Área de Trabalho.

Para atualizar, faça o mesmo com o arquivo novo. Suas configurações são mantidas.

## 2. Primeiro acesso (uma vez só)
1. Clique em **PCA assistente**. Abre uma janela do Chrome só do assistente, já no SIPAC.
2. **Faça login no SIPAC** nessa janela. O assistente nunca pede nem digita sua senha.
3. Na tela do assistente, abra **Configurações**:
   - **Conta Google:** escolha o arquivo `.json` da conta de serviço Google (recebido do responsável pela instalação) e clique em *Guardar*.
     Depois copie o e-mail que aparece.
   - **Planilha de cada grupo:** na planilha do grupo (cópia do MODELO), clique em *Compartilhar*
     e adicione o e-mail copiado como **Editor**. Em seguida, cole o link da planilha no assistente
     junto com o número do grupo e clique em *Guardar*. Por fim, clique em **Testar acesso**.

## 3. Uso
1. Clique em **PCA assistente** e confira se o SIPAC está logado (o selo no alto fica verde).
2. Em **Início**, informe o **grupo** (ex.: 3010) e o **ano da coleta** e clique em **Buscar no SIPAC**.
   Acompanhe o andamento. O botão **Parar** interrompe a busca.
3. Abra o **Resultado** e confira:
   - as **conferências**: os itens em vermelho precisam ser olhados antes de gravar;
   - quais requisições entraram e quais ficaram de fora, com o motivo;
   - a prévia da matriz e o resumo do que vai mudar.
4. Clique em **Gravar na planilha** e confirme. No fim, use **Abrir a planilha**.

## Bom saber
- Rodar de novo para o mesmo grupo e ano **refaz** a aba MAT do ano e as linhas do ano na REQ.
  A coluna OBSERVAÇÃO (na REQ e na MAT) e as colunas manuais do CATÁLOGO são mantidas.
- Códigos que não estão no CATÁLOGO são incluídos no fim com a observação
  “INCLUÍDO PELO PCA ASSISTENTE – CONFERIR”.
- As cópias de segurança ficam em abas ocultas chamadas, por exemplo, `MAT26 (antes 2026-11-12 14h05)`.
  São mantidas as 3 últimas. Para ver essas abas no Google Sheets, use *Ver → Páginas ocultas*.
- Mensagem “faça login no SIPAC”: a sessão expirou. Faça login de novo na janela do assistente e repita.
- Não use outro robô do SIPAC ao mesmo tempo com o mesmo login.
