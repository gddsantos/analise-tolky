import csv, json, re, datetime as dt
from pathlib import Path
from collections import defaultdict
import pandas as pd

csv.field_size_limit(10_000_000)

FILES = [
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube1_202604091637-002.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube2_202604091646.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube3_202604091651.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube4_202604091701.csv",
    "arquivos dados/Uniube Março csv/relatorio_automacoes_uniube5_202604091705.csv",
    "arquivos dados/relatorio_automacoes_uniube_abril_202604071615.csv",
]

def load(f):
    return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")

def jp(x):
    if x is None: return None
    if isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

# Códigos da automação Tickets (Uniube)
TICKETS_CODES = {"F27", "F270", "O242", "O744", "E461", "W253", "O24", "O74", "E46", "W25"}

# === Sub-automações Uniube — Tickets ===
# F270 — Gerais (umbrella: medicina humana / valores / pós / email / acesso)
RE_MEDICINA_HUMANA = re.compile(r"\bmedicina\s+humana\b|\bcurso\s+de\s+medicina\b(?!\s*[\.\,]?\s*veterin)|\bmedicina\b(?![\s\.,]+veterin)", re.I)
RE_VALORES  = re.compile(r"\bvalor(es)?\b|\bpre[çc]o\b|\bmensalidade(s)?\b|\bcusto\b|\bquanto\s+(custa|sai|fica|t[áa]|ta|seria|est[áa])\b|\binvestimento\b|\bquanto\s+[ée]\b|\bquanto\s+(eu\s+)?(vou|tenho\s+que)\s+pagar\b", re.I)
RE_POS      = re.compile(r"\bmestrado\b|\bp[óo]s[\s\-]?gradua[çc][ãa]o\b|\bdoutorado\b|\bespecializa[çc][ãa]o\b|\bMBA\b|\bp[óo]s\b", re.I)
RE_EMAIL_CADASTRADO = re.compile(r"\bemail\s+(errado|incorreto|desatualizado|trocar|alterar|atualiz|n[ãa]o\s+existe)|\be-?mail\s+cadastrad|\btrocar\s+(o\s+)?e?-?mail\b|\bperdi\s+(o\s+)?(acesso\s+(ao|do)\s+)?(meu\s+)?e?-?mail\b|\balterar\s+(meu\s+)?e?-?mail\b|\bdeu\s+erro.{0,30}e?-?mail", re.I)
RE_ACESSO_CANDIDATO = re.compile(r"\b[áa]rea\s+do\s+candidato\b|\bn[ãa]o\s+(consigo|estou\s+conseguindo)\s+(me\s+)?(acessar|entrar|logar|conectar|ver)|\bproblema\s+de\s+(login|acesso)\b|\besqueci\s+(a\s+)?senha\b|\btoken\s+n[ãa]o\s+(chega|chegou)\b|\bvestibular\s+online.{0,30}n[ãa]o\s+(est[áa]|to)\s+abrindo", re.I)

def re_any(*regs):
    def f(text): return any(r.search(text) for r in regs)
    return f

CHECK_GERAIS = re_any(RE_MEDICINA_HUMANA, RE_VALORES, RE_POS, RE_EMAIL_CADASTRADO, RE_ACESSO_CANDIDATO)

# E461 — Bolsa 50%
RE_BOLSA_50 = re.compile(r"\bbolsa\s+(de\s+)?50\s*%?|\bbolsa\s+(de\s+)?cinq[uü]enta(\s+por\s+cento)?|\b50%?\s+de\s+bolsa\b|\buniube\s*50\b", re.I)

# O242 — Dificuldade de finalizar a matrícula
RE_DIF_MATRICULA = re.compile(
    r"\bpagar\s+(a\s+)?matr[íi]cula\b|\bpagamento\s+(da\s+)?matr[íi]cula\b"
    r"|\bfinalizar\s+(a\s+)?matr[íi]cula\b|\bn[ãa]o\s+consigo\s+(finalizar|pagar|fazer)\s+(a\s+)?matr[íi]cula\b"
    r"|\bstatus\s+(do|da)\s+vestibular\b|\bresultado\s+(do|da)\s+vestibular\b|\bsitua[çc][ãa]o\s+(do|da)\s+vestibular\b"
    r"|\banexar\s+documento|\benviar\s+documento|\banexar\s+pdf|\bn[ãa]o\s+consigo\s+(enviar|anexar)"
    r"|\bboleto\s+(da\s+)?matr[íi]cula\b|\bqr\s*code\b|\bpix\b.{0,30}matr[íi]cula",
    re.I)

