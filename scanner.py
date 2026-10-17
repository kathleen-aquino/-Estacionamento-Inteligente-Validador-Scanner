"""R5 — Mini-scanner da linguagem de comandos do estacionamento.

Exemplo:
    # entrada e saída de um veículo
    ENTRADA BRA2E19 08:15 VAGA A12
    SAIDA BRA2E19 10:40 PAGO 12.00

Tipos de token: RESERVADA, PLACA, HORA, VAGA_ID, IDENT, INTEIRO, REAL,
                ATRIB, OP_REL, NOVA_LINHA, EOF
Maximal Munch:  '=' × '==', '<' × '<=', 12 × 12.00, 08 × 08:15
Ignora espaços e comentários (# até o fim da linha).
Erros léxicos têm linha, coluna e dica, e o scanner continua depois do erro.

BÔNUS — scanner por tabela: `scanner()` não tem um `while` escrito à mão para cada
tipo de token. Um único laço genérico segue o `delta` de um AFD combinado (AFD_SCANNER) e aplica o Maximal Munch
guardando o último estado final visitado. A versão antiga, com `while`s, continua
em `scanner_while()` e serve de referência para a bateria de equivalência.
"""
import random
import re
import unicodedata
from collections import namedtuple

from afd import AFD
from validadores import afd_placa, afd_hora

Token = namedtuple("Token", "tipo lexema linha coluna")
ErroLexico = namedtuple("ErroLexico", "linha coluna lexema mensagem dica")

RESERVADAS = {"ENTRADA", "SAIDA", "VAGA", "PAGO", "TARIFA", "ALERTA",
              "ABRIU", "PASSOU", "FECHOU", "OBSTACULO", "TEMPO", "FALHA", "MANUTENCAO"}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- decisões feitas DEPOIS do lexema
def classificar_palavra(lex, seguinte):
    """Decide o que uma PALAVRA é (reservadas + AFD_PLACA + RegEx).
    Devolve (tipo, lexema, mensagem, dica, extra):
      tipo != None → é um token; tipo None → é um erro léxico (mensagem e dica);
      extra = caracteres a mais que foram consumidos (o '$' de 'R$')."""
    if lex in RESERVADAS:
        return "RESERVADA", lex, None, None, 0
    if lex == "R" and seguinte == "$":
        return (None, "R$", "símbolo de moeda não faz parte da linguagem",
                "escreva só o valor com duas casas: PAGO 12.00", 1)
    if sem_acento(lex).upper() in RESERVADAS:
        certo = sem_acento(lex).upper()
        return (None, lex, f"palavra reservada escrita como '{lex}'",
                f"reservadas são em MAIÚSCULAS e sem acento: {certo}", 0)
    if afd_placa.aceita(lex):
        return "PLACA", lex, None, None, 0
    if re.fullmatch(r"[A-Z][0-9]{1,3}", lex):
        return "VAGA_ID", lex, None, None, 0
    if re.fullmatch(r"[A-Z]{3}[0-9]{4}", lex):
        return None, lex, "placa antiga sem hífen", f"placa antiga usa hífen: {lex[:3]}-{lex[3:]}", 0
    if re.fullmatch(r"[A-Z0-9-]{5,9}", lex) and any(c.isdigit() for c in lex):
        return (None, lex, "placa malformada",
                "use ABC-1234 (antiga) ou ABC1D23 (Mercosul), letras maiúsculas", 0)
    if re.fullmatch(r"[a-z_][a-z0-9_]*", lex):
        return "IDENT", lex, None, None, 0
    return (None, lex, "palavra não reconhecida",
            "identificadores usam minúsculas (valor_hora); vagas são letra+número (A12)", 0)


def dica_caractere(ch):
    return ("não escreva o símbolo de moeda: PAGO 12.00" if ch == "$"
            else "decimais usam ponto: 12.00" if ch == ","
            else "remova o caractere")


# ================================================================ BÔNUS: AFD combinado do scanner
CLASSES_SCANNER = ["A-Z", "let", "dig", "_", "esp", "nl", "#", "=", "<>", "!", "-", ":", ".", "outro"]


