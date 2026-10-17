"""Testes automáticos do projeto Estacionamento Inteligente.

Rodar:   python testes.py          (ou  python -m unittest testes -v)

Cada classe corresponde a um requisito do trabalho (R1–R6 + bônus).
Não precisa instalar nada: usa só o unittest da biblioteca padrão.
"""
import io
import os
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from afd import bateria, pares_equivalentes
from cancela import MaquinaEstados, TRANSICOES_CANCELA
from conectado import eventos_do_roteiro, ROTEIRO_CANCELA
from scanner import (scanner, scanner_while, RESERVADAS, ROTEIRO_OK, ROTEIRO_ERROS,
                     AFD_SCANNER, lexema_mais_longo, bateria_scanner)
from validadores import (afd_placa, afd_hora, RE_PLACA, RE_HORA,
                         PLACA_ACEITAS, PLACA_REJEITADAS, HORA_ACEITAS, HORA_REJEITADAS)


def silencioso(func, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = func(*args)
    return r, buf.getvalue()


def tipos(texto):
    return [(t.tipo, t.lexema) for t in scanner(texto)[0] if t.tipo not in ("NOVA_LINHA", "EOF")]


# ------------------------------------------------------------------ R1
class R1_Validadores(unittest.TestCase):
    def test_placa_tem_pelo_menos_5_estados(self):
        self.assertGreaterEqual(len(afd_placa.estados), 5)

    def test_horario_tem_pelo_menos_5_estados(self):
        self.assertGreaterEqual(len(afd_hora.estados), 5)

    def test_horario_usa_classes_finas(self):
        # mais de uma classe para dígitos: 0-1, 2, 3, 4-5, 6-9
        self.assertGreaterEqual(len([c for c in afd_hora.classes if c != ":"]), 4)

    def test_placa_aceita_os_dois_formatos(self):
        self.assertTrue(afd_placa.aceita("ABC-1234"))   # antiga
        self.assertTrue(afd_placa.aceita("BRA2E19"))    # Mercosul

    def test_tabela_imprime_todos_os_estados(self):
        for afd in (afd_placa, afd_hora):
            _, saida = silencioso(afd.tabela)
            for q in afd.estados:
                self.assertIn(q, saida, f"{afd.nome}: estado {q} fora da tabela()")


# ------------------------------------------------------------------ R2
class R2_Rastreamento(unittest.TestCase):
    def test_placa_aceita(self):
        ok, linhas = afd_placa.rodar("BRA2E19", imprimir=False)
        self.assertTrue(ok)
        self.assertIn("ACEITA", linhas[-1])

    def test_placa_morre_no_meio(self):
        ok, linhas = afd_placa.rodar("BRA-2E19", imprimir=False)
        self.assertFalse(ok)
        self.assertIn("morreu no meio", linhas[-1])

    def test_placa_termina_fora_de_F(self):
        ok, linhas = afd_placa.rodar("ABC-123", imprimir=False)
        self.assertFalse(ok)
        self.assertIn("∉ F", linhas[-1])

    def test_horario_aceita(self):
        self.assertTrue(afd_hora.rodar("23:59", imprimir=False)[0])

    def test_horario_morre_no_meio(self):
        ok, linhas = afd_hora.rodar("24:00", imprimir=False)
        self.assertFalse(ok)
        self.assertIn("morreu no meio", linhas[-1])

    def test_horario_termina_fora_de_F(self):
        ok, linhas = afd_hora.rodar("12:5", imprimir=False)
        self.assertFalse(ok)
        self.assertIn("∉ F", linhas[-1])


# ------------------------------------------------------------------ R3
class R3_BateriaAFDxRegex(unittest.TestCase):
    def test_placa_zero_divergencias(self):
        div, _ = silencioso(bateria, afd_placa, RE_PLACA, PLACA_ACEITAS, PLACA_REJEITADAS)
        self.assertEqual(div, 0)

    def test_horario_zero_divergencias(self):
        div, _ = silencioso(bateria, afd_hora, RE_HORA, HORA_ACEITAS, HORA_REJEITADAS)
        self.assertEqual(div, 0)

    def test_minimo_5_aceitas_e_5_rejeitadas(self):
        for ac, rj in ((PLACA_ACEITAS, PLACA_REJEITADAS), (HORA_ACEITAS, HORA_REJEITADAS)):
            self.assertGreaterEqual(len(ac), 5)
            self.assertGreaterEqual(len(rj), 5)

    def test_palavra_vazia_incluida_e_rejeitada(self):
        self.assertIn("", PLACA_REJEITADAS)
        self.assertIn("", HORA_REJEITADAS)
        self.assertFalse(afd_placa.aceita(""))
        self.assertFalse(afd_hora.aceita(""))

    def test_expectativas_corretas(self):
        for afd, ac, rj in ((afd_placa, PLACA_ACEITAS, PLACA_REJEITADAS),
                            (afd_hora, HORA_ACEITAS, HORA_REJEITADAS)):
            for w in ac:
                self.assertTrue(afd.aceita(w), f"{afd.nome} deveria aceitar {w!r}")
            for w in rj:
                self.assertFalse(afd.aceita(w), f"{afd.nome} deveria rejeitar {w!r}")

    def test_horario_exaustivo_contra_regex(self):
        """Compara AFD × RegEx em TODAS as 10.000 combinações DD:DD."""
        padrao = re.compile(RE_HORA)
        for h in range(100):
            for m in range(100):
                w = f"{h:02d}:{m:02d}"
                self.assertEqual(afd_hora.aceita(w), padrao.fullmatch(w) is not None, w)


# ------------------------------------------------------------------ R4
class R4_Cancela(unittest.TestCase):
    def setUp(self):
        self.m = MaquinaEstados("teste", "FECHADA", TRANSICOES_CANCELA)

    def test_pelo_menos_5_estados_e_6_transicoes(self):
        self.assertGreaterEqual(len(self.m.estados), 5)
        self.assertGreaterEqual(len(self.m.transicoes), 6)

    def test_fluxo_valido_entrada_normal(self):
        for ev in ["liberar", "fim_abertura", "veiculo_passou", "fim_fechamento"]:
            self.assertTrue(self.m.disparar(ev, imprimir=False), ev)
        self.assertEqual(self.m.estado, "FECHADA")

    def test_fluxo_valido_obstaculo_reabre(self):
        for ev in ["liberar", "fim_abertura", "veiculo_passou", "sensor_obstaculo"]:
            self.assertTrue(self.m.disparar(ev, imprimir=False), ev)
        self.assertEqual(self.m.estado, "ABRINDO")

    def test_fluxo_invalido_fura_cancela(self):
        self.assertFalse(self.m.disparar("veiculo_passou", imprimir=False))
        self.assertEqual(self.m.estado, "FECHADA")

    def test_fluxo_invalido_liberar_travada(self):
        self.m.disparar("liberar", imprimir=False)
        self.m.disparar("falha_motor", imprimir=False)
        self.assertFalse(self.m.disparar("liberar", imprimir=False))
        self.assertEqual(self.m.estado, "TRAVADA")

    def test_recusa_mostra_eventos_permitidos(self):
        _, saida = silencioso(self.m.disparar, "veiculo_passou")
        self.assertIn("RECUSADO", saida)
        self.assertIn("liberar", saida)


# ------------------------------------------------------------------ R5
class R5_Scanner(unittest.TestCase):
    def test_pelo_menos_8_tipos_de_token(self):
        ts = {t for t, _ in tipos(ROTEIRO_OK)}
        self.assertGreaterEqual(len(ts), 8, ts)

    def test_pelo_menos_3_reservadas(self):
        self.assertGreaterEqual(len(RESERVADAS), 3)

    def test_comando_de_entrada(self):
        self.assertEqual(tipos("ENTRADA BRA2E19 08:15 VAGA A12"),
                         [("RESERVADA", "ENTRADA"), ("PLACA", "BRA2E19"), ("HORA", "08:15"),
                          ("RESERVADA", "VAGA"), ("VAGA_ID", "A12")])

    def test_comando_de_saida(self):
        self.assertEqual(tipos("SAIDA ABC-1234 10:40 PAGO 12.00"),
                         [("RESERVADA", "SAIDA"), ("PLACA", "ABC-1234"), ("HORA", "10:40"),
                          ("RESERVADA", "PAGO"), ("REAL", "12.00")])

    def test_maximal_munch_igual(self):
        self.assertEqual(tipos("x == 3")[1], ("OP_REL", "=="))
        self.assertEqual(tipos("x = 3")[1], ("ATRIB", "="))

    def test_maximal_munch_menor_igual(self):
        self.assertEqual(tipos("x <= 3")[1], ("OP_REL", "<="))
        self.assertEqual(tipos("x < 3")[1], ("OP_REL", "<"))

    def test_maximal_munch_inteiro_real(self):
        self.assertEqual(tipos("12"), [("INTEIRO", "12")])
        self.assertEqual(tipos("12.00"), [("REAL", "12.00")])

    def test_maximal_munch_hora(self):
        self.assertEqual(tipos("08:15"), [("HORA", "08:15")])

    def test_ignora_espacos_e_comentarios(self):
        self.assertEqual(tipos("   # só comentário\n\t  PAGO   # outro\n"), [("RESERVADA", "PAGO")])

    def test_erros_tem_linha_coluna_e_dica(self):
        _, erros = scanner(ROTEIRO_ERROS)
        self.assertGreater(len(erros), 0)
        for e in erros:
            self.assertGreaterEqual(e.linha, 1)
            self.assertGreaterEqual(e.coluna, 1)
            self.assertTrue(e.dica)

    def test_posicao_do_erro_correta(self):
        _, erros = scanner("ENTRADA ABC1234")
        self.assertEqual((erros[0].linha, erros[0].coluna, erros[0].lexema), (1, 9, "ABC1234"))

    def test_dicas_especificas_do_dominio(self):
        dicas = " ".join(e.dica for e in scanner(ROTEIRO_ERROS)[1])
        self.assertIn("ABC-1234", dicas)          # placa antiga sem hífen
        self.assertIn("HH:MM", dicas)             # horário inválido
        self.assertIn("SAIDA", dicas)             # reservada com acento

    def test_continua_apos_erro(self):
        toks, erros = scanner("ENTRADA ABC1234 08:15\nPAGO 12.00")
        self.assertEqual(len(erros), 1)
        self.assertIn(("HORA", "08:15"), [(t.tipo, t.lexema) for t in toks])
        self.assertIn(("REAL", "12.00"), [(t.tipo, t.lexema) for t in toks])


# ------------------------------------------------------------------ bônus
class Bonus(unittest.TestCase):
    def test_afds_minimos(self):
        self.assertEqual(pares_equivalentes(afd_placa), [])
        self.assertEqual(pares_equivalentes(afd_hora), [])

    def test_roteiro_vira_eventos(self):
        erros, passos = eventos_do_roteiro(ROTEIRO_CANCELA)
        self.assertEqual(erros, [])
        eventos = [ev for _, _, ev, _ in passos]
        self.assertEqual(eventos[0], "liberar")
        self.assertIn("sensor_obstaculo", eventos)

    def test_linha_com_erro_lexico_nao_gera_evento(self):
        _, passos = eventos_do_roteiro("ENTRADA ABC1234 25:10 VAGA A12\nENTRADA BRA2E19 08:15 VAGA A12")
        self.assertIsNone(passos[0][2])                 # placa e hora inválidas: ignorada
        self.assertIn("erro léxico", passos[0][3])
        self.assertEqual(passos[1][2], "liberar")       # a linha correta continua valendo

    def test_saida_sem_pago_nao_libera(self):
        _, passos = eventos_do_roteiro("SAIDA ABC-1234 11:00")
        self.assertIsNone(passos[0][2])

    def test_scanner_por_tabela_igual_ao_while(self):
        self.assertEqual(bateria_scanner(), [])

    def test_scanner_por_tabela_nos_exemplos_do_enunciado(self):
        texto = "ENTRADA BRA2E19 08:15 VAGA A12\nSAIDA BRA2E19 10:40 PAGO 12.00 "
        self.assertEqual(scanner(texto), scanner_while(texto))

    def test_maximal_munch_pela_tabela(self):
        casos = {"<= 3": (2, "OP_REL"), "12.00": (5, "REAL"), "08:15": (5, "HORA"),
                 "ABC-1234": (8, "PALAVRA"), "ABC-x": (3, "PALAVRA"), "12:x": (2, "INTEIRO")}
        for texto, esperado in casos.items():
            self.assertEqual(lexema_mais_longo(texto, 0), esperado, texto)

    def test_afd_do_scanner_e_uma_tabela(self):
        self.assertGreaterEqual(len(AFD_SCANNER.estados), 5)
        _, saida = silencioso(AFD_SCANNER.tabela)
        for q in AFD_SCANNER.estados:
            self.assertIn(q, saida)


# ------------------------------------------------------------------ R6: painel ipywidgets (notebook)
class R6_PainelNotebook(unittest.TestCase):
    """Executa as células do painel.ipynb e clica em todos os botões (precisa de ipywidgets)."""

    def test_painel_roda_e_responde(self):
        try:
            import json
            import ipywidgets as W
            import IPython.display as d
        except ImportError as e:
            self.skipTest(f"ipywidgets não instalado: {e}")
        with open("painel.ipynb", encoding="utf-8") as f:
            celulas = [("".join(c["source"])) for c in json.load(f)["cells"] if c["cell_type"] == "code"]
        original = d.display
        d.display = lambda *a, **k: None
        g = {"__name__": "__main__", "display": d.display}
        try:
            with redirect_stdout(io.StringIO()):
                for fonte in celulas[:6]:          # as 6 primeiras montam o painel
                    exec(fonte, g)
                paineis = [g["painel_validadores"](), g["painel_scanner"](), g["painel_cancela"](),
                           g["painel_checklist"]()]

                def todos(w):
                    yield w
                    for ch in getattr(w, "children", ()) or ():
                        yield from todos(ch)

                cliques = 0
                for p in paineis:
                    for w in list(todos(p)):
                        if isinstance(w, W.Text):
                            for v in ("BRA2E19", "", "24:00"):
                                w.value = v
                        if isinstance(w, W.Textarea):
                            w.value = ROTEIRO_ERROS
                    for w in list(todos(p)):
                        if isinstance(w, W.Button):
                            w.click()
                            cliques += 1
        finally:
            d.display = original
        self.assertGreater(cliques, 10)


# ------------------------------------------------------------------ R6 / execução completa
class R6_ExecucaoEInterface(unittest.TestCase):
    def test_main_roda_do_inicio_ao_fim(self):
        r = subprocess.run([sys.executable, "main.py", "--sem-gui"], capture_output=True,
                           text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertNotIn("✘ ", r.stdout.split("CHECKLIST")[-1])

    def test_interface_abre_as_tres_paginas(self):
        try:
            import tkinter as tk
            raiz = tk.Tk()
            raiz.destroy()
        except Exception as e:
            self.skipTest(f"sem tkinter ou sem tela: {e}")
        import interface
        app = interface.App()
        try:
            self.assertEqual(set(app.paginas), {"Validadores", "Scanner", "Cancela"})
            for nome in app.paginas:
                app.ir(nome)
                app.update()
            pv = app.paginas["Validadores"]
            pv.usar("BRA2E19")
            while pv.anim:
                app.update()
                app.after(20)
            self.assertTrue(pv.aceitou)
            pc = app.paginas["Cancela"]
            pc.disparar("liberar")
            self.assertEqual(pc.maquina.estado, "ABRINDO")
            # numa janela baixa, cada página rola até o fim (nada fica cortado)
            app.minsize(1, 1)
            app.geometry("1200x480")
            for nome, env in app.envelopes.items():
                app.ir(nome)
                app.update()
                self.assertGreater(env.altura_minima(), env.canvas.winfo_height(), nome)
                env.canvas.yview_moveto(1.0)
                app.update()
                self.assertAlmostEqual(env.canvas.yview()[1], 1.0, places=2, msg=nome)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
