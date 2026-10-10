"""Dataset-specific choices, kept outside the generic quality/ML engines."""
from domains.network.configs import unsw_nb15_schema
from preprocessing import FieldPolicy, PreprocessingPolicy
from .preprocessing import NetworkMLPreprocessor


def unsw_nb15_ml_config():
    schema = unsw_nb15_schema()
    policy = PreprocessingPolicy(fields={
        'proto': FieldPolicy(trim=True, case='lower', reason='UNSW network schema declares protocol names case-insensitive.'),
        'service': FieldPolicy(trim=True, reason='Outer whitespace is export representation; preserve service spelling and the legitimate dash category.'),
        'state': FieldPolicy(trim=True, reason='Outer whitespace is export representation; preserve case-sensitive state codes.'),
    })
    return schema, policy, NetworkMLPreprocessor(schema, policy)
