import unittest
import copy

from src.expand_objects import ExpandSystem
from src.expand_objects import PyExpandObjectsException, PyExpandObjectsYamlStructureException, \
    PyExpandObjectsTypeError
from . import BaseTest

mock_template = template = {
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
            "heating_coil_type": "HotWater",
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
            "preheat_coil_type": "None",
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
    }
}

mock_build_path = [
    {
        'OutdoorAir:Mixer': {
            'Fields': {
                'name': '{} OA Mixing Box',
                'mixed_air_node_name': '{} Mixed Air Outlet',
                'outdoor_air_stream_node_name': '{} Outside Air Inlet',
                'relief_air_stream_node_name': '{} Relief Air Outlet',
                'return_air_stream_node_name': '{} Air Loop Inlet'
            },
            'Connectors': {
                'AirLoop': {
                    'Inlet': 'outdoor_air_stream_node_name',
                    'Outlet': 'mixed_air_node_name'
                }
            }
        }
    },
    {
        'Fan:VariableVolume': {
            'Fields': {
                'name': '{} Supply Fan',
                'air_inlet_node_name': '{} Supply Fan Inlet',
                'air_outlet_node_name': '{} Supply Fan Outlet'
            },
            'Connectors': {
                'AirLoop': {
                    'Inlet': 'air_inlet_node_name',
                    'Outlet': 'air_outlet_node_name'
                }
            }
        }
    }
]


