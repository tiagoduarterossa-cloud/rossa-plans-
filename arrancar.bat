@echo off
rem Arranca o Caderno com um duplo clique (Windows).
rem Na primeira vez prepara o ambiente e instala o Flask; depois e so arrancar.

rem Vai para a pasta onde este ficheiro esta
cd /d "%~dp0"

rem 1. Descobrir o comando do Python ("py" e o lancador oficial no Windows)
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo Nao encontrei o Python neste computador.
  echo Instala-o em https://www.python.org/downloads/
  echo e na instalacao marca a opcao "Add python.exe to PATH".
  echo Depois volta a fazer duplo clique neste ficheiro.
  echo.
  pause
  exit /b 1
)

rem A encriptacao precisa do Python 3.11 ou mais recente
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 (
  echo.
  echo O teu Python e antigo. Precisas do 3.11 ou mais recente.
  echo Instala a versao atual em https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

rem 2. Criar o ambiente virtual, so na primeira vez
if not exist ".venv\Scripts\python.exe" (
  echo A preparar o ambiente pela primeira vez, pode demorar um minuto...
  %PY% -m venv .venv || goto erro
)

rem 3. Instalar o Flask (se ja estiver instalado, nao faz nada)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto erro

rem 4. Abrir o browser 3 segundos depois, para dar tempo ao servidor de arrancar
start "" cmd /c "timeout /t 3 >nul & start http://localhost:5000"

rem 5. Arrancar a aplicacao. Enquanto esta janela estiver aberta, a app funciona.
echo.
echo O Caderno esta a correr em http://localhost:5000
echo Para parar, fecha esta janela.
echo.
".venv\Scripts\python.exe" app.py
pause
exit /b 0

:erro
echo.
echo Algo correu mal. Le a mensagem acima e manda-ma.
pause
exit /b 1
