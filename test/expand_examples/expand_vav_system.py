import yaml
import re
import copy
import argparse
import numbers
import sys
import typing
from pprint import pprint

test_epjson = {
    "HVACTemplate:System:VAV": {
        "VAV Sys 1": {
            "cooling_coil_design_setpoint": 12.8,
            "cooling_coil_setpoint_reset_type": "None",
            "cooling_coil_type": "ChilledWater",
            "dehumidification_control_type": "None",
            "dehumidification_setpoint": 60.0,
            "economizer_lockout": "NoLockout",
            "economizer_lower_temperature_limit": 4,
            "economizer_type": "DifferentialDryBulb",
            "economizer_upper_temperature_limit": 19,
            "gas_heating_coil_efficiency": 0.8,
            "gas_heating_coil_parasitic_electric_load": 0.0,
            "gas_preheat_coil_efficiency": 0.8,
            "gas_preheat_coil_parasitic_electric_load": 0.0,
            "heat_recovery_type": "None",
            "heating_coil_design_setpoint": 10.0,
            "heating_coil_setpoint_reset_type": "None",
            "heating_coil_type": "Electric",
            "humidifier_rated_capacity": 1e-06,
            "humidifier_rated_electric_power": 2690.0,
            "humidifier_setpoint": 30.0,
            "humidifier_type": "None",
            "latent_heat_recovery_effectiveness": 0.65,
            "maximum_outdoor_air_flow_rate": "Autosize",
            "minimum_outdoor_air_control_type": "FixedMinimum",
            "minimum_outdoor_air_flow_rate": "Autosize",
            "minimum_outdoor_air_schedule_name": "Min OA Sched",
            "night_cycle_control": "CycleOnAny",
            "preheat_coil_type": "Electric",
            "preheat_efficiency": 1,
            "return_plenum_name": "PLENUM-1",
            "sensible_heat_recovery_effectiveness": 0.7,
            "sizing_option": "NonCoincident",
            "supply_fan_delta_pressure": 600,
            "supply_fan_maximum_flow_rate": "Autosize",
            "supply_fan_minimum_flow_rate": "Autosize",
            "supply_fan_motor_efficiency": 0.9,
            "supply_fan_motor_in_air_stream_fraction": 1,
            "supply_fan_part_load_power_coefficients": "InletVaneDampers",
            "supply_fan_placement": "DrawThrough",
            "supply_fan_total_efficiency": 0.7,
            "system_availability_schedule_name": "FanAvailSched"
        }
    },
    "HVACTemplate:Zone:VAV": {
        "HVACTemplate:Zone:VAV 1": {
            "baseboard_heating_capacity": "Autosize",
            "baseboard_heating_type": "None",
            "constant_minimum_air_flow_fraction": 0.3,
            "damper_heating_action": "Reverse",
            "outdoor_air_flow_rate_per_person": 0.00944,
            "outdoor_air_flow_rate_per_zone": 0.0,
            "outdoor_air_flow_rate_per_zone_floor_area": 0.0,
            "outdoor_air_method": "Flow/Person",
            "reheat_coil_type": "HotWater",
            "supply_air_maximum_flow_rate": "Autosize",
            "template_thermostat_name": "All Zones",
            "template_vav_system_name": "VAV Sys 1",
            "zone_cooling_design_supply_air_temperature_input_method": "SystemSupplyAirTemperature",
            "zone_heating_design_supply_air_temperature": 50.0,
            "zone_heating_design_supply_air_temperature_input_method": "SupplyAirTemperature",
            "zone_minimum_air_flow_input_method": "Constant",
            "zone_name": "SPACE1-1"
        },
        "HVACTemplate:Zone:VAV 2": {
            "baseboard_heating_capacity": "Autosize",
            "baseboard_heating_type": "None",
            "constant_minimum_air_flow_fraction": 0.3,
            "damper_heating_action": "Reverse",
            "outdoor_air_flow_rate_per_person": 0.00944,
            "outdoor_air_flow_rate_per_zone": 0.0,
            "outdoor_air_flow_rate_per_zone_floor_area": 0.0,
            "outdoor_air_method": "Flow/Person",
            "reheat_coil_type": "None",
            "supply_air_maximum_flow_rate": "Autosize",
            "template_thermostat_name": "All Zones",
            "template_vav_system_name": "VAV Sys 1",
            "zone_cooling_design_supply_air_temperature_input_method": "SystemSupplyAirTemperature",
            "zone_heating_design_supply_air_temperature": 50.0,
            "zone_heating_design_supply_air_temperature_input_method": "SupplyAirTemperature",
            "zone_minimum_air_flow_input_method": "Constant",
            "zone_name": "SPACE1-2"
        }
    },
    "HVACTemplate:Plant:ChilledWaterLoop": {
        "Chilled Water Loop": {
            "chilled_water_design_setpoint": 7.22,
            "chilled_water_pump_configuration": "ConstantPrimaryNoSecondary",
            "chilled_water_reset_outdoor_dry_bulb_high": 26.7,
            "chilled_water_reset_outdoor_dry_bulb_low": 15.6,
            "chilled_water_setpoint_at_outdoor_dry_bulb_high": 6.7,
            "chilled_water_setpoint_at_outdoor_dry_bulb_low": 12.2,
            "chilled_water_setpoint_reset_type": "None",
            "chiller_plant_operation_scheme_type": "Default",
            "condenser_plant_operation_scheme_type": "Default",
            "condenser_water_design_setpoint": 29.4,
            "condenser_water_pump_rated_head": 179352,
            "minimum_outdoor_dry_bulb_temperature": 7.22,
            "primary_chilled_water_pump_rated_head": 179352,
            "pump_control_type": "Intermittent",
            "secondary_chilled_water_pump_rated_head": 179352
        }
    },
    "HVACTemplate:Plant:Chiller": {
        "Main Chiller": {
            "capacity": "Autosize",
            "chiller_type": "ElectricReciprocatingChiller",
            "condenser_type": "WaterCooled",
            "nominal_cop": 3.2,
            "priority": "1"
        }
    },
    "HVACTemplate:Plant:Tower": {
        "Main Tower": {
            "free_convection_capacity": "Autosize",
            "high_speed_fan_power": "Autosize",
            "high_speed_nominal_capacity": "Autosize",
            "low_speed_fan_power": "Autosize",
            "low_speed_nominal_capacity": "Autosize",
            "priority": "1",
            "tower_type": "SingleSpeed"
        }
    }
}


