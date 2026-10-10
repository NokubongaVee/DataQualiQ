"""Dataset knowledge is isolated here. Select explicitly, never by filename."""
from .schema import NetworkSchema, FieldRule


def unsw_nb15_schema():
    # No frequency-based category lists or arbitrary distribution bounds.
    count_fields = ('spkts dpkts sbytes dbytes sloss dloss swin dwin stcpb dtcpb '
                    'trans_depth response_body_len ct_srv_src ct_state_ttl ct_dst_ltm '
                    'ct_src_dport_ltm ct_dst_sport_ltm ct_dst_src_ltm ct_ftp_cmd '
                    'ct_flw_http_mthd ct_src_ltm ct_srv_dst').split()
    nonnegative = ('dur rate sload dload sinpkt dinpkt sjit djit tcprtt synack ackdat smean dmean').split()
    fields = {name: FieldRule('count') for name in count_fields}
    fields.update({name: FieldRule('nonnegative') for name in nonnegative})
    fields.update({name: FieldRule('number') for name in ('sttl', 'dttl')})
    fields.update(proto=FieldRule('protocol', case_sensitive=False),
                  service=FieldRule('category'), state=FieldRule('category'),
                  is_sm_ips_ports=FieldRule('binary'), label=FieldRule('binary'))
    # is_ftp_login is deliberately not forced binary: verify exporter semantics first.
    fields['is_ftp_login'] = FieldRule('nonnegative')
    return NetworkSchema(name='UNSW-NB15', fields=fields, target_fields=('label',),
                         leakage_fields=('attack_cat',), identifier_fields=('id',))
