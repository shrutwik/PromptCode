"""Small reviewed reference repairs for validating independent evaluator inventories.

These are test-only, never included in candidate images or workspace files.
"""
import shutil
from pathlib import Path

from app.services.interview.registry import challenge_dir


def reference_snapshot(slug: str, dest: Path) -> Path:
    shutil.copytree(challenge_dir(slug),dest,ignore=shutil.ignore_patterns('node_modules','.venv','venv','__pycache__','.pytest_cache','.git'))
    def replace(file,old,new):
        p=dest/file;s=p.read_text();assert old in s,(slug,file);p.write_text(s.replace(old,new))
    if slug=='invoice-status-transition':
        replace('src/statusMachine.ts',"  if (from === 'paid' && to !== 'void') return true;\n",'')
    elif slug=='order-hold-reason':
        replace('app/service.py','"status": order.status,','"status": order.status,\n        "hold_reason": order.hold_reason,')
    elif slug=='catalog-suggest-latency':
        replace('src/suggest.ts','globalCounter.recordScan(catalog.length);','globalCounter.recordScan(1);')
        replace('src/suggest.ts','    for (const other of catalog) { if (other.id === product.id) void other; }\n','')
    elif slug=='notification-feed-stale':
        replace('src/feedStore.ts','  const snapshot = items.map((n) => ({ ...n }));\n','')
        replace('src/feedStore.ts','items = snapshot.map','items = items.map')
    elif slug=='workspace-label-propagation':
        replace('server/app.ts','const { id, workspaceId, title } = ticket;','const { id, workspaceId, title, labelIds } = ticket;')
        replace('server/app.ts','res.json({ id, workspaceId, title });','res.json({ id, workspaceId, title, labelIds });')
        replace('server/app.ts','title: saved.title });','title: saved.title, labelIds: saved.labelIds });')
        replace('client/TicketLabels.tsx','setSelected([]);','setSelected(ticket.labelIds ?? []);')
    elif slug=='shipment-csv-merge':
        replace('shipment_merge/merge.py','seen_status: set[tuple[str, str]] = set()','seen_status: set[str] = set()')
        replace('shipment_merge/merge.py','key = (event.shipment_id, event.status)','key = event.event_id')
        replace('shipment_merge/merge.py','        if key in seen_status:\n            qty[event.shipment_id] += event.quantity_delta\n            continue','        if key in seen_status:\n            continue')
    elif slug=='tenant-document-acl':
        replace('app/service.py','if doc is None:','if doc is None or doc.tenant_id != principal.tenant_id:')
    elif slug=='webhook-delivery-retry':
        replace('src/sideEffects.ts','charges.push(deliveryId);','if (!charges.includes(deliveryId)) charges.push(deliveryId);')
        replace('src/worker.ts','  for (let attempt = 1;', '  recordCharge(job.id);\n  for (let attempt = 1;')
        replace('src/worker.ts','    recordCharge(job.id);\n','')
        replace('src/worker.ts','return Promise.all(jobs.map((job) => deliverOne(job, client, policy)));',"const results: boolean[] = []; for (let i=0;i<jobs.length;i+=5) { results.push(...await Promise.all(jobs.slice(i,i+5).map(job=>deliverOne(job,client,policy)))); } return results;")
    elif slug=='pricing-rule-extract':
        p=dest/'src/pricingEngine.ts';s=p.read_text()
        s=s.replace('  let amount = input.baseCents;', '  return applyRules(input.baseCents, input.rules);\n}\nexport function applyRules(baseCents: number, rules: Rule[]): QuoteResult {\n  let amount = baseCents;')
        s=s.replace('sortRulesForApply(input.rules)','sortRulesForApply(rules)')
        start=s.index('/** baseCents plus rules');s=s[:start]
        p.write_text(s)
    elif slug=='subscription-proration-boundary':
        replace('proration/period.py','period.start <= instant <= period.end','period.start <= instant < period.end')
    else: raise AssertionError(slug)
    return dest