class TestExpandSystem(BaseTest, unittest.TestCase):
    def setUp(self):
        return

    def teardown(self):
        return

    @BaseTest._test_logger(doc_text="HVACTemplate:System:Input Template Required")
    def test_check_templates_are_required(self):
        with self.assertRaises(TypeError):
            ExpandSystem()
        return

    @BaseTest._test_logger(doc_text="HVACTemplate:System:Verify valid template object")
    def test_verify_good_template(self):
        output = ExpandSystem(template=mock_template)
        self.assertEqual('VAV Sys 1', list(output.template.keys())[0])
        return

    def test_create_water_controller_list_from_epjson(self):
        es = ExpandSystem(template=mock_template)
        es.epjson = {
            'Controller:WaterCoil': {
                'test cooling water coil': {
                    'sensor_node_name': {
                        '^Coil:Cooling:Water': 'air_outlet_node_name'
                    },
                    'actuator_node_name': {
                        '^Coil:Cooling:Water': 'water_inlet_node_name'
                    }
                },
                'test heating water coil': {
                    'sensor_node_name': {
                        '^Coil:Heating:Water': 'air_outlet_node_name'
                    },
                    'actuator_node_name': {
                        '^Coil:Heating:Water': 'water_inlet_node_name'
                    }
                }
            }
        }
        controllerlist = es._create_controller_list_from_epjson()
        self.assertEqual('AirLoopHVAC:ControllerList', list(controllerlist.keys())[0])
        self.assertEqual(
            'test cooling water coil',
            controllerlist['AirLoopHVAC:ControllerList']['VAV Sys 1 Controllers']['controller_1_name'])
        self.assertEqual(
            'test heating water coil',
            controllerlist['AirLoopHVAC:ControllerList']['VAV Sys 1 Controllers']['controller_2_name'])
        return

    def test_create_outdoor_air_equipment_list_from_epjson(self):
        es = ExpandSystem(template=mock_template)
        temp_mock_build_path = copy.deepcopy(mock_build_path)
        temp_mock_build_path.insert(0, {
            'TestObject': {
                'Fields': {
                    'name': 'Test Name',
                },
                'Connectors': {}
            }
        })
        es.build_path = temp_mock_build_path
        oa_equipment_list_object = es._create_outdoor_air_equipment_list_from_build_path()
        self.assertEqual('AirLoopHVAC:OutdoorAirSystem:EquipmentList', list(oa_equipment_list_object.keys())[0])
        self.assertEqual(
            'Test Name',
            oa_equipment_list_object['AirLoopHVAC:OutdoorAirSystem:EquipmentList']
            ['VAV Sys 1 OA System Equipment']['component_1_name'])
        self.assertEqual(
            'VAV Sys 1 OA Mixing Box',
            oa_equipment_list_object['AirLoopHVAC:OutdoorAirSystem:EquipmentList']
            ['VAV Sys 1 OA System Equipment']['component_2_name'])
        return

    def test_reject_create_outdoor_air_equipment_list_from_epjson_without_build_path(self):
        es = ExpandSystem(template=mock_template)
        with self.assertRaisesRegex(PyExpandObjectsException, 'Build path was not provided nor was it available'):
            es._create_outdoor_air_equipment_list_from_build_path()
        return

    def test_branchlist_from_build_path(self):
        build_path = [
            {
                "Object:1": {
                    "Fields": {
                        "name": "object_1_name",
                        "field_1": "value_1",
                        "field_2": "value_2"
                    },
                    "Connectors": {
                        "AirLoop": {
                            "Inlet": "field_1",
                            "Outlet": "field_2"
                        }
                    }
                }
            },
            {
                "Object:2": {
                    "Fields": {
                        "name": "object_2_name",
                        "field_3": "value_3",
                        "field_4": "value_4"
                    },
                    "Connectors": {
                        "AirLoop": {
                            "Inlet": "field_3",
                            "Outlet": "field_4"
                        }
                    }
                }
            }
        ]
        eo = ExpandSystem(template=mock_template)
        eo.unique_name = 'TEST SYSTEM'
        output = eo._create_branch_and_branchlist_from_build_path(build_path=build_path)
        self.assertEqual(
            '{} Main Branch'.format(eo.unique_name),
            output['Branchlist']['{} Branches'.format(eo.unique_name)]['branches'][0]['branch_name'])
        return

    def test_reject_create_branch_and_branchlist_from_build_path_no_connectors(self):
        build_path = [
            {
                "Object:1": {
                    "Fields": {
                        "name": "object_1_name",
                        "field_1": "value_1",
                        "field_2": "value_2"
                    },
                    "Connectors": {
                        "AirLoop": {
                            "Inlet": "bad_field",
                            "Outlet": "field_2"
                        }
                    }
                }
            },
        ]
        eo = ExpandSystem(template=template)
        eo.unique_name = 'TEST SYSTEM'
        with self.assertRaisesRegex(PyExpandObjectsYamlStructureException, "Field/Connector mismatch"):
            eo._create_branch_and_branchlist_from_build_path(build_path=build_path)
        return

    def test_reject_create_branch_and_branchlist_from_build_path_mismatch_connectors(self):
        build_path = [
            {
                "Object:1": {
                    "Fields": {
                        "name": "object_1_name",
                        "field_1": "value_1",
                        "field_2": "value_2"
                    },
                }
            },
        ]
        eo = ExpandSystem(template=mock_template)
        eo.unique_name = 'TEST SYSTEM'
        with self.assertRaisesRegex(PyExpandObjectsYamlStructureException, "Super object is missing Connectors"):
            eo._create_branch_and_branchlist_from_build_path(build_path=build_path)
        return

    def test_create_availability_manager_assignment_list(self):
        es = ExpandSystem(template=mock_template)
        es.epjson = {
            "AvailabilityManager:NightCycle": {
                "VAV Sys 1 Availability": {
                    "applicability_schedule_name": "HVACTemplate-Always 1",
                    "control_type": "CycleOnAny",
                    "cycling_run_time": 3600,
                    "cycling_run_time_control_type": "FixedRunTime",
                    "fan_schedule_name": "FanAvailSched",
                    "thermostat_tolerance": 0.2
                }
            }
        }
        availability_manager_assignment_list_object = es._create_availability_manager_assignment_list()
        self.assertEqual(
            'AvailabilityManagerAssignmentList',
            list(availability_manager_assignment_list_object.keys())[0])
        self.assertEqual(
            'VAV Sys 1 Availability',
            availability_manager_assignment_list_object['AvailabilityManagerAssignmentList']
            ['VAV Sys 1 Availability Managers']['availability_manager_name'])
        return

    def test_reject_create_availability_manager_assignment_list_bad_object(self):
        es = ExpandSystem(template=mock_template)
        es.epjson = {
            "AvailabilityManager:NightCycle": ['bad', 'format']
        }
        with self.assertRaisesRegex(PyExpandObjectsTypeError, 'AvailabilityManager object not properly'):
            es._create_availability_manager_assignment_list()
        return

    def test_airloophvac_outdoor_air_system(self):
        es = ExpandSystem(template=mock_template)
        es.epjson = {
            "AirLoopHVAC:ControllerList": {
                "VAV Sys 1 Controllers": {
                    "controller_1_name": "VAV Sys 1 Cooling Coil Controller",
                    "controller_1_object_type": "Controller:WaterCoil",
                    "controller_2_name": "VAV Sys 1 Heating Coil Controller",
                    "controller_2_object_type": "Controller:WaterCoil"
                },
                "VAV Sys 1 OA System Controllers": {
                    "controller_1_name": "VAV Sys 1 OA Controller",
                    "controller_1_object_type": "Controller:OutdoorAir"
                }
            },
            "AirLoopHVAC:OutdoorAirSystem:EquipmentList": {
                "VAV Sys 1 OA System Equipment": {
                    "component_1_name": "VAV Sys 1 OA Mixing Box",
                    "component_1_object_type": "OutdoorAir:Mixer"
                }
            },
            "AvailabilityManagerAssignmentList": {
                "VAV Sys 1 Availability Managers": {
                    "managers": [
                        {
                            "availability_manager_name": "VAV Sys 1 Availability",
                            "availability_manager_object_type": "AvailabilityManager:NightCycle"
                        }
                    ]
                }
            }
        }
        oa_system_object = es._create_outdoor_air_system()
        self.assertEqual('AirLoopHVAC:OutdoorAirSystem', list(oa_system_object.keys())[0])
        self.assertEqual(
            'VAV Sys 1 OA System Controllers',
            oa_system_object['AirLoopHVAC:OutdoorAirSystem']['VAV Sys 1 OA System']['controller_list_name'])
        return

    def test_reject_outdoor_air_system_no_oa_controllerlist(self):
        es = ExpandSystem(template=mock_template)
        test_epjson = {
            "AirLoopHVAC:ControllerList": {
                "VAV Sys 1 Controllers": {
                    "controller_1_name": "VAV Sys 1 Cooling Coil Controller",
                    "controller_1_object_type": "Controller:WaterCoil",
                    "controller_2_name": "VAV Sys 1 Heating Coil Controller",
                    "controller_2_object_type": "Controller:WaterCoil"
                },
                "VAV Sys 1 OA System Controllers": {
                    "controller_1_name": "VAV Sys 1 OA Controller",
                    "controller_1_object_type": "Controller:OutdoorAir"
                }
            },
            "AirLoopHVAC:OutdoorAirSystem:EquipmentList": {
                "VAV Sys 1 OA System Equipment": {
                    "component_1_name": "VAV Sys 1 OA Mixing Box",
                    "component_1_object_type": "OutdoorAir:Mixer"
                }
            },
            "AvailabilityManagerAssignmentList": {
                "VAV Sys 1 Availability Managers": {
                    "managers": [
                        {
                            "availability_manager_name": "VAV Sys 1 Availability",
                            "availability_manager_object_type": "AvailabilityManager:NightCycle"
                        }
                    ]
                }
            }
        }
        no_oa_controller_epjson = copy.deepcopy(test_epjson)
        no_oa_controller_epjson["AirLoopHVAC:ControllerList"].pop("VAV Sys 1 OA System Controllers")
        es.epjson = no_oa_controller_epjson
        with self.assertRaisesRegex(PyExpandObjectsException, 'No outdoor air AirLoopHVAC:ControllerList'):
            es._create_outdoor_air_system()
        no_oa_system_epjson = copy.deepcopy(test_epjson)
        no_oa_system_epjson.pop('AirLoopHVAC:OutdoorAirSystem:EquipmentList')
        es.epjson = no_oa_system_epjson
        with self.assertRaisesRegex(
                PyExpandObjectsException,
                'Only one AirLoopHVAC:OutdoorAirSystem:EquipmentList'):
            es._create_outdoor_air_system()
        no_avail_epjson = copy.deepcopy(test_epjson)
        no_avail_epjson.pop('AvailabilityManagerAssignmentList')
        es.epjson = no_avail_epjson
        with self.assertRaisesRegex(
                PyExpandObjectsException,
                'Only one AvailabilityManagerAssignmentList'):
            es._create_outdoor_air_system()
        return

    def test_branch_from_build_path(self):
        build_path = [
            {
                "Object:1": {
                    "Fields": {
                        "name": "object_1_name",
                        "field_1": "value_1",
                        "field_2": "value_2"
                    },
                    "Connectors": {
                        "AirLoop": {
                            "Inlet": "field_1",
                            "Outlet": "field_2"
                        }
                    }
                }
            },
            {
                "Object:2": {
                    "Fields": {
                        "name": "object_2_name",
                        "field_3": "value_3",
                        "field_4": "value_4"
                    },
                    "Connectors": {
                        "AirLoop": {
                            "Inlet": "field_3",
                            "Outlet": "field_4"
                        }
                    }
                }
            }
        ]
        es = ExpandSystem(template={})
        es.unique_name = 'TEST SYSTEM'
        output = es._create_branch_and_branchlist_from_build_path(build_path=build_path)
        self.assertEqual(
            'value_3',
            output['Branch']['{} Main Branch'.format(es.unique_name)]['components'][1]['component_inlet_node_name'])
        return

    def test_reject_create_branch_and_branchlist_from_build_path_no_build_path(self):
        es = ExpandSystem(template={})
        with self.assertRaisesRegex(PyExpandObjectsException, 'Build path was not provided'):
            es._create_branch_and_branchlist_from_build_path(build_path=[])
        return

    # todo_eo: branch in _create_branch_and_branchlist_from_build_path() needs first component to be
    #  AirLoopHVAC:OutdoorAirSystem instead of individual components
    # todo_eo: system objects to create: AirLoopHVAC:OutdoorAirSystem, SupplyPath, ReturnPath
