import csv, json, re, ast
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
    if f.endswith(".csv"):
        return pd.read_csv(f, engine="python")
    return pd.read_excel(f)

def jparse(x):
    if x is None: return None
    if isinstance(x, float): return None
    if isinstance(x, (dict, list)): return x
    try: return json.loads(str(x))
    except Exception: return None

SAE_CODES = {"D71", "N43", "D710"}
# unused placeholder kept
SAE_INJECT_MARK = re.compile(r"Entre em contato diretamente com o SAE|WhatsApp da Mentoria", re.I)

# Sinais fortes de prospectivo (não-aluno) — têm prioridade
RE_NAO_ALUNO = re.compile(r"\bn[ãa]o\s+sou\s+(aluno|aluna)\b|\bn\s+sou\s+(aluno|aluna)\b|\bainda\s+n[ãa]o\s+sou\b|\bpretendo\s+ser\s+alun|\bquero\s+ser\s+alun|\bpretende\s+ser\s+alun|\bestou\s+pretendendo\b|\bcadastro\s+pra\s+ser\b|\bn[ãa]o\s+sou\s+aluno\s+(da|do)\s+uniube\b", re.I)
RE_PROSPECT = re.compile(r"\bpretendo\b|\bvestibular\s+online\b|\bfazer\s+(a\s+)?inscri[cç][ãa]o\b|\bquero\s+(me\s+)?inscrev", re.I)
RE_OUTRA_INSTIT = re.compile(r"\bsou\s+(aluno|aluna)\s+d[aeo]\s+(unifran|ufu|ifsudeste|uninter|unicamp|usp|anhanguera|estacio|unopar|unibras|cesc|unihorizontes|outra)\b|\bestou\s+(no\s+\d+|cursando).{0,50}(unifran|ufu|uninter|anhanguera|unibras|cesc)|\btransfer[êe]ncia\s+externa\s+para|\bsou\s+formad[ao]\s+em\s+\w+(?!\s*pela?\s+uniube)|\bex\s+aluna?.{0,40}\bsegunda\s+gradua|\benviei\s+(meu\s+)?hist[óo]rico.{0,30}an[áa]lise", re.I)

