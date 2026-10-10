"""Explicit semantic mappings; no validity rules are learned from frequencies."""
from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class FieldRule:
    kind: str
    required: bool = False
    allowed_values: tuple[str, ...] = ()
    case_sensitive: bool = True

    def __post_init__(self):
        if isinstance(self.allowed_values, str):
            raise ValueError('Allowed values must be a sequence, not a string.')
        if self.kind not in {'number', 'nonnegative', 'count', 'port', 'binary', 'protocol', 'category', 'ip'}:
            raise ValueError(f'Unsupported network field kind: {self.kind}')
        object.__setattr__(self, 'allowed_values', tuple(self.allowed_values))
        if not isinstance(self.required, bool) or not isinstance(self.case_sensitive, bool):
            raise ValueError('Required/case-sensitive options must be booleans.')
        if not all(isinstance(value, str) and value for value in self.allowed_values):
            raise ValueError('Allowed values must be nonempty strings.')
        if self.allowed_values and self.kind not in {'category', 'protocol'}:
            raise ValueError('Allowed values apply only to category/protocol rules.')


@dataclass(frozen=True)
class NetworkSchema:
    name: str = 'configured_network'
    fields: dict[str, FieldRule] = field(default_factory=dict)
    target_fields: tuple[str, ...] = ()
    leakage_fields: tuple[str, ...] = ()
    identifier_fields: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('Schema name must be a nonempty string.')
        object.__setattr__(self, 'fields', dict(self.fields))
        for key in ('target_fields', 'leakage_fields', 'identifier_fields'):
            if isinstance(getattr(self, key), str):
                raise ValueError(f'{key} must be a sequence of column names, not a string.')
            object.__setattr__(self, key, tuple(getattr(self, key)))
            if not all(isinstance(name, str) and name for name in getattr(self, key)):
                raise ValueError(f'{key} must contain nonempty string names.')
        if not all(isinstance(name, str) and name and isinstance(rule, FieldRule) for name, rule in self.fields.items()):
            raise ValueError('Schema fields must map string names to FieldRule objects.')

    @property
    def protected_fields(self):
        return frozenset(self.target_fields + self.leakage_fields + self.identifier_fields)

    def to_dict(self):
        return asdict(self)

    def feature_columns(self, columns):
        """Future feature projection excludes targets, leakage and identifiers."""
        return [name for name in columns if name not in self.protected_fields]

    @classmethod
    def from_dict(cls, config):
        return cls(**{**config, 'fields': {name: FieldRule(**rule) for name, rule in config.get('fields', {}).items()}})


def apply_schema_profiles(profiles, schema):
    """Keep inferred evidence, but route known representations using the schema."""
    numeric = {'number', 'nonnegative', 'count', 'port', 'binary'}
    for name, rule in schema.fields.items():
        if name not in profiles:
            continue
        profile = profiles[name]
        profile['inferred_type'] = profile['type']
        profile['inferred_role'] = profile['role']
        profile['type'] = 'numeric' if rule.kind in numeric else 'text'
        profile['role'] = 'identifier' if name in schema.identifier_fields else 'network_field'
        profile['schema_rule'] = asdict(rule)
        profile['evidence'] = profile['evidence'] + [f'Explicit schema {schema.name}: {rule.kind}.']
        # Specified categorical vocabulary is validated by the domain layer,
        # never by edit-distance proximity to the dataset's common categories.
    for name in schema.identifier_fields:
        if name in profiles:
            profiles[name]['role'] = 'identifier'
    for name in schema.target_fields + schema.leakage_fields:
        if name in profiles:
            profiles[name]['protected_fields'] = tuple(schema.protected_fields)
