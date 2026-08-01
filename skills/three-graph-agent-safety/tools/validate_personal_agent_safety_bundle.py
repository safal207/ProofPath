#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, sys
from datetime import datetime, timezone
from pathlib import Path

GRAPHS=("idea","intent","policy","memory","risk","identity","capability","temporal","fact")
DECISIONS={"ACCEPT","HOLD","BLOCK","UNKNOWN","DIVERGED","VERIFIED"}
NO_AUTH=set(GRAPHS)-{"intent"}

def fail(msg:str)->None: raise ValueError(msg)
def ts(value,label):
    if not isinstance(value,str) or not value: fail(f"{label} timestamp missing")
    try: out=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError(f"{label} timestamp invalid") from exc
    if out.tzinfo is None: fail(f"{label} timezone missing")
    return out.astimezone(timezone.utc)
def load(path:Path)->dict:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): fail("bundle must be object")
    return value

def index_graphs(bundle):
    output={}
    for gt in GRAPHS:
        graph=bundle.get(f"{gt}_graph")
        if not isinstance(graph,dict) or graph.get("graph_type")!=gt: fail(f"invalid {gt}_graph")
        nodes,edges=graph.get("nodes"),graph.get("edges")
        if not isinstance(nodes,list) or not nodes or not isinstance(edges,list): fail(f"{gt} graph incomplete")
        ids={}
        for node in nodes:
            nid=node.get("node_id")
            if not isinstance(nid,str) or not nid or nid in ids: fail(f"{gt} node id invalid")
            if not isinstance(node.get("attributes"),dict) or not isinstance(node.get("evidence_refs"),list): fail(f"{nid} malformed")
            ids[nid]=node
        adjacency={nid:[] for nid in ids}; edge_ids=set()
        for edge in edges:
            eid=edge.get("edge_id"); a=edge.get("from"); b=edge.get("to")
            if not isinstance(eid,str) or not eid or eid in edge_ids: fail(f"{gt} edge id invalid")
            edge_ids.add(eid)
            if a not in ids or b not in ids: fail(f"{gt} broken edge")
            if not isinstance(edge.get("evidence_refs"),list): fail(f"{eid} evidence missing")
            adjacency[a].append(b)
        state={}
        def visit(nid):
            if state.get(nid)==1: fail(f"{gt} graph cycle")
            if state.get(nid)==2: return
            state[nid]=1
            for child in adjacency[nid]: visit(child)
            state[nid]=2
        for nid in ids: visit(nid)
        output[gt]=ids
    return output

def evidence_refs(bundle):
    refs=set()
    for gt in GRAPHS:
        for node in bundle[f"{gt}_graph"]["nodes"]: refs.update(node.get("evidence_refs",[]))
        for edge in bundle[f"{gt}_graph"]["edges"]: refs.update(edge.get("evidence_refs",[]))
    for link in bundle.get("links",[]): refs.update(link.get("evidence_refs",[]))
    for key in ("identity_evaluation","capability_evaluation","temporal_evaluation","verification"):
        refs.update((bundle.get(key) or {}).get("evidence_refs",[]))
    return refs

def aligned(bundle,fg,tg):
    return any(x.get("from_graph")==fg and x.get("to_graph")==tg and x.get("status")=="ALIGNED" for x in bundle.get("links",[]))

