// Tudo o que acontece no browser sem recarregar a página.
// Cada bloco é independente: se a página não tiver aquele elemento, o bloco não faz nada.

// Pede algo ao servidor. Se o caderno se bloqueou entretanto (15 minutos parado),
// o servidor responde com um redirecionamento; nesse caso vamos para a página da palavra-passe.
async function pedir(endereco, opcoes) {
  const resposta = await fetch(endereco, opcoes);
  if (resposta.redirected && resposta.url.includes("/desbloquear")) {
    window.location.href = resposta.url;
    throw new Error("Caderno bloqueado");
  }
  return resposta;
}

// ---------- 1. Pesquisa enquanto escreves (página inicial) ----------
const formPesquisa = document.getElementById("form-pesquisa");
const campoPesquisa = document.getElementById("campo-pesquisa");
const resultados = document.getElementById("resultados");

if (formPesquisa) {
  let temporizador;

  campoPesquisa.addEventListener("input", () => {
    // Espera 200 ms depois da última tecla, para não fazer um pedido por cada letra
    clearTimeout(temporizador);
    temporizador = setTimeout(async () => {
      // Junta o que está no formulário (texto e filtro de categoria): q=...&cat=...
      const parametros = new URLSearchParams(new FormData(formPesquisa));
      parametros.set("q", campoPesquisa.value.trim());
      if (!parametros.get("q")) parametros.delete("q");

      const resposta = await pedir("/pesquisa?" + parametros);
      resultados.innerHTML = await resposta.text();

      // Atualiza o endereço, para o F5 ou o botão "voltar" manterem a pesquisa
      const texto = parametros.toString();
      history.replaceState(null, "", texto ? "/?" + texto : "/");
    }, 200);
  });

  // Tecla "/" em qualquer sítio da página vai para a pesquisa
  document.addEventListener("keydown", (evento) => {
    const aEscrever = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
    if (evento.key === "/" && !aEscrever) {
      evento.preventDefault();
      campoPesquisa.focus();
      campoPesquisa.select();
    }
  });
}


// ---------- 2. Pedir confirmação antes de apagar ----------
// Qualquer formulário com data-confirmar="mensagem" passa por aqui.
const janela = document.getElementById("confirmacao");
let formularioPendente = null;

document.addEventListener("submit", (evento) => {
  const form = evento.target;
  if (!form.dataset.confirmar) return;

  // Pára o envio e mostra a janela com a mensagem do formulário
  evento.preventDefault();
  formularioPendente = form;
  document.getElementById("confirmacao-texto").textContent = form.dataset.confirmar;
  janela.showModal();
});

janela.addEventListener("close", () => {
  // returnValue é o "value" do botão em que carregaste
  if (janela.returnValue === "confirmar" && formularioPendente) {
    // form.submit() envia sem voltar a passar pelo evento "submit" acima
    formularioPendente.submit();
  }
  formularioPendente = null;
});


// ---------- 3. Mostrar a caixa "Nova categoria" ----------
document.addEventListener("change", (evento) => {
  const lista = evento.target;
  if (lista.name !== "categoria_id") return;

  const caixa = lista.parentElement.querySelector("[name=nova_categoria]");
  const nova = lista.value === "nova";
  caixa.classList.toggle("escondido", !nova);
  caixa.required = nova;
  if (nova) caixa.focus();
});


// ---------- 4. Alternar entre ver e editar ----------
// Botões com data-alternar trocam o bloco [data-editavel] mais próximo entre os dois modos.
document.addEventListener("click", (evento) => {
  const botao = evento.target.closest("[data-alternar]");
  if (!botao) return;

  const bloco = botao.closest("[data-editavel]");
  const aEditar = bloco.classList.toggle("a-editar");
  if (aEditar) {
    // Põe o cursor no primeiro campo e no fim do texto
    const campo = bloco.querySelector(".modo-editar textarea, .modo-editar input[type=text]");
    campo.focus();
    campo.setSelectionRange(campo.value.length, campo.value.length);
  }
});

// Escape cancela a edição
document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Escape") return;
  const bloco = document.activeElement.closest(".a-editar");
  if (bloco) bloco.classList.remove("a-editar");
});


// ---------- 5. Riscar tarefas sem recarregar a página ----------
document.addEventListener("change", async (evento) => {
  const caixa = evento.target;
  if (!caixa.closest(".form-feito")) return;

  const entrada = caixa.closest(".entrada");
  entrada.classList.toggle("feito", caixa.checked);
  atualizarContador();

  // Avisa o servidor. Se falhar, desfaz a mudança no ecrã.
  const resposta = await pedir(caixa.form.action, { method: "POST" }).catch(() => null);
  if (!resposta || !resposta.ok) {
    caixa.checked = !caixa.checked;
    entrada.classList.toggle("feito", caixa.checked);
    atualizarContador();
    alert("Não consegui guardar. A aplicação ainda está a correr?");
  }
});

function atualizarContador() {
  const contador = document.getElementById("contador-por-fazer");
  if (!contador) return;
  const total = document.querySelectorAll(".form-feito input:not(:checked)").length;
  contador.querySelector("span").textContent = total;
  contador.classList.toggle("escondido", total === 0);
}


// ---------- 6. Procurar o tema na web (página do tema) ----------
const botaoWeb = document.getElementById("botao-web");

if (botaoWeb) {
  const painel = document.getElementById("painel-web");
  const destino = document.getElementById("resultados-web");

  async function procurarNaWeb() {
    const lingua = painel.querySelector("[name=lingua]:checked").value;
    botaoWeb.disabled = true;
    destino.innerHTML = '<p class="painel-sub a-carregar">A procurar...</p>';
    try {
      const resposta = await pedir(painel.dataset.endereco + "?lingua=" + lingua);
      if (!resposta.ok) throw new Error("Erro no servidor");
      destino.innerHTML = await resposta.text();
    } catch (erro) {
      destino.innerHTML = '<p class="erro-texto">Não consegui procurar. A aplicação ainda está a correr?</p>';
    }
    botaoWeb.disabled = false;
  }

  botaoWeb.addEventListener("click", procurarNaWeb);
  // Mudar de língua depois de uma pesquisa repete-a logo nessa língua
  painel.addEventListener("change", (evento) => {
    if (evento.target.name === "lingua" && destino.innerHTML) procurarNaWeb();
  });
}


// ---------- 7. Ctrl+Enter guarda o texto que estás a escrever ----------
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && (evento.ctrlKey || evento.metaKey) && evento.target.tagName === "TEXTAREA") {
    evento.preventDefault();
    evento.target.form.requestSubmit();
  }
});
