import yaml
import re
import copy
import argparse
import numbers
import sys
import typing
import json
from pprint import pprint


def build_parser():  # pragma: no cover
    """
    Build argument parser.
    """
    parser_object = argparse.ArgumentParser(
        prog='pyExpandObjects',
        description='Automated process that expands HVACTemplate objects into regular EnergyPlus objects.')
    parser_object.add_argument(
        "--yaml_file",
        "-y",
        nargs='?',
        help='Yaml object structure'
    )
    parser_object.add_argument(
        "--epjson_file",
        "-f",
        nargs="?",
        help="epjson file to convert"
    )
    return parser_object


def flatten_build_path(
        build_path: list,
        flat_list: list = [],
        clear: bool = True) -> list:
    """
    Flattens list of lists to one list of items.
    Due to way the BuildPath is structured, sub-lists
    are inserted from re-used objects, which makes this code
    necessary.

    This is a simple recursion function that iterates a list
    and if the element it grabs is a list, then iterates through
    that list.  Whenever a non-list element is found, it is appended
    to a flattened list object that is eventually returned.

    Clear is the option to restart flat_list.  Due to its recursive
    nature, the flat_list will continually append to the list in memory
    unless told to reset.

    :param build_path: list of nested dictionary objects
    :param flat_list: list used to store recursive addition of objects
    :param clear: Option to empty the recursive list
    :return: flattened list of objects in the build_path
    """
    if clear:
        flat_list = []
    for i in build_path:
        if isinstance(i, list):
            flatten_build_path(i, flat_list, clear=False)
        else:
            flat_list.append(i)
    return flat_list


def merge_dictionaries(
        super_dictionary: dict,
        object_dictionary: dict,
        unique_name_override: bool = True) -> dict:
    """
    Merge a high level dictionary with a sub-dictionary, both in epJSON format

    :param super_dictionary: high level dictionary used as the base object
    :param object_dictionary: dictionary to merge into base object
    :param unique_name_override: allow a duplicate unique name to overwrite an existing object
    :return: merged output of the two input dictionaries
    """
    for object_type, tmp_d in object_dictionary.items():
        if not super_dictionary.get(object_type):
            super_dictionary[object_type] = {}
        if isinstance(tmp_d, dict):
            for object_name, object_fields in tmp_d.items():
                if not unique_name_override and object_name in super_dictionary[object_type].keys():
                    print('unique name error')
                    sys.exit()
            for tmp_d_name, tmp_d_structure in tmp_d.items():
                super_dictionary[object_type][tmp_d_name] = tmp_d_structure
        elif isinstance(tmp_d, list):
            super_dictionary[object_type] = tmp_d
    return super_dictionary


def replace_values(
        super_object: dict,
        text_replacement: dict) -> dict:
    """
    Replace the pre-set string values in an object to avoid duplications.
    For example, '{}' can be replaced with '{} New Text'.  These fields will still contain
    the string formatting brackets for further manipulation.

    :param super_object: EnergyPlus super object
    :param text_replacement: string to replace with format brackets in the super object
        field values
    :return: super_object similar to the input, but with renamed string fields
    """
    if text_replacement:
        (object_type, object_constructors), = super_object.items()
        for field_name, field_value in object_constructors['Fields'].items():
            super_object[object_type]['Fields'][field_name] = field_value.replace(
                '{}',
                text_replacement
            )
    return super_object


def process_complex_inputs(
        super_dictionary: dict,
        lookup_value: typing.Union[str, int, float, dict, list],
        unique_name_input: str,
        reference_field_name: str) -> typing.Generator[str, typing.Dict[str, str], None]:
    """
    Process Yaml input and perform varying operations based on the input type.  This function cannot handle
    lookups that have more than one object type in the super dictionary path. A generator is returned due to
    the recursive application within this function.

    :param super_dictionary: epJSON formatted dictionary to be used as reference for complex lookups
    :param lookup_value: value to lookup, which can be in complex format
    :param unique_name_input: unique name modifier
    :param reference_field_name: field name to be populated with lookup value
    :return: dictionary with two values: "field" -> reference_field_name, "value" -> output from lookup value
    """
    # if the value is a string or numeric, then it's a direct input.
    # If it is a dictionary then the key-value pair is the object type (which can be a regex)
    # and lookup instructions.
    # If it is a list, then the object will be iterated for each item and the same process applied recursively
    # Anything else should return an error.
    if isinstance(lookup_value, str):
        yield {"field": reference_field_name, "value": lookup_value.format(unique_name_input)}
    elif isinstance(lookup_value, numbers.Number):
        yield {"field": reference_field_name, "value": lookup_value}
    elif isinstance(lookup_value, dict):
        # unpack the referenced object type and the lookup instructions
        (reference_object_type, lookup_instructions), = lookup_value.items()
        # try to match the reference object with EnergyPlus objects in the super_dictionary
        for object_type in super_dictionary.keys():
            if re.match(reference_object_type, object_type, re.IGNORECASE):
                # retrieve value
                # if 'self' is used as the reference node, return the energyplus object type
                # if 'key' is used as the reference node, return the unique object name
                # After those checks, the lookup_instructions is the field name of the object.
                (object_name, _), = super_dictionary[object_type].items()
                if lookup_instructions.lower() == 'self':
                    yield {"field": reference_field_name, "value": object_type}
                elif lookup_instructions.lower() == 'key':
                    yield {"field": reference_field_name, "value": object_name}
                else:
                    yield {"field": reference_field_name,
                           "value": super_dictionary[object_type]
                           [object_name][lookup_instructions]}
    # if a list is provided, then recursively apply the function and append to a list, which gets returned
    # as the "value" field.
    elif isinstance(lookup_value, list):
        onr_list = []
        for onr in lookup_value:
            onr_dictionary = {}
            for onr_field_name, onr_sub_object_structure in onr.items():
                onr_generator = process_complex_inputs(
                    super_dictionary=super_dictionary,
                    lookup_value=onr_sub_object_structure,
                    unique_name_input=unique_name_input,
                    reference_field_name=onr_field_name)
                for onr_yield_val in onr_generator:
                    onr_dictionary[onr_yield_val["field"]] = onr_yield_val["value"]
            onr_list.append(onr_dictionary)
        yield {"field": reference_field_name, "value": onr_list}
    else:
        print('error')
    return


def build_object_from_complex_inputs(
        yaml_object: dict,
        super_dictionary: dict,
        unique_name_input: str) -> dict:
    """
    Builds an energyplus object from a yaml object which uses complex inputs.

    :param yaml_object: template yaml object in dictionary format
    :param super_dictionary: epJSON formatted dictionary containing reference objects
    :param unique_name_input: unique name modifier
    :return: Valid epJSON key-value pair for an EnergyPlus Object - EnergyPlus Object, {field_names: field_values}
    """
    (object_type, object_constructors), = yaml_object.items()
    tmp_d = {}
    for reference_field_name, lookup_value in object_constructors.items():
        processed_inputs = process_complex_inputs(
            super_dictionary=super_dictionary,
            lookup_value=lookup_value,
            unique_name_input=unique_name_input,
            reference_field_name=reference_field_name)
        # iterate over generate and apply to a dictionary
        for pd in processed_inputs:
            tmp_d[pd["field"]] = pd["value"]
    key_val = tmp_d.pop('name')
    object_dictionary = {object_type: {key_val: tmp_d}}
    return object_dictionary