# Sinais de aluno ativo / ex-aluno em tema acadêmico
RE_SOU_ALUNO_FORTE = re.compile(r"\b(j[áa]\s+)?sou\s+(o\s+)?(aluno|aluna)\b|\bj[áa]\s+sou\b|\bsou\s+ex[\s\-]?(aluno|aluna)\b|\bj[áa]\s+fui\s+alun|\bsou\s+(uma\s+)?ex[\s\-]?(aluno|aluna)\b|\bestudo\s+(na|no)\s+uniube\b|\bsou\s+estudante\s+(do|da|de)\s+\d+[°º]?\s+per[ií]odo\b|\bsou\s+formad[ao]\s+(em|pela?)\s+uniube\b|\baluno\s+da\s+uniube\b|\bj[áa]\s+fa[çc]o.{0,30}\b(na\s+)?uniube\b|\bfa[çc]o\s+(o\s+)?curso.{0,30}\bpela?\s+uniube\b|\bcursando.{0,30}\buniube\b|\bme\s+formei\s+(em|na)\s+uniube\b|\bfiz\s+(com|na)\s+(voc|uniube)|\baluno\b\s*(\.|$|\?)", re.I)
RE_ALUNO_TEMA = re.compile(
    r"\btrancar\s+(meu|o)\s+curso\b|\bdestrancar\b|\breativar\s+(minha\s+)?matr|\breabrir\s+matr"
    r"|\bmeu\s+hist[óo]rico\b|\bhist[óo]rico\s+(escolar|acad[êe]mico|digital)\b"
    r"|\bdiploma\s+digital\b|\b2[ªa]?\s+via\s+(do\s+)?diploma\b|\bdiploma\s+(da|do)\s+minha\s+gradua"
    r"|\bn[ãa]o\s+(consigo|estou\s+conseguindo|consegui)\s+(me\s+)?(conectar|acessar|logar|achar)"
    r"|\bcomo\s+(eu\s+)?(fa[çc]o\s+(p|para)?\s*)?(acessar|entrar)"
    r"|\baccessar?\s+(meu\s+)?ava\b|\bliberar?\s+(o\s+)?ava\b"
    r"|\be[\s\-]?mail\s+institucional\b"
    r"|\bmeu\s+ra\b|\bsaber\s+(o\s+)?meu\s+ra\b|\brecebi\s+o\s+ra\b"
    r"|\batestado\s+de\s+matr[ií]cula\b"
    r"|\btermo\s+de\s+est[áa]gio\b|\bcomprova[cç][ãa]o\s+de\s+est[áa]gio\b|\bdocumenta[cç][ãa]o\s+de\s+est[áa]gio\b"
    r"|\bproblema\s+(com|no|cm)\s+financeiro\b|\bresolver\s+(um\s+)?problema.{0,20}\bfinanceiro\b|\bnegociar\s+d[íi]vida\b"
    r"|\bcancelar\s+(a\s+)?minha\s+compra\b|\bquero\s+(o\s+)?estorno\b|\bfui\s+aluno.{0,40}\bdiploma\b"
    r"|\bfiz\s+(a\s+)?minha\s+matr[íi]cula\b|\bj[áa]\s+(fiz|paguei)\s+(a\s+)?(minha\s+)?matr[íi]cula\b"
    r"|\bpaguei\s+(a\s+)?matr[íi]cula\s+(no\s+)?(s[áa]bado|ontem|hoje|semana\s+passada)\b"
    r"|\bs[óo]\s+uma\s+mat[ée]ria\s+foi\s+aprovada\b|\baceite\s+do\s+contrato\b"
    r"|\borienta[cç][ãa]o\s+(quanto\s+)?(às|as|para)?\s*mensalidades\b|\bdivida\b|\bd[íi]vida\b"
    r"|\baluno\s+na\s+uniube\b|\bser\s+aluno\s+na\s+uniube\b"
    r"|\btratamento\s+do\s+meu\s+curso\b|\btrancamento\s+do\s+meu\s+curso\b"
    r"|\bj[áa]\s+paguei\s+o\s+boleto.{0,30}(p[óo]s|matr)|\bpaguei\s+o\s+boleto\s+da\s+p[óo]s\b"
    r"|\bcursando\s+(agronomia|aluno).{0,40}\b(bolsa|matr|aguardando)\b"
    r"|\banexar\s+documentos\s+(no|do)\s+ava\b"
    r"|\bdisciplina(s)?\s+isolada(s)?\b|\baluno\s+especial\b|\bdisciplinas?\s+avulsa"
    r"|\bementa(s)?\s+(da|de|do)\s+disciplina"
    r"|\bcomprei\s+(o\s+|a\s+)?(curso|p[óo]s|mba)|\bcomprei\s+ontem\s+um\b"
    r"|\baluna?\s+da\s+uniube\b|\bsou\s+aluno\s+da\s+uniube\b"
    r"|\bex[\s\-]?aluno.{0,30}\b(precisa|preciso|gostaria)|\bex[\s\-]?aluna.{0,30}\b(precisa|preciso|gostaria)"
    r"|\bfa[çc]o.{0,15}\bna\s+uniube\b|\bfez\s+(com|na)\s+(voc|uniube)"
    , re.I)
RE_IA_CONFIRM = re.compile(r"como\s+voc[êe]\s+j[áa]\s+[ée]\s+aluno|como\s+voc[êe]\s+j[áa]\s+[ée]\s+aluna", re.I)

RE_UNIUBE_EXPLICITO = re.compile(r"\b(sou|j[áa]\s+sou)\s+(aluno|aluna)\s+(d[ao]\s+)?uniube\b|\baluno\s+d[ao]\s+uniube\b|\baluna\s+d[ao]\s+uniube\b|\bj[áa]\s+sou\s+alun[oa]\s+(d[ao]\s+)?uniube\b|\bestudo\s+(na|no)\s+uniube\b|\bestudante\s+(d[ao]|de)\s+\w+.{0,30}uniube\b", re.I)
RE_EX_SEGUNDA = re.compile(r"\bex[\s\-]?alun[oa].{0,60}\b(segunda\s+gradua|2[ªa]?\s+gradua|nova\s+gradua|qual\s+(o\s+)?valor)", re.I)

def _ctx(text, m, before=80, after=80):
    s = max(0, m.start()-before); e = min(len(text), m.end()+after)
    return f"...{text[s:m.start()]}«{text[m.start():m.end()]}»{text[m.end():e]}..."

