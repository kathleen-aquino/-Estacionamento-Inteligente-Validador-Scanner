"""R6 — Interface gráfica do Estacionamento Inteligente.

Feita só com tkinter (já vem com o Python, não precisa instalar nada).

    python interface.py      ou      python main.py --gui

Páginas:
  • Validadores — digita uma placa/horário e vê o AFD sendo percorrido, passo a passo.
  • Scanner     — editor com cores por tipo de token, tabela de tokens e erros com dica.
  • Cancela     — diagrama da máquina de estados ao vivo + botões de eventos.
"""
import io
import math
import tkinter as tk
from contextlib import redirect_stdout
from tkinter import ttk, font as tkfont

from cancela import MaquinaEstados, TRANSICOES_CANCELA
from conectado import eventos_do_roteiro, ROTEIRO_CANCELA
from scanner import scanner, ROTEIRO_OK, ROTEIRO_MUNCH, ROTEIRO_ERROS
from validadores import afd_placa, afd_hora

# ------------------------------------------------------------------ tema (asfalto + faixa amarela)
C = {
    "bg": "#121418", "lateral": "#0c0d10", "painel": "#1a1d23", "painel2": "#23272f",
    "linha": "#30353f", "texto": "#e8e9ec", "fraco": "#8b919c", "apagado": "#565c67",
    "destaque": "#f5c518", "destaque2": "#ffd84d", "destaque_fundo": "#3a3216",
    "ok": "#3ecf8e", "ok_fundo": "#13332a", "erro": "#ff5c5c", "erro_fundo": "#3a1b1e",
    "info": "#5aa9ff",
}
COR_TOKEN = {
    "RESERVADA": C["destaque"], "PLACA": "#5aa9ff", "HORA": "#c792ea", "VAGA_ID": "#4dd0e1",
    "IDENT": "#e8e9ec", "INTEIRO": "#ff9e64", "REAL": "#ff9e64", "ATRIB": "#f78cb4",
    "OP_REL": "#f78cb4", "NOVA_LINHA": C["apagado"], "EOF": C["apagado"],
}
F = {}   # fontes, preenchidas depois que a janela existe


def preparar_fontes():
    familias = set(tkfont.families())
    ui = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "DejaVu Sans")
               if f in familias), "TkDefaultFont")
    mono = next((f for f in ("Cascadia Mono", "Consolas", "Menlo", "JetBrains Mono",
                             "DejaVu Sans Mono", "Courier New") if f in familias), "TkFixedFont")
    F.update({
        "titulo": (ui, 18, "bold"), "subtitulo": (ui, 10), "secao": (ui, 9, "bold"),
        "texto": (ui, 10), "botao": (ui, 10, "bold"), "nav": (ui, 11), "nav_ativo": (ui, 11, "bold"),
        "logo": (ui, 11, "bold"), "grande": (ui, 16, "bold"), "enorme": (ui, 22, "bold"),
        "mono": (mono, 10), "mono_m": (mono, 11), "mono_g": (mono, 20, "bold"),
        "no": (mono, 10, "bold"), "rotulo": (mono, 9),
    })


def capturar(func, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        resultado = func(*args)
    return resultado, buf.getvalue()


# ------------------------------------------------------------------ componentes
class Botao(tk.Label):
    """Botão plano (tk.Label) para ter a mesma cara em Windows, Linux e macOS."""
    ESTILOS = {
        "primario": ("destaque", "bg", "destaque2"),
        "secundario": ("painel2", "texto", "linha"),
        "fantasma": ("painel", "fraco", "painel2"),
    }

    def __init__(self, pai, texto, comando, estilo="primario", **kw):
        bg, fg, hover = (C[k] for k in self.ESTILOS[estilo])
        super().__init__(pai, text=texto, bg=bg, fg=fg, cursor="hand2",
                         padx=kw.pop("padx", 14), pady=kw.pop("pady", 7),
                         font=kw.pop("font", F["botao"]), **kw)
        self._bg, self._hover, self.comando = bg, hover, comando
        self.bind("<Enter>", lambda e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))
        self.bind("<Button-1>", lambda e: self.comando())

    def cores(self, bg, fg, hover):
        self._bg, self._hover = bg, hover
        self.configure(bg=bg, fg=fg)


def rotulo_secao(pai, texto, bg=None):
    return tk.Label(pai, text=texto.upper(), font=F["secao"], fg=C["fraco"],
                    bg=bg or C["painel"], anchor="w")


def cartao(pai, **kw):
    return tk.Frame(pai, bg=C["painel"], highlightthickness=1,
                    highlightbackground=C["linha"], **kw)


def caixa_texto(pai, **kw):
    t = tk.Text(pai, bg=C["painel"], fg=C["texto"], insertbackground=C["destaque"],
                relief="flat", highlightthickness=0, font=kw.pop("font", F["mono"]),
                padx=10, pady=8, wrap=kw.pop("wrap", "none"), width=kw.pop("width", 10),
                selectbackground=C["destaque_fundo"], **kw)
    return t


def com_rolagem(pai, widget_cls, **kw):
    moldura = tk.Frame(pai, bg=C["painel"])
    w = widget_cls(moldura, **kw)
    barra = ttk.Scrollbar(moldura, orient="vertical", command=w.yview, style="Escuro.Vertical.TScrollbar")
    w.configure(yscrollcommand=barra.set)
    barra.pack(side="right", fill="y")
    w.pack(side="left", fill="both", expand=True)
    return moldura, w


# ------------------------------------------------------------------ desenho de grafos
def _corte(no, ux, uy):
    """Distância do centro até a borda do nó na direção (ux, uy)."""
    if no["forma"] == "circulo":
        return no["r"]
    a, b = no["a"], no["b"]
    return a * b / math.sqrt((b * ux) ** 2 + (a * uy) ** 2 or 1)


