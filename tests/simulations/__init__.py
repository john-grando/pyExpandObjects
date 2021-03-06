import unittest
import json
from pathlib import Path
import subprocess
import csv
import re
import sys
import os
from argparse import Namespace

from src.epjson_handler import EPJSON
from src.main import main
from tests import BaseTest

test_dir = Path(__file__).parent.parent


class BaseSimulationTest(BaseTest, unittest.TestCase):
    """
    Setup, extraction, and comparison functions for simulation testing.
    """

    @staticmethod
    def setup_file(file_path):
        """
        Read file path and run epJSON through processing to ensure it is a valid json before testing.
        This is to ensure that if there is a problem with the base file, it will be more obvious by returning an
        error from this function rather than pyExpandObjects.  Also, it allows for any future manipulations that may
        be useful

        :param file_path: epJSON file path
        :return: formatted epJSON
        """
        with open(file_path, 'r') as f:
            test_data = f.read()
        formatted_epjson = json.loads(test_data)
        # Do manipulations if necessary by using the following commands
        # epj = EPJSON()
        # epj.epjson_process(epjson_ref=base_raw_epjson)
        # purged_epjson = epj.purge_epjson(
        #     epjson=base_raw_epjson,
        #     purge_dictionary={})
        # formatted_epjson = copy.deepcopy(purged_epjson)
        # epj.merge_epjson(
        #     super_dictionary=formatted_epjson,
        #     object_dictionary={})
        return formatted_epjson

    @staticmethod
    def write_file_for_testing(epjson, file_name, sub_directory=('simulation', 'test')):
        """
        write file to simulation testing sudirectory
        :param epjson: epJSON dictionary
        :param sub_directory: project subdirectory
        :param file_name: file name to write
        :return: file_path for written epJSON
        """
        input_file_path = test_dir.joinpath('..', *sub_directory, file_name)
        with open(input_file_path, 'w') as f:
            json.dump(epjson, f, indent=4, sort_keys=True)
        return input_file_path

    def get_epjson_object_from_idf_file(self, idf_file_path):
        """
        Return an epJSON object from idf filfe path
        :param idf_file_path: idf file path
        :return: epJSON object
        """
        epjson_file_path = self.convert_file(idf_file_path)
        ej = EPJSON()
        return ej._get_json_file(epjson_file_path)

    def create_idf_file_from_epjson(self, epjson, file_name, sub_directory=('simulation', 'test')):
        """
        Create an epJSON and idf file from an epJSON object
        :param epjson: input epJSON object
        :param file_name: destination file name
        :param sub_directory: destination directory
        :return: idf file name
        """
        epjson_file_path = self.write_file_for_testing(epjson=epjson, file_name=file_name, sub_directory=sub_directory)
        idf_file_path = self.convert_file(epjson_file_path)
        return idf_file_path

    @staticmethod
    def convert_file(file_location):
        """
        Convert idf to epJSON and vice versa.
        converted file in alternative format is created in same directory as base file
        :param file_location: Path or string reference to file location
        :return: file path to converted file
        """
        # convert to Path if a string is passed
        if isinstance(file_location, str):
            file_location = Path(file_location)
        # calling the arguments with pathlib causes issues with the conversion exe, so direct strings are passed here.
        subprocess.run(
            [
                'wine',
                '../ConvertInputFormatWithHVACTemplate.exe',
                '-t',
                os.path.basename(file_location)
            ],
            cwd=str(test_dir / '..' / 'simulation' / 'test'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if file_location.suffix == '.epJSON':
            return file_location.with_suffix('.idf')
        elif file_location.suffix == '.idf':
            return file_location.with_suffix('.epJSON')
        else:
            print('File has incorrect extension {}'.format(file_location))
            sys.exit()

    def perform_full_comparison(self, base_idf_file_path):
        """
        Simulate and compare two files where only the objects controlling output data are manipulated.
        Due to conversion issues within EnergyPlus, the baseline file must be simulated as an idf.
        :param base_idf_file_path: idf file location containing HVACTemplate:.* objects
        :return: None.  Assertions performed within function.
        """
        # move file to testing directory manually, shutil does not work reliably for some reason
        with open(base_idf_file_path, 'r') as f1, \
                open(test_dir.joinpath('..', 'simulation', 'test', 'base_input.idf'), 'w') as f2:
            for line in f1:
                f2.write(line)
        # convert to epJSON for test simulation input
        baseline_file_location = self.convert_file(base_idf_file_path)
        # setup outputs for perform_comparison to function and write base file
        base_formatted_epjson = self.setup_file(baseline_file_location)
        # write the preformatted base file for main to call
        test_pre_input_file_path = self.write_file_for_testing(
            epjson=base_formatted_epjson,
            file_name='test_pre_input_epjson.epJSON')
        # Expand and perform comparisons between the files
        # try expansion.  If it fails, raise an error
        output_epjson = None
        try:
            output = main(
                Namespace(
                    no_schema=False,
                    file=str(test_dir / '..' / 'simulation' / 'ExampleFiles' / 'test' / test_pre_input_file_path)))
            output_epjson = output['epJSON']
            test_input_file_path = self.write_file_for_testing(
                epjson=output_epjson,
                file_name='test_input_epjson.epJSON')
            # check outputs
            self.perform_comparison([base_idf_file_path, test_input_file_path])
        except:
            print('pyExpandObjects process failed to complete')
            self.assertIsNotNone(output_epjson)
        return

    def perform_comparison(self, epjson_files):
        """
        Simulate and compare epJSON files
        :param epjson_files: input epJSON files to compare
        :return: dictionary of status outputs
        """
        total_energy_outputs = []
        warning_outputs = []
        error_outputs = []
        finished_statuses = []
        for file_path in epjson_files:
            # move files from previous runs, rm is too dangerous
            try:
                os.rename(
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout.csv'),
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout_previous.csv')
                )
            except FileNotFoundError:
                pass
            try:
                os.rename(
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout.err'),
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout_previous.err')
                )
            except FileNotFoundError:
                pass
            try:
                os.rename(
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout.end'),
                    str(test_dir / '..' / 'simulation' / 'test' / 'eplusout_previous.end')
                )
            except FileNotFoundError:
                pass
            if sys.platform.startswith('win'):
                # enable ExpandObjects for idf files (-x).
                if file_path.suffix == '.idf':
                    subprocess.run(
                        [
                            str(test_dir / '..' / 'simulation' / 'energyplus.exe'),
                            '-d',
                            str(test_dir / '..' / 'simulation' / 'test'),
                            '-x',
                            '-w',
                            str(test_dir / '..' / 'simulation' / 'WeatherData' / 'USA_CO_Golden-NREL.724666_TMY3.epw'),
                            str(file_path)
                        ]
                    )
                else:
                    subprocess.run(
                        [
                            str(test_dir / '..' / 'simulation' / 'energyplus.exe'),
                            '-d',
                            str(test_dir / '..' / 'simulation' / 'test'),
                            '-w',
                            str(test_dir / '..' / 'simulation' / 'WeatherData' / 'USA_CO_Golden-NREL.724666_TMY3.epw'),
                            str(file_path)
                        ]
                    )
                subprocess.run(
                    [
                        str(test_dir / '..' / 'simulation' / 'PostProcess' / 'ReadVarsESO.exe'),
                        'convert.rvi'
                    ],
                    cwd=str(test_dir / '..' / 'simulation' / 'test')
                )
            else:
                if file_path.suffix == '.idf':
                    subprocess.run(
                        [
                            'wine',
                            str(test_dir / '..' / 'simulation' / 'energyplus.exe'),
                            '-d',
                            str(test_dir / '..' / 'simulation' / 'test'),
                            '-x',
                            '-w',
                            str(test_dir / '..' / 'simulation' / 'WeatherData' / 'USA_CO_Golden-NREL.724666_TMY3.epw'),
                            file_path
                        ]
                    )
                else:
                    subprocess.run(
                        [
                            'wine',
                            str(test_dir / '..' / 'simulation' / 'energyplus.exe'),
                            '-d',
                            str(test_dir / '..' / 'simulation' / 'test'),
                            '-w',
                            str(test_dir / '..' / 'simulation' / 'WeatherData' / 'USA_CO_Golden-NREL.724666_TMY3.epw'),
                            file_path
                        ]
                    )
                subprocess.run(
                    [
                        'wine',
                        str(test_dir / '..' / 'simulation' / 'PostProcess' / 'ReadVarsESO.exe'),
                        'convert.rvi'
                    ],
                    cwd=str(test_dir / '..' / 'simulation' / 'test')
                )
            # get sum of output csv rows to use as comparison
            total_energy = 0
            with open(str(test_dir / '..' / 'simulation' / 'test' / 'eplusout.csv'), 'r') as f:
                csvreader = csv.reader(f)
                sum_val = []
                for idx, row in enumerate(csvreader):
                    if idx != 0:
                        for val in row:
                            try:
                                sum_val.append(float(val))
                            except ValueError:
                                pass
                total_energy = sum(sum_val)
            with open(str(test_dir / '..' / 'simulation' / 'test' / 'eplusout.end'), 'r') as f:
                lines = f.readlines()
            # check end file for matches and success message
            warning_rgx = r'(\d+)\s+Warning;'
            error_rgx = r'(\d+) Severe Errors'
            status_rgx = r'^EnergyPlus\s+Completed\s+Successfully'
            status_val = 0
            for line in lines:
                warning_match = re.match(warning_rgx, line)
                error_match = re.match(error_rgx, line)
                status_match = re.match(status_rgx, line)
                if warning_match:
                    try:
                        warning_outputs.append(float(warning_match.group(1)))
                    except TypeError:
                        # special flag for type error
                        warning_outputs.append(-1)
                if error_match:
                    try:
                        error_outputs.append(float(error_match.group(1)))
                    except TypeError:
                        error_outputs.append(-1)
                if status_match:
                    status_val = 1
            finished_statuses.append(status_val)
            total_energy_outputs.append(total_energy)
        status_checks = {
            "total_energy_outputs": total_energy_outputs,
            "warning_outputs": warning_outputs,
            "error_outputs": error_outputs,
            "finished_statuses": finished_statuses}
        for energy_val in status_checks['total_energy_outputs']:
            print("Simulation are {} % different".format(
                abs(1 - energy_val / max(status_checks['total_energy_outputs'])) * 100))
            self.assertAlmostEqual(energy_val / max(status_checks['total_energy_outputs']), 1, 2)
        for warning in status_checks['warning_outputs']:
            self.assertEqual(warning, max(status_checks['warning_outputs']))
        for error in status_checks['error_outputs']:
            self.assertEqual(error, max(status_checks['error_outputs']))
            self.assertGreaterEqual(error, 0)
        for status in status_checks['finished_statuses']:
            self.assertEqual(1, status)
        return

    def compare_epjsons(self, epjson_1, epjson_2):
        """
        Summarize and compare two epJSONs based on object counts.

        :param epjson_1: epJSON object
        :param epjson_2: epJSON object
        :return: message if failures occur, otherwise None
        """
        eo = EPJSON()
        epjson_summary_1 = eo.summarize_epjson(epjson_1)
        epjson_summary_2 = eo.summarize_epjson(epjson_2)
        # remove schedule compact
        epjson_summary_1.pop('Schedule:Compact')
        epjson_summary_2.pop('Schedule:Compact')
        msg = ''
        for k, v in epjson_summary_1.items():
            if k not in epjson_summary_2.keys():
                msg += '{} not in {}\n'.format(k, epjson_summary_2)
            else:
                if epjson_summary_1[k] != epjson_summary_2[k]:
                    msg += '{} is not the same number of objects\n'.format(k)
        for k, v in epjson_summary_2.items():
            if k not in epjson_summary_1.keys():
                msg += '{} not in {}\n'.format(k, epjson_summary_2)
        self.assertEqual('', msg, msg)
        return