# W253 — Falha na Inscrição (erro técnico/API)
RE_FALHA_INSCRICAO = re.compile(
    r"\bdeu\s+erro\b|\berro\s+(ao|na|de|t[ée]cnico)|\btimeout\b|\bfalha\s+(na|no|de)\s+(inscri|sistema|api)"
    r"|\bn[ãa]o\s+(est[áa]|to)\s+funcionand|\bsistema\s+(fora|n[ãa]o\s+funciona)|\bbugou\b"
    r"|\binscri[çc][ãa]o\s+n[ãa]o\s+(vai|funciona|completa)|\bn[ãa]o\s+consigo\s+(me\s+)?inscrev",
    re.I)

# O744 — Atendimento Humano
RE_ATEND_HUMANO = re.compile(
    r"\b(falar|conversar)\s+com\s+(um\s+|uma\s+)?(atendente|humano|pessoa|consultor|operador)"
    r"|\batendimento\s+humano\b|\bquero\s+(um\s+)?humano\b"
    r"|\btransferir\s+para\s+(atend|humano|pessoa)"
    r"|\bme\s+transferir\b|\bfalar\s+com\s+algu[ée]m\b"
    r"|\bprefiro\s+(um\s+)?(humano|pessoa|atendente)",
    re.I)

CRITERIA = {
    "F270": ("Gerais", CHECK_GERAIS),
    "F27":  ("Gerais", CHECK_GERAIS),
    "E461": ("Bolsa 50%", RE_BOLSA_50.search),
    "E46":  ("Bolsa 50%", RE_BOLSA_50.search),
    "O242": ("Dificuldade finalizar matricula", RE_DIF_MATRICULA.search),
    "O24":  ("Dificuldade finalizar matricula", RE_DIF_MATRICULA.search),
    "W253": ("Falha na Inscricao", RE_FALHA_INSCRICAO.search),
    "W25":  ("Falha na Inscricao", RE_FALHA_INSCRICAO.search),
    "O744": ("Atendimento Humano", RE_ATEND_HUMANO.search),
    "O74":  ("Atendimento Humano", RE_ATEND_HUMANO.search),
}