def seta(cv, n1, n2, rotulo="", curva=0, cor=None, largura=1.6, cor_rotulo=None, tracejado=None,
         t=0.5, lado=None, dist=13):
    cor = cor or C["apagado"]
    x1, y1, x2, y2 = n1["x"], n1["y"], n2["x"], n2["y"]
    d = math.hypot(x2 - x1, y2 - y1) or 1
    ux, uy = (x2 - x1) / d, (y2 - y1) / d
    nx, ny = -uy, ux
    cx, cy = (x1 + x2) / 2 + nx * curva, (y1 + y2) / 2 + ny * curva

    def direcao(px, py, qx, qy):
        vx, vy = qx - px, qy - py
        l = math.hypot(vx, vy) or 1
        return vx / l, vy / l

    a1 = direcao(x1, y1, cx, cy)
    a2 = direcao(x2, y2, cx, cy)
    sx, sy = x1 + a1[0] * _corte(n1, *a1), y1 + a1[1] * _corte(n1, *a1)
    ex, ey = x2 + a2[0] * (_corte(n2, *a2) + 2), y2 + a2[1] * (_corte(n2, *a2) + 2)
    opcoes = dict(fill=cor, width=largura, arrow="last", arrowshape=(10, 12, 4))
    if tracejado:
        opcoes["dash"] = tracejado
    if curva:
        cv.create_line(sx, sy, cx, cy, ex, ey, smooth=True, **opcoes)
    else:
        cv.create_line(sx, sy, ex, ey, **opcoes)
    if rotulo:
        mx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t ** 2 * ex
        my = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t ** 2 * ey
        if lado is None:
            lado = 1 if curva > 0 else -1
            if curva == 0 and ny < 0:
                lado = 1
        lx, ly = mx + nx * dist * lado, my + ny * dist * lado
        ancora = "center"
        if abs(nx) > 0.7:
            ancora = "w" if nx * lado > 0 else "e"
        txt = cv.create_text(lx, ly, text=rotulo, fill=cor_rotulo or C["fraco"], font=F["rotulo"],
                           anchor=ancora, justify="center", tags="rotulo")
        caixa = cv.bbox(txt)
        r = cv.create_rectangle(caixa[0] - 3, caixa[1] - 1, caixa[2] + 3, caixa[3] + 1,
                                fill=C["painel"], outline="", tags="rotulo")
        cv.tag_raise(txt, r)


def desenhar_no(cv, no, texto, fundo, borda, cor_texto, duplo=False, largura=2):
    x, y = no["x"], no["y"]
    if no["forma"] == "circulo":
        r = no["r"]
        cv.create_oval(x - r, y - r, x + r, y + r, fill=fundo, outline=borda, width=largura)
        if duplo:
            cv.create_oval(x - r + 4, y - r + 4, x + r - 4, y + r - 4, outline=borda, width=1.5)
    else:
        a, b = no["a"], no["b"]
        cv.create_oval(x - a, y - b, x + a, y + b, fill=fundo, outline=borda, width=largura)
    cv.create_text(x, y, text=texto, fill=cor_texto, font=F["no"])


# ------------------------------------------------------------------ página: validadores
DIGITOS = {"0-1": "01", "2": "2", "3": "3", "4-5": "45", "6-9": "6789"}

LAYOUT_AFD = {
    "AFD_PLACA": ({"p0": (0, 0), "p1": (1, 0), "p2": (2, 0), "p3": (3, 0), "p4": (4, 0),
                   "p5": (5, 0), "p7": (6, 0), "p8": (7, 0), "p9": (8, 0), "p6": (4.5, 1)}, 9),
    "AFD_HORARIO": ({"h0": (0, 0.5), "h1": (1, 0), "h2": (1, 1), "h3": (2, 0.5),
                     "h4": (3, 0.5), "h5": (4, 0.5), "h6": (5, 0.5)}, 6),
}


def rotulo_classes(classes):
    """Junta classes de dígitos num intervalo legível: ['0-1','2','3'] → '0-3'."""
    if all(c in DIGITOS for c in classes):
        ds = sorted("".join(DIGITOS[c] for c in classes))
        if [int(d) for d in ds] == list(range(int(ds[0]), int(ds[-1]) + 1)):
            return ds[0] if len(ds) == 1 else f"{ds[0]}-{ds[-1]}"
    return ", ".join(classes)


def simular(afd, w):
    """Mesma lógica de AFD.rodar(), mas devolve os passos para a animação."""
    passos, q = [], afd.inicial
    for i, c in enumerate(w):
        cl = afd.classe(c)
        prox = afd.delta.get((q, cl))
        passos.append((i, c, cl, q, prox))
        if prox is None:
            return passos, False, f"morreu no meio: δ({q}, {cl or 'fora de Σ'}) não existe"
        q = prox
    if q in afd.finais:
        return passos, True, f"terminou em {q} ∈ F"
    extra = afd.descricao.get(q, "")
    vazio = "palavra vazia: " if not w else ""
    return passos, False, f"{vazio}terminou em {q} ∉ F" + (f" ({extra})" if extra else "")