def validate(bundle):
    if bundle.get("profile")!="org.proofpath.personal-agent-safety" or bundle.get("version")!="1.2.0": fail("profile/version mismatch")
    nodes=index_graphs(bundle)
    for gt in NO_AUTH:
        for node in nodes[gt].values():
            if node["attributes"].get("authority_effect","none")!="none": fail(f"{gt} authority leak")

    for node in nodes["fact"].values():
        if not node["evidence_refs"]: fail("Fact without evidence")
        attrs=node["attributes"]; ts(attrs.get("observed_at"),"Fact")
        if not attrs.get("source"): fail("Fact source missing")

    for node in nodes["memory"].values():
        attrs=node["attributes"]
        for key in ("source_ref","recorded_at","retrieved_at","purpose","freshness","conflict_state","authority_effect"):
            if key not in attrs: fail(f"Memory {key} missing")
        ts(attrs["recorded_at"],"Memory recorded_at"); ts(attrs["retrieved_at"],"Memory retrieved_at")

    for node in nodes["policy"].values():
        attrs=node["attributes"]
        for key in ("policy_id","revision","issuer","effect","authority_effect"):
            if key not in attrs: fail(f"Policy {key} missing")

    subjects=set(); current_subjects=set()
    for node in nodes["identity"].values():
        attrs=node["attributes"]
        for key in ("subject_id","actor_type","issuer","authenticated_at","assurance_level","current","authority_effect"):
            if key not in attrs: fail(f"Identity {key} missing")
        if not node["evidence_refs"]: fail("Identity without evidence")
        ts(attrs["authenticated_at"],"Identity")
        if attrs["subject_id"] in subjects: fail("duplicate identity subject")
        subjects.add(attrs["subject_id"])
        if attrs["current"] is True: current_subjects.add(attrs["subject_id"])

    capabilities={}
    for node in nodes["capability"].values():
        attrs=node["attributes"]
        for key in ("capability_id","provider","action","target_scope","status","bound_subject_id","authority_effect"):
            if key not in attrs: fail(f"Capability {key} missing")
        if not node["evidence_refs"] or attrs["bound_subject_id"] not in subjects: fail("Capability binding invalid")
        if attrs["capability_id"] in capabilities: fail("duplicate capability")
        if attrs.get("valid_from"): ts(attrs["valid_from"],"Capability valid_from")
        if attrs.get("expires_at"): ts(attrs["expires_at"],"Capability expires_at")
        capabilities[attrs["capability_id"]]=node

    for node in nodes["temporal"].values():
        attrs=node["attributes"]
        for key in ("time_kind","source","clock_domain","authority_effect"):
            if key not in attrs: fail(f"Temporal {key} missing")
        if not node["evidence_refs"]: fail("Temporal without evidence")
        fields=[key for key in ("occurred_at","not_before","not_after") if attrs.get(key)]
        if not fields: fail("Temporal instant/window missing")
        for key in fields: ts(attrs[key],f"Temporal {key}")
        if attrs.get("not_before") and attrs.get("not_after") and ts(attrs["not_before"],"Temporal start")>=ts(attrs["not_after"],"Temporal end"): fail("Temporal window invalid")

    link_ids=set()
    for link in bundle.get("links",[]):
        lid=link.get("link_id"); fg=link.get("from_graph"); tg=link.get("to_graph")
        if not isinstance(lid,str) or not lid or lid in link_ids: fail("link id invalid")
        link_ids.add(lid)
        if fg not in nodes or tg not in nodes or link.get("from_node_id") not in nodes[fg] or link.get("to_node_id") not in nodes[tg]: fail("broken link")

    manifest=bundle.get("evidence_manifest")
    if not isinstance(manifest,dict): fail("evidence manifest missing")
    if any(ref not in manifest for ref in evidence_refs(bundle)): fail("unresolved evidence reference")
    for digest in manifest.values():
        if not isinstance(digest,str) or len(digest)!=64 or any(ch not in "0123456789abcdef" for ch in digest): fail("evidence digest invalid")

    memory=bundle.get("memory_use") or {}
    if memory.get("authority_effect")!="none": fail("memory authority leak")
    for nid in memory.get("included",[]):
        node=nodes["memory"].get(nid)
        if not node: fail("included memory missing")
        attrs=node["attributes"]
        if attrs.get("freshness") in ("stale","unknown") or attrs.get("conflict_state")!="clear": fail("stale/conflicted memory included")

    policy=bundle.get("policy_evaluation") or {}; risk=bundle.get("risk_assessment") or {}
    identity=bundle.get("identity_evaluation") or {}; capability=bundle.get("capability_evaluation") or {}
    temporal=bundle.get("temporal_evaluation") or {}; decision=bundle.get("decision") or {}
    status=decision.get("status")
    if status not in DECISIONS: fail("decision invalid")
    if capability.get("authority_effect")!="none": fail("capability authority leak")

    if status in ("ACCEPT","VERIFIED"):
        current=[node for node in nodes["intent"].values() if node["attributes"].get("current") is True]
        if len(current)!=1: fail("exactly one current intent required")
        attrs=current[0]["attributes"]; principal=attrs.get("principal_id")
        if not principal: fail("intent principal missing")
        if policy.get("effect") not in ("ALLOW","CONSTRAIN"): fail("policy does not permit")
        if risk.get("residual_tier") not in ("low","moderate"): fail("risk not acceptable")
        if identity.get("binding_status")!="VERIFIED" or identity.get("assurance_level") not in ("moderate","high","hardware"): fail("identity not verified")
        if identity.get("principal_id")!=principal: fail("identity principal mismatch")
        if identity.get("actor_id") not in current_subjects or identity.get("executor_id") not in current_subjects: fail("identity not current")
        if capability.get("state")!="ENABLED" or capability.get("scope_status")!="IN_SCOPE" or capability.get("identity_bound") is not True: fail("capability not admissible")
        selected=capabilities.get(capability.get("capability_id"))
        if not selected: fail("selected capability missing")
        cattrs=selected["attributes"]
        if cattrs.get("status")!="ENABLED" or cattrs.get("bound_subject_id")!=identity.get("executor_id"): fail("capability executor mismatch")
        if cattrs.get("action")!=capability.get("action") or cattrs.get("target_scope")!=capability.get("target"): fail("capability selection mismatch")
        if temporal.get("state")!="VALID": fail("temporal state invalid")
        evaluated=ts(temporal.get("evaluated_at"),"Temporal evaluation")
        if temporal.get("dispatch_deadline") and evaluated>ts(temporal["dispatch_deadline"],"Dispatch deadline"): fail("evaluation after deadline")
        if attrs.get("valid_from") and evaluated<ts(attrs["valid_from"],"Intent start"): fail("intent not yet valid")
        if attrs.get("valid_until") and evaluated>ts(attrs["valid_until"],"Intent end"): fail("intent expired")
        if cattrs.get("valid_from") and evaluated<ts(cattrs["valid_from"],"Capability start"): fail("capability not yet valid")
        if cattrs.get("expires_at") and evaluated>ts(cattrs["expires_at"],"Capability end"): fail("capability expired")
        for pair in (("idea","intent"),("identity","intent"),("identity","capability"),("intent","policy"),("temporal","intent"),("temporal","capability")):
            if not aligned(bundle,*pair): fail(f"missing aligned {pair[0]}->{pair[1]}")
        if any(x.get("status")=="open" and x.get("severity") in ("high","critical") for x in bundle.get("mismatches",[])): fail("open high-impact mismatch")

    if status=="VERIFIED" and ((bundle.get("verification") or {}).get("status")!="verified" or not (bundle.get("verification") or {}).get("evidence_refs")): fail("verified without evidence")
    if status in ("HOLD","BLOCK","UNKNOWN") and decision.get("side_effect_allowed") is True: fail("unsafe side effect allowance")

