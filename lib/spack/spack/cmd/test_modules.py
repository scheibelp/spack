from __future__ import print_function
import argparse

import llnl.util.tty as tty

import spack
import spack.cmd
from spack.modules import MergedTclModule, TclModule

import StringIO

description = "Test out merged module functionality"


def setup_parser(subparser):
    subparser.add_argument(
        'packages', nargs=argparse.REMAINDER,
        help="specs of packages to install")


def test_modules(parser, args):
    specs = spack.cmd.parse_specs(args.packages, concretize=True)
    
    #module = TclModule(specs[0])
    #collect_output = StringIO.StringIO()
    #module.write(output=collect_output)    
    #print(collect_output.getvalue())
    
    env_var = "compiler"
    spec_to_val = {"%gcc@4.4.7":"gcc_4.4.7", "%gcc@4.8.5": "gcc_4.8.5"}
    merged_module = MergedTclModule(specs, env_var, spec_to_val)
    collect_output = StringIO.StringIO()
    merged_module.write(output=collect_output)
    
    print(collect_output.getvalue())
