"""R4 — Máquina de estados de negócio: a cancela do estacionamento.

    estado atual | evento             | próximo
    -------------+--------------------+----------
    FECHADA      | liberar            | ABRINDO
    ABRINDO      | fim_abertura       | ABERTA
    ABRINDO      | falha_motor        | TRAVADA
    ABERTA       | veiculo_passou     | FECHANDO
    ABERTA       | tempo_esgotado     | FECHANDO
    FECHANDO     | fim_fechamento     | FECHADA
    FECHANDO     | sensor_obstaculo   | ABRINDO   (reabre por segurança)
    FECHANDO     | falha_motor        | TRAVADA
    TRAVADA      | manutencao_ok      | FECHADA
"""


class MaquinaEstados:
    def __init__(self, nome, inicial, transicoes):
        self.nome, self.inicial, self.transicoes = nome, inicial, dict(transicoes)
        self.estados = sorted({e for e, _ in transicoes} | set(transicoes.values()))
        self.reiniciar()

    def reiniciar(self):
        self.estado, self.historico = self.inicial, []

    def permitidos(self, estado=None):
        estado = estado or self.estado
        return sorted(ev for (e, ev) in self.transicoes if e == estado)

    def disparar(self, evento, imprimir=True):
        prox = self.transicoes.get((self.estado, evento))
        if prox is None:
            if imprimir:
                print(f"  ✘ evento '{evento}' RECUSADO em {self.estado}. "
                      f"Eventos permitidos: {self.permitidos()}")
            return False
        if imprimir:
            print(f"  ✔ {self.estado:9} --{evento}--> {prox}")
        self.historico.append((self.estado, evento, prox))
        self.estado = prox
        return True

    def executar(self, eventos, titulo):
        self.reiniciar()
        print(f"▶ {titulo}")
        for ev in eventos:
            if not self.disparar(ev):
                print(f"  FLUXO INVÁLIDO (parou em {self.estado})\n")
                return False
        print(f"  FLUXO VÁLIDO (terminou em {self.estado})\n")
        return True


TRANSICOES_CANCELA = {
    ("FECHADA",  "liberar"):          "ABRINDO",
    ("ABRINDO",  "fim_abertura"):     "ABERTA",
    ("ABERTA",   "veiculo_passou"):   "FECHANDO",
    ("ABERTA",   "tempo_esgotado"):   "FECHANDO",
    ("FECHANDO", "fim_fechamento"):   "FECHADA",
    ("FECHANDO", "sensor_obstaculo"): "ABRINDO",
    ("ABRINDO",  "falha_motor"):      "TRAVADA",
    ("FECHANDO", "falha_motor"):      "TRAVADA",
    ("TRAVADA",  "manutencao_ok"):    "FECHADA",
}

cancela = MaquinaEstados("CANCELA", "FECHADA", TRANSICOES_CANCELA)


def desenhar_cancela(arquivo=None):
    """Bônus: desenho da máquina gerado a partir das transições (Graphviz)."""
    try:
        import graphviz
    except ImportError:
        print("(desenho pulado: rode 'pip install graphviz')")
        return None
    g = graphviz.Digraph("cancela", graph_attr={"rankdir": "LR"},
                         node_attr={"shape": "box", "style": "rounded"})
    g.node("", shape="none", width="0")
    g.edge("", cancela.inicial)
    for (e, ev), p in cancela.transicoes.items():
        g.edge(e, p, label=ev)
    if arquivo:
        try:
            g.render(arquivo, format="png", cleanup=True)
            print(f"desenho salvo em {arquivo}.png")
        except Exception as e:
            print(f"(PNG não salvo — instale o Graphviz do sistema: {type(e).__name__})")
    return g


def demo():
    print("=" * 70 + "\nMÁQUINA DE ESTADOS — CANCELA\n" + "=" * 70)
    print(f"{len(cancela.estados)} estados: {cancela.estados}")
    print(f"{len(cancela.transicoes)} transições")
    for e in cancela.estados:
        print(f"  {e:9} permite {cancela.permitidos(e)}")
    print()
    cancela.executar(["liberar", "fim_abertura", "veiculo_passou", "fim_fechamento"],
                     "Válido 1 — entrada normal")
    cancela.executar(["liberar", "fim_abertura", "veiculo_passou", "sensor_obstaculo",
                      "fim_abertura", "tempo_esgotado", "fim_fechamento"],
                     "Válido 2 — obstáculo reabre a cancela")
    cancela.executar(["veiculo_passou"],
                     "Inválido 1 — veículo passou com a cancela fechada (fura-cancela)")
    cancela.executar(["liberar", "falha_motor", "liberar"],
                     "Inválido 2 — tentar liberar com a cancela travada")


if __name__ == "__main__":
    demo()