def classify(user_text, ia_text):
    # Prioridade 1: menção explícita a ser aluno da Uniube
    m = RE_UNIUBE_EXPLICITO.search(user_text)
    if m: return "CORRETO", "aluno Uniube explicito", _ctx(user_text, m)
    # Prioridade 2: ex-aluno querendo nova graduação = prospectivo
    m = RE_EX_SEGUNDA.search(user_text)
    if m: return "ERRADO", "ex-aluno quer nova graduacao", _ctx(user_text, m)
    # Prioridade 3: explicita não ser aluno
    m = RE_NAO_ALUNO.search(user_text)
    if m: return "ERRADO", "explicita nao ser aluno", _ctx(user_text, m)
    # Prioridade 4: aluno de outra instituição
    m = RE_OUTRA_INSTIT.search(user_text)
    if m: return "ERRADO", "aluno de outra instituicao", _ctx(user_text, m)
    # Aluno ativo tratando tema acadêmico
    m = RE_ALUNO_TEMA.search(user_text)
    if m: return "CORRETO", "aluno tema academico", _ctx(user_text, m)
    m = RE_SOU_ALUNO_FORTE.search(user_text)
    if m: return "CORRETO", "declarou ser aluno ativo", _ctx(user_text, m)
    m = RE_IA_CONFIRM.search(ia_text)
    if m: return "CORRETO", "IA confirmou aluno", _ctx(ia_text, m)
    m = RE_PROSPECT.search(user_text)
    if m: return "ERRADO", "prospectivo", _ctx(user_text, m)
    return "ERRADO", "sem sinais de aluno", ""

def main():
    dfs = [load(f) for f in FILES]
    df = pd.concat(dfs, ignore_index=True)
    print(f"loaded rows={len(df)} convs={df['conversation_id'].nunique()}")

    convs = defaultdict(lambda: {"confirmed":False,"confirmed_main":False,"confirmed_followup":False,"injected":False,"replied":False,"date":None,"user_msgs":[],"ia_msgs":[],"codes":set(),"trigger_msg":None,"evid_acionamento":None,"evid_injecao":None,"evid_envio":None})

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

        # Detecta se esse request é um followup (IA reprocessando)
        is_followup = False
        if isinstance(payloads, list):
            for it in payloads:
                if isinstance(it, dict) and "followup" in (it.get("caller") or "").lower():
                    is_followup = True
                    break

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
                    # captura evidência da primeira validation que confirmou
                    if codes & SAE_CODES and st["evid_acionamento"] is None:
                        st["evid_acionamento"] = f"caller: {item.get('caller')}\nresponse: {content[:400]}"
                elif "decisionchain" in caller or "decision-chain" in caller:
                    chain_codes |= codes
        # Confirmação agora depende apenas do validation (chain ignorado)
        confirmed_codes = valid_codes & SAE_CODES
        if confirmed_codes:
            st["confirmed"] = True
            st["codes"] |= confirmed_codes
            if is_followup:
                st["confirmed_followup"] = True
            else:
                st["confirmed_main"] = True
            # trigger_msg: última mensagem do usuário neste request
            if st["trigger_msg"] is None and isinstance(msgs, list):
                for m in reversed(msgs):
                    if isinstance(m, dict) and m.get("role") == "user":
                        t = m.get("content") or ""
                        if isinstance(t, list):
                            t = " ".join(c.get("text","") if isinstance(c, dict) else str(c) for c in t)
                        if t:
                            st["trigger_msg"] = t[:500]
                            break

        if isinstance(payloads, list):
            for item in payloads:
                if not isinstance(item, dict): continue
                caller = (item.get("caller") or "").lower()
                if "createassistantresponse" not in caller: continue
                pl = jparse(item.get("payload") or "")
                if not isinstance(pl, dict): continue
                for m in pl.get("messages", []):
                    if not isinstance(m, dict): continue
                    if m.get("role") != "system": continue
                    c = m.get("content", "")
                    if not isinstance(c, str): continue
                    # Só conta como injetado se o marcador SAE está DENTRO de <realtime>
                    for rt in re.findall(r"<realtime>(.*?)</realtime>", c, re.S):
                        m_mark = SAE_INJECT_MARK.search(rt)
                        if m_mark:
                            st["injected"] = True
                            if st["evid_injecao"] is None:
                                # captura ~300 chars ao redor do marker
                                start = max(0, m_mark.start()-100)
                                end = min(len(rt), m_mark.end()+200)
                                st["evid_injecao"] = f"<realtime>...{rt[start:end]}...</realtime>"
                            break
                    if st["injected"]:
                        break
                if st["injected"]:
                    break

        for t in st["ia_msgs"]:
            m_mark = SAE_INJECT_MARK.search(t)
            if m_mark:
                st["replied"] = True
                if st["evid_envio"] is None:
                    start = max(0, m_mark.start()-100)
                    end = min(len(t), m_mark.end()+200)
                    st["evid_envio"] = t[start:end]
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
        verdict, motivo, evid_correto = classify(ut, it)
        if st["confirmed_main"] and st["confirmed_followup"]:
            origem = "principal+followup"
        elif st["confirmed_main"]:
            origem = "principal"
        else:
            origem = "followup"
        out_rows.append({
            "conversation_id": cid,
            "verdict": verdict,
            "motivo": motivo,
            "codigos": ",".join(sorted(st["codes"])),
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