def get_option_tree(
        template_name: str,
        data: dict) -> dict:
    """
    Retrieve dictionary of alternate build instructions from yaml 'OptionTree'

    :param template_name: string value of HVACTemplate object
    :param data: yaml data in dictionary form
    :return: Dictionary of alternate build instructions
    """
    template_parse_regex = re.compile(r'HVACTemplate:(.*):(.*)', re.IGNORECASE)
    template_classes = re.match(template_parse_regex, template_name)
    # whenever getting values that you might edit later, use copy.deepcopy()
    # so a new dictionary is created; otherwise, every time you call that
    # value again the updated will be returned... even if you use .copy()
    yaml_option_tree = copy.deepcopy(data[':'.join(['OptionTree'])])
    option_tree = yaml_option_tree['HVACTemplate'][template_classes[1]][template_classes[2]]
    return option_tree


def get_action_field_names(
        action: str,
        option_tree: dict,
        template_dictionary: dict) -> typing.List[str]:
    """
    Some HVACTemplate field selections require alternative build operations to be performed from the
    base path.  This function creates a list of the field names that cause an alternative build for
    a specified action.

    :param action: 'Replace', 'Remove', or 'Insert' actions
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: Object containing the user-provided template inputs
    :return: list of field names that trigger the specified action
    """
    if option_tree.get(action):
        action_field_names = [
            field_name for field_name in template_dictionary.keys()
            if field_name in option_tree[action].keys()
        ]
    else:
        action_field_names = []
    return action_field_names


def get_all_action_field_names(
        option_tree: dict,
        template_dictionary: dict) -> dict:
    """
    Create dictionary of all actions to be performed, based on the template dictionary
    inputs and the given option_tree.

    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: Object containing the user-provided template inputs
    :return: Dictionary containing remove, replace, and insert actions
    """
    remove_field_names = get_action_field_names(
        action='RemoveElements',
        option_tree=option_tree,
        template_dictionary=template_dictionary
    )
    replace_field_names = get_action_field_names(
        action='ReplaceElements',
        option_tree=option_tree,
        template_dictionary=template_dictionary
    )
    insert_field_names = get_action_field_names(
        action='InsertElements',
        option_tree=option_tree,
        template_dictionary=template_dictionary
    )
    return {
        'remove': remove_field_names,
        'replace': replace_field_names,
        'insert': insert_field_names}


def perform_build_operations(
        connector_path: str,
        option_tree: dict,
        template_dictionary: dict,
        super_dictionary: dict,
        unique_name: str,
        input_epjson: dict,
        data: dict) -> typing.Tuple[dict, typing.List[dict]]:
    """
    Perform operations to create a build_path and create an epJSON object from that output.

    :param connector_path: fluid flow loop to follow.
    :param option_tree: Alternative build instruction object in yaml OptionTree
    :param template_dictionary: HVACTemplate user inputs
    :param super_dictionary: high level dictionary to hold epJSON objects
    :param unique_name: unique name modifier
    :param input_epjson: epJSON file containing HVACTemplate objects
    :param data: loaded Yaml file
    :return: epJSON dictionary of built objects, build path of super objects
    """
    build_path = create_build_path(
        connector_path=connector_path,
        option_tree=option_tree,
        template_dictionary=template_dictionary,
        super_dictionary=super_dictionary,
        unique_name=unique_name,
        input_epjson=input_epjson,
        data=data)
    print('BuldPath complete')
    print(build_path)
    # Build a dictionary of valid epJSON objects from build path
    object_from_path = create_epjson(
        connector_path=connector_path,
        unique_name=unique_name,
        build_path=build_path)
    super_dictionary = merge_dictionaries(
        super_dictionary=super_dictionary,
        object_dictionary=object_from_path,
        unique_name_override=True)
    # build additional objects (e.g. Controllers)
    # these are stored in the option tree under AdditionalObjects
    # for standard objects, and AdditionalTemplateObjects for
    # template triggered objects
    additional_objects = create_additional_objects(
        option_tree=option_tree,
        connector_path=connector_path,
        super_dictionary=super_dictionary,
        unique_name=unique_name,
        template_dictionary=template_dictionary,
        input_epjson=input_epjson,
        data=data)
    super_dictionary = merge_dictionaries(
        super_dictionary=super_dictionary,
        object_dictionary=additional_objects,
        unique_name_override=True)
    return super_dictionary, build_path


