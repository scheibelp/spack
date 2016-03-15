##############################################################################
# Copyright (c) 2013, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Written by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License (as published by
# the Free Software Foundation) version 2.1 dated February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
import argparse
import hashlib

import llnl.util.tty as tty
import spack
import spack.cmd
import spack.util.crypto
from spack.stage import Stage, FailedDownloadError
from spack.version import *

description = "Checksum available versions of a package."


def setup_parser(subparser):
    subparser.add_argument(
        'package', metavar='PACKAGE', help='Package to list versions for')
    subparser.add_argument(
        '--keep-stage', action='store_true', dest='keep_stage',
        help="Don't clean up staging area when command completes.")
    subparser.add_argument(
        'versions', nargs=argparse.REMAINDER, help='Versions to generate checksums for')


def get_checksums(versions, urls, **kwargs):
    # Allow commands like create() to do some analysis on the first
    # archive after it is downloaded.
    first_stage_function = kwargs.get('first_stage_function', None)
    keep_stage = kwargs.get('keep_stage', False)

    tty.msg("Downloading...")
    hashes = []
    i = 0
    for url, version in zip(urls, versions):
        try:
            with Stage(url, keep=keep_stage) as stage:
                stage.fetch()
                if i == 0 and first_stage_function:
                    first_stage_function(stage)

                hashes.append((version,
                               spack.util.crypto.checksum(hashlib.md5, stage.archive_file)))
                i += 1
        except FailedDownloadError as e:
            tty.msg("Failed to fetch %s" % url)
        except Exception as e:
            tty.msg('Something failed on %s, skipping.\n    (%s)' % (url, e))

    return hashes


def checksum(parser, args):
    # get the package we're going to generate checksums for
    pkg = spack.repo.get(args.package)

    # If the user asked for specific versions, use those.
    if args.versions:
        versions = {}
        for v in args.versions:
            v = ver(v)
            if not isinstance(v, Version):
                tty.die("Cannot generate checksums for version lists or " +
                        "version ranges.  Use unambiguous versions.")
            versions[v] = pkg.url_for_version(v)
    else:
        versions = pkg.fetch_remote_versions()
        if not versions:
            tty.die("Could not fetch any versions for %s" % pkg.name)

    sorted_versions = sorted(versions, reverse=True)

    tty.msg("Found %s versions of %s" % (len(versions), pkg.name),
            *spack.cmd.elide_list(
                ["%-10s%s" % (v, versions[v]) for v in sorted_versions]))
    print
    archives_to_fetch = tty.get_number(
        "How many would you like to checksum?", default=5, abort='q')

    if not archives_to_fetch:
        tty.msg("Aborted.")
        return

    version_hashes = get_checksums(
        sorted_versions[:archives_to_fetch],
        [versions[v] for v in sorted_versions[:archives_to_fetch]],
        keep_stage=args.keep_stage)

    if not version_hashes:
        tty.die("Could not fetch any versions for %s" % pkg.name)

    version_lines = ["    version('%s', '%s')" % (v, h) for v, h in version_hashes]
    tty.msg("Checksummed new versions of %s:" % pkg.name, *version_lines)