class PaginaValidadores(tk.Frame):
    def __init__(self, pai):
        super().__init__(pai, bg=C["bg"])
        self.afd = afd_placa
        self.anim = None
        self.passos, self.k, self.aceitou, self.motivo = [], 0, None, ""

        topo = tk.Frame(self, bg=C["bg"])
        topo.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(topo, text="Validadores", font=F["titulo"], fg=C["texto"], bg=C["bg"]).pack(anchor="w")
        tk.Label(topo, text="Digite uma placa ou um horário e acompanhe o AFD lendo cada caractere.",
                 font=F["subtitulo"], fg=C["fraco"], bg=C["bg"]).pack(anchor="w")

        # --- linha de entrada
        linha = tk.Frame(self, bg=C["bg"])
        linha.pack(fill="x", padx=24, pady=(14, 6))
        seg = tk.Frame(linha, bg=C["painel2"])
        seg.pack(side="left")
        self.b_placa = Botao(seg, "Placa", lambda: self.trocar(afd_placa), "secundario", padx=18)
        self.b_hora = Botao(seg, "Horário", lambda: self.trocar(afd_hora), "secundario", padx=18)
        self.b_placa.pack(side="left")
        self.b_hora.pack(side="left")

        moldura = tk.Frame(linha, bg=C["painel2"], highlightthickness=2,
                           highlightbackground=C["linha"], highlightcolor=C["destaque"])
        moldura.pack(side="left", padx=12)
        self.entrada = tk.Entry(moldura, font=F["mono_g"], width=14, bg=C["painel2"], fg=C["texto"],
                                insertbackground=C["destaque"], relief="flat", highlightthickness=0)
        self.entrada.pack(padx=10, pady=4)
        self.entrada.bind("<Return>", lambda e: self.validar())
        Botao(linha, "Validar  ▶", self.validar, pady=10).pack(side="left")
        Botao(linha, "↻ Repetir", lambda: self.validar(), "fantasma", pady=10).pack(side="left", padx=6)

        self.chips = tk.Frame(self, bg=C["bg"])
        self.chips.pack(fill="x", padx=24, pady=(2, 10))

        # --- resultado + fita
        res = cartao(self)
        res.pack(fill="x", padx=24)
        self.selo = tk.Label(res, font=F["enorme"], bg=C["painel"], width=11, anchor="w")
        self.selo.pack(side="left", padx=(16, 8), pady=12)
        info = tk.Frame(res, bg=C["painel"])
        info.pack(side="left", fill="x", expand=True)
        self.motivo_lbl = tk.Label(info, font=F["texto"], fg=C["fraco"], bg=C["painel"], anchor="w")
        self.motivo_lbl.pack(fill="x")
        self.fita = tk.Canvas(info, height=46, bg=C["painel"], highlightthickness=0)
        self.fita.pack(fill="x", pady=(4, 6))

        # --- diagrama
        cd = cartao(self)
        cd.pack(fill="x", padx=24, pady=10)
        cab = tk.Frame(cd, bg=C["painel"])
        cab.pack(fill="x", padx=14, pady=(10, 0))
        self.titulo_diag = rotulo_secao(cab, "")
        self.titulo_diag.pack(side="left")
        self.legenda = tk.Label(cab, font=F["texto"], fg=C["fraco"], bg=C["painel"])
        self.legenda.pack(side="right")
        self.diag = tk.Canvas(cd, height=250, bg=C["painel"], highlightthickness=0)
        self.diag.pack(fill="x", padx=6, pady=(0, 6))
        self.diag.bind("<Configure>", lambda e: self.desenhar())

        # --- rastreamento + tabela δ
        baixo = tk.Frame(self, bg=C["bg"])
        baixo.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        esq, dir_ = cartao(baixo), cartao(baixo)
        esq.pack(side="left", fill="both", expand=True, padx=(0, 6))
        dir_.pack(side="left", fill="both", expand=True, padx=(6, 0))
        rotulo_secao(esq, "rastreamento — rodar()").pack(fill="x", padx=14, pady=(10, 0))
        m, self.trace = com_rolagem(esq, caixa_texto, height=8, wrap="word")
        m.pack(fill="both", expand=True, padx=4, pady=4)
        rotulo_secao(dir_, "tabela de transição — tabela()").pack(fill="x", padx=14, pady=(10, 0))
        m, self.tab = com_rolagem(dir_, caixa_texto, height=8)
        m.pack(fill="both", expand=True, padx=4, pady=4)
        for t in (self.trace, self.tab):
            t.tag_configure("ok", foreground=C["ok"])
            t.tag_configure("erro", foreground=C["erro"])
            t.tag_configure("fraco", foreground=C["fraco"])
            t.tag_configure("dest", foreground=C["destaque"])
            t.tag_configure("linha_atual", background=C["destaque_fundo"], foreground=C["destaque"])
            t.tag_configure("linha_visitada", background=C["painel2"])

        self.trocar(afd_placa, "BRA2E19")

    # ---- ações
    def trocar(self, afd, palavra=None):
        self.afd = afd
        ativo, inativo = (self.b_placa, self.b_hora) if afd is afd_placa else (self.b_hora, self.b_placa)
        ativo.cores(C["destaque"], C["bg"], C["destaque2"])
        inativo.cores(C["painel2"], C["fraco"], C["linha"])
        self.titulo_diag.configure(text=f"{afd.nome} — {len(afd.estados)} estados")
        for w in self.chips.winfo_children():
            w.destroy()
        tk.Label(self.chips, text="exemplos:", font=F["texto"], fg=C["fraco"], bg=C["bg"]).pack(side="left")
        if afd is afd_placa:
            exemplos = [("ABC-1234", True), ("BRA2E19", True), ("BRA-2E19", False), ("ABC-123", False), ("ABC1234", False)]
        else:
            exemplos = [("08:15", True), ("23:59", True), ("24:00", False), ("12:5", False), ("12:60", False)]
        exemplos.append(("", False))
        for w, ok in exemplos:
            b = Botao(self.chips, w or "ε (vazia)", lambda w=w: self.usar(w), "secundario",
                      padx=10, pady=3, font=F["mono"])
            b.cores(C["painel2"], C["ok"] if ok else C["erro"], C["linha"])
            b.pack(side="left", padx=3)
        self.usar(palavra if palavra is not None else exemplos[0][0])

    def usar(self, w):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, w)
        self.validar()

    def validar(self):
        if self.anim:
            self.after_cancel(self.anim)
        w = self.entrada.get()
        self.palavra = w
        self.passos, self.aceitou, self.motivo = simular(self.afd, w)
        self.k = 0
        self.selo.configure(text="lendo…", fg=C["fraco"])
        self.motivo_lbl.configure(text="")
        self.trace.delete("1.0", "end")
        self.trace.insert("end", f"{self.afd.nome}: rodar({w!r})\n", "fraco")
        self.trace.insert("end", f"início em {self.afd.inicial}\n", "fraco")
        self.passo()

    def passo(self):
        self.desenhar()
        if self.k < len(self.passos):
            i, c, cl, q, prox = self.passos[self.k]
            rot = cl or "fora de Σ"
            if prox is None:
                self.trace.insert("end", f"[{i}] {c!r:5} {rot:9} δ({q}, {rot}) indefinida → MORREU\n", "erro")
            else:
                self.trace.insert("end", f"[{i}] {c!r:5} {rot:9} δ({q}, {cl}) = {prox}\n")
            self.trace.see("end")
            self.k += 1
            self.anim = self.after(280, self.passo)
        else:
            self.anim = None
            ok = self.aceitou
            self.selo.configure(text="✔ ACEITA" if ok else "✘ REJEITADA", fg=C["ok"] if ok else C["erro"])
            self.motivo_lbl.configure(text=self.motivo, fg=C["ok"] if ok else C["erro"])
            self.trace.insert("end", f"⇒ {'ACEITA' if ok else 'REJEITADA'}: {self.motivo}\n", "ok" if ok else "erro")
            self.desenhar()

    # ---- desenho
    def estado_atual(self):
        q, visitados, arestas, morte = self.afd.inicial, {self.afd.inicial}, set(), None
        for (i, c, cl, de, prox) in self.passos[:self.k]:
            if prox is None:
                morte = (de, cl)
                break
            arestas.add((de, prox))
            q = prox
            visitados.add(q)
        return q, visitados, arestas, morte

    def desenhar(self):
        self.desenhar_fita()
        self.desenhar_tabela()
        cv, afd = self.diag, self.afd
        cv.delete("all")
        W = max(cv.winfo_width(), 600)
        pos, colunas = LAYOUT_AFD[afd.nome]
        margem, r = 60, 22
        passo_x = (W - 2 * margem) / (colunas - 1)
        nos = {q: {"x": margem + x * passo_x, "y": 60 + y * 115, "forma": "circulo", "r": r}
               for q, (x, y) in pos.items()}
        atual, visitados, percorridas, morte = self.estado_atual()
        terminou = self.k >= len(self.passos)
        self.legenda.configure(text=f"estado atual: {atual} — {afd.descricao.get(atual, '')}"
                                    f"     classes: {'  '.join(afd.classes)}")

        agrupadas = {}
        for (q, cl), p in afd.delta.items():
            agrupadas.setdefault((q, p), []).append(cl)
        for (q, p), cls in agrupadas.items():
            usada = (q, p) in percorridas
            seta(cv, nos[q], nos[p], rotulo_classes(cls), 0,
                 cor=C["destaque"] if usada else C["apagado"], largura=2.4 if usada else 1.4,
                 cor_rotulo=C["destaque"] if usada else C["fraco"])
        ini = nos[afd.inicial]
        cv.create_line(ini["x"] - r - 34, ini["y"], ini["x"] - r - 2, ini["y"], arrow="last",
                       fill=C["fraco"], width=1.6, arrowshape=(10, 12, 4))

        if morte:
            n = nos[morte[0]]
            x0, y0 = n["x"] + r * 0.72, n["y"] + r * 0.72
            cv.create_line(x0, y0, x0 + 26, y0 + 26, fill=C["erro"], width=2, dash=(4, 3), arrow="last")
            cv.create_text(x0 + 30, y0 + 30, text=f"✘ {morte[1] or 'fora de Σ'}: sem transição",
                           fill=C["erro"], font=F["rotulo"], anchor="w")

        for q, n in nos.items():
            final = q in afd.finais
            if q == atual and terminou:
                cor = C["ok"] if self.aceitou else C["erro"]
                desenhar_no(cv, n, q, cor, cor, C["bg"], final, 3)
            elif q == atual:
                desenhar_no(cv, n, q, C["destaque"], C["destaque"], C["bg"], final, 3)
            elif q in visitados:
                desenhar_no(cv, n, q, C["destaque_fundo"], C["destaque"], C["destaque"], final)
            else:
                desenhar_no(cv, n, q, C["painel2"], C["linha"], C["fraco"], final)

    def desenhar_fita(self):
        cv = self.fita
        cv.delete("all")
        w = getattr(self, "palavra", "")
        if not w:
            cv.create_text(4, 23, text="ε  (palavra vazia)", fill=C["fraco"], font=F["mono_m"], anchor="w")
            return
        tam = 32
        for i, c in enumerate(w):
            x = 2 + i * (tam + 4)
            if i < self.k:
                morreu = self.passos[i][4] is None
                fundo, borda, cor = (C["erro_fundo"], C["erro"], C["erro"]) if morreu else \
                                    (C["destaque_fundo"], C["destaque"], C["destaque"])
            elif i == self.k and self.k < len(self.passos):
                fundo, borda, cor = C["destaque"], C["destaque"], C["bg"]
            else:
                fundo, borda, cor = C["painel2"], C["linha"], C["fraco"]
            cv.create_rectangle(x, 4, x + tam, 4 + tam, fill=fundo, outline=borda, width=1.5)
            cv.create_text(x + tam / 2, 4 + tam / 2, text=c if c != " " else "␣", fill=cor, font=F["mono_m"])

    def desenhar_tabela(self):
        _, saida = capturar(self.afd.tabela)
        atual, visitados, _, _ = self.estado_atual()
        t = self.tab
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", saida)
        for idx, q in enumerate(self.afd.estados):
            linha = 4 + idx
            if q == atual:
                t.tag_add("linha_atual", f"{linha}.0", f"{linha}.end")
            elif q in visitados:
                t.tag_add("linha_visitada", f"{linha}.0", f"{linha}.end")
        t.tag_add("fraco", "1.0", "3.end")
        t.configure(state="disabled")