def create_build_path(
        connector_path: str,
        option_tree: dict,
        template_dictionary: dict,
        super_dictionary: dict,
        unique_name: str,
        input_epjson: dict,
        data: dict) -> typing.List[dict]:
    """
    Perform operations to create a build_path, which is a list of EnergyPlus
    super objects.  These super objects are dictionaries that contain two sub-keys:
      - Fields: The key-value pairs for field names and their values
      - Connectors: Information regarding the input and output nodes for each ConnectorPath,
        which is the fluid flow loop (Air, ChilledWaterLoop, HotWaterLoop).

    :param connector_path: fluid flow loop to follow.  Necessary for recursive call to perform_build_operations
    :param option_tree: yaml OptionTree
    :param template_dictionary: HVACTemplate user inputs
    :param super_dictionary: High level dictionary used for writing output. The instantiation of this objects needs
      to be outside the scope of the function due to recursive operations.
    :param unique_name: unique name modifier
    :param input_epjson: epJSON file containing HVACTemplate objects
    :param data: loaded yaml file
    :return: build_path for a chosen fluid flow loop, which is a list of super objects
    """
    # capitalize connector path
    connector_path = connector_path[0].upper() + connector_path[1:]
    selected_template = option_tree['Base']
    print('### selected template ###')
    print(selected_template)
    build_path = selected_template['BuildPath']
    # check for nested HVACTemplate objects.  They will appear as string objects with the
    # template name (e.g. HVACTemplate:Plant:Chiller).
    # if so do a recursive build on that object, insert it into the original position, and then flatten the
    # build path again.
    for idx, super_object in enumerate(build_path):
        if isinstance(super_object, str) and \
                re.match('^HVACTemplate:.*', super_object, re.IGNORECASE):
            # in this test program, we have to grab global objects, which are the yaml data and the
            # epjson object.  In production, these should be stored class attributes.
            sub_template_object = input_epjson[super_object]
            sub_build_path = None
            for sub_object_name, sub_object_dictionary in sub_template_object.items():
                sub_option_tree = get_option_tree(super_object, data)
                _, sub_build_path = perform_build_operations(
                    connector_path=connector_path,
                    option_tree=sub_option_tree,
                    template_dictionary=sub_object_dictionary,
                    super_dictionary=super_dictionary,
                    unique_name=sub_object_name,
                    input_epjson=input_epjson,
                    data=data)
            # a side effect of the recursion is that nested lists are produced
            # so we need to flatten them.
            build_path[idx] = sub_build_path
            build_path = flatten_build_path(build_path)
    actions = get_all_action_field_names(
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    print('pre-replaced element path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    # remove example
    if actions.get('remove'):
        build_path = remove_objects(
            action='remove',
            action_list=actions['remove'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path)
    print('post-removed path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    # replace example
    # At the moment, replace happens even if correct equipment in place.
    # I'm sure there is a work-around to this but for now it doesn't break anything.
    if actions.get('replace'):
        build_path = replace_objects(
            action='replace',
            action_list=actions['replace'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path)
    print('post-replaced path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    # apply base transitions.  This needs to be done before inserting optional elements.
    # If an element is inserted that is the same object type, then the transition mapping
    # would output to both objects.
    if selected_template.get('Transitions'):
        build_path = apply_transitions_to_objects(
            transition_structure=selected_template['Transitions'],
            template_dictionary=template_dictionary,
            build_path=build_path)
    print('post-transition path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    # insert example
    if actions.get('insert'):
        build_path = insert_objects(
            action='insert',
            action_list=actions['insert'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path)
    print('post-insert element path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    # insert unique name
    build_path = insert_unique_name(
        unique_name=unique_name,
        build_path=build_path
    )
    print('post-variable rename path')
    for idx, super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, super_object))
    return build_path


def get_action_structure(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict) -> typing.Generator[dict, typing.Tuple[str, dict], None]:
    """
    Create a generator that yields an object reference and structure for actions to be performed.
    The object reference may either be a string value of an object type or regular expression.  The
    option structure is the object containing the details for the action to be performed.

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: dictionary containing build path variations
    :param template_dictionary: HVACTemplate with user inputs
    :return: Iterator of [EnergyPlus object reference, action_structure]
    """
    # capitalize action
    action = action[0].upper() + action[1:]
    for field_name in action_list:
        # get the action subtree
        if option_tree[''.join([action, 'Elements'])].get(field_name) and \
                option_tree[''.join([action, 'Elements'])][field_name].get(template_dictionary[field_name]):
            option_references = \
                option_tree[''.join([action, 'Elements'])][field_name][template_dictionary[field_name]]
            # for each option reference in the list, yield the object_type (can be regex) and dictionary of
            # option instructions
            for option_reference in option_references:
                for object_type, option_structure in option_reference.items():
                    yield object_type, option_structure
    return


def remove_objects(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict,
        build_path: typing.List[dict]) -> typing.List[dict]:
    """
    Remove object in a build path using alternate build instructions

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: dictionary containing build path variations
    :param template_dictionary: HVACTemplate with user inputs
    :param build_path: list of EnergyPlus super objects in build order
    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for object_type_reference, option_structure in object_references:
        count_matches = 0
        # If 'Occurrence' is specified, then only replace when that occurrence happens.
        occurrence = option_structure.get('Occurrence', 1)
        for idx, super_object in enumerate(build_path):
            for object_type in super_object.keys():
                if re.match(object_type_reference, object_type, re.IGNORECASE):
                    count_matches += 1
                    if count_matches == occurrence:
                        build_path.pop(idx)
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= occurrence:
            print('error')
            print('replace error')
            sys.exit()
    return build_path


def replace_objects(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict,
        build_path: typing.List[dict]) -> typing.List[dict]:
    """
    Replace object in a flattened path using alternate build instructions

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: dictionary containing build path variations
    :param template_dictionary: HVACTemplate with user inputs
    :param build_path: list of EnergyPlus super objects in build order
    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for object_type_reference, option_structure in object_references:
        count_matches = 0
        # If 'Occurrence' is specified, then only replace when that occurrence happens.
        occurrence = option_structure.get('Occurrence', 1)
        for idx, super_object in enumerate(build_path):
            for object_type in super_object.keys():
                if re.match(object_type_reference, object_type, re.IGNORECASE):
                    count_matches += 1
                    if count_matches == occurrence:
                        # get object from template
                        new_object = copy.deepcopy(
                            option_structure['Object'])
                        # rename fields
                        replacement = option_structure.get('FieldNameReplacement')
                        # rename if applicable
                        new_object = replace_values(
                            new_object,
                            replacement)
                        # replace old object with new
                        build_path[idx] = new_object
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= occurrence:
            print('error')
            print('replace error')
            sys.exit()
    return build_path


def apply_transitions_to_objects(
        transition_structure: dict,
        template_dictionary: dict,
        build_path: typing.Union[dict, typing.List[dict]]) -> typing.Union[dict, typing.List[dict]]:
    """
    Transfer user input data from HVACTemplate object to the objects in the build path.
    If a dictionary is passed, return a dictionary.  Otherwise return a list.

    :param transition_structure: transition key-value pairs for passing user input data
    :param template_dictionary: user-inputs in HVACTemplate object
    :param build_path: list of EnergyPlus super objects in build order

    :return: build_path with template input data transferred to objects
    """
    if isinstance(build_path, dict):
        as_object = True
        build_path = [build_path, ]
    else:
        as_object = False
    for transition_field_name, value_reference in transition_structure.items():
        print(value_reference)
        for reference_object_type, field_name in value_reference.items():
            for super_object in build_path:
                for object_type in super_object:
                    if re.match(reference_object_type, object_type, re.IGNORECASE):
                        if not super_object[object_type]['Fields'].get(field_name):
                            super_object[object_type]['Fields'][field_name] = None
                        super_object[object_type]['Fields'][field_name] = \
                            template_dictionary[transition_field_name]
    if as_object:
        return build_path[0]
    else:
        return build_path


def insert_objects(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict,
        build_path: typing.List[dict]) -> typing.List[dict]:
    """
    Insert object in a build path using alternate build instructions

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: dictionary containing build path variations
    :param template_dictionary: HVACTemplate with user inputs
    :param build_path: list of EnergyPlus super objects in build order
    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for object_reference, option_structure in object_references:
        # iterate over regex matches and do operations when the right occurrence happens
        count_matches = 0
        # If 'Occurrence' is specified, then only replace when that occurrence happens.
        occurrence = option_structure.get('Occurrence', 1)
        for idx, super_object in enumerate(build_path):
            for object_type in super_object.keys():
                if re.match(object_reference, object_type, re.IGNORECASE):
                    count_matches += 1
                    if count_matches == occurrence:
                        # Look for 'BeforeObject' the 'After'.
                        object_location_offset = option_structure['Location']
                        insert_offset = None
                        if object_location_offset.lower() == 'after"':
                            insert_offset = 1
                        elif not insert_offset and object_location_offset.lower() == 'before':
                            insert_offset = 0
                        else:
                            print("error")
                            print("insert location error")
                            sys.exit()
                        insert_location = idx + insert_offset
                        # get object to be inserted from yaml option tree
                        new_object = copy.deepcopy(
                            option_structure['Object']
                        )
                        # get rename format
                        replacement = (
                            option_structure.get('FieldNameReplacement')
                        )
                        # rename if possible
                        new_object = replace_values(
                            new_object,
                            replacement
                        )
                        # apply specific transitions
                        transition_structure = option_structure.pop('Transitions', None)
                        if transition_structure:
                            for sub_object_type, sub_object_structure in new_object.items():
                                for sub_object_name, sub_object_fields in sub_object_structure.items():
                                    # This is similar to the additional object method of inserting transitions
                                    # however, the object here is a super object, not an additional object, so it
                                    # has an extra level of Fields/Connectors.
                                    # it could be refactored with an optional flag
                                    if sub_object_name.lower() == 'fields':
                                        for sub_template_field, object_field in transition_structure.items():
                                            new_object[sub_object_type][sub_object_name][object_field] = \
                                                template_dictionary[sub_template_field]
                        build_path.insert(
                            insert_location,
                            new_object)
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= occurrence:
            print('error')
            print('insert error')
            sys.exit()
    return build_path


def insert_unique_name(
        unique_name: str,
        build_path: typing.Union[dict, typing.List[dict]]) -> typing.Union[dict, typing.List[dict]]:
    """
    Insert a unique names string into field values where the format symbol '{}' is present.
    If a dictionary is passed, return a dictionary.  Otherwise return a list.

    :param unique_name: Unique name to be applied to string fields
    :param build_path: list of EnergyPlus super objects in build order

    :return: build_path of same structure with string fields formatted to have unique names
    """
    if isinstance(build_path, dict):
        as_object = True
        build_path = [build_path, ]
    else:
        as_object = False
    for super_object in build_path:
        for object_type, object_constructors in super_object.items():
            for field_name, field_value in object_constructors['Fields'].items():
                if isinstance(field_value, str):
                    super_object[object_type]['Fields'][field_name] = \
                        field_value.format(unique_name)
    if as_object:
        return build_path[0]
    else:
        return build_path


def create_epjson(
        connector_path: str,
        unique_name: str,
        build_path: typing.Union[dict, typing.List[dict]]) -> dict:
    """
    Build epJSON formatted dictionary of EnergyPlus objects from super objects.

    :param connector_path: Fluid flow to follow in build path.
        i.e. Air, HotWater, ChilledWater, or MixedWater connectors.
    :param unique_name: unique name modifier
    :param build_path: list of EnergyPlus super objects in build order
    :return: epJSON formatted dictionary
    """
    # if one super_object is passed, wrap a list around it to make it a build_path
    if isinstance(build_path, dict):
        build_path = [build_path, ]
    out_node_name = None
    object_dictionary = {}
    for idx, super_object in enumerate(build_path):
        # store object key and make sure not in list as you iterate:
        unique_object_names = []
        for object_type, object_constructors in super_object.items():
            # use copy so that the original structure is preserved for future queries
            tmp_d = copy.deepcopy(object_constructors['Fields'])
            object_name = tmp_d.pop('name')
            # not necessary but it's a good reminder that this object is the target value
            object_values = tmp_d
            # create the object type if it doesn't exist
            if not object_dictionary.get(object_type):
                object_dictionary[object_type] = {}
            # for the first object, do not alter the input node name.
            # for subsequent objects, set the input node name value to the
            # output node name value of the previous object.
            # also check for duplicates
            if object_name in unique_object_names:
                print('non-unique object error')
                sys.exit()
            unique_object_names.append(object_name)
            if object_constructors.get('Connectors'):
                # An id in the build path can actually have N objects; however, only one should be
                # used to connect the nodes along a build path.  Therefore, all objects except one should
                # have a variable 'UseInBuildPath' set to False.  check for that here.  If that is the case,
                # then just write out the object to the epjson dictionary and do not do any connections.
                if object_constructors['Connectors'][connector_path].get('UseInBuildPath', True):
                    if idx == 0:
                        object_dictionary[object_type][object_name] = object_values
                        out_node = object_constructors['Connectors'][connector_path]['Outlet']
                        if isinstance(out_node, str) and '{}' in out_node:
                            out_node_name = out_node.format(unique_name)
                        else:
                            out_node_name = (
                                object_constructors['Fields']
                                [object_constructors['Connectors'][connector_path]['Outlet']]
                            )
                    else:
                        object_values[
                            object_constructors['Connectors'][connector_path]['Inlet']
                        ] = out_node_name
                        object_dictionary[object_type][object_name] = object_values
                        out_node = object_constructors['Connectors'][connector_path]['Outlet']
                        if isinstance(out_node, str) and '{}' in out_node:
                            out_node_name = out_node.format(unique_name)
                        else:
                            out_node_name = (
                                object_constructors['Fields']
                                [object_constructors['Connectors'][connector_path]['Outlet']]
                            )
                else:
                    object_dictionary[object_type][object_name] = object_values
            else:
                object_dictionary[object_type][object_name] = object_values
    return object_dictionary


def create_additional_objects(
        super_dictionary: dict,
        option_tree: dict,
        connector_path: str,
        unique_name: str,
        template_dictionary: dict,
        input_epjson: dict,
        data: dict) -> dict:
    """
    Convert additional objects from yaml OptionTree into epJSON objects.

    :param super_dictionary: epJSON dictionary of EnergyPlus objects
    :param option_tree: dictionary containing build path variations
    :param connector_path: fluid flow path to follow
    :param unique_name: unique name modifier
    :param template_dictionary: HVACTemplate user inputs
    :param input_epjson: epJSON file containing HVACTemplate objects
    :param data: loaded yaml object
    :return: epJSON dictionary of created additional objects
    """
    object_dictionary = {}
    # iterate over AdditionalObjects and process
    if option_tree.get('AdditionalObjects'):
        for new_object_structure in option_tree['AdditionalObjects']:
            for object_or_template, object_structure in new_object_structure.items():
                # check for 'Transitions' structure and pop it if present
                transition_structure = object_structure.pop('Transitions', None)
                # when you need the current objects being built included into the
                # super dictionary, you can quickly append them with d_new = dict(d_super, **d_current)
                # it is done here because some AdditionalObjects need to reference nodes of other AdditionalObjects
                # via complex inputs
                sub_object_dictionary = process_additional_object_input(
                    object_or_template=object_or_template,
                    object_structure=object_structure,
                    connector_path=connector_path,
                    super_dictionary=dict(super_dictionary, **object_dictionary),
                    unique_name=unique_name,
                    input_epjson=input_epjson,
                    data=data)
                # apply transition fields
                if transition_structure:
                    for sub_object_type, sub_object_structure in sub_object_dictionary.items():
                        tmp_d = {}
                        for sub_object_name, sub_object_fields in sub_object_structure.items():
                            # apply all base fields and values to object before transition
                            for field, value in sub_object_fields.items():
                                tmp_d[field] = value
                            # overwrite, or add, fields and values to object
                            for sub_template_field, object_field in transition_structure.items():
                                if template_dictionary.get(sub_template_field):
                                    tmp_d[object_field] = template_dictionary[sub_template_field]
                            sub_object_dictionary[sub_object_type][sub_object_name] = tmp_d
                object_dictionary = merge_dictionaries(
                    super_dictionary=object_dictionary,
                    object_dictionary=sub_object_dictionary,
                    unique_name_override=True)
    # process additional template objects
    if option_tree.get('AdditionalTemplateObjects'):
        for template_field, template_structure in option_tree['AdditionalTemplateObjects'].items():
            for template_option, add_object_structure in template_structure.items():
                # check the option that triggers the object to be created.
                # If a default option is specified (e.g. the field is left blank),
                # then a comparison of None for that template object and
                # "None" is performed.
                if (not template_dictionary.get(template_field) and template_option == "None") or \
                        (template_dictionary.get(template_field, None) and re.match(
                            template_option,
                            template_dictionary[template_field])):
                    for new_object_structure in add_object_structure:
                        for object_or_template, object_structure in new_object_structure.items():
                            # check for transitions and pop them if present
                            transition_structure = object_structure.pop('Transitions', None)
                            sub_object_dictionary = process_additional_object_input(
                                object_or_template=object_or_template,
                                object_structure=object_structure,
                                connector_path=connector_path,
                                super_dictionary=dict(super_dictionary, **object_dictionary),
                                unique_name=unique_name,
                                input_epjson=input_epjson,
                                data=data)
                            # apply transition fields
                            if transition_structure:
                                for sub_object_type, sub_object_structure in sub_object_dictionary.items():
                                    tmp_d = {}
                                    for sub_object_name, sub_object_fields in sub_object_structure.items():
                                        # apply all base fields and values to object before transition
                                        for field, value in sub_object_fields.items():
                                            tmp_d[field] = value
                                        # overwrite, or add, fields and values to object
                                        for sub_template_field, object_field in transition_structure.items():
                                            if template_dictionary.get(sub_template_field):
                                                tmp_d[object_field] = template_dictionary[sub_template_field]
                                        sub_object_dictionary[sub_object_type][sub_object_name] = tmp_d
                            object_dictionary = merge_dictionaries(
                                super_dictionary=object_dictionary,
                                object_dictionary=sub_object_dictionary,
                                unique_name_override=True)
    return object_dictionary


def process_additional_object_input(
        object_or_template,
        object_structure,
        connector_path,
        super_dictionary,
        unique_name,
        input_epjson,
        data):
    """
    Perform operations to convert instructions from a yaml 'additional object' into epJSON object.

    :param object_or_template: key value of instruction.  It is either an EnergyPlus object (regex alowed) or a
        reference to an HVACTemplate.
    :param object_structure: structure of passed instructions
    :param connector_path: fluid flow path to follow
    :param super_dictionary: high level dictionary containing epJSON objects from the build path
    :param unique_name: unique name modifier
    :param input_epjson: epJSON file containing HVACTemplate objects
    :param data: loaded yaml objects
    :return: epJSON formatted dictionary
    """
    object_dictionary = {}
    # check if additional object iterator is a energyplus object key or an HVACTemplate object key.
    if not object_or_template.startswith('HVACTemplate'):
        additional_object = {object_or_template: object_structure}
        for additional_sub_object, additional_sub_object_fields in additional_object.items():
            sub_additional_object_dictionary = build_object_from_complex_inputs(
                super_dictionary=super_dictionary,
                yaml_object={additional_sub_object: copy.deepcopy(additional_sub_object_fields)},
                unique_name_input=unique_name)
            object_dictionary = merge_dictionaries(
                super_dictionary=object_dictionary,
                object_dictionary=sub_additional_object_dictionary,
                unique_name_override=False
            )
    # if the object is just a string, it should be for an HVACTemplate OptionTree build.
    # The key is the unique name modifier
    elif object_or_template.startswith('HVACTemplate'):
        sub_template_object = input_epjson.get(object_or_template)
        # in this test program, we have to grab global objects, which are the yaml data and the
        # epjson object.  In production, these should be stored class attributes.
        # Also, some internal yaml templates are not accessible via EnergyPlus, so they will not have
        # a template input
        sub_option_tree = get_option_tree(object_or_template, data)
        if isinstance(sub_template_object, dict):
            # todo_eo: It is unclear if this section is necessary.
            # It does not appear this code is ever used.  It appears that
            # when additional objects are called, an associated HVACTemplate is not usually specified.
            # This code is left here in case that situation occurs, but additional debugging might be necessary.
            for sub_object_name, sub_template_dictionary in sub_template_object.items():
                sub_object_dictionary, _ = perform_build_operations(
                    connector_path=object_structure.get('ConnectorPath', connector_path),
                    option_tree=sub_option_tree,
                    template_dictionary=sub_template_dictionary,
                    super_dictionary=super_dictionary,
                    unique_name=object_structure['UniqueName'],
                    input_epjson=input_epjson,
                    data=data)
                object_dictionary = merge_dictionaries(
                    super_dictionary=object_dictionary,
                    object_dictionary=sub_object_dictionary,
                    unique_name_override=False
                )
        else:
            # if a template was not found for the nested HVACTemplate object, then process with a blank
            # template object.
            # for now, just specify the connector_path.  Will have to make a mapping dictionary later
            sub_object_dictionary, _ = perform_build_operations(
                connector_path=object_structure.get('ConnectorPath', connector_path),
                option_tree=sub_option_tree,
                template_dictionary={},
                super_dictionary=super_dictionary,
                unique_name=object_structure['UniqueName'],
                input_epjson=input_epjson,
                data=data)
            object_dictionary = merge_dictionaries(
                super_dictionary=object_dictionary,
                object_dictionary=sub_object_dictionary,
                unique_name_override=False)
    else:
        print('value was not additional object key nor an HVACTemplate string')
        sys.exit()
    return object_dictionary


def build_compact_schedule(
        data: dict,
        schedule_type: str,
        insert_values: typing.Union[int, str, list]) -> dict:
    """
    Create compact schedule from specified yaml object and value

    :param data: loaded yaml object
    :param schedule_type: string value identifying schedule template
    :param insert_values: list of values to insert in template
    :return: epJSON formatted schedule object
    """
    if not isinstance(insert_values, list):
        insert_values = [insert_values, ]
    schedule_object = {'Schedule:Compact': {}}
    always_temperature_object = copy.deepcopy(data['Schedule']['Compact'][schedule_type])
    # for each element in the schedule, convert to numeric if value replacement occurs
    formatted_data_lines = [
        float(i.format(*insert_values))
        if re.match(r'.*{.*}', i, re.IGNORECASE) else i
        for i in always_temperature_object['data']]
    schedule_object['Schedule:Compact'][always_temperature_object['name'].format(insert_values[0])] = \
        formatted_data_lines
    return schedule_object


def create_thermostats(
        template_dictionary: dict,
        thermostat_name: str,
        data: dict) -> dict:
    """
    Create thermostat objects and associated equipment

    :param template_dictionary: HVACTemplate dictionary of user inputs
    :param thermostat_name: unique name of thermostat object
    :param data: loaded yaml object
    :return: dictionary of epJSON objects containing original super_dictionary objects and epJSON objects.
    """
    object_dictionary = {}
    # Do simple if-else statements to find the right thermostat type, then write it to an object dictionary.
    # it's easier to just construct thermostats from if-else statements than to build an alternate
    # yaml hierarchy.
    thermostat_options_object = {
        'heating_schedule': template_dictionary.get('heating_setpoint_schedule_name'),
        'constant_heating_setpoint': template_dictionary.get('constant_heating_setpoint'),
        'cooling_schedule': template_dictionary.get('cooling_setpoint_schedule_name'),
        'constant_cooling_setpoint': template_dictionary.get('constant_cooling_setpoint')
    }
    schedule_objects = []
    for thermostat_type in ['heating', 'cooling']:
        # build constant setpoints into schedule.  make error if both type specified:
        if thermostat_options_object.get('constant_{}_setpoint'.format(thermostat_type)):
            if not thermostat_options_object.get('{}_schedule'.format(thermostat_type)):
                # create thermostat schedules and save them to temporary dictionaries
                schedule_object = build_compact_schedule(
                    data=data,
                    schedule_type='ALWAYS_VAL',
                    insert_values=template_dictionary['constant_{}_setpoint'.format(thermostat_type)]
                )
                schedule_objects.append(schedule_object)
                # apply new schedule to the thermostat object
                thermostat_options_object['{}_schedule'.format(thermostat_type)] = \
                    'ALWAYS_{}'.format(thermostat_options_object['constant_{}_setpoint'.format(thermostat_type)])
            else:
                print('schedule error')
                sys.exit()
    # create thermostat object type based on which inputs were provided.
    thermostat_object = {}
    if thermostat_options_object.get('heating_schedule') and \
            thermostat_options_object.get('cooling_schedule'):
        thermostat_object['ThermostatSetpoint:DualSetpoint'] = {}
        thermostat_object['ThermostatSetpoint:DualSetpoint'][thermostat_name] = {}
        thermostat_object['ThermostatSetpoint:DualSetpoint'][thermostat_name][
            'heating_setpoint_temperature_schedule_name'] = \
            thermostat_options_object['heating_schedule']
        thermostat_object['ThermostatSetpoint:DualSetpoint'][thermostat_name][
            'cooling_setpoint_temperature_schedule_name'] = \
            thermostat_options_object['cooling_schedule']
    elif thermostat_options_object.get('heating_schedule') and not \
            thermostat_options_object.get('cooling_schedule'):
        thermostat_object['ThermostatSetpoint:SingleHeating'] = {}
        thermostat_object['ThermostatSetpoint:SingleHeating'][thermostat_name] = {}
        thermostat_object['ThermostatSetpoint:SingleHeating'][thermostat_name][
            'setpoint_temperature_schedule_name'] = \
            thermostat_options_object['heating_schedule']
    elif not thermostat_options_object.get('heating_schedule') and \
            thermostat_options_object.get('cooling_schedule'):
        thermostat_object['ThermostatSetpoint:SingleCooling'] = {}
        thermostat_object['ThermostatSetpoint:SingleCooling'][thermostat_name] = {}
        thermostat_object['ThermostatSetpoint:SingleCooling'][thermostat_name][
            'setpoint_temperature_schedule_name'] = \
            thermostat_options_object['cooling_schedule']
    else:
        print('thermostat error')
        sys.exit()
    # update super dictionary with new objects
    for so in schedule_objects:
        object_dictionary = merge_dictionaries(
            super_dictionary=object_dictionary,
            object_dictionary=so
        )
    object_dictionary = merge_dictionaries(
        super_dictionary=object_dictionary,
        object_dictionary=thermostat_object)
    return object_dictionary


def modify_zone_control_thermostats(
        super_dictionary: dict,
        data: dict):
    """
    Edit ZoneControl:Thermostat objects with information present within the super_dictionary of epJSON obects.

    :param super_dictionary: high level dictionary of epJSON objects
    :param data: loaded yaml object
    :return: modified epJSON objects from super dictionary
    """
    object_dictionary = {}
    # find ZoneControlThermostats with each thermostat name and update fields
    # get thermostat name
    tmp_schedule_dictionary = {}
    tmp_modified_object_dictionary = {}
    for object_type, object_structure in super_dictionary.items():
        if object_type.lower() == 'zonecontrol:thermostat':
            for object_name, object_fields in object_structure.items():
                thermostat_name = object_structure[object_name]['control_1_name']
                # get thermostat type
                thermostats = {
                    i: j for i, j
                    in super_dictionary.items()
                    if re.match(r'^ThermostatSetpoint', i, re.IGNORECASE)}
                # iterate over thermostats looking for a name match
                for thermostat_type, thermostat_structure in thermostats.items():
                    for thermostat_search_name, thermostat_search_fields in thermostat_structure.items():
                        # after a match is found, create an always available schedule and update the object
                        # fields for the ZoneControl:Thermostat.  Save these as temp dictionaries to avoid
                        # updating a dictionary while iterating through itself.
                        if thermostat_search_name.lower() == thermostat_name.lower():
                            if re.match(r'.*SingleHeating$', thermostat_type, re.IGNORECASE):
                                control_schedule = build_compact_schedule(
                                    data=data,
                                    schedule_type='ALWAYS_VAL',
                                    insert_values=1
                                )
                            elif re.match(r'.*SingleCooling$', thermostat_type, re.IGNORECASE):
                                control_schedule = build_compact_schedule(
                                    data=data,
                                    schedule_type='ALWAYS_VAL',
                                    insert_values=2
                                )
                            elif re.match(r'.*DualSetpoint$', thermostat_type, re.IGNORECASE):
                                control_schedule = build_compact_schedule(
                                    data=data,
                                    schedule_type='ALWAYS_VAL',
                                    insert_values=4
                                )
                            else:
                                print('thermostat schedule error')
                                sys.exit()
                            # populate new object fields and add to temporary dictionaries
                            (control_schedule_type, control_schedule_structure), = control_schedule.items()
                            tmp_schedule_dictionary[control_schedule_type] = control_schedule_structure
                            (control_schedule_name, _), = control_schedule_structure.items()
                            # copy of super dictionary is necessary in case any transitions or other
                            # default values were applied to the objects before this process.
                            if not tmp_modified_object_dictionary.get(object_type):
                                tmp_modified_object_dictionary[object_type] = {object_name: {}}
                            if not tmp_modified_object_dictionary[object_type].get(object_name):
                                tmp_modified_object_dictionary[object_type][object_name] = {}
                            if super_dictionary.get(object_type):
                                if super_dictionary[object_type].get(object_name):
                                    tmp_modified_object_dictionary[object_type][object_name] = \
                                        copy.deepcopy(super_dictionary[object_type][object_name])
                            tmp_modified_object_dictionary[object_type][object_name]['control_1_object_type'] = \
                                thermostat_type
                            tmp_modified_object_dictionary[object_type][object_name]['control_type_schedule_name'] = \
                                control_schedule_name
    # update super dictionary with new objects
    object_dictionary = merge_dictionaries(
        super_dictionary=object_dictionary,
        object_dictionary=tmp_schedule_dictionary
    )
    object_dictionary = merge_dictionaries(
        super_dictionary=object_dictionary,
        object_dictionary=tmp_modified_object_dictionary
    )
    return object_dictionary


def create_branches(
        build_path: typing.List[dict],
        unique_name: str,
        connectors_to_build: tuple = ('Air', 'ChilledWaterLoop', 'HotWaterLoop', 'CondenserWaterLoop')):
    """
    Build branches from build_paths

    :param build_path: path of objects along a fluid flow
    :param unique_name: unique name modifier
    :param connectors_to_build: fluid flows to track
    :return: Two items:
        - dictionary of epJSON objects containing original object_dictionary objects plus new objects.
        - dictionary of demand-side coils in each water type fluid flow path (e.g. ChilledWaterLoop).
    """
    object_dictionary = {}
    # collect all connector path keys to use as the key for each branch iteration
    if not object_dictionary.get('BranchList'):
        object_dictionary['BranchList'] = {}
    if not object_dictionary.get('Branch'):
        object_dictionary['Branch'] = {}
    demand_chilled_water_objects = []
    demand_hot_water_objects = []
    demand_mixed_water_objects = []
    connectors_list = []
    for build_object in build_path:
        for super_object in build_object.values():
            connector_object = super_object.get('Connectors')
            if connector_object:
                for connector_type in connector_object.keys():
                    connectors_list.append(connector_type)
    connectors_set = set(connectors_to_build).intersection(set(connectors_list))
    # iterate over build path for each connector type and build the branch
    for connector_type in connectors_set:
        if connector_type.capitalize() == 'Air':
            component_list = []
            for build_object in build_path:
                for object_type, super_object in build_object.items():
                    # do I need to run a check that consecutive objects have inlet/outlet nodes?
                    connector_object = super_object.get('Connectors')
                    if connector_object:
                        object_connector = connector_object.get(connector_type)
                        if object_connector:
                            component_dictionary = {
                                'component_object_type': object_type,
                                'component_object_name': super_object['Fields']['name'],
                                'component_inlet_node_name': super_object['Fields'][object_connector['Inlet']],
                                'component_outlet_node_name': super_object['Fields'][object_connector['Outlet']]}
                            component_list.append(component_dictionary)
            object_dictionary["Branch"][' '.join([unique_name, connector_type, 'Branch'])] = component_list
            object_dictionary["BranchList"][' '.join([unique_name, connector_type, 'Branches'])] =  \
                {"branches": [{"branch_name": ' '.join([unique_name, connector_type, 'Branch'])}]}
        else:
            for build_object in build_path:
                for object_type, super_object in build_object.items():
                    # only retrieve demand-side water coils or air loop objects.  Supply side water loopp
                    # branches are created in the additional objects fields of the templates
                    if re.match('^Coil.*', object_type, re.IGNORECASE):
                        # do I need to run a check that consecutive objects have inlet/outlet nodes?
                        connector_object = super_object.get('Connectors')
                        if connector_object:
                            object_connector = connector_object.get(connector_type)
                            if object_connector:
                                object_dictionary["Branch"][' '.join([super_object['Fields']['name'], 'Branch'])] = {
                                    'component_object_type': object_type,
                                    'component_object_name': super_object['Fields']['name'],
                                    'component_inlet_node_name': super_object['Fields'][object_connector['Inlet']],
                                    'component_outlet_node_name': super_object['Fields'][object_connector['Outlet']]}
                        # build demand branch list
                        if re.match('^Coil:Cooling:Water.*', object_type, re.IGNORECASE):
                            demand_chilled_water_objects.append(' '.join([super_object['Fields']['name'], 'Branch']))
                        elif re.match('^Coil:Heating:Water.*|^ZoneHVAC:Baseboard.*Water', object_type, re.IGNORECASE):
                            demand_hot_water_objects.append(' '.join([super_object['Fields']['name'], 'Branch']))
                        elif re.match('^Coil:.*HeatPump.*', object_type, re.IGNORECASE):
                            demand_mixed_water_objects.append(' '.join([super_object['Fields']['name'], 'Branch']))
    demand_dictionary = {
        "DemandChilledWater": demand_chilled_water_objects,
        "DemandHotWater": demand_hot_water_objects,
        "DemandMixedWater": demand_mixed_water_objects}
    return object_dictionary, demand_dictionary


def create_controller_list(
        object_dictionary,
        unique_name):
    controller_list_dictionary = {'AirLoopHVAC:ControllerList': {}}
    for object_type, objects in object_dictionary.items():
        if object_type == 'Controller:WaterCoil':
            controller_name = '{} Controllers'.format(unique_name)
        elif object_type == 'Controller:OutdoorAir':
            controller_name = '{} OA Controllers'.format(unique_name)
        else:
            continue
        if not controller_list_dictionary.get(controller_name):
            controller_list_dictionary['AirLoopHVAC:ControllerList'][controller_name] = {}
        object_count = 1
        for object_name in objects:
            controller_list_dictionary['AirLoopHVAC:ControllerList'][controller_name][
                'controller_{}_name'.format(object_count)] = object_name
            controller_list_dictionary['AirLoopHVAC:ControllerList'][controller_name][
                'controller_{}_object_type'.format(object_count)] = object_type
            object_count += 1
    return controller_list_dictionary


def create_oa_equipment_list(
        build_path,
        unique_name):
    # build AirLoopOutdoorAirSystemEquipmentList
    oa_equipment_list_dictionary = {'AirLoopHVAC:OutdoorAirSystem:EquipmentList': {}}
    object_count = 1
    stop_loop = False
    for super_object in build_path:
        for object_type, object_constructor in super_object.items():
            if stop_loop:
                continue
            oa_equipment_list_dictionary['AirLoopHVAC:OutdoorAirSystem:EquipmentList'][
                '{} OA System Equipment'.format(unique_name)] = {}
            oa_equipment_list_dictionary['AirLoopHVAC:OutdoorAirSystem:EquipmentList'][
                '{} OA System Equipment'.format(unique_name)][
                'component_{}_object_type'.format(object_count)] = \
                object_type
            oa_equipment_list_dictionary['AirLoopHVAC:OutdoorAirSystem:EquipmentList'][
                '{} OA System Equipment'.format(unique_name)][
                'component_{}_object_name'.format(object_count)] = \
                object_constructor['Fields']['name']
            if object_type == 'OutdoorAir:Mixer':
                stop_loop = True
        object_count += 1
    return oa_equipment_list_dictionary


def create_static_system_objects(
        super_dictionary,
        data,
        unique_name):
    static_objects = {}
    for yaml_base_object in [
        data['AirLoopHVAC']['OutdoorAirSystem']['Base'],
        # data['AirLoopHVAC']['Base']
    ]:
        yaml_copy = copy.deepcopy(yaml_base_object)
        additional_object = build_object_from_complex_inputs(
            yaml_object=yaml_copy,
            super_dictionary=super_dictionary,
            unique_name_input=unique_name
        )
        static_objects = merge_dictionaries(
            super_dictionary=static_objects,
            object_dictionary=additional_object,
            unique_name_override=False
        )
    return static_objects

# In this process note one import aspect. Specific field names are
# rarely used, if at all.  Most of the structure comes from the yaml
# object, which means that very little (comparatively)
# python code will need to be rewritten, i.e. this chunk should work for
# (hopefully) all HVACTemplate:System objects.  Possibly, most of the code
# could be reused for zone and water loop templates as well.


def main(input_args):
    with open(input_args.epjson_file, 'r') as f:
        test_data = f.read()
    test_epjson = json.loads(test_data)
    with open(input_args.yaml_file, 'r') as f:
        # get yaml data
        data = yaml.load(f, Loader=yaml.FullLoader)
        # extract system template objects from epJSON
        system_templates = [i for i in test_epjson if i.startswith('HVACTemplate:System')]
        # save outputs to dictionary
        system_dictionary = {}
        # iterate over templates
        for st in system_templates:
            # continue
            # get template object as dictionary
            hvac_system_template_obj = test_epjson[st]
            system_build_paths = []
            system_unique_names = []
            for system_name, system_template_dictionary in hvac_system_template_obj.items():
                print('System Name')
                print(system_name)
                option_tree = get_option_tree(st, data)
                sub_system_dictionary, system_build_path = perform_build_operations(
                    connector_path='Air',
                    option_tree=option_tree,
                    template_dictionary=system_template_dictionary,
                    super_dictionary={},
                    unique_name=system_name,
                    input_epjson=test_epjson,
                    data=data)
                system_dictionary[system_name] = sub_system_dictionary
                system_build_paths.append(system_build_path)
                system_unique_names.append(system_name)
                pprint(sub_system_dictionary, width=150)
                # build AirLoopHVACControllerList by looping through controllers in each system
                system_controller_list_dictionary = create_controller_list(
                    object_dictionary=sub_system_dictionary,
                    unique_name=system_name
                )
                system_oa_equipment_list_dictionary = create_oa_equipment_list(
                    build_path=system_build_path,
                    unique_name=system_name
                )
                for additional_dictionary in [system_controller_list_dictionary, system_oa_equipment_list_dictionary]:
                    system_dictionary[system_name] = merge_dictionaries(
                        super_dictionary=system_dictionary[system_name],
                        object_dictionary=additional_dictionary,
                        unique_name_override=False
                    )
                static_objects = create_static_system_objects(
                    super_dictionary=system_dictionary[system_name],
                    data=data,
                    unique_name=system_name)
                system_dictionary[system_name] = merge_dictionaries(
                    super_dictionary=system_dictionary[system_name],
                    object_dictionary=static_objects,
                    unique_name_override=False
                )
        print('Energyplus epJSON objects')
        pprint(system_dictionary, width=150)
        # do zone builds in scope of the system build.  In production, these will be separate or child classes that
        # get system information when necessary.
        zone_templates = [i for i in test_epjson if i.startswith('HVACTemplate:Zone')]
        # save outputs to dictionary
        zone_dictionary = {}
        # iterate over templates
        zone_build_paths = []
        zone_unique_names = []
        print('##### Zone Template Output #####')
        for zt in zone_templates:
            # get template object as dictionary
            hvac_zone_template_obj = test_epjson[zt]
            for template_zone_name, zone_template_dictionary in hvac_zone_template_obj.items():
                # continue
                print('##### New Zone Template #####')
                print('Zone Name')
                print(template_zone_name)
                option_tree = get_option_tree(zt, data)
                sub_zone_dictionary, zone_build_path = perform_build_operations(
                    connector_path='Air',
                    option_tree=option_tree,
                    template_dictionary=zone_template_dictionary,
                    super_dictionary={},
                    unique_name=zone_template_dictionary["zone_name"],
                    input_epjson=test_epjson,
                    data=data)
                zone_dictionary[template_zone_name] = sub_zone_dictionary
                zone_build_paths.append(zone_build_path)
                zone_unique_names.append(zone_template_dictionary["zone_name"])
        print('zone object list')
        pprint(zone_dictionary, width=150)
        # sys.exit()
        # build AirLoopHVAC splitters and paths
        # print('##### New AirLoopHVAC Objects ######')
        # for system_name, system_template_dictionary in hvac_system_template_obj.items():
        #     for template_zone_name, zone_template_dictionary in hvac_zone_template_obj.items():
        #         if system_name == zone_template_dictionary['template_vav_system_name']:
        #             print(template_zone_name)
        # sys.exit()
        # plant system loop build
        plant_templates = [i for i in test_epjson if re.match('HVACTemplate:Plant:.*Loop', i, re.IGNORECASE)]
        # save outputs to dictionary
        plant_dictionary = {}
        plant_build_paths = []
        plant_unique_names = []
        for pt in plant_templates:
            hvac_plant_template_obj = test_epjson[pt]
            for template_plant_name, plant_template_dictionary in hvac_plant_template_obj.items():
                print('##### New Plant Template #####')
                print('Plant Name')
                print(template_plant_name)
                connector_path_rgx = re.match(r'^HVACTemplate:Plant:(.*)', pt, re.IGNORECASE)
                option_tree = get_option_tree(pt, data)
                sub_plant_dictionary, plant_build_path = perform_build_operations(
                    connector_path=connector_path_rgx.group(1),
                    option_tree=option_tree,
                    template_dictionary=plant_template_dictionary,
                    super_dictionary={},
                    unique_name=connector_path_rgx.group(1),
                    input_epjson=test_epjson,
                    data=data)
                plant_dictionary[template_plant_name] = sub_plant_dictionary
                plant_build_paths.append(plant_build_path)
                plant_unique_names.append(template_plant_name)
        pprint(plant_dictionary, width=150)
        # sys.exit()
        print('##### New Plant Template Output #####')
        pprint(plant_dictionary, width=150)
        # Collect all template objects to one epjson object for further processing
        epjson_dictionary = {}
        for template_dictionary in [
                system_dictionary,
                zone_dictionary,
                plant_dictionary]:
            for template_name, epjson_object in template_dictionary.items():
                epjson_dictionary = merge_dictionaries(
                    super_dictionary=epjson_dictionary,
                    object_dictionary=epjson_object,
                    unique_name_override=False
                )
        # build system branches
        print('##### Branch Build #####')
        system_branch_dictionary = {}
        zone_branch_dictionary = {}
        system_demand_branchlist = []
        zone_demand_branchlist = []
        for sbp, unique_name in zip(system_build_paths, system_unique_names):
            sub_system_branch_dictionary, sub_system_demand_branchlist = create_branches(
                build_path=sbp,
                unique_name=unique_name)
            system_demand_branchlist.append(sub_system_demand_branchlist)
            system_branch_dictionary = merge_dictionaries(
                super_dictionary=system_branch_dictionary,
                object_dictionary=sub_system_branch_dictionary,
                unique_name_override=False
            )
        for zbp, unique_name in zip(zone_build_paths, zone_unique_names):
            sub_zone_branch_dictionary, sub_zone_demand_branchlist = create_branches(
                build_path=zbp,
                unique_name=unique_name,
                connectors_to_build=('HotWaterLoop', 'ChilledWaterLoop', 'CondenserWaterLoop'))
            zone_demand_branchlist.append(sub_zone_demand_branchlist)
            zone_branch_dictionary = merge_dictionaries(
                super_dictionary=zone_branch_dictionary,
                object_dictionary=sub_zone_branch_dictionary,
                unique_name_override=False
            )
        branch_dictionary = {}
        for bd in [system_branch_dictionary, zone_branch_dictionary]:
            # returned value is an object with Branch and BranchList keys
            branch_dictionary = merge_dictionaries(
                super_dictionary=branch_dictionary,
                object_dictionary=bd,
                unique_name_override=False)
        print('##### New Branch Output #####')
        pprint(branch_dictionary, width=150)
        epjson_dictionary = merge_dictionaries(
            super_dictionary=epjson_dictionary,
            object_dictionary=branch_dictionary)
        # use the stored demand branch lists to create a BranchList
        # Add pumps and pipes.  This will require the use of the template input fields as well.
        print(system_demand_branchlist)
        print(zone_demand_branchlist)
        pprint(epjson_dictionary, width=150)
        # build thermostats
        # this should be one of the last steps as it scans the epjson_dictionary
        thermostat_templates = [i for i in test_epjson if re.match('HVACTemplate:Thermostat', i, re.IGNORECASE)]
        # save outputs to dictionary
        thermostat_dictionary = {}
        for tt in thermostat_templates:
            hvac_thermostat_template_obj = test_epjson[tt]
            for template_thermostat_name, thermostat_template_dictionary in hvac_thermostat_template_obj.items():
                print('##### New Thermostat Template #####')
                print('Thermostat Name')
                print(template_thermostat_name)
                thermostat_sub_dictionary = create_thermostats(
                    template_dictionary=thermostat_template_dictionary,
                    thermostat_name=template_thermostat_name,
                    data=data)
                thermostat_dictionary[template_thermostat_name] = thermostat_sub_dictionary
        print('##### New Thermostat Output #####')
        pprint(thermostat_dictionary, width=150)
        for template_dictionary in thermostat_dictionary.values():
            epjson_dictionary = merge_dictionaries(
                super_dictionary=epjson_dictionary,
                object_dictionary=template_dictionary,
                unique_name_override=True)
        # Modify epjson object using its own sub-objects as references
        # This should serve as a last step for only objects that can't be
        # completed in above processes.
        modified_epjson_objects = modify_zone_control_thermostats(
            super_dictionary=epjson_dictionary,
            data=data)
        epjson_dictionary = merge_dictionaries(
            super_dictionary=epjson_dictionary,
            object_dictionary=modified_epjson_objects)
        print('##### Modified Objects Output #####')
        pprint(modified_epjson_objects, width=150)
        print('##### EPJSON Output #####')
        pprint(epjson_dictionary, width=150)
    return


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    main(args)

##########################
# todo_eo: Remaining example buildout
##########################
# General High Priority
###########################

##########################
# System ideas and cleanup
##########################

################
# Zone equipment
################

#############
# Plant Loops
#############

#############
# Thermostats
#############

#################
# Cleanup
# Input all necessary fields into yaml for energyplus objects
# build out all necessary additional equipment
#################

################
# Additional
# Make AirLoopHVAC at end of script to connect nodes
# set default schedules (e.g. always on) as default values
# make one of the last steps of the program to iterate over fields and add missing schedules.
# can be generalized to a function that just adds any missing default objects
#######
# Check references to non-standard inputs referenced in Input Output Reference
# e.g. HVACTemplate:Plant:Chiller:ObjectReference and make sure these are handled
# similarly.  If they need to differ, then include it in the NFP.
###############