def classe_scanner(c):
    """Caractere → classe de símbolos do AFD_SCANNER."""
    if c in " \t\r":
        return "esp"
    if c == "\n":
        return "nl"
    if "A" <= c <= "Z":
        return "A-Z"
    if c.isalpha():
        return "let"                      # minúsculas e letras acentuadas
    if c.isdigit():
        return "dig"
    return {"_": "_", "#": "#", "=": "=", "<": "<>", ">": "<>", "!": "!",
            "-": "-", ":": ":", ".": "."}.get(c, "outro")


ESTADOS_SCANNER = ["q0", "U1", "U2", "U3", "W", "H", "PA", "N", "NC", "HORA", "ND", "REAL",
                   "EQ", "LT", "NOT", "OPEQ", "ESP", "COM", "NL"]

# estado final → tipo do lexema reconhecido (a "saída" do estado)
TIPO_FINAL = {"U1": "PALAVRA", "U2": "PALAVRA", "U3": "PALAVRA", "W": "PALAVRA", "PA": "PALAVRA",
              "N": "INTEIRO", "HORA": "HORA", "ND": "ERRO_REAL", "REAL": "REAL",
              "EQ": "ATRIB", "LT": "OP_REL", "OPEQ": "OP_REL", "NOT": "ERRO_BANG",
              "ESP": "ESPACO", "COM": "COMENTARIO", "NL": "NOVA_LINHA"}

DESCRICAO_SCANNER = {
    "q0": "início de um lexema", "U1": "1 maiúscula", "U2": "2 maiúsculas",
    "U3": "3 maiúsculas (ABC)", "W": "palavra", "H": "ABC- (falta dígito)",
    "PA": "placa antiga ABC-1…", "N": "inteiro", "NC": "08: (falta dígito)", "HORA": "08:15",
    "ND": "12. (sem decimais)", "REAL": "12.00", "EQ": "=", "LT": "< ou >",
    "NOT": "! sozinho", "OPEQ": "==, <=, >=, !=", "ESP": "espaços", "COM": "# comentário",
    "NL": "fim de linha"}


def _montar_delta():
    d = {}

    def liga(origem, classes, destino):
        for cl in classes:
            d[(origem, cl)] = destino

    palavra = ["A-Z", "let", "dig", "_"]
    # --- palavras (e a placa antiga ABC-1234, onde o '-' só entra depois de 3 maiúsculas)
    liga("q0", ["A-Z"], "U1")
    liga("q0", ["let", "_"], "W")
    liga("U1", ["A-Z"], "U2")
    liga("U1", ["let", "dig", "_"], "W")
    liga("U2", ["A-Z"], "U3")
    liga("U2", ["let", "dig", "_"], "W")
    liga("U3", ["A-Z", "let", "dig", "_"], "W")
    liga("U3", ["-"], "H")
    liga("W", palavra, "W")
    liga("H", ["dig"], "PA")
    liga("PA", ["A-Z", "let", "dig"], "PA")
    # --- números: inteiro, hora 08:15, real 12.00
    liga("q0", ["dig"], "N")
    liga("N", ["dig"], "N")
    liga("N", [":"], "NC")
    liga("NC", ["dig"], "HORA")
    liga("HORA", ["dig"], "HORA")
    liga("N", ["."], "ND")
    liga("ND", ["dig"], "REAL")
    liga("REAL", ["dig"], "REAL")
    # --- operadores
    liga("q0", ["="], "EQ")
    liga("q0", ["<>"], "LT")
    liga("q0", ["!"], "NOT")
    for q in ("EQ", "LT", "NOT"):
        liga(q, ["="], "OPEQ")
    # --- ignorados: espaços, comentário (vai até o '\n') e fim de linha
    liga("q0", ["esp"], "ESP")
    liga("ESP", ["esp"], "ESP")
    liga("q0", ["#"], "COM")
    liga("COM", [c for c in CLASSES_SCANNER if c != "nl"], "COM")
    liga("q0", ["nl"], "NL")
    return d


DELTA_SCANNER = _montar_delta()
AFD_SCANNER = AFD("AFD_SCANNER", ESTADOS_SCANNER, CLASSES_SCANNER, DELTA_SCANNER, "q0",
                  TIPO_FINAL.keys(), classe_scanner, DESCRICAO_SCANNER)


