"""Modelos de mensagem da aba 'Gerador de Avisos'. Texto fixo, sem IA.

Para mudar uma frase, edite a função do modelo correspondente.
Campos que faltam na planilha aparecem no texto como  ⚠️[PREENCHER: ...]
e geram um aviso na tela, para nada sair errado sem você perceber.
"""
from __future__ import annotations


def _campo(valor, rotulo, avisos, grave=False):
    if valor:
        return valor
    avisos.append(("erro" if grave else "aviso",
                   f"{rotulo} não encontrado(a) para esta turma; deixei ⚠️[PREENCHER] no texto."))
    return f"⚠️[PREENCHER: {rotulo}]"


def boas_vindas(t, avisos):
    curso = _campo(t.curso_licenca, "Curso/Licença", avisos)
    data = _campo(t.inicio_online, "Início Online (data do 1º encontro)", avisos)
    zoom = _campo(t.zoom, "Link do Zoom", avisos, grave=True)
    return f"""Sejam todos bem-vindos ao curso de *{curso}* da *Academia Exemplo* ⚽📚

📅 *No dia _{data}_ teremos nosso primeiro encontro!*
🕖 *Horário:* das 19h às 22h
💻 *Aulas on-line via Zoom*
🔗 Link: {zoom}
_(O mesmo link será utilizado em todas as aulas on-line)_

📆 As aulas acontecerão, conforme calendário que será enviado.
ℹ️ Todas as informações do curso também estão disponíveis na *descrição do grupo.*"""


def descricao_whatsapp(t, avisos):
    zoom = _campo(t.zoom, "Link do Zoom", avisos, grave=True)
    ini_p = _campo(t.inicio_presencial, "Início Presencial", avisos)
    fim_p = _campo(t.fim_presencial, "Fim Presencial", avisos)
    ini_o = _campo(t.inicio_online, "Início Online", avisos)
    fim_o = _campo(t.fim_online, "Fim Online", avisos)
    local = _campo(t.local, "Local do Presencial", avisos)
    return f"""📚 Link da aula *Online*:
{zoom}

📅 *Datas:*
*Presencial*: {ini_p} à {fim_p}
*Online*: {ini_o} à {fim_o}

⏰ *Horários das aulas:*
*Online*: a partir de *19:00*
*Presencial*: 08h às 18h

📍 Endereço do *PRESENCIAL*: {local}"""


def aviso_presencial(t, avisos):
    local = _campo(t.local, "Local do Presencial", avisos)
    ini_p = _campo(t.inicio_presencial, "Início Presencial", avisos)
    fim_p = _campo(t.fim_presencial, "Fim Presencial", avisos)
    # CONFERIR: as frases de Certificação e obs foram completadas a partir de um PDF com linhas cortadas.
    return f"""Turma, segue as informações necessárias para se preparar para a parte *PRESENCIAL*:

*Formato do Curso*
A parte presencial contará com aulas teóricas e práticas realizadas em sala e campo.

*Local*
{local}

*Datas e Horários*
O curso ocorrerá do dia {ini_p} à {fim_p} das 08h às 18:00h.

*Certificação*
Se faz necessário ter *100% de presença (durante a parte presencial e online)* para que se possa obter a declaração de presença.

*O que trazer*
Recomendamos que traga, se desejar, um notebook para anotações e trabalhos de grupo, além de chuteira para a parte prática.

*obs* : Solicitamos que os participantes cheguem com *15 minutos de antecedência* e em caso de ausência, avisar previamente a organização.

Estamos ansiosos para iniciar essa jornada de aprendizado com você!"""


def orientacoes_gerais(t, avisos):
    zoom = _campo(t.zoom, "Link do Zoom", avisos, grave=True)
    # CONFERIR: a última frase de "Identificação no Zoom" foi completada a partir de um PDF com linha cortada.
    return f"""Grupo da Turma no WhatsApp
Para facilitar a comunicação e atualizações importantes, acesse o grupo da turma no WhatsApp pelo link:
Entrar no grupo da turma do WhatsApp

Acesso às Aulas Online
- Clique no botão abaixo para acessar as aulas no Zoom. Este link será utilizado para todas as aulas online: {zoom}
- Dicas para Melhor Experiência:
  - Recomendamos instalar o aplicativo Zoom no seu computador para maior estabilidade e funcionalidade.
  - Caso prefira, também é possível utilizar o cliente Zoom diretamente pelo navegador.
- Sala de Espera:
  - Ao acessar a aula no horário indicado, você será direcionado para a sala de espera.
  - A liberação para a aula será feita pontualmente no horário ou alguns minutos após o início.

Presença e Frequência
- Identificação no Zoom:
  - Utilize o nome completo/correto ao ingressar na reunião.
  - Caso precise renomear-se, clique em “Mais” (três pontinhos) ao lado do seu nome na lista de participantes. Certifique-se de que o nome completo esteja correto.
- Frequência:
  - A presença será coletada apenas durante as aulas ao vivo.
  - Frequência mínima exigida: 100%.
- Gravações das Aulas:
  - As reuniões serão gravadas e disponibilizadas na plataforma da Academy para consulta posterior.
  - Importante: Assistir às gravações não contabiliza presença.

Calendário das Aulas
O calendário completo das aulas online pode ser acessado na página inicial."""


MODELOS = {
    "1. Boas-Vindas": boas_vindas,
    "2. Descrição do WhatsApp": descricao_whatsapp,
    "3. Aviso Presencial": aviso_presencial,
    "4. Orientações Gerais (Plataforma)": orientacoes_gerais,
}


def montar(nome_modelo, turma):
    """Devolve (texto, avisos). Os avisos são tuplas (gravidade, mensagem)."""
    avisos = list(turma.avisos)
    texto = MODELOS[nome_modelo](turma, avisos)
    return texto, avisos