# ------------------------------------------------------------------ página: scanner
EXEMPLOS_SCANNER = [("Válido", ROTEIRO_OK), ("Maximal Munch", ROTEIRO_MUNCH),
                    ("Com erros", ROTEIRO_ERROS), ("Roteiro da cancela", ROTEIRO_CANCELA)]


class PaginaScanner(tk.Frame):
    def __init__(self, pai, app):
        super().__init__(pai, bg=C["bg"])
        self.app = app
        self.agendado = None
        self.tokens, self.erros = [], []

        topo = tk.Frame(self, bg=C["bg"])
        topo.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(topo, text="Scanner", font=F["titulo"], fg=C["texto"], bg=C["bg"]).pack(anchor="w")
        tk.Label(topo, text="Escreva comandos do estacionamento. Os tokens são coloridos enquanto você digita; "
                            "clique num erro para ir até ele.",
                 font=F["subtitulo"], fg=C["fraco"], bg=C["bg"]).pack(anchor="w")

        chips = tk.Frame(self, bg=C["bg"])
        chips.pack(fill="x", padx=24, pady=(12, 8))
        tk.Label(chips, text="carregar:", font=F["texto"], fg=C["fraco"], bg=C["bg"]).pack(side="left")
        for nome, texto in EXEMPLOS_SCANNER:
            Botao(chips, nome, lambda t=texto: self.carregar(t), "secundario", padx=10, pady=3).pack(side="left", padx=3)
        Botao(chips, "Executar na cancela  ▶", self.executar, pady=5).pack(side="right")

        corpo = tk.Frame(self, bg=C["bg"])
        corpo.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        corpo.columnconfigure(0, weight=3, uniform="col")
        corpo.columnconfigure(1, weight=2, uniform="col")
        corpo.rowconfigure(0, weight=3, uniform="linha")   # roteiro
        corpo.rowconfigure(1, weight=2, uniform="linha")   # erros léxicos: nunca fica espremido

        # editor com numeração de linhas
        ed = cartao(corpo)
        ed.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        rotulo_secao(ed, "roteiro").pack(fill="x", padx=14, pady=(10, 2))
        area = tk.Frame(ed, bg=C["painel"])
        area.pack(fill="both", expand=True, padx=4, pady=4)
        self.numeros = tk.Text(area, width=4, bg=C["painel"], fg=C["apagado"], relief="flat",
                               font=F["mono_m"], padx=6, pady=8, highlightthickness=0, takefocus=0)
        self.numeros.pack(side="left", fill="y")
        barra = ttk.Scrollbar(area, orient="vertical", style="Escuro.Vertical.TScrollbar")
        barra.pack(side="right", fill="y")
        self.editor = caixa_texto(area, font=F["mono_m"], undo=True, height=10)
        self.editor.pack(side="left", fill="both", expand=True)

        def rolar(*a):
            barra.set(*a)
            self.numeros.yview_moveto(a[0])
        self.editor.configure(yscrollcommand=rolar)
        barra.configure(command=self.editor.yview)
        for tipo, cor in COR_TOKEN.items():
            self.editor.tag_configure(tipo, foreground=cor)
        self.editor.tag_configure("RESERVADA", foreground=C["destaque"], font=F["mono_m"] + ("bold",))
        self.editor.tag_configure("comentario", foreground=C["apagado"])
        self.editor.tag_configure("erro", background=C["erro_fundo"], foreground=C["erro"], underline=True)
        self.editor.tag_configure("foco", background=C["destaque_fundo"])
        self.editor.bind("<<Modified>>", self.ao_editar)

        # tokens
        tk_ = cartao(corpo)
        tk_.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(6, 0))
        rotulo_secao(tk_, "tokens").pack(fill="x", padx=14, pady=(10, 0))
        self.resumo = tk.Label(tk_, font=F["texto"], fg=C["fraco"], bg=C["painel"], anchor="w")
        self.resumo.pack(fill="x", padx=14, pady=(0, 4))
        moldura = tk.Frame(tk_, bg=C["painel"])
        moldura.pack(fill="both", expand=True, padx=4, pady=4)
        self.tabela = ttk.Treeview(moldura, columns=("pos", "tipo", "lexema"), show="headings",
                                   style="Escuro.Treeview")
        medir = tkfont.Font(font=F["mono"]).measure
        for col, txt, amostra in (("pos", "lin:col", "00:00 "), ("tipo", "tipo", "NOVA_LINHA  "),
                                  ("lexema", "lexema", "valor_hora  ")):
            self.tabela.heading(col, text=txt, anchor="w")
            self.tabela.column(col, width=medir(amostra) + 12, minwidth=medir(amostra),
                               anchor="w", stretch=col == "lexema")
        for tipo, cor in COR_TOKEN.items():
            self.tabela.tag_configure(tipo, foreground=cor)
        sb = ttk.Scrollbar(moldura, orient="vertical", command=self.tabela.yview, style="Escuro.Vertical.TScrollbar")
        self.tabela.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tabela.pack(fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_selecionar_token)

        # erros
        er = cartao(corpo)
        er.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        rotulo_secao(er, "erros léxicos").pack(fill="x", padx=14, pady=(10, 2))
        m, self.lista_erros = com_rolagem(er, caixa_texto, height=8, wrap="word")
        m.pack(fill="both", expand=True, padx=4, pady=4)
        self.lista_erros.tag_configure("cab", foreground=C["erro"], font=F["mono"] + ("bold",))
        self.lista_erros.tag_configure("dica", foreground=C["destaque"])
        self.lista_erros.tag_configure("ok", foreground=C["ok"])

        self.carregar(ROTEIRO_OK + "SAIDA ABC1234 25:00 PAGO R$12\n")

    def carregar(self, texto):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", texto)
        self.analisar()

    def ao_editar(self, _):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            if self.agendado:
                self.after_cancel(self.agendado)
            self.agendado = self.after(180, self.analisar)

    def analisar(self):
        self.agendado = None
        texto = self.editor.get("1.0", "end-1c")
        self.tokens, self.erros = scanner(texto)
        ed = self.editor
        for tag in list(COR_TOKEN) + ["comentario", "erro", "foco"]:
            ed.tag_remove(tag, "1.0", "end")
        for n, linha in enumerate(texto.split("\n"), start=1):
            m = linha.find("#")
            if m >= 0:
                ed.tag_add("comentario", f"{n}.{m}", f"{n}.end")
        for t in self.tokens:
            if t.tipo not in ("NOVA_LINHA", "EOF"):
                ed.tag_add(t.tipo, f"{t.linha}.{t.coluna - 1}", f"{t.linha}.{t.coluna - 1 + len(t.lexema)}")
        for e in self.erros:
            ed.tag_add("erro", f"{e.linha}.{e.coluna - 1}", f"{e.linha}.{e.coluna - 1 + len(e.lexema)}")

        total = int(ed.index("end-1c").split(".")[0])
        self.numeros.configure(state="normal")
        self.numeros.delete("1.0", "end")
        self.numeros.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        self.numeros.configure(state="disabled")
        self.numeros.yview_moveto(ed.yview()[0])

        self.tabela.delete(*self.tabela.get_children())
        for k, t in enumerate(self.tokens):
            self.tabela.insert("", "end", iid=str(k), values=(f"{t.linha}:{t.coluna}", t.tipo, t.lexema), tags=(t.tipo,))
        tipos = {t.tipo for t in self.tokens} - {"NOVA_LINHA", "EOF"}
        self.resumo.configure(text=f"{len(self.tokens)} tokens · {len(tipos)} tipos · {len(self.erros)} erros",
                              fg=C["erro"] if self.erros else C["fraco"])

        le = self.lista_erros
        le.configure(state="normal")
        le.delete("1.0", "end")
        if not self.erros:
            le.insert("end", "✔ nenhum erro léxico", "ok")
        for k, e in enumerate(self.erros):
            tag = f"e{k}"
            le.insert("end", f"✘ {e.linha}:{e.coluna}  {e.lexema!r}  {e.mensagem}\n", ("cab", tag))
            le.insert("end", f"   dica → {e.dica}\n\n", ("dica", tag))
            le.tag_bind(tag, "<Button-1>", lambda ev, e=e: self.focar(e.linha, e.coluna, len(e.lexema)))
            le.tag_bind(tag, "<Enter>", lambda ev: le.configure(cursor="hand2"))
            le.tag_bind(tag, "<Leave>", lambda ev: le.configure(cursor=""))
        le.configure(state="disabled")

    def focar(self, linha, coluna, tam):
        ed = self.editor
        ed.tag_remove("foco", "1.0", "end")
        ini, fim = f"{linha}.{coluna - 1}", f"{linha}.{coluna - 1 + max(tam, 1)}"
        ed.tag_add("foco", ini, fim)
        ed.tag_raise("foco")
        ed.mark_set("insert", ini)
        ed.see(ini)
        ed.focus_set()

    def ao_selecionar_token(self, _):
        sel = self.tabela.selection()
        if sel:
            t = self.tokens[int(sel[0])]
            if t.tipo not in ("NOVA_LINHA", "EOF"):
                self.focar(t.linha, t.coluna, len(t.lexema))

    def executar(self):
        erros, passos = eventos_do_roteiro(self.editor.get("1.0", "end-1c"))
        self.app.ir("Cancela")
        self.app.paginas["Cancela"].executar_roteiro(erros, passos)


