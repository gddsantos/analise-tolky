import csv, json, re, ast
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
    if f.endswith(".csv"):
        return pd.read_csv(f, engine="python")
    return pd.read_excel(f)

def jparse(x):
    if x is None: return None
    if isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    s = str(x)
    try: return json.loads(s)
    except Exception:
        try: return ast.literal_eval(s)
        except Exception: return None

SAE_CODES = {"D71", "N43", "D710"}
# unused placeholder kept
SAE_INJECT_MARK = re.compile(r"Entre em contato diretamente com o SAE|WhatsApp da Mentoria", re.I)

# Sinais fortes de prospectivo (não-aluno) — têm prioridade
RE_NAO_ALUNO = re.compile(r"\bn[ãa]o\s+sou\s+aluno\b|\bn[ãa]o\s+sou\s+aluna\b|\bainda\s+n[ãa]o\s+sou\b|\bpretendo\s+ser\s+alun|\bquero\s+ser\s+alun|\bpretende\s+ser\s+alun", re.I)
RE_PROSPECT = re.compile(r"\bpretendo\b|\bvestibular\s+online\b|\bfazer\s+(a\s+)?inscri[cç][ãa]o\b|\bquero\s+(me\s+)?inscrev", re.I)
RE_OUTRA_INSTIT = re.compile(r"\b(unifran|ufu|ifsudeste|uninter|unicamp|usp|anhanguera|estacio|unopar|unibras|cesc|unihorizontes)\b|\bsou\s+aluno\s+d[ao]\b|\boutra\s+(faculdade|institui)", re.I)

# Sinais de aluno ativo
RE_SOU_ALUNO_FORTE = re.compile(r"\b(j[áa]\s+)?sou\s+(o\s+)?(aluno|aluna)\b(?!\s+d[aeo])|\bj[áa]\s+sou\s*(\.|$|\?|!)|\bsou\s+ex[\s\-]?(aluno|aluna)\b|\bj[áa]\s+fui\s+alun|\bestudo\s+(na|no)\s+uniube\b|\bsou\s+estudante\s+d[ao]\s+uniube\b", re.I)
RE_ALUNO_TEMA = re.compile(r"\btrancar\s+(meu|o)\s+curso\b|\bdestrancar\b|\breativar\s+matr|\breabrir\s+matr|\b(sou|j[áa]\s+sou)\s+(aluno|aluna).*\b(trancad|pagar|divida|d[íi]vida)\b|\bmeu\s+hist[óo]rico\b|\bminha\s+frequ[êe]ncia\b|\bminhas\s+aulas\b|\bminhas\s+disciplinas\b|\bn[ãa]o\s+consigo\s+acessar\s+(o\s+)?ava\b|\bmeu\s+ra\b|\batestado\s+de\s+matr[ií]cula\b|\btermo\s+de\s+est[áa]gio\b|\bdocumenta[cç][ãa]o\s+de\s+est[áa]gio\b|\bproblema\s+(com|no)\s+financeiro\b|\bnegociar\s+d[íi]vida\b|\b2[ªa]?\s+via\s+(do\s+)?diploma\b|\bdiploma\s+(da|do)\s+minha\s+gradua", re.I)
RE_IA_CONFIRM = re.compile(r"como\s+voc[êe]\s+j[áa]\s+[ée]\s+aluno|como\s+voc[êe]\s+j[áa]\s+[ée]\s+aluna", re.I)

def classify(user_text, ia_text):
    # Prioridade: sinais explícitos de prospectivo
    if RE_NAO_ALUNO.search(user_text):
        return "ERRADO", "explicita nao ser aluno"
    # Se mencionou outra instituição como aluno → não é aluno Uniube
    if RE_OUTRA_INSTIT.search(user_text):
        return "ERRADO", "aluno de outra instituicao"
    # Aluno ativo tratando tema acadêmico
    if RE_ALUNO_TEMA.search(user_text):
        return "CORRETO", "aluno tema academico"
    if RE_SOU_ALUNO_FORTE.search(user_text):
        return "CORRETO", "declarou ser aluno ativo"
    if RE_IA_CONFIRM.search(ia_text):
        return "CORRETO", "IA confirmou aluno"
    if RE_PROSPECT.search(user_text):
        return "ERRADO", "prospectivo"
    return "ERRADO", "sem sinais de aluno"

