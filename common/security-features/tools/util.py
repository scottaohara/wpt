from __future__ import print_function

import os, sys, json, re

script_directory = os.path.dirname(os.path.abspath(__file__))
template_directory = os.path.abspath(
    os.path.join(script_directory, 'template'))
test_root_directory = os.path.abspath(
    os.path.join(script_directory, '..', '..', '..'))


def get_template(basename):
    with open(os.path.join(template_directory, basename), "r") as f:
        return f.read()


def write_file(filename, contents):
    with open(filename, "w") as f:
        f.write(contents)


def read_nth_line(fp, line_number):
    fp.seek(0)
    for i, line in enumerate(fp):
        if (i + 1) == line_number:
            return line


def load_spec_json(path_to_spec):
    re_error_location = re.compile('line ([0-9]+) column ([0-9]+)')
    with open(path_to_spec, "r") as f:
        try:
            return json.load(f)
        except ValueError as ex:
            print(ex.message)
            match = re_error_location.search(ex.message)
            if match:
                line_number, column = int(match.group(1)), int(match.group(2))
                print(read_nth_line(f, line_number).rstrip())
                print(" " * (column - 1) + "^")
            sys.exit(1)


class ShouldSkip(Exception):
    def __init__(self):
        pass


class PolicyDelivery(object):
    def __init__(self, type, key, value):
        self.type = type
        self.key = key
        self.value = value

    @classmethod
    def list_from_json(cls, list, target_policy_delivery,
                       supported_delivery_types):
        # type: (dict, PolicyDelivery, typing.List[str]) -> typing.List[PolicyDelivery]
        if list is None:
            return []

        out = []
        for obj in list:
            policy_delivery = PolicyDelivery.from_json(
                obj, target_policy_delivery, supported_delivery_types)
            # Drop entries with null values.
            if policy_delivery.value is None:
                continue
            out.append(policy_delivery)
        return out

    @classmethod
    def from_json(cls, obj, target_policy_delivery, supported_delivery_types):
        # type: (dict, PolicyDelivery, typing.List[str]) -> PolicyDelivery
        '''
           Creates PolicyDelivery from `obj`.
           In addition to dicts (in the same format as to_json() outputs),
           this method accepts the following placeholders:
             "policy":
               `target_policy_delivery`
             "policyIfNonNull":
               `target_policy_delivery` if its value is not None.
             "anotherPolicy":
               A PolicyDelivery that has the same key as
               `target_policy_delivery` but a different value.
               The delivery type is selected from `supported_delivery_types`.
        '''

        if obj == "policy":
            policy_delivery = target_policy_delivery
        elif obj == "nonNullPolicy":
            if target_policy_delivery.value is None:
                raise ShouldSkip()
            policy_delivery = target_policy_delivery
        elif obj == "anotherPolicy":
            policy_delivery = target_policy_delivery.get_another_policy(
                supported_delivery_types[0])
        elif type(obj) == dict:
            policy_delivery = PolicyDelivery(obj['deliveryType'], obj['key'],
                                             obj['value'])
        else:
            raise Exception('policy delivery is invalid: ' + obj)

        # Omit unsupported combinations of source contexts and delivery type.
        if policy_delivery.type not in supported_delivery_types:
            raise ShouldSkip()

        return policy_delivery

    def to_json(self):
        # type: () -> dict
        return {
            "deliveryType": self.type,
            "key": self.key,
            "value": self.value
        }

    def get_another_policy(self, type):
        # type: (str) -> PolicyDelivery
        if self.key == 'referrerPolicy':
            if self.value == 'no-referrer':
                return PolicyDelivery(type, self.key, 'unsafe-url')
            else:
                return PolicyDelivery(type, self.key, 'no-referrer')
        else:
            raise Exception('delivery key is invalid: ' + self.key)


class SourceContext(object):
    def __init__(self, source_context_type, policy_deliveries):
        # type: (unicode, typing.List[PolicyDelivery]) -> None
        self.source_context_type = source_context_type
        self.policy_deliveries = policy_deliveries

    @classmethod
    def from_json(cls, obj, target_policy_delivery, delivery_type_schema):
        source_context_type = obj.get('sourceContextType')
        policy_deliveries = PolicyDelivery.list_from_json(
            obj.get('policyDeliveries'), target_policy_delivery,
            delivery_type_schema['source_context'][source_context_type])
        return SourceContext(source_context_type, policy_deliveries)

    def to_json(self):
        return {
            "sourceContextType": self.source_context_type,
            "policyDeliveries": [x.to_json() for x in self.policy_deliveries]
        }


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SourceContext):
            return obj.to_json()
        if isinstance(obj, PolicyDelivery):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)