# ------------------------------------------------------------------ página: cancela
# layout sem cruzamentos: TRAVADA fica dentro do triângulo FECHADA–ABRINDO–FECHANDO
POS_CANCELA = {"FECHADA": (0.06, 0.50), "ABRINDO": (0.56, 0.11), "ABERTA": (0.90, 0.50),
               "FECHANDO": (0.56, 0.89), "TRAVADA": (0.36, 0.50)}
CURVA_CANCELA = {("FECHANDO", "ABRINDO"): 18}
# posição de cada rótulo: (t ao longo da aresta, lado, distância)
ROTULO_CANCELA = {("FECHANDO", "ABRINDO"): (0.30, 1, 13), ("ABERTA", "FECHANDO"): (0.5, -1, 13), ("FECHANDO", "FECHADA"): (0.5, -1, 13),
                  ("TRAVADA", "FECHADA"): (0.5, 1, 11)}
ANGULO = {"FECHADA": 0, "ABRINDO": 40, "ABERTA": 82, "FECHANDO": 40, "TRAVADA": 18}


class PaginaCancela(tk.Frame):
    def __init__(self, pai):
        super().__init__(pai, bg=C["bg"])
        self.maquina = MaquinaEstados("CANCELA", "FECHADA", TRANSICOES_CANCELA)
        self.ultima, self.recusa = None, False
        self.angulo, self.anim_braco, self.fila = 0.0, None, None

        topo = tk.Frame(self, bg=C["bg"])
        topo.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(topo, text="Cancela", font=F["titulo"], fg=C["texto"], bg=C["bg"]).pack(anchor="w")
        tk.Label(topo, text="Máquina de estados de negócio. Eventos em amarelo são os permitidos no estado atual; "
                            "os outros são recusados.",
                 font=F["subtitulo"], fg=C["fraco"], bg=C["bg"]).pack(anchor="w")

        corpo = tk.Frame(self, bg=C["bg"])
        corpo.pack(fill="both", expand=True, padx=24, pady=(14, 20))
        for col, peso in enumerate((2, 3, 3)):
            corpo.columnconfigure(col, weight=peso, uniform="col")
        corpo.rowconfigure(0, weight=5)
        corpo.rowconfigure(1, weight=4)

        cd = cartao(corpo)
        cd.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0, 6))
        rotulo_secao(cd, f"diagrama — {len(self.maquina.estados)} estados, "
                         f"{len(self.maquina.transicoes)} transições").pack(fill="x", padx=14, pady=(10, 0))
        self.diag = tk.Canvas(cd, height=290, width=200, bg=C["painel"], highlightthickness=0)
        self.diag.pack(fill="both", expand=True, padx=6, pady=6)
        self.diag.bind("<Configure>", lambda e: self.desenhar())

        lado = cartao(corpo)
        lado.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.ilustra = tk.Canvas(lado, width=230, height=140, bg=C["painel"], highlightthickness=0)
        self.ilustra.pack(pady=(12, 0))
        self.lbl_estado = tk.Label(lado, font=F["grande"], fg=C["destaque"], bg=C["painel"])
        self.lbl_estado.pack()
        self.lbl_permitidos = tk.Label(lado, font=F["texto"], fg=C["fraco"], bg=C["painel"], wraplength=220)
        self.lbl_permitidos.pack(pady=(0, 10))

        ev = cartao(corpo)
        ev.grid(row=1, column=1, sticky="nsew", padx=6, pady=(6, 0))
        cab = tk.Frame(ev, bg=C["painel"])
        cab.pack(fill="x", padx=14, pady=(10, 6))
        rotulo_secao(cab, "eventos").pack(side="left")
        Botao(cab, "↺ reiniciar", self.reiniciar, "fantasma", padx=8, pady=2).pack(side="right")
        grade = tk.Frame(ev, bg=C["painel"])
        grade.pack(fill="x", padx=10, pady=(0, 10))
        self.botoes = {}
        eventos = sorted({e for (_, e) in TRANSICOES_CANCELA})
        for k, nome in enumerate(eventos):
            b = Botao(grade, nome, lambda n=nome: self.disparar(n), "secundario", padx=4, pady=8, font=F["mono"])
            b.grid(row=k // 2, column=k % 2, sticky="ew", padx=3, pady=3)
            grade.columnconfigure(k % 2, weight=1, uniform="ev")
            self.botoes[nome] = b

        lg = cartao(corpo)
        lg.grid(row=1, column=2, sticky="nsew", padx=(6, 0), pady=(6, 0))
        rotulo_secao(lg, "histórico").pack(fill="x", padx=14, pady=(10, 2))
        m, self.log = com_rolagem(lg, caixa_texto, height=8, wrap="word")
        m.pack(fill="both", expand=True, padx=4, pady=4)
        self.log.tag_configure("ok", foreground=C["ok"])
        self.log.tag_configure("erro", foreground=C["erro"])
        self.log.tag_configure("fraco", foreground=C["fraco"])
        self.log.tag_configure("dest", foreground=C["destaque"])

        self.atualizar()

    # ---- lógica
    def escrever(self, texto, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def disparar(self, evento):
        antes = self.maquina.estado
        if self.maquina.disparar(evento, imprimir=False):
            self.ultima, self.recusa = (antes, self.maquina.estado), False
            self.escrever(f"✔ {antes} --{evento}--> {self.maquina.estado}", "ok")
        else:
            self.ultima, self.recusa = None, True
            self.escrever(f"✘ '{evento}' recusado em {antes}. Permitidos: {', '.join(self.maquina.permitidos())}", "erro")
        self.atualizar()

    def reiniciar(self):
        if self.fila:
            self.after_cancel(self.fila)
            self.fila = None
        self.maquina.reiniciar()
        self.ultima, self.recusa = None, False
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.atualizar()

    def executar_roteiro(self, erros, passos):
        self.reiniciar()
        self.escrever("▶ roteiro vindo do scanner", "dest")
        for e in erros:
            self.escrever(f"✘ erro léxico {e.linha}:{e.coluna} {e.lexema!r} → {e.dica}", "erro")
        fila = list(passos)

        def proximo():
            if not fila:
                self.escrever(f"■ fim do roteiro — cancela em {self.maquina.estado}", "dest")
                self.fila = None
                return
            linha, cmd, ev, nota = fila.pop(0)
            self.escrever(f"linha {linha}: {cmd}", "fraco")
            if ev:
                self.disparar(ev)
            else:
                self.escrever(f"⚠ {nota}", "dest")
            self.fila = self.after(650, proximo)
        proximo()

    def atualizar(self):
        estado = self.maquina.estado
        permitidos = self.maquina.permitidos()
        self.lbl_estado.configure(text=estado, fg=C["erro"] if estado == "TRAVADA" else C["destaque"])
        self.lbl_permitidos.configure(text="permitidos: " + ", ".join(permitidos))
        for nome, b in self.botoes.items():
            if nome in permitidos:
                b.cores(C["destaque"], C["bg"], C["destaque2"])
            else:
                b.cores(C["painel2"], C["apagado"], C["linha"])
        self.desenhar()
        self.animar_braco()

    # ---- desenho
    def desenhar(self):
        cv = self.diag
        cv.delete("all")
        W, H = max(cv.winfo_width(), 500), max(cv.winfo_height(), 300)
        nos = {e: {"x": 10 + x * (W - 20), "y": 6 + y * (H - 12), "forma": "elipse", "a": 48, "b": 18}
               for e, (x, y) in POS_CANCELA.items()}
        agrupadas = {}
        for (e, ev), p in TRANSICOES_CANCELA.items():
            agrupadas.setdefault((e, p), []).append(ev)
        for (e, p), evs in agrupadas.items():
            usada = self.ultima == (e, p)
            permitida = e == self.maquina.estado
            cor = C["destaque"] if usada else (C["fraco"] if permitida else C["apagado"])
            t, lado, dist = ROTULO_CANCELA.get((e, p), (0.5, None, 13))
            seta(cv, nos[e], nos[p], "\n".join(evs), CURVA_CANCELA.get((e, p), 0), cor=cor,
                 largura=2.6 if usada else 1.5, cor_rotulo=C["destaque"] if (usada or permitida) else C["fraco"],
                 t=t, lado=lado, dist=dist)
        cv.tag_raise("rotulo")
        n = nos["FECHADA"]
        cv.create_line(n["x"], n["y"] - 56, n["x"], n["y"] - 21, arrow="last", fill=C["fraco"], width=1.6)
        cv.create_text(n["x"], n["y"] - 64, text="início", fill=C["fraco"], font=F["rotulo"])
        for e, n in nos.items():
            if e == self.maquina.estado:
                cor = C["erro"] if (self.recusa or e == "TRAVADA") else C["destaque"]
                desenhar_no(cv, n, e, cor, cor, C["bg"], largura=3)
            else:
                desenhar_no(cv, n, e, C["painel2"], C["linha"], C["fraco"])

    def animar_braco(self):
        alvo = ANGULO[self.maquina.estado]
        if self.anim_braco:
            self.after_cancel(self.anim_braco)

        def passo():
            dif = alvo - self.angulo
            self.angulo += dif * 0.25 if abs(dif) > 0.5 else dif
            self.desenhar_ilustracao()
            self.anim_braco = self.after(16, passo) if abs(alvo - self.angulo) > 0.01 else None
        passo()

    def desenhar_ilustracao(self):
        cv = self.ilustra
        cv.delete("all")
        estado = self.maquina.estado
        cv.create_rectangle(0, 118, 230, 140, fill="#2a2d33", outline="")
        for x in range(10, 230, 40):
            cv.create_rectangle(x, 127, x + 20, 130, fill=C["destaque"], outline="")
        cv.create_rectangle(30, 60, 54, 120, fill="#3b4049", outline="")
        luz = {"FECHADA": C["erro"], "ABRINDO": C["destaque"], "ABERTA": C["ok"],
               "FECHANDO": C["destaque"], "TRAVADA": C["erro"]}[estado]
        cv.create_oval(36, 68, 48, 80, fill=luz, outline="")
        px, py = 42, 60
        ang = math.radians(self.angulo)
        comp = 170
        segs = 8
        for k in range(segs):
            a0, a1 = k / segs * comp, (k + 1) / segs * comp
            x0, y0 = px + a0 * math.cos(ang), py - a0 * math.sin(ang)
            x1, y1 = px + a1 * math.cos(ang), py - a1 * math.sin(ang)
            cor = (C["erro"] if k % 2 == 0 else "#f2f2f2") if estado == "TRAVADA" else \
                  (C["destaque"] if k % 2 == 0 else "#1b1b1b")
            cv.create_line(x0, y0, x1, y1, fill=cor, width=9)
        cv.create_oval(px - 7, py - 7, px + 7, py + 7, fill="#5a606b", outline="")
        if estado == "TRAVADA":
            cv.create_text(175, 24, text="⚠ falha", fill=C["erro"], font=F["botao"])


# ------------------------------------------------------------------ rolagem da página inteira
class PaginaRolavel(tk.Frame):
    """Envelope com rolagem vertical para uma página inteira.

    Se a janela for mais alta que a página, a página estica e ocupa tudo (sem barra).
    Se for mais baixa (tela pequena ou escala do Windows em 125%/150%), a página mantém
    a altura mínima de que precisa e aparece a barra de rolagem; a roda do mouse também rola.
    Caixas de texto e tabelas continuam rolando sozinhas quando o mouse está sobre elas."""

    def __init__(self, pai):
        super().__init__(pai, bg=C["bg"])
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                   style="Escuro.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.pagina = None
        self._janela = None
        self.canvas.bind("<Configure>", lambda e: self.ajustar())
        self._ultima_altura = None
        self.after(400, self._vigiar)

    def _vigiar(self):
        """Se o conteúdo da página passou a pedir outra altura (texto novo, fonte maior
        no Windows...), reajusta para nada ficar espremido."""
        try:
            if self.pagina is not None and self.winfo_ismapped():
                req = self.altura_minima()
                if req != self._ultima_altura:
                    self._ultima_altura = req
                    self.ajustar()
            self.after(400, self._vigiar)
        except tk.TclError:
            pass                                # janela fechada

    def colocar(self, pagina):
        self.pagina = pagina
        self._janela = self.canvas.create_window((0, 0), window=pagina, anchor="nw")
        pagina.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=(0, 0, e.width, e.height)),
                    add="+")

    def altura_minima(self):
        return self.pagina.winfo_reqheight()

    def ajustar(self):
        if not self.pagina:
            return
        larg = self.canvas.winfo_width()
        alt_tela = self.canvas.winfo_height()
        alt = max(alt_tela, self.altura_minima())
        self.canvas.itemconfigure(self._janela, width=larg, height=alt)
        self.canvas.configure(scrollregion=(0, 0, larg, alt))
        precisa = alt > alt_tela + 1
        if precisa and not self.barra.winfo_ismapped():
            self.barra.pack(side="right", fill="y", before=self.canvas)
        elif not precisa and self.barra.winfo_ismapped():
            self.barra.pack_forget()
            self.canvas.yview_moveto(0)

    def rolar(self, e):
        """Chamado pela roda do mouse (bind_all na janela)."""
        if not self.barra.winfo_ismapped():
            return
        w = e.widget
        if isinstance(w, (tk.Text, ttk.Treeview, tk.Listbox)):
            return                          # deixa a caixa de texto/tabela rolar ela mesma
        if getattr(e, "num", None) == 4:
            passo = -1
        elif getattr(e, "num", None) == 5:
            passo = 1
        else:
            passo = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(passo * 3, "units")


