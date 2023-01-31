# Copyright 2013-2023 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
import os
import shutil

import llnl.util.tty as tty

import spack.cmd
import spack.cmd.common.arguments as arguments
import spack.util.path
from spack.error import SpackError

description = "add a spec to an environment's dev-build information"
section = "environments"
level = "long"


def setup_parser(subparser):
    subparser.add_argument("-p", "--path", help="Source location of package")

    clone_group = subparser.add_mutually_exclusive_group()
    clone_group.add_argument(
        "--no-clone",
        action="store_false",
        dest="clone",
        default=None,
        help="Do not clone. The package already exists at the source path",
    )
    clone_group.add_argument(
        "--clone",
        action="store_true",
        dest="clone",
        default=None,
        help="Clone the package even if the path already exists",
    )

    scopes = spack.config.scopes()
    scopes_metavar = spack.config.scopes_metavar
    subparser.add_argument(
        "--scope",
        choices=scopes,
        metavar=scopes_metavar,
        help="configuration scope to modify",
    )

    subparser.add_argument(
        "-f", "--force", help="Remove any files or directories that block cloning source code"
    )

    arguments.add_common_arguments(subparser, ["spec"])


def develop(parser, args):
    # TODO: note that this command could technically proceed without an
    # active env, but in that case would require absolute paths
    env = spack.cmd.require_active_env(cmd_name="develop")

    if not args.spec:
        if args.clone is False:
            raise SpackError("No spec provided to spack develop command")

        # download all dev specs
        for name, entry in env.dev_specs.items():
            path = entry.get("path", name)
            abspath = spack.util.path.canonicalize_path(path, default_wd=env.path)

            if os.path.exists(abspath):
                msg = "Skipping developer download of %s" % entry["spec"]
                msg += " because its path already exists."
                tty.msg(msg)
                continue

            spec = spack.spec.Spec(entry["spec"])
            pkg_cls = spack.repo.path.get_pkg_class(spec.name)
            pkg_cls(spec).stage.steal_source(abspath)

        if not env.dev_specs:
            tty.warn("No develop specs to download")

        return

    specs = spack.cmd.parse_specs(args.spec)
    if len(specs) > 1:
        raise SpackError("spack develop requires at most one named spec")

    spec = specs[0]
    if not spec.versions.concrete:
        raise SpackError("Packages to develop must have a concrete version")

    # default path is relative path to spec.name
    path = args.path or spec.name
    abspath = spack.util.path.canonicalize_path(path, default_wd=env.path)

    # clone default: only if the path doesn't exist
    clone = args.clone
    if clone is None:
        clone = not os.path.exists(abspath)

    if not clone and not os.path.exists(abspath):
        raise SpackError("Provided path %s does not exist" % abspath)

    if clone:
        if os.path.exists(abspath):
            if args.force:
                shutil.rmtree(abspath)
            else:
                msg = "Path %s already exists and cannot be cloned to." % abspath
                msg += " Use `spack develop -f` to overwrite."
                raise SpackError(msg)

        # Stage, at the moment, requires a concrete Spec, since it needs the
        # dag_hash for the stage dir name. Below though we ask for a stage
        # to be created, to copy it afterwards somewhere else. It would be
        # better if we can create the `source_path` directly into its final
        # destination.
        pkg_cls = spack.repo.path.get_pkg_class(spec.name)
        pkg_cls(spec).stage.steal_source(abspath)

    if not args.scope:
        modify_scope = "env:{0}".format(env.name)
    else:
        modify_scope = args.scope
    dev_specs = spack.config.get("develop", scope=modify_scope)
    if spec.name in dev_specs:
        tty.msg(
            "Updating {0}:\n\told: {1}\n\tnew: {2}".format(
                str(spec), dev_specs[spec.name], abspath
            )
        )
    else:
        tty.msg("New development spec: {0}".format(str(spec)))

    entry = {
        "spec": str(spec),
    }
    if path != spec.name:
        entry["path"] = path
    dev_specs[spec.name] = entry

    spack.config.set("develop", dev_specs, modify_scope)

    # Note: this is needed to force a re-read of the env
    with env.write_transaction():
        pass
