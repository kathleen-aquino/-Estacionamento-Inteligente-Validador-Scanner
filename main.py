"""Estacionamento Inteligente — ponto de entrada.

    python main.py            roda todas as demonstrações e a checklist, depois pergunta se abre a interface
    python main.py --gui      abre direto a interface gráfica
    python main.py --sem-gui  só as demonstrações (sem perguntar nada)
"""
import os
import sys

# acentos e símbolos (δ, ∈, ✔) no terminal do Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import validadores
import cancela
import scanner
import conectado
from afd import AFD, pares_equivalentes, desenhar
from validadores import afd_placa, afd_hora, classe_placa


def bonus_minimo():
    print("=" * 70 + "\nBÔNUS — AFD MÍNIMO (preenchimento de tabela, Aula 07)\n" + "=" * 70)
    for afd in (afd_placa, afd_hora):
        eq = pares_equivalentes(afd)
        print(f"{afd.nome}: {len(afd.estados)} estados, pares equivalentes = {eq} →",
              "MÍNIMO ✔" if not eq else "pode ser reduzido")
    # versão "ingênua" da placa (ramos separados até o fim), só para comparação
    ingenua = AFD("PLACA_INGENUA",
                  ["q0", "q1", "q2", "q3", "a4", "a5", "a6", "a7", "a8", "m4", "m5", "m6", "m7"],
                  ["L", "N", "-"],
                  {("q0", "L"): "q1", ("q1", "L"): "q2", ("q2", "L"): "q3",
                   ("q3", "-"): "a4", ("q3", "N"): "m4",
                   ("a4", "N"): "a5", ("a5", "N"): "a6", ("a6", "N"): "a7", ("a7", "N"): "a8",
                   ("m4", "L"): "m5", ("m5", "N"): "m6", ("m6", "N"): "m7"},
                  "q0", {"a8", "m7"}, classe_placa)
    print("\nVersão ingênua (13 estados): pares equivalentes =", pares_equivalentes(ingenua))
    print("Juntando a6≡m5, a7≡m6, a8≡m7 chegamos exatamente aos 10 estados de AFD_PLACA.\n")


def bonus_desenhos():
    print("=" * 70 + "\nBÔNUS — DESENHOS COM GRAPHVIZ (a partir do delta)\n" + "=" * 70)
    os.makedirs("img", exist_ok=True)
    desenhar(afd_placa, "img/afd_placa")
    desenhar(afd_hora, "img/afd_horario")
    desenhar(scanner.AFD_SCANNER, "img/afd_scanner")
    cancela.desenhar_cancela("img/cancela")
    print()


def checklist(div):
    print("=" * 70 + "\nCHECKLIST\n" + "=" * 70)
    sc = scanner.scanner
    tipos = {t.tipo for t in sc(scanner.ROTEIRO_OK + "ALERTA x <= 3")[0]}
    toks_err, erros = sc(scanner.ROTEIRO_ERROS)
    m = cancela.cancela
    checks = {
        "AFD_PLACA ≥ 5 estados":                len(afd_placa.estados) >= 5,
        "AFD_HORARIO ≥ 5 estados":              len(afd_hora.estados) >= 5,
        "0 divergências AFD × RegEx":           div["placa"] == 0 and div["hora"] == 0,
        "palavra vazia testada":                "" in validadores.PLACA_REJEITADAS and "" in validadores.HORA_REJEITADAS,
        "máquina ≥ 5 estados e ≥ 6 transições": len(m.estados) >= 5 and len(m.transicoes) >= 6,
        "scanner ≥ 8 tipos de token":           len(tipos - {"NOVA_LINHA", "EOF"}) >= 8,
        "≥ 3 palavras reservadas":              len(scanner.RESERVADAS) >= 3,
        "erros com linha, coluna e dica":       all(e.linha and e.coluna and e.dica for e in erros),
        "scanner continua após erro":           any(t.linha == 4 for t in toks_err),
        "AFDs mínimos (bônus)":                 not pares_equivalentes(afd_placa) and not pares_equivalentes(afd_hora),
        "Scanner por tabela ≡ while (bônus)":   not scanner.bateria_scanner(),
    }
    for k, v in checks.items():
        print(("✔ " if v else "✘ ") + k)
    print("\nTipos de token usados:", sorted(tipos))
    return all(checks.values())


def main():
    args = sys.argv[1:]
    if "--gui" in args:
        from interface import abrir_interface
        abrir_interface()
        return

    div = validadores.demo()
    bonus_minimo()
    bonus_desenhos()
    cancela.demo()
    scanner.demo()
    print()
    conectado.demo()
    print()
    ok = checklist(div)

    if "--sem-gui" not in args:
        try:
            resp = input("\nAbrir a interface gráfica? [s/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp in ("s", "sim", "y"):
            from interface import abrir_interface
            abrir_interface()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