def lexema_mais_longo(texto, i):
    """Maximal Munch pela tabela: segue o delta, guarda o último estado final e
    'volta' até ele quando a transição morre. Devolve (fim, tipo) ou None (erro léxico)."""
    q, j, ultimo = AFD_SCANNER.inicial, i, None
    while j < len(texto):
        q = DELTA_SCANNER.get((q, classe_scanner(texto[j])))
        if q is None:
            break
        j += 1
        if q in TIPO_FINAL:
            ultimo = (j, TIPO_FINAL[q])
    return ultimo


def mostrar_munch(texto, i=0):
    """Rastreamento do Maximal Munch passo a passo (como o rodar() dos AFDs)."""
    q, ultimo = AFD_SCANNER.inicial, None
    print(f"lexema_mais_longo({texto!r}, {i})")
    for j in range(i, len(texto)):
        cl = classe_scanner(texto[j])
        prox = DELTA_SCANNER.get((q, cl))
        if prox is None:
            print(f"  [{j}] {texto[j]!r:5} classe {cl:5} δ({q}, {cl}) indefinida → para")
            break
        q = prox
        marca = ""
        if q in TIPO_FINAL:
            ultimo = (j + 1, TIPO_FINAL[q])
            marca = f"   ← final ({TIPO_FINAL[q]}): guarda"
        print(f"  [{j}] {texto[j]!r:5} classe {cl:5} → {q}{marca}")
    if ultimo is None:
        print("  ⇒ nenhum estado final visitado: erro léxico")
    else:
        fim, tipo = ultimo
        print(f"  ⇒ MAXIMAL MUNCH: {texto[i:fim]!r} como {tipo}")


# ================================================================ scanner por tabela
def scanner(texto):
    """Scanner dirigido por tabela: cada lexema vem de lexema_mais_longo() (delta combinado)."""
    tokens, erros = [], []
    i, linha, col, n = 0, 1, 1, len(texto)

    def emitir(tipo, lex, l, c):
        tokens.append(Token(tipo, lex, l, c))

    def erro(lex, l, c, msg, dica):
        erros.append(ErroLexico(l, c, lex, msg, dica))

    while i < n:
        l0, c0 = linha, col
        achado = lexema_mais_longo(texto, i)

        if achado is None:                    # nenhuma transição sai de q0: erro e segue em frente
            ch = texto[i]
            i += 1
            col += 1
            erro(ch, l0, c0, f"caractere inesperado {ch!r}", dica_caractere(ch))
            continue

        fim, tipo = achado
        lex = texto[i:fim]
        i, col = fim, col + len(lex)

        if tipo in ("ESPACO", "COMENTARIO"):
            continue
        if tipo == "NOVA_LINHA":
            if tokens and tokens[-1].tipo != "NOVA_LINHA":
                emitir("NOVA_LINHA", "\\n", l0, c0)
            linha, col = linha + 1, 1
            continue
        if tipo == "PALAVRA":
            t, lex2, msg, dica, extra = classificar_palavra(lex, texto[i] if i < n else "")
            i += extra
            col += extra
            if t:
                emitir(t, lex2, l0, c0)
            else:
                erro(lex2, l0, c0, msg, dica)
        elif tipo == "HORA" and not afd_hora.aceita(lex):
            erro(lex, l0, c0, "horário inválido", "use HH:MM entre 00:00 e 23:59 (ex.: 08:15)")
        elif tipo == "ERRO_REAL":
            erro(lex, l0, c0, "valor incompleto", f"valores precisam de casas decimais: {lex}00")
        elif tipo == "ERRO_BANG":
            erro(lex, l0, c0, "'!' sozinho não é operador", "para 'diferente' use !=")
        else:                                  # INTEIRO, HORA, REAL, ATRIB, OP_REL
            emitir(tipo, lex, l0, c0)

    if tokens and tokens[-1].tipo != "NOVA_LINHA":
        emitir("NOVA_LINHA", "\\n", linha, col)
    emitir("EOF", "", linha, col)
    return tokens, erros