# ------------------------------------------------------------------ janela principal
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        preparar_fontes()
        self.title("Estacionamento Inteligente")
        # abre no tamanho da tela (descontando a barra de tarefas), no máximo 1280x860
        larg = min(1280, self.winfo_screenwidth() - 40)
        alt = min(860, self.winfo_screenheight() - 90)
        self.geometry(f"{larg}x{alt}+{max(0, (self.winfo_screenwidth() - larg) // 2)}+10")
        self.minsize(900, 480)
        self.configure(bg=C["bg"])
        self.estilos()

        escala = max(1.0, self.winfo_fpixels("1i") / 96)
        lateral = tk.Frame(self, bg=C["lateral"], width=int(228 * escala))
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        logo = tk.Frame(lateral, bg=C["lateral"])
        logo.pack(fill="x", padx=18, pady=(22, 26))
        tk.Label(logo, text="P", font=F["grande"], bg=C["destaque"], fg=C["bg"], width=2).pack(side="left")
        tk.Label(logo, text="Estacionamento\nInteligente", font=F["logo"], fg=C["texto"],
                 bg=C["lateral"], justify="left").pack(side="left", padx=(10, 0))

        area = tk.Frame(self, bg=C["bg"])
        area.pack(side="left", fill="both", expand=True)
        self.envelopes = {n: PaginaRolavel(area) for n in ("Validadores", "Scanner", "Cancela")}
        self.paginas = {
            "Validadores": PaginaValidadores(self.envelopes["Validadores"].canvas),
            "Scanner": PaginaScanner(self.envelopes["Scanner"].canvas, self),
            "Cancela": PaginaCancela(self.envelopes["Cancela"].canvas),
        }
        for n, pag in self.paginas.items():
            self.envelopes[n].colocar(pag)
        self.atual = None
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(ev, lambda e: self.envelopes[self.atual].rolar(e) if self.atual else None)
        icones = {"Validadores": "◆", "Scanner": "≡", "Cancela": "⊓"}
        self.nav = {}
        for nome in self.paginas:
            item = tk.Frame(lateral, bg=C["lateral"], cursor="hand2")
            item.pack(fill="x", pady=1)
            barra = tk.Frame(item, bg=C["lateral"], width=4)
            barra.pack(side="left", fill="y")
            lbl = tk.Label(item, text=f"  {icones[nome]}   {nome}", font=F["nav"], fg=C["fraco"],
                           bg=C["lateral"], anchor="w", pady=10)
            lbl.pack(side="left", fill="x", expand=True)
            for w in (item, lbl):
                w.bind("<Button-1>", lambda e, n=nome: self.ir(n))
            self.nav[nome] = (item, barra, lbl)
        tk.Label(lateral, text="AFD · máquina de estados · scanner", font=F["subtitulo"],
                 fg=C["apagado"], bg=C["lateral"], wraplength=int(180 * escala), justify="left").pack(side="bottom", anchor="w",
                                                                                     padx=18, pady=18)
        self.ir("Validadores")

    def estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        altura_linha = tkfont.Font(font=F["mono"]).metrics("linespace") + 8
        s.configure("Escuro.Treeview", background=C["painel"], fieldbackground=C["painel"],
                    foreground=C["texto"], borderwidth=0, rowheight=altura_linha, font=F["mono"])
        s.configure("Escuro.Treeview.Heading", background=C["painel2"], foreground=C["fraco"],
                    borderwidth=0, relief="flat", font=F["secao"])
        s.map("Escuro.Treeview", background=[("selected", C["destaque_fundo"])],
              foreground=[("selected", C["destaque"])])
        s.map("Escuro.Treeview.Heading", background=[("active", C["linha"])])
        s.layout("Escuro.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Escuro.Vertical.TScrollbar", background=C["painel2"], troughcolor=C["painel"],
                    bordercolor=C["painel"], arrowcolor=C["fraco"], lightcolor=C["painel2"],
                    darkcolor=C["painel2"], gripcount=0)
        s.map("Escuro.Vertical.TScrollbar", background=[("active", C["linha"])])

    def ir(self, nome):
        for n, env in self.envelopes.items():
            env.pack_forget()
            item, barra, lbl = self.nav[n]
            ativo = n == nome
            for w in (item, lbl):
                w.configure(bg=C["painel"] if ativo else C["lateral"])
            barra.configure(bg=C["destaque"] if ativo else C["lateral"])
            lbl.configure(fg=C["texto"] if ativo else C["fraco"], font=F["nav_ativo"] if ativo else F["nav"])
        self.atual = nome
        self.envelopes[nome].pack(fill="both", expand=True)
        self.update_idletasks()
        self.envelopes[nome].ajustar()


def abrir_interface():
    App().mainloop()


if __name__ == "__main__":
    abrir_interface()
