"""Optional vocabulary-based domain hints; never used to select checks or actions."""
from collections import defaultdict

from type_inference import infer_all_column_profiles


DOMAIN_PROFILES = {
    "human_resources": {
        "strong_terms": {"employee", "employees", "staff", "personnel", "payroll", "manager", "department", "division", "compensation", "salary", "hire", "role", "position", "team", "employment"},
        "strong_role_support": {"person_name": 2.6, "monetary_value": 2.4, "category": 2.0, "identifier": 1.8, "date": 1.8, "phone": 1.3, "email": 1.3},
        "evidence": {
            "employee": "employee/personnel-related column detected",
            "salary": "compensation-related column detected",
            "department": "organisational department column detected",
            "hire": "employment-related date detected",
            "manager": "management/leadership column detected",
        },
    },
    "education": {
        "strong_terms": {"student", "students", "learner", "learners", "teacher", "school", "course", "programme", "program", "semester", "assessment", "grade", "mark", "class", "enrollment", "academic"},
        "strong_role_support": {"person_name": 2.4, "measurement": 2.5, "category": 2.0, "identifier": 1.8, "date": 1.6, "email": 1.2, "phone": 1.1},
        "evidence": {
            "student": "student/learner-related column detected",
            "programme": "study programme or course column detected",
            "assessment": "assessment/mark-related measurement detected",
            "semester": "term or academic period detected",
        },
    },
    "sales": {
        "strong_terms": {"customer", "customers", "buyer", "client", "product", "order", "invoice", "transaction", "purchase", "sale", "sales", "revenue", "cart", "pricing", "customer_id"},
        "strong_role_support": {"person_name": 1.8, "monetary_value": 2.8, "quantity": 2.3, "identifier": 1.8, "date": 1.7, "category": 1.2, "phone": 1.0, "email": 1.0},
        "evidence": {
            "customer": "customer or buyer column detected",
            "product": "product or item column detected",
            "order": "transaction or order signal detected",
            "invoice": "sales/invoice-related evidence detected",
        },
    },
    "inventory": {
        "strong_terms": {"stock", "inventory", "warehouse", "supplier", "sku", "item", "batch", "location", "units", "available", "storage", "warehouse", "bin"},
        "strong_role_support": {"quantity": 3.0, "monetary_value": 2.2, "category": 1.8, "identifier": 2.1, "date": 1.3},
        "evidence": {
            "stock": "stock or inventory signal detected",
            "supplier": "supplier or warehouse signal detected",
            "sku": "item identifier or SKU detected",
            "location": "storage location detected",
        },
    },
    "healthcare": {
        "strong_terms": {"patient", "patients", "doctor", "doctors", "diagnosis", "treatment", "medication", "hospital", "clinic", "symptom", "care", "medical", "clinical"},
        "strong_role_support": {"person_name": 2.5, "identifier": 1.8, "measurement": 2.3, "category": 1.7, "date": 1.6, "phone": 1.2, "email": 1.1},
        "evidence": {
            "patient": "patient-related record detected",
            "diagnosis": "clinical diagnosis signal detected",
            "treatment": "treatment/medical care signal detected",
            "hospital": "care-setting signal detected",
        },
    },
    "finance": {
        "strong_terms": {"account", "accounts", "balance", "ledger", "payment", "payments", "currency", "bank", "finance", "transaction", "credit", "debit", "invoice", "balance"},
        "strong_role_support": {"monetary_value": 3.4, "identifier": 1.8, "date": 1.5, "category": 1.2},
        "evidence": {
            "account": "account or ledger signal detected",
            "payment": "payment-related monetary signal detected",
            "balance": "financial balance signal detected",
            "currency": "currency or financial value detected",
        },
    },
}

GENERIC_ROLE_WEIGHTS = {
    "identifier": 0.7,
    "date": 0.5,
    "category": 0.7,
    "phone": 0.5,
    "email": 0.5,
    "quantity": 0.8,
    "measurement": 0.8,
    "monetary_value": 0.9,
    "person_name": 1.0,
    "contact_information": 0.6,
}


def _normalise_label(value):
    if value is None:
        return ""
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _tokenise(value):
    text = _normalise_label(value)
    if not text:
        return set()
    return {part for part in text.split("_") if part}


