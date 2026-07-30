#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, sys
from pathlib import Path

GRAPHS=("idea","intent","policy","memory","risk","fact")
DECISIONS={"ACCEPT","HOLD","BLOCK","UNKNOWN","DIVERGED","VERIFIED"}

def fail(msg:str)->None: raise ValueError(msg)
def load(path:Path)->dict:
    x=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(x,dict): fail("bundle must be object")
    return x
def graph_nodes(bundle:dict)->dict[str,dict[str,dict]]:
    out={}
    for gt in GRAPHS:
        g=bundle.get(f"{gt}_graph")
        if not isinstance(g,dict) or g.get("graph_type")!=gt: fail(f"missing/invalid {gt}_graph")
        nodes=g.get("nodes"); edges=g.get("edges")
        if not isinstance(nodes,list) or not nodes: fail(f"{gt}_graph nodes required")
        if not isinstance(edges,list): fail(f"{gt}_graph edges required")
        ids={}
        for n in nodes:
            nid=n.get("node_id")
            if not isinstance(nid,str) or not nid or nid in ids: fail(f"{gt} node id invalid/duplicate")
            if not isinstance(n.get("evidence_refs"),list): fail(f"{nid} evidence_refs required")
            ids[nid]=n
        adjacency={nid:[] for nid in ids}
        for e in edges:
            a,b=e.get("from"),e.get("to")
            if a not in ids or b not in ids: fail(f"{gt} broken edge")
            adjacency[a].append(b)
        state={}
        def visit(n):
            if state.get(n)==1: fail(f"{gt} graph cycle")
            if state.get(n)==2:return
            state[n]=1
            for x in adjacency[n]:visit(x)
            state[n]=2
        for nid in ids:visit(nid)
        out[gt]=ids
    return out

def validate(bundle:dict)->None:
    if bundle.get("profile")!="org.proofpath.personal-agent-safety" or bundle.get("version")!="1.1.0": fail("profile/version mismatch")
    nodes=graph_nodes(bundle)
    for gt in ("idea","memory","risk","fact"):
        for n in nodes[gt].values():
            attrs=n.get("attributes") or {}
            if attrs.get("authority_effect","none")!="none": fail(f"{gt} cannot create authority")
    for n in nodes["fact"].values():
        if not n["evidence_refs"]: fail("Fact without evidence")
        a=n.get("attributes") or {}
        if not a.get("observed_at") or not a.get("source"): fail("Fact provenance missing")
    for n in nodes["memory"].values():
        a=n.get("attributes") or {}
        for k in ("source_ref","recorded_at","retrieved_at","purpose","freshness","conflict_state","authority_effect"):
            if k not in a: fail(f"Memory {k} missing")
        if a["authority_effect"]!="none": fail("memory authority leak")
    for n in nodes["policy"].values():
        a=n.get("attributes") or {}
        for k in ("policy_id","revision","issuer","effect"):
            if k not in a: fail(f"Policy {k} missing")
    for n in nodes["risk"].values():
        a=n.get("attributes") or {}
        for k in ("hazard","likelihood","impact","uncertainty","mitigation","residual_tier"):
            if k not in a: fail(f"Risk {k} missing")
    for link in bundle.get("links",[]):
        fg,tg=link.get("from_graph"),link.get("to_graph")
        if fg not in nodes or tg not in nodes: fail("link graph invalid")
        if link.get("from_node_id") not in nodes[fg] or link.get("to_node_id") not in nodes[tg]: fail("broken link")
    mu=bundle.get("memory_use") or {}
    if mu.get("authority_effect")!="none": fail("memory_use authority leak")
    for nid in mu.get("included",[]):
        n=nodes["memory"].get(nid)
        if not n: fail("included memory missing")
        a=n.get("attributes") or {}
        if a.get("freshness") in ("stale","unknown") or a.get("conflict_state")!="clear": fail("stale/conflicted memory included")
    pe=bundle.get("policy_evaluation") or {}
    risk=bundle.get("risk_assessment") or {}
    dec=bundle.get("decision") or {}
    status=dec.get("status")
    if status not in DECISIONS: fail("decision invalid")
    if status in ("ACCEPT","VERIFIED"):
        if pe.get("effect") not in ("ALLOW","CONSTRAIN"): fail("policy does not permit")
        if risk.get("residual_tier") in ("high","critical","unknown",None): fail("risk not acceptable")
        current=any((n.get("attributes") or {}).get("current") is True for n in nodes["intent"].values())
        if not current: fail("current intent missing")
    if status=="VERIFIED" and (bundle.get("verification") or {}).get("status")!="verified": fail("verified decision without verification")
    if status in ("HOLD","BLOCK","UNKNOWN") and dec.get("side_effect_allowed") is True: fail("unsafe side effect allowance")

def self_test(base:dict)->None:
    mutations=[]
    x=copy.deepcopy(base); x["memory_use"]["authority_effect"]="allow_send"; mutations.append(x)
    x=copy.deepcopy(base); x["memory_graph"]["nodes"][0]["attributes"]["freshness"]="stale"; mutations.append(x)
    x=copy.deepcopy(base); x["risk_assessment"]["residual_tier"]="critical"; mutations.append(x)
    x=copy.deepcopy(base); x["intent_graph"]["nodes"][0]["attributes"]["current"]=False; mutations.append(x)
    x=copy.deepcopy(base); x["fact_graph"]["nodes"][0]["evidence_refs"]=[]; mutations.append(x)
    for i,x in enumerate(mutations,1):
        try: validate(x)
        except ValueError: continue
        raise SystemExit(f"negative control {i} unexpectedly passed")
    print("PASS: 5 semantic negative controls")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("bundle",type=Path); p.add_argument("--self-test",action="store_true")
    a=p.parse_args(); b=load(a.bundle); validate(b)
    print("PASS: Personal Agent Safety Bundle v1.1")
    if a.self_test:self_test(b)
    return 0
if __name__=="__main__": sys.exit(main())
