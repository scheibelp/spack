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
import os

import llnl.util.tty as tty

import spack
import spack.cmd

description = "Create RPM specs and sources for RPM installs"

def setup_parser(subparser):
    subparser.add_argument(
        'package', help="spec of package to install")
    subparser.add_argument(
        '--outputDir', dest='outputDir', help="rpmbuild SOURCES directory")
    
def create_spec(pkgName, rpmName, dependencies, installDir):
    spec = """Summary: The srpm contains the .spec, a copy of the spack repo, and the artifact
Name: {1}
Version: 1.0
Release: 1
License: LLNL
Group: Development/Tools
{2}
SOURCE0 : %{{name}}-%{{version}}.tar.gz

%description
%{{summary}}

%prep
%setup -q

%build
# Empty section.

%install
rm -rf %{{buildroot}}
mkdir -p  %{{buildroot}}
./bin/spack install {0}
cp -a `find opt/ -name "*{0}-*"`/* %{{buildroot}}

%clean
rm -rf %{{buildroot}}

%files
%defattr(-,root,root,-)
/*

%changelog
* Thu Jan 14 2016  Peter S 1.0-1
- First Build
""".format(
        pkgName, 
        rpmName, 
        "Requires: %s" % ' '.join(dependencies) if dependencies else "",
        installDir)

    return spec


def generate_specs(spec, visited, installDir):
    if spec in visited:
        return list()
    visited.add(spec)
    allSpecs = list()
    for child in spec.dependencies.itervalues():
        allSpecs.extend(generate_specs(child, visited, installDir))
    rpmName = "spack-%s" % spec.name
    deps = list("spack-%s" % x for x in spec.dependencies)
    allSpecs.append((rpmName, create_spec(spec.name, rpmName, deps, installDir)))
    return allSpecs


def rpm_install(parser, args):
    specs = spack.cmd.parse_specs(args.package, concretize=True)
    if len(specs) > 1:
        tty.die("Only 1 top-level package can be specified")
    topSpec = iter(specs).next()
    
    #import pdb; pdb.set_trace()
    
    rpmSpecs = generate_specs(topSpec, set(), '/usr/')
    for rpmName, spec in rpmSpecs:
        with open(os.path.join(args.outputDir, "%s.spec" % rpmName), 'wb') as F:
            F.write(spec)
