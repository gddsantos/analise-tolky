import csv, json, re, datetime as dt
from pathlib import Path
from collections import defaultdict
import pandas as pd

csv.field_size_limit(10_000_000)

FILES = [
    "relatorio_automacoes_uniube_agregado_01.03_202603311646.csv",
    "relatorio_automacoes_uniube_agregado_09.03_202603311542.xlsx",
    "relatorio_automacoes_uniube_agregado_16.03_202603311537.xlsx",
    "relatorio_automacoes_uniube_agregado_23.03_202603311534.xlsx",
    "relatorio_automacoes_uniube_final_marco_202604071619.csv",
    "relatorio_automacoes_uniube_abril_202604071615.csv",
]

def load(f):
    return pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f, engine="python")

def jp(x):
    if x is None: return None
    if isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

# Códigos da automação Tickets (v1: F27, v2: F270/O242/O744/E461/W253)
TICKETS_CODES = {"F27", "F270", "O242", "O744", "E461", "W253", "O24", "O74", "E46", "W25"}

# Critérios por sub-código (regex aplicada ao texto completo da conversa)
RE_MEDICINA = re.compile(r"\bmedicina\s+humana\b|\bcurso\s+de\s+medicina\b(?!\s*[\.\,]?\s*veterin)|\bmedicina\b(?![\s\.,]+veterin)", re.I)
RE_VALORES  = re.compile(r"\bvalor(es)?\b|\bpre[çc]o\b|\bmensalidade(s)?\b|\bcusto\b|\bquanto\s+(custa|sai|fica|tá|ta|seria|est[áa]|é\b)\b|\binvestimento\b|\bdesconto\b|\bbolsa\s+\d|\bquanto\s+(é|sai)\b|\bquanto\s+(eu\s+)?(vou|tenho\s+que)\s+pagar\b", re.I)
RE_POS      = re.compile(r"\bmestrado\b|\bp[óo]s[\s\-]?gradua[çc][ãa]o\b|\bdoutorado\b|\bespecializa[çc][ãa]o\b|\bMBA\b|\bp[óo]s\b(?!\s+ten)", re.I)
RE_EMAIL    = re.compile(r"\bemail\s+(errado|incorreto|desatualizado|trocar|alterar|atualiz|n[ãa]o\s+existe)|\be-?mail\s+cadastrad|\btrocar\s+(o\s+)?e?-?mail\b|\bperdi\s+(o\s+)?(acesso\s+(ao|do)\s+)?(meu\s+)?e?-?mail\b|\balterar\s+(meu\s+)?e?-?mail\b|\bdeu\s+erro.{0,30}e?-?mail|\be?-?mail\s+(n[ãa]o\s+)?existe", re.I)
RE_ACESSO   = re.compile(r"\b[áa]rea\s+do\s+candidato\b|\bn[ãa]o\s+(consigo|estou\s+conseguindo|consegui|to\s+conseguindo)\s+(me\s+)?(acessar|entrar|logar|conectar|finalizar|ver|achar|enviar)|\bproblema\s+de\s+(login|acesso)\b|\bsenha\b|\besqueci\s+(a\s+)?senha\b|\btoken\s+n[ãa]o\s+(chega|chegou)\b|\bc[óo]digo\s+n[ãa]o\s+(chega|chegou)\b|\besperando\s+(receber\s+)?(um\s+|o\s+)?token\b|\bvestibular\s+online.{0,30}n[ãa]o\s+(est[áa]|to)\s+(abrindo|funcionand)|\bdocumento(s)?\s+(em\s+)?pdf.{0,30}n[ãa]o\s+est[áa]\s+enviand", re.I)

# fallback: qualquer indicação de problema/atendimento humano
RE_HUMANO = re.compile(r"\bfalar\s+com\s+(humano|atendente|pessoa)\b|\batendimento\s+humano\b|\bn[ãa]o\s+(consigo|estou\s+conseguindo)\b|\bproblema\b|\berro\b|\breclama", re.I)

def re_any(*regs):
    def f(text): return any(r.search(text) for r in regs)
    return f

# Todos os códigos viram umbrella: qualquer um dos 5 critérios = CORRETO
UMBRELLA = re_any(RE_MEDICINA, RE_VALORES, RE_POS, RE_EMAIL, RE_ACESSO)

CRITERIA = {
    "F270": ("ticket umbrella", UMBRELLA),
    "F27":  ("ticket umbrella", UMBRELLA),
    "O242": ("ticket umbrella", UMBRELLA),
    "O24":  ("ticket umbrella", UMBRELLA),
    "O744": ("ticket umbrella", UMBRELLA),
    "O74":  ("ticket umbrella", UMBRELLA),
    "E461": ("ticket umbrella", UMBRELLA),
    "E46":  ("ticket umbrella", UMBRELLA),
    "W253": ("ticket umbrella", UMBRELLA),
    "W25":  ("ticket umbrella", UMBRELLA),
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
    })

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

    out_rows = []
    conv_dates = {}
    daily = defaultdict(lambda: {"total":0,"confirmed":0,"correto":0})
    for cid, st in convs.items():
        if st["date"]:
            conv_dates[cid] = st["date"]
            daily[st["date"]]["total"] += 1
        if not st["confirmed_codes"]: continue
        if st["date"]: daily[st["date"]]["confirmed"] += 1

        full_text = " ".join(st["user_msgs"])
        # Identifica quais critérios bateram
        criterios_hit = []
        if RE_MEDICINA.search(full_text):  criterios_hit.append("Medicina Humana")
        if RE_VALORES.search(full_text):   criterios_hit.append("Valor/Mensalidade")
        if RE_POS.search(full_text):       criterios_hit.append("Mestrado/Pós")
        if RE_EMAIL.search(full_text):     criterios_hit.append("Email cadastrado")
        if RE_ACESSO.search(full_text):    criterios_hit.append("Acesso/Login")

        if criterios_hit:
            verdict = "CORRETO"
            motivo = "bateu: " + ", ".join(criterios_hit)
        else:
            verdict = "ERRADO"
            motivo = "nenhum dos 5 criterios (Medicina/Valor/Pos/Email/Acesso) foi mencionado"
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
        })

    out = pd.DataFrame(out_rows)
    Path("analises").mkdir(exist_ok=True)
    out.to_csv("analises/02_tickets_avaliacoes.csv", index=False)

    correto = int((out["verdict"]=="CORRETO").sum())
    errado  = int((out["verdict"]=="ERRADO").sum())
    meta = {
        "funnel": {"total": total, "confirmed": confirmed, "injected": confirmed, "replied": correto},
        "conv_dates": conv_dates,
        "daily_funnel": {d: dict(v) for d, v in daily.items()},
    }
    Path("analises/02_tickets_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"total={total} confirmed={confirmed} correto={correto} errado={errado}")
    print(f"datas: {len(set(conv_dates.values()))}")

if __name__ == "__main__":
    main()
