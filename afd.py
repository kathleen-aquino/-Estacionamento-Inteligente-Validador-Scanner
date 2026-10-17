"""Infraestrutura: classe AFD, bateria AFD x RegEx, minimização e desenho."""
import re
from itertools import combinations


class AFD:
    """AFD com classes de símbolos: delta[(estado, classe)] = próximo estado.
    Transição ausente = estado morto (a palavra 'morre no meio')."""

    def __init__(self, nome, estados, classes, delta, inicial, finais, classe, descricao=None):
        self.nome, self.estados, self.classes = nome, list(estados), list(classes)
        self.delta, self.inicial, self.finais = dict(delta), inicial, set(finais)
        self.classe = classe                 # função: caractere -> nome da classe (ou None)
        self.descricao = descricao or {}

    def aceita(self, w):
        q = self.inicial
        for c in w:
            q = self.delta.get((q, self.classe(c)))
            if q is None:
                return False
        return q in self.finais

    def rodar(self, w, imprimir=True):
        """Rastreamento passo a passo. Devolve (aceitou, linhas)."""
        linhas = [f"{self.nome}: rodar({w!r})", f"  início em {self.inicial}"]
        q, aceitou = self.inicial, None
        for i, c in enumerate(w):
            cl = self.classe(c)
            prox = self.delta.get((q, cl))
            rotulo = cl if cl is not None else "fora de Σ"
            if prox is None:
                linhas.append(f"  [{i}] {c!r:5} classe {rotulo:9}  δ({q}, {rotulo}) indefinida → MORREU NO MEIO")
                linhas.append("  ⇒ REJEITADA: morreu no meio (não existe transição)")
                aceitou = False
                break
            linhas.append(f"  [{i}] {c!r:5} classe {rotulo:9}  δ({q}, {cl}) = {prox}")
            q = prox
        if aceitou is None:
            if q in self.finais:
                linhas.append(f"  ⇒ ACEITA: terminou em {q} ∈ F")
                aceitou = True
            else:
                linhas.append(f"  ⇒ REJEITADA: terminou em {q} ∉ F ({self.descricao.get(q, '')})")
                aceitou = False
        if imprimir:
            print("\n".join(linhas))
        return aceitou, linhas

    def tabela(self):
        larg = max(6, *(len(c) for c in self.classes)) + 1
        cab = "estado".ljust(8) + "".join(c.center(larg) for c in self.classes)
        print(f"Tabela de transição — {self.nome}")
        print(cab)
        print("-" * len(cab))
        for q in self.estados:
            marca = ("→" if q == self.inicial else " ") + ("*" if q in self.finais else " ")
            linha = (marca + q).ljust(8)
            linha += "".join((self.delta.get((q, c)) or "—").center(larg) for c in self.classes)
            print(linha + ("   " + self.descricao[q] if q in self.descricao else ""))
        print("(→ inicial, * final, — sem transição = morre)")


def bateria(afd, regex, aceitas, rejeitadas):
    """Compara AFD × RegEx (fullmatch) em todas as palavras. Devolve nº de divergências."""
    padrao = re.compile(regex)
    print(f"Bateria {afd.nome}   RegEx: {regex}")
    print(f"{'palavra':14}{'esperado':10}{'AFD':8}{'RegEx':8}status")
    divergencias = erros = 0
    sim = lambda b: "aceita" if b else "rejeita"
    for w, esperado in [(w, True) for w in aceitas] + [(w, False) for w in rejeitadas]:
        a, r = afd.aceita(w), padrao.fullmatch(w) is not None
        status = "ok"
        if a != r:
            status = "DIVERGÊNCIA"
            divergencias += 1
        elif a != esperado:
            status = "esperado errado"
            erros += 1
        print(f"{(repr(w) if w else 'ε (vazia)'):14}{sim(esperado):10}{sim(a):8}{sim(r):8}{status}")
    print(f"→ {len(aceitas)} aceitas, {len(rejeitadas)} rejeitadas, "
          f"{divergencias} divergência(s), {erros} erro(s) de expectativa\n")
    return divergencias


def pares_equivalentes(afd):
    """Bônus: algoritmo de preenchimento de tabela (Aula 07).
    Devolve a lista de pares de estados equivalentes (vazia = AFD mínimo)."""
    estados = afd.estados + ["∅"]                       # completa com estado morto
    d = lambda q, c: afd.delta.get((q, c), "∅") if q != "∅" else "∅"
    F = afd.finais
    marcado = {frozenset(p): (p[0] in F) != (p[1] in F) for p in combinations(estados, 2)}
    mudou = True
    while mudou:
        mudou = False
        for par, m in marcado.items():
            if m:
                continue
            p, q = tuple(par)
            for c in afd.classes:
                a, b = d(p, c), d(q, c)
                if a != b and marcado[frozenset((a, b))]:
                    marcado[par] = mudou = True
                    break
    return sorted(tuple(sorted(p)) for p, m in marcado.items() if not m)


def desenhar(afd, arquivo=None):
    """Bônus: gera o desenho do AFD com Graphviz a partir do próprio delta.
    Precisa de `pip install graphviz` e do Graphviz instalado no sistema."""
    try:
        import graphviz
    except ImportError:
        print("(desenho pulado: rode 'pip install graphviz' para gerar as imagens)")
        return None
    g = graphviz.Digraph(afd.nome, graph_attr={"rankdir": "LR"}, node_attr={"fontname": "Helvetica"})
    g.node("", shape="none", width="0")
    for q in afd.estados:
        g.node(q, shape="doublecircle" if q in afd.finais else "circle")
    g.edge("", afd.inicial)
    arestas = {}
    for (q, c), p in afd.delta.items():
        arestas.setdefault((q, p), []).append(c)
    for (q, p), cs in arestas.items():
        g.edge(q, p, label=", ".join(cs))
    if arquivo:
        try:
            g.render(arquivo, format="png", cleanup=True)
            print(f"desenho salvo em {arquivo}.png")
        except Exception as e:
            print(f"(PNG não salvo — instale o Graphviz do sistema: {type(e).__name__})")
    return g