def main():
    dfs = [load(f) for f in FILES]
    df = pd.concat(dfs, ignore_index=True)
    print(f"loaded rows={len(df)} convs={df['conversation_id'].nunique()}")

    convs = defaultdict(lambda: {
        "confirmed_codes": set(),
        "chain_codes": set(),
        "valid_codes": set(),
        "valid_codes_main": set(),
        "valid_codes_followup": set(),
        "date": None,
        "user_msgs": [],
        "ia_msgs": [],
        "trigger_msg": None,
        "injected": False,
        "replied": False,
        "evid_acionamento": None,
        "evid_injecao": None,
        "evid_envio": None,
    })

    TICKETS_INJECT_MARK = re.compile(
        r"passar(?:\s+o)?\s+atendimento\s+para\s+o\s+setor\s+de\s+atendimento\s+ao\s+candidato",
        re.I
    )

    for _, row in df.iterrows():
        cid = row["conversation_id"]
        st = convs[cid]

        msgs = jp(row.get("all_request_messages")) or jp(row.get("main_request_messages")) or []
        if isinstance(msgs, list):
            for m in msgs:
                if not isinstance(m, dict): continue
                role = m.get("role")
                txt = m.get("content") or ""
                if isinstance(txt, list):
                    txt = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in txt)
                if role == "user" and txt and txt not in st["user_msgs"]:
                    st["user_msgs"].append(txt)
                elif role == "assistant" and txt and txt not in st["ia_msgs"]:
                    st["ia_msgs"].append(txt)

        responses = jp(row.get("responses")) or []

        if st["date"] is None and isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                inner = jp(item.get("response") or "")
                if isinstance(inner, dict) and "created" in inner:
                    try:
                        st["date"] = dt.datetime.fromtimestamp(int(inner["created"]), dt.UTC).strftime("%Y-%m-%d")
                        break
                    except Exception: pass

        payloads = jp(row.get("payloads")) or []
        is_followup = False
        if isinstance(payloads, list):
            for it in payloads:
                if isinstance(it, dict) and "followup" in (it.get("caller") or "").lower():
                    is_followup = True
                    break

        # Detecta Tickets INJETADO dentro de <realtime> no system prompt
        if not st["injected"] and isinstance(payloads, list):
            for it in payloads:
                if not isinstance(it, dict): continue
                if (it.get("caller") or "").lower() != "createassistantresponse": continue
                pl = jp(it.get("payload") or "")
                if not isinstance(pl, dict): continue
                for m in pl.get("messages", []):
                    if not isinstance(m, dict) or m.get("role") != "system": continue
                    c = m.get("content", "")
                    if not isinstance(c, str): continue
                    for rt in re.findall(r"<realtime>(.*?)</realtime>", c, re.S):
                        m_mark = TICKETS_INJECT_MARK.search(rt)
                        if m_mark:
                            st["injected"] = True
                            if st["evid_injecao"] is None:
                                start = max(0, m_mark.start()-100)
                                end = min(len(rt), m_mark.end()+200)
                                st["evid_injecao"] = f"<realtime>...{rt[start:end]}...</realtime>"
                            break
                    if st["injected"]: break
                if st["injected"]: break

        # Detecta Tickets ENVIADO nas mensagens do assistant
        if not st["replied"]:
            for m in (msgs if isinstance(msgs, list) else []):
                if not isinstance(m, dict) or m.get("role") != "assistant": continue
                t = m.get("content") or ""
                if isinstance(t, list):
                    t = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in t)
                if isinstance(t, str):
                    m_mark = TICKETS_INJECT_MARK.search(t)
                    if m_mark:
                        st["replied"] = True
                        if st["evid_envio"] is None:
                            start = max(0, m_mark.start()-100)
                            end = min(len(t), m_mark.end()+200)
                            st["evid_envio"] = t[start:end]
                        break

        if isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "tickets" not in caller: continue
                inner = jp(item.get("response") or "")
                if not isinstance(inner, dict): continue
                try: content = inner["choices"][0]["message"]["content"]
                except Exception: continue
                parsed = jp(content)
                resp = parsed.get("response") if isinstance(parsed, dict) else None
                if isinstance(resp, str): resp = [resp]
                if not isinstance(resp, list): resp = []
                codes = {str(c).upper() for c in resp if c and str(c).upper() != "NULL"}
                codes &= TICKETS_CODES
                if "validation" in caller:
                    st["valid_codes"] |= codes
                    if codes and st["evid_acionamento"] is None:
                        st["evid_acionamento"] = f"caller: {item.get('caller')}\nresponse: {content[:400]}"
                    if is_followup:
                        st["valid_codes_followup"] |= codes
                    else:
                        st["valid_codes_main"] |= codes
                elif "decisionchain" in caller:
                    st["chain_codes"] |= codes
                    # guarda trigger da primeira vez que chain teve código Tickets
                    if codes and st["trigger_msg"] is None and isinstance(msgs, list):
                        for m in reversed(msgs):
                            if isinstance(m, dict) and m.get("role") == "user":
                                t = m.get("content") or ""
                                if isinstance(t, list):
                                    t = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in t)
                                if t:
                                    st["trigger_msg"] = t[:500]
                                    break

    for st in convs.values():
        # Confirmação depende apenas do validation (chain ignorado)
        st["confirmed_codes"] = st["valid_codes"]

    total = len(convs)
    confirmed = sum(1 for c in convs.values() if c["confirmed_codes"])
    injected  = sum(1 for c in convs.values() if c["injected"])
    replied   = sum(1 for c in convs.values() if c["replied"])

    out_rows = []
    conv_dates = {}
    daily = defaultdict(lambda: {"total":0,"confirmed":0,"injected":0,"replied":0,"correto":0})
    for cid, st in convs.items():
        if st["date"]:
            conv_dates[cid] = st["date"]
            daily[st["date"]]["total"] += 1
        if not st["confirmed_codes"]: continue
        if st["date"]:
            daily[st["date"]]["confirmed"] += 1
            if st["injected"]: daily[st["date"]]["injected"] += 1
            if st["replied"]:  daily[st["date"]]["replied"]  += 1

        full_text = " ".join(st["user_msgs"])

        def _ctx(text, m, before=80, after=80):
            s = max(0, m.start()-before); e = min(len(text), m.end()+after)
            return f"...{text[s:m.start()]}«{text[m.start():m.end()]}»{text[m.end():e]}..."

        def _first_match(text, code):
            # Retorna (nome, match_object) do primeiro regex que bate para o code
            if code in ("F270","F27"):
                for nome, rg in [("Medicina Humana",RE_MEDICINA_HUMANA),("Valor/Mensalidade",RE_VALORES),
                                 ("Mestrado/Pós",RE_POS),("Email cadastrado",RE_EMAIL_CADASTRADO),("Acesso/Login",RE_ACESSO_CANDIDATO)]:
                    m = rg.search(text)
                    if m: return (nome, m)
                return (None, None)
            mapping = {"E461":("Bolsa 50%",RE_BOLSA_50),"E46":("Bolsa 50%",RE_BOLSA_50),
                       "O242":("Dificuldade matricula",RE_DIF_MATRICULA),"O24":("Dificuldade matricula",RE_DIF_MATRICULA),
                       "W253":("Falha na Inscricao",RE_FALHA_INSCRICAO),"W25":("Falha na Inscricao",RE_FALHA_INSCRICAO),
                       "O744":("Atendimento Humano",RE_ATEND_HUMANO),"O74":("Atendimento Humano",RE_ATEND_HUMANO)}
            if code in mapping:
                nome, rg = mapping[code]
                m = rg.search(text)
                return (nome, m) if m else (None, None)
            return (None, None)

        hits = []
        misses = []
        evid_correto = ""
        for code in sorted(st["confirmed_codes"]):
            nome_default = CRITERIA.get(code, ("desconhecido", None))[0]
            nome_hit, m = _first_match(full_text, code)
            if nome_hit and m:
                hits.append(f"{nome_hit} ({code})")
                if not evid_correto:
                    evid_correto = f"[{code}/{nome_hit}] {_ctx(full_text, m)}"
            else:
                misses.append(f"{nome_default} ({code})")
        if hits:
            verdict = "CORRETO"
            motivo = "bateu: " + "; ".join(hits)
        else:
            verdict = "ERRADO"
            motivo = "nao bateu: " + "; ".join(misses)
        if verdict == "CORRETO" and st["date"]:
            daily[st["date"]]["correto"] += 1

        has_main = bool(st["valid_codes_main"])
        has_fu = bool(st["valid_codes_followup"])
        if has_main and has_fu: origem = "principal+followup"
        elif has_main: origem = "principal"
        else: origem = "followup"
        out_rows.append({
            "conversation_id": cid,
            "verdict": verdict,
            "motivo": motivo,
            "codigos": ",".join(sorted(st["confirmed_codes"])),
            "origem": origem,
            "trigger_msg": st["trigger_msg"] or "",
            "user_msgs": " | ".join(st["user_msgs"][:5]),
            "evid_acionamento": st["evid_acionamento"] or "",
            "evid_injecao": st["evid_injecao"] or "",
            "evid_envio": st["evid_envio"] or "",
            "evid_correto": evid_correto,
        })

    out = pd.DataFrame(out_rows)
    Path("analises").mkdir(exist_ok=True)
    out.to_csv("analises/02_tickets_avaliacoes.csv", index=False)

    correto = int((out["verdict"]=="CORRETO").sum())
    errado  = int((out["verdict"]=="ERRADO").sum())
    meta = {
        "funnel": {"total": total, "confirmed": confirmed, "injected": injected, "replied": replied},
        "conv_dates": conv_dates,
        "daily_funnel": {d: dict(v) for d, v in daily.items()},
    }
    Path("analises/02_tickets_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"total={total} confirmed={confirmed} correto={correto} errado={errado}")
    print(f"datas: {len(set(conv_dates.values()))}")

if __name__ == "__main__":
    main()
