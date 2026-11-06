"""Histórico de atendimentos.

Dois modos, escolhidos automaticamente:
  * modo "drive"  (Streamlit Community Cloud): o histórico vive no arquivo Excel
    Atendimentos_PowerBI.xlsx do seu Google Drive, que o Power BI já lê. Cada resposta
    baixa o arquivo, acrescenta a linha e envia de volta (conta de serviço do Google).
  * modo "sqlite" (Colab / computador): como na v4 (historico.db + Excel local).

O modo "drive" liga quando existem os segredos HISTORICO_DRIVE_FILE_ID e [gcp_service_account].
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import config
import ia

COLUNAS = ["id", "data_hora", "id_turma", "operador", "duvida", "resposta",
           "encaminhado_email", "assunto", "modelo_ia", "tempo_ms", "origem", "canal"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_trava = threading.Lock()
_cache = {"t": 0.0, "df": None}


def _agora() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- escolha do modo
def _segredo(nome):
    v = os.environ.get(nome)
    if v:
        return v
    try:
        import streamlit as st
        return st.secrets.get(nome)
    except Exception:
        return None


def _credenciais_info():
    bruto = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if bruto:
        return json.loads(bruto)
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


def modo() -> str:
    return "drive" if (_segredo("HISTORICO_DRIVE_FILE_ID") and _credenciais_info()) else "sqlite"


# --------------------------------------------------------------------------- Google Drive
def _servico():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    cred = Credentials.from_service_account_info(
        _credenciais_info(), scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=cred, cache_discovery=False)


def _drive_baixar():
    """Devolve os bytes do Excel no Drive (ou None se o arquivo estiver vazio)."""
    from googleapiclient.http import MediaIoBaseDownload
    req = _servico().files().get_media(fileId=_segredo("HISTORICO_DRIVE_FILE_ID"))
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    feito = False
    while not feito:
        _, feito = dl.next_chunk()
    dados = buf.getvalue()
    return dados or None


def _drive_enviar(dados: bytes):
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(dados), mimetype=XLSX_MIME, resumable=False)
    _servico().files().update(fileId=_segredo("HISTORICO_DRIVE_FILE_ID"), media_body=media).execute()


def _com_tentativas(fn, *args):
    for i in range(3):
        try:
            return fn(*args)
        except Exception:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))


def _df_de_bytes(dados) -> pd.DataFrame:
    if not dados:
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_excel(io.BytesIO(dados), sheet_name=0)
    for c in COLUNAS:
        if c not in df.columns:
            df[c] = None
    return df[COLUNAS]


def _bytes_de_df(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    _formatar(df).to_excel(buf, index=False, sheet_name="Atendimentos")
    return buf.getvalue()


def _formatar(df: pd.DataFrame) -> pd.DataFrame:
    """Mesmo formato que o painel v4 gravava (com colunas data e hora separadas)."""
    df = df.copy()
    df["assunto"] = df["assunto"].fillna("Não classificado")
    df["canal"] = df["canal"].fillna("WhatsApp")  # registros antigos eram todos do WhatsApp
    dt = pd.to_datetime(df["data_hora"], errors="coerce")
    for pos, (nome, fmt) in enumerate((("data", "%Y-%m-%d"), ("hora", "%H:%M")), start=2):
        if nome in df.columns:
            df = df.drop(columns=[nome])
        df.insert(pos, nome, dt.dt.strftime(fmt))
    return df


# --------------------------------------------------------------------------- SQLite (modo antigo)
def _conectar():
    pasta = os.path.dirname(config.DB_PATH)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    return sqlite3.connect(config.DB_PATH, timeout=15)


def _sqlite_iniciar():
    con = _conectar()
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            id_turma INTEGER,
            operador TEXT,
            duvida TEXT,
            resposta TEXT,
            encaminhado_email INTEGER DEFAULT 0,
            assunto TEXT,
            modelo_ia TEXT,
            tempo_ms INTEGER,
            origem TEXT DEFAULT 'painel',
            canal TEXT)""")
        colunas = [c[1] for c in con.execute("PRAGMA table_info(atendimentos)")]
        if "assunto" not in colunas:
            con.execute("ALTER TABLE atendimentos ADD COLUMN assunto TEXT")
        if "canal" not in colunas:
            con.execute("ALTER TABLE atendimentos ADD COLUMN canal TEXT")
        con.commit()
        vazio = con.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0] == 0
        if vazio and os.path.exists(config.ARQ_HISTORICO_ANTIGO):
            _importar_antigo_sqlite(con)
    finally:
        con.close()


def _importar_antigo_sqlite(con):
    try:
        for data, duvida, resposta in _linhas_antigas():
            con.execute("INSERT INTO atendimentos (data_hora, duvida, resposta, origem) VALUES (?,?,?,?)",
                        (data, duvida, resposta, "importado"))
        con.commit()
    except Exception:  # noqa: BLE001 (importação é opcional)
        con.rollback()


