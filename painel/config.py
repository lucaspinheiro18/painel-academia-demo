"""Configurações do painel. Se um nome de arquivo ou de aba mudar, ajuste aqui."""
import os

# Pasta onde ficam as planilhas (a pasta de fora de painel/, como no repositório do GitHub)
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# --- IA ---
MODELO_IA = os.environ.get("APP_MODELO_IA", "gemini-3.5-flash-lite")
TEMPERATURA = 0.1

# --- Planilhas (ficam na pasta de fora de painel/) ---
ARQ_CBF = os.path.join(BASE, "Turmas_Ficticias.xlsx")
ABA_CBF = "Licenças"
ARQ_ORG = os.path.join(BASE, "Organizacao_Ficticia.xlsx")
ABA_ORG = "2026"
ARQ_FAQ = os.path.join(BASE, "FAQ_Ficticia.xlsx")
ARQ_HISTORICO_ANTIGO = os.path.join(BASE, "Historico_Atendimentos.xlsx")  # importado uma única vez, se existir

# --- Histórico de atendimentos (SQLite) ---
DB_PATH = os.environ.get("APP_DB_PATH", "historico.db")
# Excel único, reescrito a cada resposta (é o arquivo que o Power BI lê). Fica ao lado do historico.db.
XLSX_PATH = os.environ.get(
    "APP_XLSX_PATH",
    os.path.join(os.path.dirname(DB_PATH), "Atendimentos_PowerBI.xlsx"))

# --- Textos fixos ---
EMAIL_ATENDIMENTO = "atendimento@academiaexemplo.example"
# A Academia Exemplo não indica hotéis: o assistente usa este texto se o aluno perguntar sobre hospedagem.
TEXTO_SEM_HOTEL = (
    "A Academia Exemplo não possui hotéis parceiros ou indicações oficiais "
    "de hospedagem para esta turma."
)

# --- Assistente de E-mail ---
# Assinatura que fecha toda resposta por e-mail (ajuste ao seu gosto).
ASSINATURA_EMAIL = "Equipe de Atendimento\nAcademia Exemplo"
# Usado quando o assunto não está na FAQ: resposta curta para você revisar ou tratar à mão.
TEXTO_EMAIL_FORA_FAQ = (
    "Recebemos a sua mensagem e agradecemos o contato.\n\n"
    "Para que possamos orientá-lo(a) corretamente, nossa equipe irá analisar a sua solicitação "
    "e retornará assim que possível."
)

# Quando Curso, Licença ou Local estão vazios (e a célula NÃO é mesclada),
# repetir o valor da linha de cima, como o painel antigo fazia.
# O painel sempre avisa quando isso acontece. Datas nunca são repetidas.
HERDAR_CELULA_VAZIA = True