def main():
    dfs = [load(f) for f in FILES]
    df = pd.concat(dfs, ignore_index=True)
    print(f"loaded rows={len(df)} convs={df['conversation_id'].nunique()}")

    convs = defaultdict(lambda: {"confirmed":False,"injected":False,"replied":False,"date":None,"user_msgs":[],"ia_msgs":[]})

    for _, row in df.iterrows():
        cid = row["conversation_id"]
        st = convs[cid]

        msgs = jparse(row.get("all_request_messages")) or jparse(row.get("main_request_messages")) or []
        if isinstance(msgs, list):
            for m in msgs:
                if not isinstance(m, dict): continue
                role = m.get("role")
                txt = m.get("content") or ""
                if isinstance(txt, list):
                    txt = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in txt)
                if role == "user" and txt:
                    if txt not in st["user_msgs"]:
                        st["user_msgs"].append(txt)
                elif role == "assistant" and txt:
                    if txt not in st["ia_msgs"]:
                        st["ia_msgs"].append(txt)

        payloads = jparse(row.get("payloads")) or {}
        responses = jparse(row.get("responses")) or {}

        if st["date"] is None and isinstance(responses, list):
            import datetime as _dt
            for item in responses:
                if not isinstance(item, dict): continue
                inner = jparse(item.get("response") or "")
                if isinstance(inner, dict) and "created" in inner:
                    try:
                        st["date"] = _dt.datetime.utcfromtimestamp(int(inner["created"])).strftime("%Y-%m-%d")
                        break
                    except Exception:
                        pass

        chain_codes, valid_codes = set(), set()
        if isinstance(responses, list):
            for item in responses:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                raw = item.get("response") or ""
                # raw is a stringified chat completion
                inner = jparse(raw)
                content = ""
                if isinstance(inner, dict):
                    try:
                        content = inner["choices"][0]["message"]["content"]
                    except Exception:
                        content = ""
                parsed = jparse(content)
                resp_codes = []
                if isinstance(parsed, dict):
                    r = parsed.get("response", [])
                    if isinstance(r, list): resp_codes = r
                    elif isinstance(r, str): resp_codes = [r]
                codes = {str(c).upper() for c in resp_codes if c and str(c).upper() != "NULL"}
                if "validation" in caller:
                    valid_codes |= codes
                elif "decisionchain" in caller or "decision-chain" in caller:
                    chain_codes |= codes
        if (chain_codes & valid_codes) & SAE_CODES:
            st["confirmed"] = True

        if isinstance(payloads, list):
            for item in payloads:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "createassistantresponse" not in caller: continue
                blob = json.dumps(item, ensure_ascii=False)
                if "<realtime>" in blob and SAE_INJECT_MARK.search(blob):
                    st["injected"] = True
                    break

        for t in st["ia_msgs"]:
            if SAE_INJECT_MARK.search(t):
                st["replied"] = True
                break

    total = len(convs)
    confirmed = sum(1 for c in convs.values() if c["confirmed"])
    injected  = sum(1 for c in convs.values() if c["injected"])
    replied   = sum(1 for c in convs.values() if c["replied"])

    # Funil por dia
    daily = defaultdict(lambda: {"total":0,"confirmed":0,"injected":0,"replied":0})
    for cid, st in convs.items():
        d = st["date"]
        if not d: continue
        daily[d]["total"] += 1
        if st["confirmed"]: daily[d]["confirmed"] += 1
        if st["injected"]:  daily[d]["injected"]  += 1
        if st["replied"]:   daily[d]["replied"]   += 1

    out_rows = []
    conv_dates = {}
    for cid, st in convs.items():
        if st["date"]: conv_dates[cid] = st["date"]
        if not st["confirmed"]: continue
        ut = " ".join(st["user_msgs"]).lower()
        it = " ".join(st["ia_msgs"]).lower()
        verdict, motivo = classify(ut, it)
        out_rows.append({
            "conversation_id": cid,
            "verdict": verdict,
            "motivo": motivo,
            "user_msgs": " | ".join(st["user_msgs"][:5]),
        })

    out = pd.DataFrame(out_rows)
    Path("analises").mkdir(exist_ok=True)
    out.to_csv("analises/01_sae_avaliacoes.csv", index=False)

    correto = int((out["verdict"]=="CORRETO").sum())
    errado  = int((out["verdict"]=="ERRADO").sum())
    meta = {
        "funnel": {"total": total, "confirmed": confirmed, "injected": injected, "replied": replied},
        "conv_dates": conv_dates,
        "daily_funnel": dict(daily),
    }
    Path("analises/01_sae_metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    print(f"total={total} confirmed={confirmed} injected={injected} replied={replied} correto={correto} errado={errado}")
    print(f"datas distintas: {len(set(conv_dates.values()))}")

if __name__ == "__main__":
    main()
