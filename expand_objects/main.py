import argparse
import os
from expand_objects.hvac_template import HVACTemplate


def build_parser():  # pragma: no cover
    """
    Build argument parser.
    """
    parser = argparse.ArgumentParser(
        prog='pyExpandObjects',
        description='Automated process that expands HVACTemplate objects into regular EnergyPlus objects.')
    parser.add_argument(
        '--no-schema',
        '-ns',
        action='store_false',
        help='Skip schema validations')
    parser.add_argument(
        "file",
        nargs='?',
        help='Path of epJSON file to convert'
    )
    return parser


def main(args=None):
    hvt = HVACTemplate(
        no_schema=args.no_schema
    )
    output = {'outputPreProcessorMessage': []}
    if args.file.endswith('.epJSON'):
        if os.path.exists(args.file):
            hvt.logger.info('Proceessing %s', args.file)
            output['epjson'] = hvt.run(input_epjson=args.file)
        else:
            hvt.logger.warning('File does not exist: %s. file not processed', args.file)
            output['outputPreProcessorMessage'].append(
                'File does not exist: {}.  File not processed'.format(args.file))
    else:
        hvt.logger.warning('Bad file extension for %s.  File not processed', args.file)
        output['outputPreProcessorMessage'].append(
            'Bad file extension for {}.  File not processed'.format(args.file))
    return output


if __name__ == "__main__":
    epJSON_parser = build_parser()
    epJSON_args = epJSON_parser.parse_args()
    main(epJSON_args)
