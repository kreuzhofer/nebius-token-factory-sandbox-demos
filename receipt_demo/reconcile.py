"""Deterministic accounting over model interpretations and source fingerprints."""
from decimal import Decimal

from .models import Decisions, Entry, Report


def reconcile(receipts, decisions: Decisions):
    by_id = {receipt.receipt_id: receipt for receipt in receipts}
    if len(by_id) != len(receipts):
        raise ValueError('Duplicate input identifiers')
    flags = {}
    for flag in decisions.monetary_flags:
        if flag.receipt_id not in by_id or not flag.reason.strip():
            raise ValueError('Invalid monetary flag')
        flags.setdefault(flag.receipt_id, []).append(flag.reason)
    entries = []
    for receipt in receipts:
        reasons = list(receipt.monetary_issues) + flags.get(receipt.receipt_id, [])
        signed = None
        for name in ('total', 'currency', 'transaction_type'):
            if getattr(receipt, name) is None:
                reasons.append(f'Unknown {name}')
        if receipt.total is not None and receipt.transaction_type:
            amount = Decimal(receipt.total)
            if receipt.transaction_type == 'refund':
                amount = -abs(amount)
            elif amount < 0:
                reasons.append('Negative purchase total; refund direction is unresolved')
            signed = str(amount)
        if receipt.components_complete and receipt.comparable_components and receipt.total is not None:
            component_total = sum(map(Decimal, receipt.comparable_components), Decimal('0'))
            if abs(abs(component_total) - abs(Decimal(receipt.total))) > Decimal('0.01'):
                reasons.append('Printed components contradict the payable total')
        if receipt.error:
            outcome, reasons = 'error', [receipt.error]
        else:
            outcome = 'flagged' if reasons else 'included'
        entries.append(Entry(receipt_id=receipt.receipt_id, source=receipt.source,
                             outcome=outcome, reasons=reasons,
                             signed_amount=signed, currency=receipt.currency))

    # Confirm duplicates from actual bytes/pixels, even with inconsistent model readings.
    # Collapse these groups before semantic decisions so suspected groups affect originals too.
    canonical, fingerprints = {}, {}
    for receipt in receipts:
        keys = [value for value in (receipt.content_hash, receipt.pixel_hash) if value]
        prior = next((fingerprints[key] for key in keys if key in fingerprints), None)
        canonical[receipt.receipt_id] = prior or receipt.receipt_id
        for key in keys:
            fingerprints[key] = canonical[receipt.receipt_id]
    by_entry = {entry.receipt_id: entry for entry in entries}
    touched = set()
    for group in decisions.duplicates:
        if any(key not in by_id for key in group.receipt_ids) or not group.reason.strip():
            raise ValueError('Invalid duplicate group')
        ids = list(dict.fromkeys(canonical[key] for key in group.receipt_ids))
        if len(ids) < 2:
            continue  # Already confirmed by source identity.
        if touched.intersection(ids):
            raise ValueError('Overlapping semantic duplicate groups')
        touched.update(ids)
        conflicts = False
        for field in ('merchant', 'currency', 'transaction_date', 'transaction_type', 'total'):
            values = [getattr(by_id[key], field) for key in ids if getattr(by_id[key], field) is not None]
            normalized = {Decimal(value) if field == 'total' else value.strip().casefold() for value in values}
            conflicts = conflicts or len(normalized) > 1
        if group.confidence == 'confirmed' and not conflicts:
            keeper = next((key for key in ids if by_entry[key].outcome == 'included'), ids[0])
            for key in ids:
                if key != keeper:
                    canonical[key] = keeper
        else:
            for key in ids:
                entry = by_entry[key]
                if entry.outcome != 'error':
                    entry.outcome = 'flagged'
                    reason = group.reason
                    if conflicts:
                        reason += ' (conflicting extracted fields prevent confirmation)'
                    entry.reasons.append('Suspected duplicate: ' + reason)
    for entry in entries:
        key = canonical[entry.receipt_id]
        while canonical[key] != key:
            key = canonical[key]
        if key != entry.receipt_id:
            entry.outcome, entry.duplicate_of = 'duplicate', key
            entry.reasons.append('Confirmed duplicate; counted at most once through ' + key)
    totals = {}
    for entry in entries:
        if entry.outcome == 'included':
            totals[entry.currency] = totals.get(entry.currency, Decimal('0')) + Decimal(entry.signed_amount)
    status = 'completed_with_flags' if any(e.outcome != 'included' for e in entries) else 'completed'
    return Report(status=status, entries=entries, totals={key: str(value) for key, value in sorted(totals.items())},
                  receipts=receipts, artifacts={'json': 'report.json', 'pdf': 'report.pdf'})
