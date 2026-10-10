"""Thin schema-aware preprocessing adapter; assessment does not invoke it."""
from .generic_preprocessor import preprocess_dataframe
from .generic_preprocessor import PreprocessingPolicy
from dataclasses import replace
from domains.network.validators import valid_value


def preprocess_network(df, schema, policy=None, findings=None):
    policy = policy or PreprocessingPolicy()
    for name, plan in policy.fields.items():
        if name in schema.fields and plan.case and schema.fields[name].case_sensitive:
            raise ValueError(f'Case carries meaning in configured field {name!r}.')
    policy = replace(policy, protected_fields=tuple(set(policy.protected_fields) | schema.protected_fields))
    rules = {name: (lambda value, rule=rule: valid_value(value, rule)) for name, rule in schema.fields.items()}
    output, audit = preprocess_dataframe(df, policy=policy, findings=findings, validation_rules=rules)
    audit['future_feature_columns'] = schema.feature_columns(output.columns)
    audit['excluded_predictive_fields'] = sorted(schema.protected_fields & set(output.columns))
    return output, audit
