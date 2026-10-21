# Caderno pessoal

Aplicação local para guardar notas sobre vários temas. Escreves o nome de um tema
na barra de pesquisa e aparece tudo o que lá deixaste. Se o tema não existir,
podes criá-lo logo ali.

Corre só no teu computador. Não tem contas nem precisa de internet
(só para instalar o Flask da primeira vez).

## Arrancar pela primeira vez

Precisas do Python 3.9 ou mais recente. Abre um terminal na pasta do projeto.

1. Cria um ambiente virtual (uma pasta `.venv` com o Python e as bibliotecas deste projeto,
   separadas do resto do computador):

   ```
   python3 -m venv .venv
   ```

2. Ativa o ambiente virtual:

   - macOS / Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`

   O terminal passa a mostrar `(.venv)` no início da linha.

3. Instala o Flask:

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

## Onde ficam os dados

Tudo fica no ficheiro `caderno.db`, criado na pasta do projeto no primeiro arranque.
Se apagares esse ficheiro, perdes as tuas notas. Ele está no `.gitignore`,
por isso nunca é enviado para o GitHub.

## Organização do código

- `app.py` - o servidor: cada endereço (página) e o que acontece lá
- `base_dados.py` - tudo o que lê e escreve na base de dados
- `templates/` - o HTML das páginas
- `static/estilo.css` - o aspeto visual