def self_test(base):
    tests=[]
    def mutate(label,fn):
        value=copy.deepcopy(base); fn(value); tests.append((label,value))
    mutate("memory authority",lambda x:x["memory_use"].update(authority_effect="allow"))
    mutate("stale memory",lambda x:x["memory_graph"]["nodes"][0]["attributes"].update(freshness="stale"))
    mutate("critical risk",lambda x:x["risk_assessment"].update(residual_tier="critical"))
    mutate("missing intent",lambda x:x["intent_graph"]["nodes"][0]["attributes"].update(current=False))
    mutate("Fact evidence",lambda x:x["fact_graph"]["nodes"][0].update(evidence_refs=[]))
    mutate("identity mismatch",lambda x:x["identity_evaluation"].update(binding_status="MISMATCH"))
    mutate("weak identity",lambda x:x["identity_evaluation"].update(assurance_level="low"))
    mutate("revoked capability",lambda x:x["capability_evaluation"].update(state="REVOKED"))
    mutate("capability scope",lambda x:x["capability_evaluation"].update(scope_status="OUT_OF_SCOPE"))
    mutate("capability binding",lambda x:x["capability_evaluation"].update(identity_bound=False))
    mutate("expired time",lambda x:x["temporal_evaluation"].update(state="EXPIRED"))
    mutate("deadline race",lambda x:x["temporal_evaluation"].update(evaluated_at="2026-08-02T00:31:00Z"))
    mutate("principal mismatch",lambda x:x["identity_evaluation"].update(principal_id="user:other"))
    mutate("executor mismatch",lambda x:x["capability_graph"]["nodes"][0]["attributes"].update(bound_subject_id="user:alexey"))
    mutate("critical mismatch",lambda x:x.update(mismatches=[{"code":"EVALUATION_DISPATCH_RACE","severity":"critical","status":"open","reason":"binding changed","node_refs":["temporal:evaluation"]}]))
    for index,(label,value) in enumerate(tests,1):
        try: validate(value)
        except ValueError: continue
        raise SystemExit(f"negative control {index} ({label}) unexpectedly passed")
    print(f"PASS: {len(tests)} semantic negative controls")

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("bundle",type=Path); parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args(); bundle=load(args.bundle); validate(bundle)
    print("PASS: Personal Agent Safety Bundle v1.2")
    if args.self_test: self_test(bundle)
    return 0
if __name__=="__main__": sys.exit(main())
