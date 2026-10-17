"""Bônus — Tudo conectado: roteiro → scanner → tokens → eventos da cancela.

    ENTRADA <placa> <hora> ...           → liberar
    SAIDA <placa> <hora> PAGO <valor>    → liberar   (sem PAGO a cancela não abre)
    ABRIU / FECHOU                       → fim_abertura / fim_fechamento
    PASSOU                               → veiculo_passou
    OBSTACULO                            → sensor_obstaculo
    TEMPO                                → tempo_esgotado
    FALHA / MANUTENCAO                   → falha_motor / manutencao_ok

Linhas com erro léxico são ignoradas (não geram evento).
"""
from cancela import cancela
from scanner import scanner

EVENTO_DE = {"ABRIU": "fim_abertura", "FECHOU": "fim_fechamento", "PASSOU": "veiculo_passou",
             "OBSTACULO": "sensor_obstaculo", "TEMPO": "tempo_esgotado",
             "FALHA": "falha_motor", "MANUTENCAO": "manutencao_ok"}


def linhas_de_tokens(tokens):
    atual = []
    for t in tokens:
        if t.tipo in ("NOVA_LINHA", "EOF"):
            if atual:
                yield atual
            atual = []
        else:
            atual.append(t)


def eventos_do_roteiro(texto):
    """Passa o roteiro pelo scanner e traduz cada comando num evento da cancela.
    Devolve (erros_lexicos, passos), onde cada passo é (linha, comando, evento|None, nota|None).

    Uma linha com erro léxico NÃO gera evento: o comando está malformado (placa sem hífen,
    horário 25:10...) e a cancela não deve abrir por causa dele."""
    tokens, erros = scanner(texto)
    erros_por_linha = {}
    for e in erros:
        erros_por_linha.setdefault(e.linha, []).append(e)
    comandos = {cmd[0].linha: cmd for cmd in linhas_de_tokens(tokens)}

    passos = []
    for linha in sorted(set(comandos) | set(erros_por_linha)):
        cmd = comandos.get(linha, [])
        texto_cmd = " ".join(t.lexema for t in cmd)
        if linha in erros_por_linha:
            ruins = ", ".join(repr(e.lexema) for e in erros_por_linha[linha])
            if not texto_cmd:
                texto_cmd = ruins
            passos.append((linha, texto_cmd, None, f"linha com erro léxico ({ruins}): comando ignorado"))
            continue
        cab = cmd[0]
        if cab.tipo != "RESERVADA":
            ev, nota = None, "ignorado: comando não começa com palavra reservada"
        elif cab.lexema == "ENTRADA":
            ev, nota = "liberar", None
        elif cab.lexema == "SAIDA":
            if any(t.lexema == "PAGO" for t in cmd):
                ev, nota = "liberar", None
            else:
                ev, nota = None, "pagamento pendente: nenhum evento gerado"
        elif cab.lexema in EVENTO_DE:
            ev, nota = EVENTO_DE[cab.lexema], None
        else:
            ev, nota = None, "comando de configuração: não gera evento"
        passos.append((linha, texto_cmd, ev, nota))
    return erros, passos


def executar_roteiro(texto, maquina=cancela):
    erros, passos = eventos_do_roteiro(texto)
    for e in erros:
        print(f"ERRO léxico {e.linha}:{e.coluna} {e.lexema!r} → {e.dica}")
    maquina.reiniciar()
    print(f"cancela começa em {maquina.estado}")
    for linha, texto_cmd, ev, nota in passos:
        print(f"linha {linha}: {texto_cmd}")
        if ev:
            maquina.disparar(ev)
        else:
            print(f"  ⚠ {nota} (cancela continua {maquina.estado})")
    print(f"cancela termina em {maquina.estado}")


ROTEIRO_CANCELA = """ENTRADA BRA2E19 08:15 VAGA A12
ABRIU
PASSOU
OBSTACULO      # alguém parou embaixo da cancela
ABRIU
TEMPO
FECHOU
SAIDA ABC-1234 11:00      # sem PAGO
PASSOU                    # tentativa de fura-cancela
SAIDA BRA2E19 10:40 PAGO 12.00
ABRIU
PASSOU
FECHOU
"""


def demo():
    print("=" * 70 + "\nBÔNUS — TUDO CONECTADO (roteiro → eventos da cancela)\n" + "=" * 70)
    executar_roteiro(ROTEIRO_CANCELA)


if __name__ == "__main__":
    demo()
