# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import llnl.util.tty as tty

import spack.cmd
import spack.cmd.common.arguments as arguments
import spack.environment as ev

description = "remove specs from an environment"
section = "environments"
level = "long"


def setup_parser(subparser):
    subparser.add_argument(
        "-a", "--all", action="store_true", help="remove all specs from (clear) the environment"
    )

    # Note: by default we want to modify the environment scope, but
    # config.default_modify_scope may not refer to the environment at
    # the time this parser is instantiated
    scopes = spack.config.scopes()
    scopes_metavar = spack.config.SCOPES_METAVAR
    subparser.add_argument(
        "--scope", choices=scopes, metavar=scopes_metavar, help="configuration scope to modify"
    )

    arguments.add_common_arguments(subparser, ["specs"])


def _update_config(specs_to_remove, remove_all=False):
    dev_configs = spack.config.matched_config("develop")

    for scope, dev_config in dev_configs:
        modified = False
        for spec in specs_to_remove:
            if spec.name in dev_config:
                tty.msg("Undevelop: removing {0}".format(spec.name))
                del dev_config[spec.name]
                modified = True
        if remove_all and dev_config:
            dev_config = {}
            modified = True
        if modified:
            spack.config.set("develop", dev_config, scope=scope)


def undevelop(parser, args):
    remove_specs = None
    remove_all = False
    if args.all:
        remove_all = True
    else:
        remove_specs = spack.cmd.parse_specs(args.specs)

    env = ev.active_environment()
    if env:
        with env.write_transaction():
            _update_config(remove_specs, remove_all)

    updated_all_dev_specs = set(spack.config.get("develop"))
    remove_spec_names = set(x.name for x in remove_specs)

    if remove_all:
        not_fully_removed = updated_all_dev_specs
    else:
        not_fully_removed = updated_all_dev_specs & remove_spec_names

    if not_fully_removed:
        tty.msg(
            "The following specs could not be removed as develop specs"
            " - see `spack config blame develop` to locate files requiring"
            f" manual edits: {', '.join(not_fully_removed)}"
        )