# ================================================================ versão de referência (com whiles)
def scanner_while(texto):
    """Versão original, escrita à mão com `while`s. Mantida só para comparar com o scanner por tabela."""
    tokens, erros = [], []
    i, linha, col = 0, 1, 1
    n = len(texto)

    def emitir(tipo, lex, l, c):
        tokens.append(Token(tipo, lex, l, c))

    def erro(lex, l, c, msg, dica):
        erros.append(ErroLexico(l, c, lex, msg, dica))

    while i < n:
        ch = texto[i]
        ini, l0, c0 = i, linha, col

        # ---- espaços e comentários (ignorados)
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "#":
            while i < n and texto[i] != "\n":
                i += 1
                col += 1
            continue
        if ch == "\n":
            if tokens and tokens[-1].tipo != "NOVA_LINHA":
                emitir("NOVA_LINHA", "\\n", l0, c0)
            i += 1
            linha += 1
            col = 1
            continue

        # ---- palavras: reservadas, placas, vagas, identificadores
        if ch.isalpha() or ch == "_":
            while i < n and (texto[i].isalnum() or texto[i] == "_"):
                i += 1
            # Maximal Munch da placa antiga: 3 maiúsculas + '-' + dígito
            if (re.fullmatch(r"[A-Z]{3}", texto[ini:i]) and i + 1 < n
                    and texto[i] == "-" and texto[i + 1].isdigit()):
                i += 1
                while i < n and texto[i].isalnum():
                    i += 1
            lex = texto[ini:i]
            col += i - ini
            tipo, lex2, msg, dica, extra = classificar_palavra(lex, texto[i] if i < n else "")
            i += extra
            col += extra
            if tipo:
                emitir(tipo, lex2, l0, c0)
            else:
                erro(lex2, l0, c0, msg, dica)
            continue

        # ---- números: INTEIRO, REAL, HORA (Maximal Munch)
        if ch.isdigit():
            while i < n and texto[i].isdigit():
                i += 1
            tipo = "INTEIRO"
            if i + 1 < n and texto[i] == ":" and texto[i + 1].isdigit():      # 08 → 08:15
                i += 1
                while i < n and texto[i].isdigit():
                    i += 1
                tipo = "HORA"
            elif i < n and texto[i] == ".":
                if i + 1 < n and texto[i + 1].isdigit():                       # 12 → 12.00
                    i += 1
                    while i < n and texto[i].isdigit():
                        i += 1
                    tipo = "REAL"
                else:
                    i += 1
                    tipo = "ERRO_REAL"
            lex = texto[ini:i]
            col += i - ini
            if tipo == "HORA" and not afd_hora.aceita(lex):
                erro(lex, l0, c0, "horário inválido",
                     "use HH:MM entre 00:00 e 23:59 (ex.: 08:15)")
            elif tipo == "ERRO_REAL":
                erro(lex, l0, c0, "valor incompleto",
                     f"valores precisam de casas decimais: {lex}00")
            else:
                emitir(tipo, lex, l0, c0)
            continue

        # ---- operadores (Maximal Munch: '=' × '==', '<' × '<=' ...)
        if ch in "=<>!":
            if i + 1 < n and texto[i + 1] == "=":
                lex, tipo = ch + "=", "OP_REL"
            else:
                lex = ch
                tipo = "ATRIB" if ch == "=" else ("OP_REL" if ch in "<>" else None)
            i += len(lex)
            col += len(lex)
            if tipo:
                emitir(tipo, lex, l0, c0)
            else:
                erro(lex, l0, c0, "'!' sozinho não é operador", "para 'diferente' use !=")
            continue

        # ---- qualquer outro caractere: erro e segue em frente
        i += 1
        col += 1
        erro(ch, l0, c0, f"caractere inesperado {ch!r}", dica_caractere(ch))

    if tokens and tokens[-1].tipo != "NOVA_LINHA":
        emitir("NOVA_LINHA", "\\n", linha, col)
    emitir("EOF", "", linha, col)
    return tokens, erros


