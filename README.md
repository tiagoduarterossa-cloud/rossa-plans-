# Caderno pessoal

Aplicação local para guardar notas sobre vários temas. Escreves o nome de um tema
na barra de pesquisa e aparece tudo o que lá deixaste. Se o tema não existir,
podes criá-lo logo ali.

Corre só no teu computador e fica encriptado no disco, protegido por uma palavra-passe.
A internet só é usada para instalar as bibliotecas da primeira vez e, se quiseres,
para procurar o nome de um tema na Wikipédia.

## Windows: duplo clique

Faz duplo clique em `arrancar.bat`. Na primeira vez prepara tudo sozinho
(precisa de internet só para instalar as bibliotecas) e depois abre o browser em
<http://localhost:5000>. A app funciona enquanto a janela preta estiver aberta.
Para parar, fecha essa janela.

Se o Windows mostrar "O Windows protegeu o seu PC", carrega em "Mais informações"
e depois em "Executar mesmo assim".

## Arrancar à mão, pelo terminal

Precisas do Python 3.11 ou mais recente. Abre um terminal na pasta do projeto.

1. Cria um ambiente virtual (uma pasta `.venv` com o Python e as bibliotecas deste projeto,
   separadas do resto do computador):

   ```
   python3 -m venv .venv
   ```

2. Ativa o ambiente virtual:

   - macOS / Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`

   O terminal passa a mostrar `(.venv)` no início da linha.

3. Instala as bibliotecas (Flask e cryptography):

   ```
   pip install -r requirements.txt
   ```

4. Arranca a aplicação:

   ```
   python app.py
   ```

5. Abre <http://localhost:5000> no browser.

Para parar, carrega em `Ctrl+C` no terminal.

## Das vezes seguintes

Só os passos 2, 4 e 5: ativar o ambiente, `python app.py` e abrir o browser.

## Problemas comuns

- **No Mac, a porta 5000 já está ocupada** ("Address already in use"): é o Recetor AirPlay.
  Desliga-o em Definições do Sistema > Geral > AirDrop e Handoff, ou muda `port=5000`
  para `port=5001` no fim do `app.py` e abre <http://localhost:5001>.

## Onde ficam os dados e a encriptação

Tudo fica no ficheiro `caderno.cofre`, na pasta do projeto, encriptado com a tua
palavra-passe (AES, através da biblioteca `cryptography`). Quando desbloqueias,
o caderno é desencriptado só para a memória do computador; a versão legível nunca
é escrita no disco.

- **Não há recuperação.** Sem a palavra-passe, ninguém abre o cofre.
- O caderno bloqueia sozinho ao fim de 15 minutos sem uso, ou quando carregas em Bloquear.
- Se vieres das versões anteriores, o `caderno.db` antigo passa para dentro do cofre
  na primeira vez e é renomeado para `caderno-antigo-NAO-ENCRIPTADO.db`. A página inicial
  lembra-te de o apagar quando confirmares que está tudo lá.
- Faz cópias do `caderno.cofre` (por exemplo para uma pen). Estão encriptadas, por isso
  podes guardá-las onde quiseres.
- Nenhum destes ficheiros vai para o GitHub (estão no `.gitignore`).

## Ligações e pesquisa na web

- **Ligações** (painel na página de cada tema): compara o tema com todos os outros e mostra
  o que têm em comum. Corre tudo no teu computador, sem internet.
- **Na web**: procura o nome do tema na Wikipédia (português, inglês ou alemão) e marca
  as palavras dos artigos que também estão nas tuas notas. Só é enviado o nome do tema,
  e só quando carregas em Procurar. As tuas notas nunca saem do computador.

## Organização do código

- `app.py` - o servidor: cada endereço (página) e o que acontece lá
- `base_dados.py` - tudo o que lê e escreve na base de dados
- `cofre.py` - a encriptação e a palavra-passe
- `ligacoes.py` - o "mentalista" que encontra ligações entre temas
- `web.py` - a pesquisa na Wikipédia
- `templates/` - o HTML das páginas
  - `base.html` - a moldura comum (avisos e janela de confirmação)
  - `inicio.html` e `_resultados.html` - pesquisa, filtros e lista de temas
  - `tema.html` e `_web.html` - a página de um tema, as ligações e a pesquisa na web
  - `categorias.html` - criar, mudar e apagar categorias
  - `desbloquear.html` - a palavra-passe
  - `_componentes.html` - peças reutilizáveis (ícones, etiquetas, escolha de categoria)
- `static/estilo.css` - o aspeto visual
- `static/app.js` - o que acontece no browser sem recarregar a página

## Atalhos de teclado

- `/` na página inicial vai para a pesquisa
- `Ctrl+Enter` guarda o texto que estás a escrever
- `Esc` cancela uma edição
