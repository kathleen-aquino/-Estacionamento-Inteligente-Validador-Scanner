"""R1, R2, R3 — Os dois validadores (AFD) do estacionamento: placa e horário."""
from afd import AFD, bateria


# ============================================================ AFD 1: PLACA
#  Antiga: LLL-NNNN (ABC-1234)    Mercosul: LLLNLNN (BRA2E19)
#
#          L      L      L      -      N      N      N      N
#  →(p0)──▶(p1)──▶(p2)──▶(p3)──▶(p4)──▶(p5)──▶(p7)──▶(p8)──▶((p9))
#                          │                    ▲
#                          │ N                  │ L
#                          └──────▶(p6)─────────┘

def classe_placa(c):
    if "A" <= c <= "Z":
        return "L"
    if "0" <= c <= "9":
        return "N"
    if c == "-":
        return "-"
    return None


afd_placa = AFD(
    nome="AFD_PLACA",
    estados=["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"],
    classes=["L", "N", "-"],
    delta={
        ("p0", "L"): "p1", ("p1", "L"): "p2", ("p2", "L"): "p3",
        ("p3", "-"): "p4", ("p3", "N"): "p6",          # bifurcação antiga / Mercosul
        ("p4", "N"): "p5", ("p5", "N"): "p7",          # antiga: -NN ...
        ("p6", "L"): "p7",                             # Mercosul: N L ...
        ("p7", "N"): "p8", ("p8", "N"): "p9",          # tronco comum: NN
    },
    inicial="p0", finais={"p9"}, classe=classe_placa,
    descricao={"p0": "início", "p1": "1 letra", "p2": "2 letras", "p3": "3 letras",
               "p4": "antiga: leu '-'", "p5": "antiga: 1º dígito", "p6": "Mercosul: 1º dígito",
               "p7": "faltam 2 dígitos", "p8": "falta 1 dígito", "p9": "placa completa"},
)

RE_PLACA = r"^[A-Z]{3}(-[0-9]{2}|[0-9][A-Z])[0-9]{2}$"
PLACA_ACEITAS = ["ABC-1234", "BRA2E19", "XYZ-0000", "RIO2A18", "AAA0A00", "QWE-9876"]
PLACA_REJEITADAS = ["", "ABC1234", "BRA-2E19", "abc-1234", "ABC-123", "BRA2E1",
                    "AB-1234", "BRA2E199", "ABC 1234", "ABC-12345"]


# ============================================================ AFD 2: HORÁRIO
#  HH:MM de 00:00 a 23:59 — classes finas de dígitos
#
#         0-1         0-9          :        0-5         0-9
#  →(h0)──────▶(h1)─────────▶(h3)─────▶(h4)──────▶(h5)──────▶((h6))
#    │                         ▲
#    │ 2                       │ 0-3
#    └─────────▶(h2)───────────┘

def classe_hora(c):
    if c in ("0", "1"):
        return "0-1"
    if c == "2":
        return "2"
    if c == "3":
        return "3"
    if c in ("4", "5"):
        return "4-5"
    if c in ("6", "7", "8", "9"):
        return "6-9"
    if c == ":":
        return ":"
    return None


D_0a9 = ["0-1", "2", "3", "4-5", "6-9"]
D_0a5 = ["0-1", "2", "3", "4-5"]
D_0a3 = ["0-1", "2", "3"]

delta_hora = {("h0", "0-1"): "h1", ("h0", "2"): "h2", ("h3", ":"): "h4"}
delta_hora.update({("h1", c): "h3" for c in D_0a9})   # 0X ou 1X: qualquer unidade
delta_hora.update({("h2", c): "h3" for c in D_0a3})   # 2X: só 20..23
delta_hora.update({("h4", c): "h5" for c in D_0a5})   # dezena do minuto 0..5
delta_hora.update({("h5", c): "h6" for c in D_0a9})   # unidade do minuto

afd_hora = AFD(
    nome="AFD_HORARIO",
    estados=["h0", "h1", "h2", "h3", "h4", "h5", "h6"],
    classes=["0-1", "2", "3", "4-5", "6-9", ":"],
    delta=delta_hora, inicial="h0", finais={"h6"}, classe=classe_hora,
    descricao={"h0": "início", "h1": "hora 0X/1X", "h2": "hora 2X", "h3": "hora completa",
               "h4": "leu ':'", "h5": "dezena do minuto", "h6": "horário completo"},
)

RE_HORA = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
HORA_ACEITAS = ["00:00", "08:15", "23:59", "19:45", "12:30", "09:05", "20:00"]
HORA_REJEITADAS = ["", "24:00", "8:15", "12:60", "12:5", "1230", "23:59:00",
                   "ab:cd", "12h30", "30:00", " 08:15"]


# ============================================================ DEMONSTRAÇÃO
def demo():
    """Roda tabela(), rodar() e bateria para os dois AFDs. Devolve as divergências."""
    divergencias = {}

    print("=" * 70 + "\nAFD 1 — PLACA (antiga + Mercosul)\n" + "=" * 70)
    afd_placa.tabela()
    print("\n--- R2: rastreamento passo a passo ---")
    afd_placa.rodar("BRA2E19"); print()
    afd_placa.rodar("BRA-2E19"); print()      # morre no meio: em p5 espera dígito e chega 'E'
    afd_placa.rodar("ABC-123"); print()       # termina em p8, que não é final
    print("--- R3: bateria AFD × RegEx ---")
    divergencias["placa"] = bateria(afd_placa, RE_PLACA, PLACA_ACEITAS, PLACA_REJEITADAS)

    print("=" * 70 + "\nAFD 2 — HORÁRIO HH:MM (classes finas)\n" + "=" * 70)
    afd_hora.tabela()
    print("\n--- R2: rastreamento passo a passo ---")
    afd_hora.rodar("23:59"); print()
    afd_hora.rodar("24:00"); print()          # morre no meio: depois do '2' só vale 0-3
    afd_hora.rodar("12:5"); print()           # termina em h5: faltou a unidade do minuto
    print("--- R3: bateria AFD × RegEx ---")
    divergencias["hora"] = bateria(afd_hora, RE_HORA, HORA_ACEITAS, HORA_REJEITADAS)
    return divergencias


if __name__ == "__main__":
    demo()