def _linhas_antigas():
    df = pd.read_excel(config.ARQ_HISTORICO_ANTIGO)
    for _, lin in df.iterrows():
        bruto = str(lin.get("Data/Hora", ""))
        try:
            data = datetime.strptime(bruto, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            data = bruto
        duvida, _ = ia.mascarar(str(lin.get("Dúvida Original do Aluno", "")))
        resposta, _ = ia.mascarar(str(lin.get("Resposta Gerada", "")))
        yield data, duvida, resposta


# --------------------------------------------------------------------------- interface pública (a mesma da v4)
def iniciar():
    if modo() == "drive":
        with _trava:
            df = _df_de_bytes(_com_tentativas(_drive_baixar))   # falha aqui = erro claro de acesso
            if df.empty and os.path.exists(config.ARQ_HISTORICO_ANTIGO):
                try:
                    novas = [{"id": i + 1, "data_hora": d, "duvida": q, "resposta": r, "origem": "importado"}
                             for i, (d, q, r) in enumerate(_linhas_antigas())]
                    if novas:
                        _com_tentativas(_drive_enviar, _bytes_de_df(pd.DataFrame(novas).reindex(columns=COLUNAS)))
                except Exception:  # noqa: BLE001
                    pass
        return
    _sqlite_iniciar()


def _ler_drive(forcar=False) -> pd.DataFrame:
    if not forcar and _cache["df"] is not None and time.time() - _cache["t"] < 15:
        return _cache["df"]
    df = _df_de_bytes(_com_tentativas(_drive_baixar))
    _cache.update(t=time.time(), df=df)
    return df


def registrar(id_turma, operador, duvida_mascarada, resposta, encaminhado, modelo_ia, tempo_ms, assunto=None, canal="WhatsApp"):
    if modo() == "drive":
        with _trava:
            df = _ler_drive(forcar=True)
            novo_id = int(pd.to_numeric(df["id"], errors="coerce").max() or 0) + 1 if len(df) else 1
            linha = {"id": novo_id, "data_hora": _agora(), "id_turma": id_turma, "operador": operador or None,
                     "duvida": duvida_mascarada, "resposta": resposta, "encaminhado_email": int(bool(encaminhado)),
                     "assunto": assunto, "modelo_ia": modelo_ia, "tempo_ms": tempo_ms, "origem": "painel",
                     "canal": canal}
            df = pd.concat([df, pd.DataFrame([linha])], ignore_index=True)[COLUNAS]
            _com_tentativas(_drive_enviar, _bytes_de_df(df))
            _cache.update(t=time.time(), df=df)
        return
    con = _conectar()
    try:
        con.execute(
            """INSERT INTO atendimentos
               (data_hora, id_turma, operador, duvida, resposta, encaminhado_email, assunto, modelo_ia, tempo_ms, canal)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (_agora(), id_turma, operador or None, duvida_mascarada, resposta,
             int(bool(encaminhado)), assunto, modelo_ia, tempo_ms, canal))
        con.commit()
    finally:
        con.close()
    atualizar_xlsx()


def total() -> int:
    if modo() == "drive":
        return len(_ler_drive())
    con = _conectar()
    try:
        return con.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
    finally:
        con.close()


def tabela() -> pd.DataFrame:
    """Todo o histórico, com colunas de data e hora separadas (facilita filtros no Power BI)."""
    if modo() == "drive":
        df = _ler_drive().copy()
        df["id"] = pd.to_numeric(df["id"], errors="coerce")
        df = df.sort_values("id").reset_index(drop=True)
        return _formatar(df)
    con = _conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM atendimentos ORDER BY id", con)
    finally:
        con.close()
    return _formatar(df)


def exportar_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    tabela().to_excel(buf, index=False, sheet_name="Atendimentos")
    return buf.getvalue()


def atualizar_xlsx():
    """Modo sqlite: reescreve o Excel local. Modo drive: não faz nada (o Excel do Drive já é o histórico)."""
    if modo() == "drive":
        return None
    try:
        pasta = os.path.dirname(config.XLSX_PATH)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        tmp = config.XLSX_PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(exportar_xlsx_bytes())
        os.replace(tmp, config.XLSX_PATH)
        return None
    except Exception as e:  # noqa: BLE001
        return str(e)


def diagnostico():
    """Para o botão 'Testar conexão': devolve (ok, mensagem em português)."""
    if modo() != "drive":
        return True, "Modo local (SQLite). O histórico fica no arquivo historico.db."
    try:
        svc = _servico()
        info = svc.files().get(fileId=_segredo("HISTORICO_DRIVE_FILE_ID"),
                               fields="name,mimeType,capabilities(canEdit)", supportsAllDrives=True).execute()
        if not info.get("capabilities", {}).get("canEdit"):
            return False, f"Achei o arquivo '{info.get('name')}', mas a conta de serviço só pode LER. Compartilhe como Editor."
        if "spreadsheet" not in info.get("mimeType", "") and "sheet" in info.get("mimeType", ""):
            return False, "O arquivo é uma Planilha Google, não um .xlsx. Use o arquivo Excel (.xlsx) do Drive."
        df = _ler_drive(forcar=True)
        return True, f"Conectado ao Drive: '{info.get('name')}' com {len(df)} atendimento(s) e permissão de edição."
    except Exception as e:  # noqa: BLE001
        return False, f"Não consegui acessar o arquivo no Drive: {e}"
