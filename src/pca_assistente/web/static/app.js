// PCA assistente — tema, toasts, situação do Chrome e acompanhamento da tarefa (registro ao vivo).
const PCA = (() => {
  const $ = s => document.querySelector(s);

  function toast(txt, tom) {
    const t = document.createElement('div');
    t.className = 'toast'; if (tom) t.dataset.tom = tom; t.textContent = txt;
    $('#toasts').appendChild(t); setTimeout(() => t.remove(), 5000);
  }

  async function post(url, corpo) {
    try {
      const r = await fetch(url, {method: 'POST', body: corpo || new FormData()});
      const j = await r.json().catch(() => ({}));
      return r.ok ? {ok: true, ...j} : {ok: false, erro: j.erro || ('Erro ' + r.status)};
    } catch (e) { return {ok: false, erro: 'O app não respondeu. Ele está aberto?'}; }
  }

  function situacao(c) {
    const el = $('#situacao'); if (!el || !c) return;
    const [tom, txt] = !c.chrome ? ['perigo', 'Chrome do assistente fechado']
      : c.login ? ['aten', 'Faça login no SIPAC'] : c.sipac ? ['ok', 'SIPAC aberto'] : ['aten', 'Abra o SIPAC no Chrome'];
    el.innerHTML = `<a class="pill" data-tom="${tom}" href="/configuracoes"><span class="luz" data-tom="${tom}"></span>${txt}</a>`;
  }

  let desde = 0, timer = null;
  function acompanhar(op = {}) {
    let estava = !!op.aoTerminar;  // tarefa recém-iniciada: pode terminar antes da primeira consulta
    const passo = async () => {
      let e;
      try { e = await (await fetch('/estado?desde=' + desde)).json(); } catch (_) { timer = setTimeout(passo, 3000); return; }
      situacao(e.chrome);
      const log = $('#log');
      if (log && e.linhas.length) {
        for (const l of e.linhas) { log.textContent += l.t + '\n'; desde = l.n; }
        log.scrollTop = log.scrollHeight;
      }
      const nome = $('#tarefa-nome'); if (nome) nome.textContent = e.nome || '';
      const prog = $('#prog');
      if (prog) {
        prog.hidden = !e.rodando;
        prog.classList.toggle('indet', !e.prog);
        if (e.prog) prog.querySelector('i').style.width = (100 * e.prog[0] / e.prog[1]) + '%';
      }
      const bb = $('#bt-buscar'), bp = $('#bt-parar');
      if (bb) bb.disabled = e.rodando;
      if (bp) { bp.hidden = !e.rodando; bp.disabled = e.parando; }
      const fim = $('#fim'); if (fim) fim.hidden = e.rodando || !e.tem_resultado || !!e.erro;
      if (estava && !e.rodando) {
        if (e.erro) toast(e.erro, 'perigo'); else if (e.resultado) toast(e.resultado, 'ok');
        if (op.aoTerminar) op.aoTerminar(e);
      }
      estava = e.rodando;
      timer = setTimeout(passo, e.rodando ? 700 : 3000);
    };
    clearTimeout(timer); passo();
  }

  // tema
  const bt = document.querySelector('[data-tema]');
  if (bt) bt.addEventListener('click', () => {
    const r = document.documentElement, escuro = r.getAttribute('data-theme') === 'dark'
      || (!r.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
    const novo = escuro ? 'light' : 'dark'; r.setAttribute('data-theme', novo);
    try { localStorage.setItem('tema', novo); } catch (_) {}
  });

  if (!document.querySelector('#log')) fetch('/estado').then(r => r.json()).then(e => situacao(e.chrome)).catch(() => {});
  return {toast, post, acompanhar};
})();