def build_parser():  # pragma: no cover
    """
    Build argument parser.
    """
    parser_object = argparse.ArgumentParser(
        prog='pyExpandObjects',
        description='Automated process that expands HVACTemplate objects into regular EnergyPlus objects.')
    parser_object.add_argument(
        "yaml_file",
        nargs='?',
        help='Paths of epJSON files to convert'
    )
    return parser_object


def flatten_build_path(build_path, flat_list=[], clear=True):
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
    """
    if clear:
        flat_list = []
    for i in build_path:
        if isinstance(i, list):
            flatten_build_path(i, flat_list, clear=False)
        else:
            flat_list.append(i)
    return flat_list


def replace_values(super_object: dict, text_replacement: dict) -> dict:
    """
    Replace the pre-set string values in an object to avoid duplications

    :param super_object: EnergyPlus super object
    :param text_replacement: string to replace with format brackets in the super object
        field values
    :return: super_object similar to the input, but with renamed string fields
    """
    if text_replacement:
        (energyplus_object_type, energyplus_object_constructors), = super_object.items()
        for field_name, field_value in energyplus_object_constructors['Fields'].items():
            super_object[energyplus_object_type]['Fields'][field_name] = field_value.replace(
                '{}',
                text_replacement
            )
    return super_object


def build_energyplus_object_from_complex_inputs(
        yaml_object: dict,
        energyplus_object_dictionary: dict,
        unique_name_input: str) -> typing.Tuple[str, dict]:
    """
    Builds an energyplus object from a yaml object which uses complex inputs.

    :param yaml_object: template yaml object in dictionary format
    :param energyplus_object_dictionary: epJSON formatted dictionary containing reference objects
    :param unique_name_input: string to convert text to unique name using an existing epJSON dictionary
        for a HVAC System

    :return: Valid epJSON key-value pair for an EnergyPlus Object - EnergyPlus Object, {field_names: field_values}
    """
    (energyplus_object_type, energyplus_object_constructors), = yaml_object.items()
    tmp_d = {}
    # if the value is a string or numeric, then it's a direct input.  If it is a dictionary
    # then the key-value pair is the object type and reference node holding the value to be input.
    # Anything else should return an error.
    for reference_field_name, object_node_reference in energyplus_object_constructors.items():
        if isinstance(object_node_reference, str):
            tmp_d[reference_field_name] = object_node_reference.format(unique_name_input)
        elif isinstance(object_node_reference, numbers.Number):
            tmp_d[reference_field_name] = object_node_reference
        elif isinstance(object_node_reference, dict):
            # Optional key 'Occurrence' can be used with the value being an integer.
            # {'Occurrence': N} is used to get nth match of the object_type search.
            object_occurrence = object_node_reference.pop('Occurrence', 1)
            (reference_object_type, reference_node), = object_node_reference.items()
            # Regular expression match the object type and the reference object type
            count_matches = 0
            for object_type in energyplus_object_dictionary.keys():
                # if 'self' is used as the reference node, just return the energyplus object type
                # break the loop to prevent un-hashable entries
                if re.match(reference_object_type, object_type):
                    if reference_node == 'self':
                        tmp_d[reference_field_name] = object_type
                        continue
                    count_matches += 1
                    if count_matches == object_occurrence:
                        (energyplus_object_name, _), = energyplus_object_dictionary[object_type].items()
                        # if 'key' is used as the reference node, just get the unique object name
                        # e.g. {object_type: {unique_object_name: object_fields}
                        if reference_node == 'key':
                            tmp_d[reference_field_name] = energyplus_object_name
                        else:
                            tmp_d[reference_field_name] = \
                                energyplus_object_dictionary[object_type][energyplus_object_name][reference_node]
        else:
            print('error')
    # Make a check that every reference node was applied
    key_val = tmp_d.pop('name')
    return energyplus_object_type, {key_val: tmp_d}


def get_option_tree(template_name: str, data: dict) -> dict:
    """
    Retrieve dictionary of alternate build instructions from yaml dictionary

    :param template_name: string value of HVACTemplate object
    :param data: yaml data in dictionary form
    :return: Dictionary of alternate build instructions
    """
    template_parse_regex = re.compile(r'HVACTemplate:(.*):(.*)')
    template_classes = re.match(template_parse_regex, template_name)
    # whenever getting values that you might edit later, use copy.deepcopy()
    # so a new dictionary is created; otherwise, every time you call that
    # value again the updated will be returned... even if you use .copy()
    yaml_option_tree = copy.deepcopy(data[':'.join(['OptionTree'])])
    option_tree = yaml_option_tree['HVACTemplate'][template_classes[1]][template_classes[2]]
    return option_tree


def get_action_field_names(action: str, option_tree: dict, template_dictionary: dict) -> typing.List[str]:
    # field names that cause a specified set of actions to be performed.
    # The yaml is structured so that each
    # the template object key value (e.g. heating_coil_type) triggers
    # an action.  The sub-objects in [Remove,Replace,Insert]Element
    # have keys that matches the options
    """
    Compare option_tree alternate build actions against the template inputs
    and return the field names when matched.

    :param action: 'Replace', 'Remove', or 'Insert' actions
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: Object containing the user-provided template inputs
    :return:
    """
    if option_tree.get(action):
        action_field_names = [
            field_name for field_name in template_dictionary.keys()
            if field_name in option_tree[action].keys()
        ]
    else:
        action_field_names = []
    return action_field_names


def get_all_action_field_names(option_tree: dict, template_dictionary: dict) -> dict:
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
        'insert': insert_field_names
    }


def get_action_structure(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict) -> typing.Generator[int, str, dict]:
    """

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: user-inputs in HVACTemplate object

    :return: Iterator of [EnergyPlus object reference, action_structure]
    """
    # capitalize action
    action = action[0].upper() + action[1:]
    for field_name in action_list:
        # get the replacement subtree
        if option_tree[''.join([action, 'Elements'])].get(field_name) and \
                option_tree[''.join([action, 'Elements'])][field_name] \
                .get(template_dictionary[field_name]):
            objects_reference = \
                option_tree[''.join([action, 'Elements'])][field_name][template_dictionary[field_name]]
            # for each subtree reference (more than one can be done)
            for object_reference, option_structure in objects_reference.items():
                yield object_reference, option_structure


def remove_objects(
        action: str,
        action_list: typing.List[str],
        option_tree: dict,
        template_dictionary: dict,
        build_path: typing.List[dict]) -> typing.List[dict]:
    """
    Remove object in a flattened path using alternate build instructions

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: user-inputs in HVACTemplate object
    :param build_path: list of EnergyPlus super objects in build order

    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for remove_object_reference, remove_option_structure in object_references:
        count_matches = 0
        # If 'Occurrence' is specified, then only replace when that occurrence happens.
        remove_at_occurrence = remove_option_structure.get('Occurrence', 1)
        for idx, energyplus_super_object in enumerate(build_path):
            for energyplus_object_type in energyplus_super_object.keys():
                if re.match(remove_object_reference, energyplus_object_type):
                    count_matches += 1
                    if count_matches == remove_at_occurrence:
                        build_path.pop(idx)
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= remove_at_occurrence:
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
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: user-inputs in HVACTemplate object
    :param build_path: list of EnergyPlus super objects in build order

    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for replace_object_reference, replace_option_structure in object_references:
        count_matches = 0
        # If 'Occurrence' is specified, then only replace when that occurrence happens.
        replace_at_occurrence = replace_option_structure.get('Occurrence', 1)
        for idx, energyplus_super_object in enumerate(build_path):
            for energyplus_object_type in energyplus_super_object.keys():
                if re.match(replace_object_reference, energyplus_object_type):
                    count_matches += 1
                    if count_matches == replace_at_occurrence:
                        # get object from template
                        new_object = copy.deepcopy(
                            replace_option_structure['Object']
                        )
                        # rename fields
                        replacement = (
                            replace_option_structure.get('FieldNameReplacement')
                        )
                        # rename if applicable
                        new_object = replace_values(
                            new_object,
                            replacement
                        )
                        # replace old object with new
                        build_path[idx] = new_object
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= replace_at_occurrence:
            print('error')
            print('replace error')
            sys.exit()
    return build_path