def _semantic_tokens_from_profile(profile):
    tags = set()
    for value in profile.get("semantic_tags", []) or []:
        if isinstance(value, str):
            tags.add(_normalise_label(value))
    role = _normalise_label(profile.get("role", "unknown"))
    if role and role != "unknown":
        tags.add(role)
    return tags


def _domain_concept_family(domain, signal):
    """Map related signals to one underlying concept family for a given domain."""
    normalised = _normalise_label(signal)
    if not normalised:
        return signal

    profile = DOMAIN_PROFILES.get(domain, {})
    strong_terms = set(profile.get("strong_terms", set()))
    candidate_terms = {normalised}
    candidate_terms.update(_tokenise(normalised))

    for term in sorted(strong_terms, key=len, reverse=True):
        if term in candidate_terms or term in normalised or normalised in term:
            return term

    if domain == "human_resources":
        if normalised in {"employee", "employees", "staff", "personnel", "person", "manager", "role", "position", "team"}:
            return "employee"
        if normalised in {"salary", "compensation", "payroll", "wage", "income"}:
            return "salary"
        if normalised in {"department", "division", "team", "manager"}:
            return "department"
        if normalised in {"hire", "employment", "start", "joined", "tenure"}:
            return "employment"
        if normalised in {"phone", "email", "contact"}:
            return "contact"
        if normalised in {"id", "identifier", "employee_id", "emp_id"}:
            return "identifier"

    if domain == "education":
        if normalised in {"student", "students", "learner", "learners", "teacher"}:
            return "student"
        if normalised in {"programme", "program", "course", "semester", "term", "class", "classroom"}:
            return "programme"
        if normalised in {"assessment", "grade", "mark", "score", "result"}:
            return "assessment"
        if normalised in {"phone", "email", "contact"}:
            return "contact"
        if normalised in {"id", "identifier", "student_id", "learner_id"}:
            return "identifier"

    if domain == "sales":
        if normalised in {"customer", "customers", "buyer", "client", "client_id"}:
            return "customer"
        if normalised in {"product", "products", "item", "sku", "inventory"}:
            return "product"
        if normalised in {"order", "invoice", "transaction", "purchase", "sale", "sales", "revenue", "pricing", "price", "total"}:
            return "transaction"
        if normalised in {"date", "order_date", "purchase_date", "created_at"}:
            return "date"
        if normalised in {"phone", "email", "contact"}:
            return "contact"
        if normalised in {"id", "identifier", "customer_id"}:
            return "identifier"

    if domain == "inventory":
        if normalised in {"stock", "inventory", "available", "units", "quantity"}:
            return "stock"
        if normalised in {"supplier", "warehouse", "storage", "location", "bin"}:
            return "location"
        if normalised in {"sku", "item", "batch", "product_id"}:
            return "identifier"
        if normalised in {"date", "stock_date"}:
            return "date"

    if domain == "healthcare":
        if normalised in {"patient", "patients", "doctor", "doctors", "care"}:
            return "patient"
        if normalised in {"diagnosis", "treatment", "medication", "medical", "clinical", "symptom"}:
            return "clinical"
        if normalised in {"hospital", "clinic"}:
            return "care_setting"
        if normalised in {"phone", "email", "contact"}:
            return "contact"
        if normalised in {"id", "identifier", "patient_id"}:
            return "identifier"

    if domain == "finance":
        if normalised in {"account", "accounts", "ledger", "bank", "balance", "payment", "payments", "currency", "credit", "debit", "invoice"}:
            return "financial"
        if normalised in {"date", "payment_date", "posted_at"}:
            return "date"
        if normalised in {"id", "identifier", "account_id"}:
            return "identifier"

    return normalised


def _collect_column_domain_candidates(column_name, profile):
    label = _normalise_label(column_name)
    role = (profile or {}).get("role", "unknown")
    confidence = float((profile or {}).get("confidence", 0.0) or 0.0)
    semantic_tags = _semantic_tokens_from_profile(profile)

    domain_candidates = defaultdict(set)

    for domain, domain_profile in DOMAIN_PROFILES.items():
        hits = set()
        direct_term_found = False

        for term in domain_profile["strong_terms"]:
            if set(term.split("_")).issubset(_tokenise(label)) or term in semantic_tags:
                hits.add(term)
                direct_term_found = True

        if direct_term_found and role in domain_profile["strong_role_support"]:
            hits.add(f"role:{role}")

        if hits:
            for hit in hits:
                domain_candidates[domain].add(_domain_concept_family(domain, hit))

    return domain_candidates, role, confidence


