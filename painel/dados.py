"""Leitura das planilhas: Academia Exemplo (turmas), Organização (Zoom) e FAQ."""
from __future__ import annotations

import glob
import os
import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime

import openpyxl

import config

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

MESES_PT = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}

COLUNAS_CBF = {
    "curso": "Curso",
    "licenca": "Licença",
    "ini_pres": "Início Presencial",
    "fim_pres": "Fim Presencial",
    "ini_onl": "Início Online",
    "fim_onl": "Fim Online",
    "local": "Local do Presencial",
}

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Um aviso é uma tupla (gravidade, texto); gravidade: "erro" ou "aviso".
Aviso = tuple


@dataclass
class Turma:
    id: int
    curso: str = ""
    licenca: str = ""
    inicio_presencial: str = ""
    fim_presencial: str = ""
    inicio_online: str = ""
    fim_online: str = ""
    local: str = ""
    zoom: str = ""
    avisos: list = field(default_factory=list)

    @property
    def curso_licenca(self) -> str:
        if self.curso and self.licenca:
            return f"{self.curso} ({self.licenca})"
        return self.curso or self.licenca


@dataclass
class Base:
    turmas: dict
    faq: list
    faq_texto: str
    avisos: list


# ----------------------------------------------------------------------------
# utilitários
# ----------------------------------------------------------------------------
def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_id(v):
    """Converte 932, 932.0 ou '932' em 932. Devolve None se não for um número inteiro."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else None
    try:
        f = float(str(v).strip().replace(",", "."))
    except ValueError:
        return None
    return int(f) if f.is_integer() else None


def formatar_data(v):
    """Devolve (texto, invalida). Ex.: 05 de Out. de 2026."""
    if _txt(v) == "":
        return "", False
    d = None
    if isinstance(v, datetime):
        d = v
    elif isinstance(v, date):
        d = datetime(v.year, v.month, v.day)
    else:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                d = datetime.strptime(_txt(v), fmt)
                break
            except ValueError:
                continue
    if d is None:
        return "", True
    return f"{d.day:02d} de {MESES_PT[d.month]}. de {d.year}", False


def limpar_comentario(texto: str) -> str:
    """Remove o cabeçalho que o Excel coloca em comentários encadeados."""
    t = texto or ""
    t = re.sub(
        r"\[(?:Threaded comment|Coment[aá]rio encadeado)\].*?(?:Comment|Coment[aá]rio):\s*",
        "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"^\s*Endereço:[\s\xa0]*", "", t.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip()


def localizar_arquivo(nome: str):
    """Acha o arquivo pelo nome; aceita cópias como 'nome (1).xlsx' (a mais recente)."""
    if os.path.exists(nome):
        return nome
    stem, ext = os.path.splitext(nome)
    candidatos = glob.glob(f"{glob.escape(stem)}*{ext}")
    candidatos = [c for c in candidatos if not os.path.basename(c).startswith("~$")]
    if not candidatos:
        return None
    return max(candidatos, key=os.path.getmtime)


def assinatura_arquivos():
    """Usada como chave de cache: se uma planilha mudar, o painel relê sozinho."""
    sig = []
    for nome in (config.ARQ_CBF, config.ARQ_ORG, config.ARQ_FAQ):
        p = localizar_arquivo(nome)
        sig.append((nome, p, os.path.getmtime(p) if p else None))
    return tuple(sig)


class Planilha:
    """Uma aba do Excel com células mescladas resolvidas e cabeçalho localizado."""

    def __init__(self, ws):
        self.ws = ws
        self._mesclada = {}
        for rng in ws.merged_cells.ranges:
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    if (r, c) != (rng.min_row, rng.min_col):
                        self._mesclada[(r, c)] = (rng.min_row, rng.min_col)
        self.linha_cab = self._achar_cabecalho()
        self.colunas = {}  # nome (minúsculo) -> número da coluna
        if self.linha_cab:
            for c in range(1, ws.max_column + 1):
                nome = _txt(ws.cell(self.linha_cab, c).value).casefold()
                if nome and nome not in self.colunas:
                    self.colunas[nome] = c

    def _achar_cabecalho(self):
        for r in range(1, min(self.ws.max_row, 10) + 1):
            for c in range(1, self.ws.max_column + 1):
                if _txt(self.ws.cell(r, c).value).casefold() == "id":
                    return r
        return None

    def celula(self, r, c):
        return self.ws.cell(*self._mesclada.get((r, c), (r, c)))

    def cel(self, r, nome):
        c = self.colunas.get(nome.casefold())
        return self.celula(r, c) if c else None


# ----------------------------------------------------------------------------
# planilha Academia Exemplo
# ----------------------------------------------------------------------------
def _ler_cbf(avisos_globais: list) -> dict:
    caminho = localizar_arquivo(config.ARQ_CBF)
    if not caminho:
        raise FileNotFoundError(f"Planilha não encontrada: {config.ARQ_CBF}")
    wb = openpyxl.load_workbook(caminho, data_only=True)
    try:
        if config.ABA_CBF not in wb.sheetnames:
            raise ValueError(f"Aba '{config.ABA_CBF}' não encontrada em {os.path.basename(caminho)}. "
                             f"Abas existentes: {', '.join(wb.sheetnames)}")
        pl = Planilha(wb[config.ABA_CBF])
        if "id" not in pl.colunas:
            raise ValueError(f"Coluna 'ID' não encontrada na aba '{config.ABA_CBF}'.")
        ausentes = [n for n in COLUNAS_CBF.values() if n.casefold() not in pl.colunas]
        if ausentes:
            avisos_globais.append(("aviso", "Colunas não encontradas na planilha Academia Exemplo: "
                                   + ", ".join(ausentes)))

        turmas: dict = {}
        ultimo: dict = {}
        for r in range(pl.linha_cab + 1, pl.ws.max_row + 1):
            id_ = parse_id(pl.cel(r, "ID").value)
            if id_ is None:
                continue
            if id_ in turmas:
                avisos_globais.append(("aviso", f"O ID {id_} aparece mais de uma vez na planilha; usei a última linha."))
            t = Turma(id=id_)
            herdados: list = []

            def texto_herdavel(chave):
                cel = pl.cel(r, COLUNAS_CBF[chave])
                v = _txt(cel.value) if cel is not None else ""
                if v:
                    ultimo[chave] = v
                    return v
                if cel is not None and config.HERDAR_CELULA_VAZIA and chave in ultimo:
                    herdados.append(COLUNAS_CBF[chave])
                    return ultimo[chave]
                return ""

            t.curso = texto_herdavel("curso")
            t.licenca = texto_herdavel("licenca")

            # local + comentário da célula (endereço completo)
            cel = pl.cel(r, COLUNAS_CBF["local"])
            base_local = _txt(cel.value) if cel is not None else ""
            if base_local:
                comentario = limpar_comentario(cel.comment.text) if cel.comment else ""
                t.local = f"{base_local} - {comentario}" if comentario else base_local
                ultimo["local"] = t.local
            elif cel is not None and config.HERDAR_CELULA_VAZIA and "local" in ultimo:
                t.local = ultimo["local"]
                herdados.append(COLUNAS_CBF["local"])

            # datas (nunca herdadas)
            for chave, atributo in (("ini_pres", "inicio_presencial"), ("fim_pres", "fim_presencial"),
                                    ("ini_onl", "inicio_online"), ("fim_onl", "fim_online")):
                cel = pl.cel(r, COLUNAS_CBF[chave])
                if cel is None:
                    continue
                texto, invalida = formatar_data(cel.value)
                setattr(t, atributo, texto)
                if invalida:
                    t.avisos.append(("aviso", f"'{COLUNAS_CBF[chave]}': o valor \"{_txt(cel.value)}\" não é uma data válida."))

            if herdados:
                t.avisos.append(("aviso", "Células vazias na planilha; usei o valor da linha anterior em: "
                                 + ", ".join(herdados) + ". Confira antes de enviar."))
            turmas[id_] = t
        return turmas
    finally:
        wb.close()


# ----------------------------------------------------------------------------
# planilha Organização (links do Zoom)
# ----------------------------------------------------------------------------
def _urls_da_celula(cel) -> list:
    urls = []
    if cel is not None:
        if cel.hyperlink is not None and cel.hyperlink.target:
            urls.append(cel.hyperlink.target)
        urls += [u.rstrip(").,;") for u in URL_RE.findall(_txt(cel.value))]
    return urls


def _e_whatsapp(url: str) -> bool:
    u = url.lower()
    return "whatsapp" in u or "wa.me" in u


def _ler_zooms(avisos_globais: list) -> dict:
    caminho = localizar_arquivo(config.ARQ_ORG)
    if not caminho:
        avisos_globais.append(("erro", f"Planilha de Organização não encontrada ({config.ARQ_ORG}): "
                               "os links do Zoom não serão preenchidos."))
        return {}
    wb = openpyxl.load_workbook(caminho, data_only=True)
    try:
        if config.ABA_ORG not in wb.sheetnames:
            avisos_globais.append(("erro", f"Aba '{config.ABA_ORG}' não encontrada na planilha de Organização."))
            return {}
        pl = Planilha(wb[config.ABA_ORG])
        if "id" not in pl.colunas:
            avisos_globais.append(("erro", "Coluna 'ID' não encontrada na planilha de Organização."))
            return {}
        cols_zoom = [c for nome, c in pl.colunas.items() if "zoom" in nome or "zom" in nome]
        zooms: dict = {}
        for r in range(pl.linha_cab + 1, pl.ws.max_row + 1):
            id_ = parse_id(pl.cel(r, "ID").value)
            if id_ is None:
                continue
            achado = ""
            for c in cols_zoom:  # 1º: colunas cujo nome tem "zoom"
                for u in _urls_da_celula(pl.celula(r, c)):
                    if not _e_whatsapp(u):
                        achado = u
                        break
                if achado:
                    break
            if not achado:  # 2º: qualquer célula com link do zoom.us
                for c in range(1, pl.ws.max_column + 1):
                    for u in _urls_da_celula(pl.celula(r, c)):
                        if "zoom.us" in u.lower() and not _e_whatsapp(u):
                            achado = u
                            break
                    if achado:
                        break
            if achado:
                zooms[id_] = achado
        return zooms
    finally:
        wb.close()


# ----------------------------------------------------------------------------
# FAQ
# ----------------------------------------------------------------------------
def _ler_faq(avisos_globais: list):
    caminho = localizar_arquivo(config.ARQ_FAQ)
    if not caminho:
        avisos_globais.append(("erro", f"FAQ não encontrada ({config.ARQ_FAQ}): o Assistente de Atendimento ficará indisponível."))
        return [], ""
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        linhas = list(wb.active.iter_rows(values_only=True))
    finally:
        wb.close()
    if not linhas:
        avisos_globais.append(("erro", "A planilha de FAQ está vazia."))
        return [], ""
    cab = [_txt(c).casefold() for c in linhas[0]]
    i_assunto = cab.index("assunto") if "assunto" in cab else 0
    i_resp = cab.index("regra/resposta") if "regra/resposta" in cab else 1
    faq = []
    for lin in linhas[1:]:
        if len(lin) <= max(i_assunto, i_resp):
            continue
        assunto, resp = _txt(lin[i_assunto]), _txt(lin[i_resp])
        if assunto and resp:
            faq.append((assunto, resp))
    if not faq:
        avisos_globais.append(("erro", "Nenhuma linha válida encontrada na FAQ."))
    return faq, "\n".join(f"- {a}: {r}" for a, r in faq)


# ----------------------------------------------------------------------------
# ponto de entrada
# ----------------------------------------------------------------------------
def carregar_base() -> Base:
    avisos: list = []
    turmas = _ler_cbf(avisos)
    zooms = _ler_zooms(avisos)
    for id_, t in turmas.items():
        t.zoom = zooms.get(id_, "")
    faq, faq_texto = _ler_faq(avisos)
    return Base(turmas=turmas, faq=faq, faq_texto=faq_texto, avisos=avisos)