def perform_build_path(
        connector_path: str,
        option_tree: dict,
        template_dictionary: dict,
        unique_name: str,
        **kwargs):
    # capitalize connector path
    connector_path = connector_path[0].upper() + connector_path[1:]
    selected_template = option_tree['Base']
    print('### selected template ###')
    print(selected_template)
    # a side effect of the yaml structure is that nested lists are produced
    # so we need to flatten them.
    build_path = flatten_build_path(selected_template['BuildPath'])
    # check for nested HVACTemplate objects.  They will appear as string objects with the
    # template name (e.g. HVACTemplate:Plant:Chiller).
    # if so do a recursive build on that object, insert it into the original position, and then flatten the
    # build path again.
    for idx, energyplus_super_object in enumerate(build_path):
        if isinstance(energyplus_super_object, str) and re.match('^HVACTemplate:.*', energyplus_super_object):
            # in this test program, we have to grab global objects, which are the yaml data and the
            # epjson object.  In production, these should be stored class attributes.
            sub_data = kwargs['data']
            sub_template_object = test_epjson[energyplus_super_object]
            for sub_object_name, sub_object_dictionary in sub_template_object.items():
                sub_option_tree = get_option_tree(energyplus_super_object, sub_data)
                _, sub_build_path = perform_build_operations(
                    connector_path=connector_path,
                    option_tree=sub_option_tree,
                    template_dictionary=sub_object_dictionary,
                    unique_name=sub_object_name,
                    **kwargs
                )
            build_path[idx] = sub_build_path
            build_path = flatten_build_path(build_path)
    actions = get_all_action_field_names(
        option_tree=option_tree,
        template_dictionary=template_dictionary
    )
    print('pre-replaced element path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # remove example
    if actions.get('remove'):
        build_path = remove_objects(
            action='remove',
            action_list=actions['remove'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path
        )
    print('post-removed path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # replace example
    # At the moment, replace happens even if correct equipment in place.
    # I'm sure there is a work-around to this but for now it doesn't break anything.
    if actions.get('replace'):
        build_path = replace_objects(
            action='replace',
            action_list=actions['replace'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path
        )
    print('post-replaced path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # apply base transitions.  This needs to be done before inserting optional elements.
    # If an element is inserted that is the same object type, then the transition mapping
    # would output to both objects.
    if selected_template.get('Transitions'):
        build_path = apply_transitions_to_objects(
            transition_structure=selected_template['Transitions'],
            template_dictionary=template_dictionary,
            build_path=build_path
        )
    print('post-transition path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # insert example
    if actions.get('insert'):
        build_path = insert_objects(
            action='insert',
            action_list=actions['insert'],
            option_tree=option_tree,
            template_dictionary=template_dictionary,
            build_path=build_path
        )
    print('post-insert element path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # insert system name
    build_path = insert_unique_name(
        unique_name=unique_name,
        build_path=build_path
    )
    return build_path


global_obj_d = {}


def merge_dictionaries(
        super_dictionary,
        object_dictionary,
        unique_name_override=True):
    """
    Merge the global epJSON object dictionary with a sub-dictionary

    :param super_dictionary:
    :param object_dictionary:
    :param unique_name_override:
    :return:
    """
    for energyplus_object_type, tmp_d in object_dictionary.items():
        if not super_dictionary.get(energyplus_object_type):
            super_dictionary[energyplus_object_type] = {}
        if isinstance(tmp_d, dict):
            for object_name, object_fields in tmp_d.items():
                if not unique_name_override and object_name in super_dictionary[energyplus_object_type].keys():
                    print('unique name error')
                    sys.exit()
            super_dictionary[energyplus_object_type] = tmp_d
        elif isinstance(tmp_d, list):
            super_dictionary[energyplus_object_type] = tmp_d
    return super_dictionary


def perform_build_operations(
        connector_path: str,
        option_tree: dict,
        template_dictionary: dict,
        unique_name: str,
        **kwargs):
    build_path = perform_build_path(
        connector_path=connector_path,
        option_tree=option_tree,
        template_dictionary=template_dictionary,
        unique_name=unique_name,
        **kwargs
    )
    global global_obj_d
    print('BuldPath complete')
    print(build_path)
    print('post-variable rename path')
    for idx, energyplus_super_object in enumerate(build_path):
        print('object {} - {}'.format(idx, energyplus_super_object))
    # Build a dictionary of valid epJSON objects from constructors
    # from build path
    object_from_path = build_epjson(
        connector_path=connector_path,
        unique_name=unique_name,
        build_path=build_path
    )
    merge_dictionaries(
        super_dictionary=global_obj_d,
        object_dictionary=object_from_path,
        unique_name_override=True)
    # build additional objects (e.g. Controllers)
    # these are stored in the option tree under AdditionalObjects
    # for standard objects, and AdditionalTemplateObjects for
    # template triggered objects
    additional_objects = build_additional_objects(
        option_tree=option_tree,
        connector_path=connector_path,
        energyplus_object_dictionary=global_obj_d,
        unique_name=unique_name,
        template_dictionary=template_dictionary,
        **kwargs
    )
    merge_dictionaries(
        super_dictionary=global_obj_d,
        object_dictionary=additional_objects,
        unique_name_override=True)
    return global_obj_d, build_path


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
        for reference_energyplus_object_type, field_name in value_reference.items():
            for energyplus_super_object in build_path:
                for energyplus_object_type in energyplus_super_object:
                    if re.match(reference_energyplus_object_type, energyplus_object_type):
                        if not energyplus_super_object[energyplus_object_type]['Fields'].get(field_name):
                            energyplus_super_object[energyplus_object_type]['Fields'][field_name] = None
                        energyplus_super_object[energyplus_object_type]['Fields'][field_name] = (
                            template_dictionary[transition_field_name]
                        )
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
    Insert object in a flattened path using alternate build instructions

    :param action: action to be performed
    :param action_list: list of field_names triggering actions
    :param option_tree: Dictionary containing build path variations
    :param template_dictionary: user-inputs in HVACTemplate object
    :param build_path: list of EnergyPlus super objects in build order

    :return: build_path with replaced objects
    """
    object_references = get_action_structure(
        action=action,
        action_list=action_list,
        option_tree=option_tree,
        template_dictionary=template_dictionary)
    for insert_object_reference, insert_option_structure in object_references:
        # iterate over regex matches and do operations when the right occurrence happens
        count_matches = 0
        for idx, energyplus_super_object in enumerate(build_path):
            for energyplus_object_type in energyplus_super_object.keys():
                if re.match(insert_object_reference, energyplus_object_type):
                    count_matches += 1
                    if count_matches == insert_option_structure.get('Occurrence', 1):
                        # Look for 'BeforeObject' the 'After'.  Prevent inserting twice with check
                        # on reference_object
                        object_location_offset = insert_option_structure['Location']
                        insert_offset = None
                        if object_location_offset == 'After"':
                            insert_offset = 1
                        elif not insert_offset and object_location_offset == 'Before':
                            insert_offset = 0
                        else:
                            print("error")
                            print("insert location error")
                            sys.exit()
                        insert_location = idx + insert_offset
                        # get object to be inserted from yaml option tree
                        new_object = copy.deepcopy(
                            insert_option_structure['Object']
                        )
                        # get rename format
                        replacement = (
                            insert_option_structure.get('FieldNameReplacement')
                        )
                        # rename if possible
                        new_object = replace_values(
                            new_object,
                            replacement
                        )
                        # apply specific transitions
                        new_object = apply_transitions_to_objects(
                            transition_structure=insert_option_structure['Transitions'],
                            template_dictionary=template_dictionary,
                            build_path=new_object
                        )
                        build_path.insert(
                            insert_location,
                            new_object
                        )
        # check if the number of matches actually met the occurrence threshold
        if not count_matches >= insert_option_structure.get('Occurrence', 1):
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

    :return: build_path of same structure with string fields formatted to have unqiue names
    """
    if isinstance(build_path, dict):
        as_object = True
        build_path = [build_path, ]
    else:
        as_object = False
    for energyplus_super_object in build_path:
        for energyplus_object_type, energyplus_object_constructors in energyplus_super_object.items():
            for field_name, field_value in energyplus_object_constructors['Fields'].items():
                if isinstance(field_value, str):
                    energyplus_super_object[energyplus_object_type]['Fields'][field_name] = \
                        field_value.format(unique_name)
    if as_object:
        return build_path[0]
    else:
        return build_path


def build_epjson(
        connector_path: str,
        unique_name: str,
        build_path: typing.Union[dict, typing.List[dict]]) -> dict:
    """
    Build epJSON formatted dictionary of EnergyPlus objects from super objects.

    :param connector_path: air, HotWater, ChilledWater, or MixedWater connectors to use
    :param unique_name: unique name string.
    :param build_path: list of EnergyPlus super objects in build order

    :return: epJSON formatted dictionary
    """
    # capitalize connector path
    connector_path = connector_path[0].upper() + connector_path[1:]
    if isinstance(build_path, dict):
        build_path = [build_path, ]
    out_node_name = None
    epjson_object = {}
    for idx, energyplus_super_object in enumerate(build_path):
        # store object key and make sure not in list as you iterate:
        unique_object_names = []
        for energyplus_object_type, energyplus_object_constructors in energyplus_super_object.items():
            # use copy so that the original structure is preserved for future queries
            tmp_d = copy.deepcopy(energyplus_object_constructors['Fields'])
            object_key = tmp_d.pop('name')
            # not necessary but it's a good reminder that this object is the target value
            object_values = tmp_d
            # create the object type if it doesn't exist
            if not epjson_object.get(energyplus_object_type):
                epjson_object[energyplus_object_type] = {}
            # for the first object, do not alter the input node name.
            # for subsequent objects, set the input node name value to the
            # output node name value of the previous object.
            # also check for duplicates
            if object_key in unique_object_names:
                print('non-unique object error')
                sys.exit()
            unique_object_names.append(object_key)
            if energyplus_object_constructors.get('Connectors'):
                if idx == 0:
                    epjson_object[energyplus_object_type][object_key] = object_values
                    out_node = energyplus_object_constructors['Connectors'][connector_path]['Outlet']
                    if isinstance(out_node, str) and '{}' in out_node:
                        out_node_name = out_node.format(unique_name)
                    else:
                        out_node_name = (
                            energyplus_object_constructors['Fields']
                            [energyplus_object_constructors['Connectors'][connector_path]['Outlet']]
                        )
                else:
                    object_values[
                        energyplus_object_constructors['Connectors'][connector_path]['Inlet']
                    ] = out_node_name
                    epjson_object[energyplus_object_type][object_key] = object_values
                    out_node = energyplus_object_constructors['Connectors'][connector_path]['Outlet']
                    if isinstance(out_node, str) and '{}' in out_node:
                        out_node_name = out_node.format(unique_name)
                    else:
                        out_node_name = (
                            energyplus_object_constructors['Fields']
                            [energyplus_object_constructors['Connectors'][connector_path]['Outlet']]
                        )
            else:
                epjson_object[energyplus_object_type][object_key] = object_values
    return epjson_object


def process_additional_object_input(
        object_or_template,
        object_structure,
        connector_path,
        energyplus_object_dictionary,
        unique_name,
        **kwargs):
    object_dictionary = {}
    if not object_or_template.startswith('HVACTemplate'):
        additional_object = {object_or_template: object_structure}
        for additional_sub_object, additional_sub_object_fields in additional_object.items():
            energyplus_object, tmp_d = build_energyplus_object_from_complex_inputs(
                yaml_object={additional_sub_object: copy.deepcopy(additional_sub_object_fields)},
                energyplus_object_dictionary=energyplus_object_dictionary,
                unique_name_input=unique_name
            )
            if not object_dictionary.get(energyplus_object):
                object_dictionary[energyplus_object] = {}
            for object_name, object_fields in tmp_d.items():
                if object_name in object_dictionary[energyplus_object].keys():
                    print('unique name error')
                    sys.exit()
            object_dictionary[energyplus_object] = tmp_d
    # if the object is just a string, it should be for an HVACTemplate OptionTree build.
    # The key is the unique name modifier
    elif object_or_template.startswith('HVACTemplate'):
        # in this test program, we have to grab global objects, which are the yaml data and the
        # epjson object.  In production, these should be stored class attributes.
        sub_data = kwargs['data']
        sub_template_object = test_epjson.get(object_or_template)
        # some internal yaml templates are not accessible via EnergyPlus, so they will not have
        # a json input
        sub_option_tree = get_option_tree(object_or_template, sub_data)
        if isinstance(sub_template_object, dict):
            for sub_object_name, sub_object_dictionary in sub_template_object.items():
                energyplus_epjson_objects, _ = perform_build_operations(
                    connector_path=object_structure.get('ConnectorPath', connector_path),
                    option_tree=sub_option_tree,
                    template_dictionary=sub_object_dictionary,
                    unique_name=object_structure['UniqueName'],
                    data=sub_data
                )
                for energyplus_object, tmp_d in energyplus_epjson_objects.items():
                    if not object_dictionary.get(energyplus_object):
                        object_dictionary[energyplus_object] = {}
                    for object_name, object_fields in tmp_d.items():
                        if object_name in object_dictionary[energyplus_object].keys():
                            print('unique name error')
                            sys.exit()
                    object_dictionary[energyplus_object] = tmp_d
        else:
            # for now, just specify the connector_path.  Will have to make a mapping dictionary later
            energyplus_epjson_objects, _ = perform_build_operations(
                connector_path=object_structure.get('ConnectorPath', connector_path),
                option_tree=sub_option_tree,
                template_dictionary={},
                unique_name=object_structure['UniqueName'],
                data=sub_data
            )
            object_dictionary = merge_dictionaries(
                super_dictionary=object_dictionary,
                object_dictionary=energyplus_epjson_objects,
                unique_name_override=False)
    else:
        print('value was not additional object key nor an HVACTemplate string')
        sys.exit()
    return object_dictionary


def build_additional_objects(
        option_tree: dict,
        energyplus_object_dictionary: dict,
        connector_path: str,
        unique_name: str,
        template_dictionary: dict,
        **kwargs) -> dict:
    """
    Build additional objects in option tree

    :param option_tree: Dictionary containing build path variations
    :param energyplus_object_dictionary: epjson dictionary of EnergyPlus objects
    :param unique_name: unique name string
    :return:
    """
    object_dictionary = {}
    if option_tree.get('AdditionalObjects'):
        # check if additional object iterator is a energyplus object key or an HVACTemplate object key.
        for object_or_template, object_structure in option_tree['AdditionalObjects'].items():
            sub_object_dictionary = process_additional_object_input(
                object_or_template=object_or_template,
                object_structure=object_structure,
                option_tree=option_tree,
                connector_path=connector_path,
                energyplus_object_dictionary=energyplus_object_dictionary,
                unique_name=unique_name,
                **kwargs
            )
            object_dictionary = merge_dictionaries(
                super_dictionary=object_dictionary,
                object_dictionary=sub_object_dictionary,
                unique_name_override=True)
    if option_tree.get('AdditionalTemplateObjects'):
        for template_field, template_structure in option_tree['AdditionalTemplateObjects'].items():
            for template_option, add_object_structure in template_structure.items():
                if template_option == template_dictionary[template_field]:
                    print(template_option)
                    for object_or_template, object_structure in add_object_structure.items():
                        sub_object_dictionary = process_additional_object_input(
                            object_or_template=object_or_template,
                            object_structure=object_structure,
                            option_tree=option_tree,
                            connector_path=connector_path,
                            energyplus_object_dictionary=energyplus_object_dictionary,
                            unique_name=unique_name,
                            **kwargs
                        )
                        object_dictionary = merge_dictionaries(
                            super_dictionary=object_dictionary,
                            object_dictionary=sub_object_dictionary,
                            unique_name_override=True)
    return object_dictionary

# In this process note one import aspect. Specific field names are
# rarely used, if at all.  Most of the structure comes from the yaml
# object, which means that very little (comparatively)
# python code will need to be rewritten, i.e. this chunk should work for
# (hopefully) all HVACTemplate:System objects.  Possibly, most of the code
# could be reused for zone and water loop templates as well.


def main(input_args):
    with open(input_args.yaml_file, 'r') as f:
        # get yaml data
        data = yaml.load(f, Loader=yaml.FullLoader)
        # extract system template objects from epJSON
        system_templates = [i for i in test_epjson if i.startswith('HVACTemplate:System')]
        # iterate over templates
        for st in system_templates:
            # continue
            # get template object as dictionary
            hvac_system_template_obj = test_epjson[st]
            for system_name, system_template_dictionary in hvac_system_template_obj.items():
                print('System Name')
                print(system_name)
                option_tree = get_option_tree(st, data)
                energyplus_epjson_system_object, system_build_path = perform_build_operations(
                    connector_path='air',
                    option_tree=option_tree,
                    template_dictionary=system_template_dictionary,
                    unique_name=system_name,
                    data=data
                )
                print('Energyplus epJSON objects')
                pprint(energyplus_epjson_system_object, width=150)
                print('Supply Path outlet')
                for energyplus_arguments in system_build_path[-1].values():
                    last_node = energyplus_arguments['Fields'][energyplus_arguments['Connectors']['Air']['Outlet']]
                print(last_node)
                print('Supply Path inlet')
                selected_template = option_tree['Base']
                (controller_reference_object_type, controller_reference_field_name), = \
                    selected_template['Connectors']['Supply']['Inlet'].items()
                (energyplus_object_name, _), = energyplus_epjson_system_object[controller_reference_object_type].items()
                print(
                    energyplus_epjson_system_object[controller_reference_object_type]
                    [energyplus_object_name][controller_reference_field_name]
                )
                print('Demand Path inlet')
                print(selected_template['Connectors']['Demand']['Inlet'].format(system_name))
                print('Demand Path outlet')
                print(selected_template['Connectors']['Demand']['Outlet'].format(system_name))
                # NodeLists, other controllers, etc. can be created based on logically parsing the epJSON object,
                # the super object, the flattened path, or any combination of these objects
                # OutdoorAir:Nodelist Example:
                (energyplus_object_type, energyplus_object_constructors), = system_build_path[0].items()
                # rename the inlet node to current conventions
                energyplus_epjson_system_object[energyplus_object_type][
                    energyplus_object_constructors['Fields']['name']]['air_inlet_node_name'] = \
                    '{} Outside Air Inlet'.format(system_name)
                # get the yaml object to construct
                outdoor_air_node_list = copy.deepcopy(data['OutdoorAir:NodeList']['Base'])
                # build object and add to dictionary
                (outdoor_air_node_list_object_type, _), = outdoor_air_node_list.items()
                energyplus_epjson_system_object[outdoor_air_node_list_object_type] = \
                    ['{} Outside Air Inlet'.format(system_name), ]
                print('epJSON with Nodelist')
                print('##### System Template Output #####')
                pprint(energyplus_epjson_system_object, width=150)
                # pprint(build_path, width=150)
        # do zone builds in scope of the system build.  In production, these will be separate or child classes that
        # get system information when necessary.
        zone_templates = [i for i in test_epjson if i.startswith('HVACTemplate:Zone')]
        # iterate over templates
        energyplus_epjson_zone_objects = []
        energyplus_zone_build_paths = []
        for zt in zone_templates:
            # get template object as dictionary
            hvac_zone_template_obj = test_epjson[zt]
            for template_zone_name, zone_template_dictionary in hvac_zone_template_obj.items():
                continue
                print('##### New Zone Template #####')
                print('Zone Name')
                print(template_zone_name)
                option_tree = get_option_tree(zt, data)
                energyplus_epjson_zone_object, zone_build_path = perform_build_operations(
                    connector_path='air',
                    option_tree=option_tree,
                    template_dictionary=zone_template_dictionary,
                    unique_name=zone_template_dictionary["zone_name"]
                )
                print('##### Zone Template Output #####')
                energyplus_epjson_zone_objects.append(energyplus_epjson_zone_object)
                energyplus_zone_build_paths.append(zone_build_path)
        print('zone object list')
        pprint(energyplus_epjson_zone_objects, width=150)
        # plant system loop build
        plant_templates = [i for i in test_epjson if re.match('HVACTemplate:Plant:.*Loop', i)]
        for pt in plant_templates:
            hvac_plant_template_obj = test_epjson[pt]
            for template_plant_name, plant_template_dictionary in hvac_plant_template_obj.items():
                print('##### New Plant Template #####')
                print('Plant Name')
                print(template_plant_name)
                connector_path_rgx = re.match(r'^HVACTemplate:Plant:(.*)', pt)
                option_tree = get_option_tree(pt, data)
                energyplus_epjson_plant_object, plant_build_path = perform_build_operations(
                    connector_path=connector_path_rgx.group(1),
                    option_tree=option_tree,
                    template_dictionary=plant_template_dictionary,
                    unique_name='ChilledWaterLoop',
                    data=data
                )
                print('##### New Plant Template Output #####')
                pprint(energyplus_epjson_plant_object, width=150)
                # pprint(build_path, width=150)
        # build branches
        global_obj_d['Branch'] = {}
        # collect all connector path keys to use as the key for each branch iteration
        connectors_list = []
        for build_object in system_build_path:
            print('-----------')
            for super_object in build_object.values():
                connector_object = super_object.get('Connectors')
                if connector_object:
                    for connector_type in connector_object.keys():
                        connectors_list.append(connector_type)
        print(connectors_list)
        print(system_build_path)
        # iterate over build path for each connector type and build the branch
        for connector_type in set(connectors_list):
            print('--------------')
            print(connector_type)
            component_list = []
            for build_object in system_build_path:
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
            global_obj_d['Branch'] = {connector_type: component_list}
            pprint(global_obj_d['Branch'], width=150)
    return


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    main(args)

##########################
# todo_eo: Remaining example buildout
##########################
# System ideas and cleanup
##########################

################
# Zone equipment
################

#############
# Plant Loops
#############
# Supply side should be similar to the HVACTemplate system build
# Demand side, loop through all objects in all air loops and set in a list.  Then, build loop for each object like
# how zones are created.
#######################

#################
# Cleanup
# Input all necessary fields into yaml for energyplus objects
# build out all necessary additional equipment
#################