# ================================================================ bateria: tabela × while
PEDACOS = ["ENTRADA", "SAIDA", "SAÍDA", "saida", "PAGO", "VAGA", "BRA2E19", "ABC-1234", "ABC1234",
           "ABC-", "AB1-2", "A_B-1", "08:15", "25:10", "8:1", "12.00", "12.", "12:", "12", "A12",
           "valor_hora", "R$", "R", "_x", "=", "==", "<", "<=", ">", ">=", "!", "!=", "$", ",", "@",
           "-", ":", ".", "é", "1", "Z", " ", " ", "\t", "\n", "\n", "# comentário", "#"]


def entradas_teste(n=2000, semente=7):
    """Roteiros fixos + n entradas aleatórias coladas a partir de PEDACOS (inclui casos de borda)."""
    rnd = random.Random(semente)
    fixas = [ROTEIRO_OK, ROTEIRO_MUNCH, ROTEIRO_ERROS, "", "\n", "   ", "# só comentário"]
    return fixas + ["".join(rnd.choice(PEDACOS) for _ in range(rnd.randint(1, 14))) for _ in range(n)]


def bateria_scanner(entradas=None):
    """Compara scanner (tabela) × scanner_while. Devolve a lista de entradas divergentes."""
    entradas = entradas_teste() if entradas is None else entradas
    return [e for e in entradas if scanner(e) != scanner_while(e)]


def mostrar_scan(texto):
    tokens, erros = scanner(texto)
    print(f"{'lin:col':8}{'TIPO':12}lexema")
    for t in tokens:
        print(f"{t.linha}:{t.coluna:<6}{t.tipo:12}{t.lexema}")
    print(f"\n{len(tokens)} tokens, {len(erros)} erro(s) léxico(s)")
    for e in erros:
        print(f"  ERRO {e.linha}:{e.coluna} {e.lexema!r}: {e.mensagem}\n       dica → {e.dica}")
    return tokens, erros


ROTEIRO_OK = """# entrada e saída de um veículo
ENTRADA BRA2E19 08:15 VAGA A12
SAIDA BRA2E19 10:40 PAGO 12.00   # pagou na saída
ENTRADA ABC-1234 09:00 VAGA B7
TARIFA valor_hora = 6.00
ALERTA permanencia >= 240
ALERTA vagas_livres <= 5
"""

ROTEIRO_MUNCH = "ALERTA x == 3\nALERTA x = 3\nALERTA x < 3\nALERTA x <= 3\nPAGO 12\nPAGO 12.00\n08 08:15"

ROTEIRO_ERROS = """ENTRADA ABC1234 25:10 VAGA A12
SAÍDA BRA2E19 10:40 PAGO R$12.00
saida BR2E19 10:40 PAGO 12.
TARIFA valor_hora = 6,50 @
"""


def demo_tabela():
    print("=" * 70 + "\nBÔNUS — SCANNER POR TABELA (δ combinado, sem while)\n" + "=" * 70)
    AFD_SCANNER.tabela()
    print("\n(PALAVRA, INTEIRO, HORA... = tipo do lexema em cada estado final;"
          " reservadas/placa/vaga são decididas depois, pela tabela de palavras e pelo AFD_PLACA)\n")
    print("Maximal Munch pela tabela — guarda o último estado final e volta até ele:\n")
    for entrada in ("<= 3", "12.00", "08:15", "ABC-1234", "12:x", "ABC-x"):
        mostrar_munch(entrada)
        print()
    entradas = entradas_teste()
    div = bateria_scanner(entradas)
    print(f"Bateria scanner por tabela × scanner com while: {len(entradas)} entradas, "
          f"{len(div)} divergência(s)")
    return len(div)


def demo():
    print("=" * 70 + "\nSCANNER — entrada válida\n" + "=" * 70)
    mostrar_scan(ROTEIRO_OK)
    print("\n" + "=" * 70 + "\nSCANNER — Maximal Munch\n" + "=" * 70)
    mostrar_scan(ROTEIRO_MUNCH)
    print("\n" + "=" * 70 + "\nSCANNER — entrada com erros (continua após cada erro)\n" + "=" * 70)
    mostrar_scan(ROTEIRO_ERROS)
    print()
    return demo_tabela()


if __name__ == "__main__":
    demo()