def infer_dataset_context(df, column_profiles=None):
    if df is None or df.empty:
        return {"name": "unknown", "confidence": 0.0, "evidence": ["dataset is empty"]}

    if column_profiles is None:
        column_profiles = infer_all_column_profiles(df)

    domain_scores = defaultdict(float)
    domain_concepts = defaultdict(set)
    domain_evidence = defaultdict(set)
    supporting_columns = defaultdict(set)
    column_count = len(column_profiles)

    for column_name, profile in column_profiles.items():
        if profile is None:
            continue

        domain_candidates, role, confidence = _collect_column_domain_candidates(column_name, profile)
        if not domain_candidates:
            continue

        for domain, concept_families in domain_candidates.items():
            if not concept_families:
                continue

            domain_profile = DOMAIN_PROFILES[domain]
            contribution = 0.0
            column_evidence = set()

            for concept in sorted(concept_families):
                if concept.startswith("role:"):
                    actual_role = concept.split(":", 1)[1]
                    weight = domain_profile["strong_role_support"].get(actual_role, 0.8)
                    contribution += max(0.4, min(1.2, weight * (0.22 + confidence * 0.4)))
                    column_evidence.add(f"{actual_role} role support")
                    continue

                term_score = 2.2 if concept in domain_profile["strong_terms"] else 1.4
                if concept in {"contact", "identifier"}:
                    term_score *= 0.7
                if concept in {"department", "programme", "student", "employee", "customer", "product", "transaction", "financial", "patient", "clinical"}:
                    term_score *= 1.2
                contribution += term_score
                column_evidence.add(f"{concept} signal in column {column_name}")

            contribution = min(contribution, 4.2)
            domain_scores[domain] += contribution
            supporting_columns[domain].add(column_name)
            domain_concepts[domain].update(concept_families)
            domain_evidence[domain].update(column_evidence)

    if not domain_scores:
        return {"name": "unknown", "confidence": 0.30, "evidence": ["Insufficient domain-specific evidence"]}

    ordered = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
    best_domain, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0

    distinct_supporting_columns = len(supporting_columns.get(best_domain, set()))
    distinct_concepts = len(domain_concepts.get(best_domain, set()))
    substantive_concepts = {
        concept for concept in domain_concepts.get(best_domain, set())
        if concept not in {"identifier", "date", "contact", "currency", "financial", "role:identifier", "role:date", "role:contact_information", "role:phone", "role:email", "role:monetary_value"}
    }
    support_ratio = min(distinct_supporting_columns / max(column_count, 1), 1.0)
    concept_ratio = min(distinct_concepts / max(column_count, 1), 1.0)
    gap_ratio = max(0.0, (best_score - second_score) / max(best_score, 1.0))

    confidence = 0.18
    confidence += 0.30 * min(1.0, support_ratio)
    confidence += 0.24 * min(1.0, concept_ratio)
    confidence += 0.22 * min(1.0, gap_ratio)
    confidence += 0.10 * min(1.0, best_score / max(sum(domain_scores.values()), 1.0))
    # Domain names remain header-based hypotheses even with several signals.
    confidence = max(0.0, min(0.75, confidence))

    if distinct_supporting_columns < 2 or len(substantive_concepts) < 2 or best_score < 3.2 or gap_ratio < 0.12:
        return {"name": "unknown", "confidence": round(min(0.35, confidence), 2), "evidence": ["Insufficient domain-specific evidence"]}

    if len(df) < 5 or distinct_supporting_columns < 3:
        confidence = min(confidence, 0.75)

    evidence_list = sorted(domain_evidence.get(best_domain, set()))
    if not evidence_list:
        evidence_list = [f"{best_domain} patterns detected across the dataset"]

    return {
        "name": best_domain,
        "confidence": round(confidence, 2),
        "evidence": evidence_list,
        "limitations": ["Vocabulary-based context hint; not an established domain or business workflow."],
    }
