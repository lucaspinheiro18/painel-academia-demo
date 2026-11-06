"""Preenche o histórico com atendimentos FICTÍCIOS para a demonstração (só se estiver vazio)."""
import random
from datetime import datetime, timedelta

import config
import historico

ASSUNTOS = {
    "Certificado": "Quando recebo o certificado do curso?",
    "Frequência mínima": "Se eu faltar uma aula ainda consigo o certificado?",
    "Link das aulas online": "Não achei o link do Zoom da turma.",
    "Local do presencial": "Qual será o endereço da parte presencial?",
    "Gravações": "As aulas ficam gravadas? Posso assistir depois?",
    "Troca de turma": "Preciso trocar de turma, como faço?",
    "Reembolso": "Quero saber como pedir reembolso.",
    "O que levar ao presencial": "O que devo levar no presencial?",
}
PESOS = [18, 22, 14, 12, 8, 6, 4, 6]


def semear(n=80, semente=7):
    if historico.modo() != "sqlite" or historico.total() > 0:
        return
    rnd = random.Random(semente)
    agora = datetime.now()
    con = historico._conectar()
    try:
        for _ in range(n):
            assunto = rnd.choices(list(ASSUNTOS), PESOS)[0]
            canal = rnd.choices(["WhatsApp", "E-mail"], [65, 35])[0]
            quando = agora - timedelta(days=rnd.randint(0, 20), hours=rnd.randint(0, 9), minutes=rnd.randint(0, 59))
            con.execute(
                """INSERT INTO atendimentos (data_hora, id_turma, operador, duvida, resposta, encaminhado_email,
                   assunto, modelo_ia, tempo_ms, origem, canal) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (quando.strftime("%Y-%m-%d %H:%M:%S"), rnd.choice([None, *range(101, 221)]),
                 rnd.choice(["Operador A", "Operador B", "Operador C"]), ASSUNTOS[assunto],
                 "(resposta de exemplo)", int(rnd.random() < .08), assunto, config.MODELO_IA,
                 rnd.randint(1200, 4200), "demo", canal))
        con.commit()
    finally:
        con.close()
    historico.atualizar_xlsx()
