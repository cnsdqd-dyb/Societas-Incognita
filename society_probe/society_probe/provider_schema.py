"""Provider grammar projection; local action constraints remain authoritative."""
import copy


def validate_phase_response(kind,value):
    """Missing protocol fields stop rollout; illegal chosen actions remain data."""
    if kind=='act':
        if (not isinstance(value,dict) or set(value)!={'action','communication'}
                or not isinstance(value['action'],dict) or not isinstance(value['action'].get('tool'),str)
                or not isinstance(value['communication'],dict) or not isinstance(value['communication'].get('op'),str)):
            raise ValueError('Action phase response is missing the required action/communication contract; rollout paused, raw response retained')
    elif kind=='communicate':
        if (not isinstance(value,dict) or set(value)!={'communication'}
                or not isinstance(value['communication'],dict) or not isinstance(value['communication'].get('op'),str)):
            raise ValueError('Communication phase response violates its output contract; rollout paused, raw response retained')
    return value


def mistral_transport_schema(contract):
    # Some large bounds/uniqueness constraints in the compound action contract
    # are rejected by Mistral's grammar compiler (HTTP 400/3051). Keep the
    # object structure, required fields, variants and enumerations. Numeric,
    # string-length and array bounds are checked by the actual world interface.
    omitted={'minimum','maximum','exclusiveMinimum','exclusiveMaximum',
             'minLength','maxLength','minItems','maxItems','uniqueItems'}
    def project(value):
        if isinstance(value,list): return [project(v) for v in value]
        if isinstance(value,dict):
            return {k:project(v) for k,v in value.items() if k not in omitted}
        return copy.deepcopy(value)
    return project(contract)
