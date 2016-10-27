##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License (as
# published by the Free Software Foundation) version 2.1, February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
import spack
from llnl.util.filesystem import join_path

import argparse

from collections import defaultdict
import itertools
import os

description = "Project Spack's fully-qualified names to a tree of simplified symlinks"

def setup_parser(subparser):
    subparser.add_argument('--root', dest='root')
    subparser.add_argument(
        '--transitive', dest='transitive', action='store_true')
    subparser.add_argument('action')
    subparser.add_argument('target', nargs=argparse.REMAINDER)

class PackageProjection(object):
    def __init__(self, element_groups, dep=None):
        self.element_groups = element_groups
        self.dep = dep

    def project(self, spec):
        if self.dep:
            if self.dep == spec.name or self.dep not in spec:
                return
            spec = spec[self.dep]
        projected_groups = list()
        for element_group in self.element_groups:
            projected = list(x.project(spec) for x in element_group)
            projected = list(x for x in projected if x)
            if projected:
                projected_groups.append(projected)

        if projected_groups:
            return join_path(*('-'.join(x) for x in projected_groups))

def get_package_config(name, config, exclude_multiply=None,
        force_basename=False, dep=None):
    """
    Notes:
    
    - siblings may reuse multipliers, but children never reuse multipliers
      which were used by their parents
    - (implied) parent multiplier actions override child multiplier actions
    - always append to basename for multipliers of multipliers
    """
    primary_section = config.get(name, {})
    all_section = config.get('all', {})
    if 'descriptor' in primary_section:
        #TODO: if this is wrapped in package projection, I can later make sure
        #that descriptor projections are included when I attempt to skip
        #duplicates when a package provides multiple dependencies (which are
        #mentioned as components)
        return PackageDetailProjection(primary_section['descriptor'])
    elif 'components' in primary_section:
        components_section = primary_section['components']
    elif 'descriptor' in all_section:
        return PackageDetailProjection(all_section['descriptor'])
    elif 'components' in all_section:
        components_section = all_section['components']

    element_groups = list()
    element_group = list()
    exclude_multiply = set(exclude_multiply) if exclude_multiply else set()

    parent_exclude = set(exclude_multiply)
    for item in components_section:
        t = item.strip().split(':')
        if t[0] == 'dep':
            parent_exclude.add(t[1])
        elif t[0] == 'once':
            parent_exclude.add(t[1])
    
    for item in components_section:
        t = item.strip().split(':')
        if t[0] == '/':
            if force_basename:
                continue
            element_groups.append(element_group)
            element_group = list()
        else:
            if t[0] == 'dep':
                pkg = t[1]
                if pkg in exclude_multiply:
                    continue
                cfg_id = pkg if len(t) < 3 else t[2]
                element = get_package_config(cfg_id, config, parent_exclude,
                    force_basename=True, dep=pkg)
            elif t[0] == 'once':
                cfg_id = t[1]
                if cfg_id in exclude_multiply:
                    continue
                element = process_this(t[2:])
            elif t[0] in ['this', 'this?']:
                element = process_this(t)
            element_group.append(element)

    if element_group:
        element_groups.append(element_group)
    return PackageProjection(element_groups, dep=dep)

class PackageDetailProjection(object):
    def __init__(self, true_fmt, query_spec=None, false_fmt=None):
        self.query_spec = query_spec
        self.true_fmt = true_fmt
        self.false_fmt = false_fmt

    def project(self, spec):
        if not self.query_spec or spec.satisfies(self.query_spec):
            return spec.format(self.true_fmt)
        elif self.false_fmt:
            return spec.format(self.false_fmt)

def process_this(t):
    if t[0] == 'this':
        _, true_fmt = t
        query_spec, false_fmt = None, None
    elif t[0] == 'this?':
        _, query_spec, true_fmt = t[:3]
        false_fmt = t[3] if len(t) > 3 else None
    return PackageDetailProjection(true_fmt, query_spec, false_fmt)

def get_target_projections(pkg, config):
    targets = config.get(pkg, {}).get('targets', [])
    return list(
        TargetProjection(t['match'], t['target'], t['output'])
        for t in targets)
        
class TargetProjection(object):
    def __init__(self, match, target, output):
        self.match = match
        self.target = target
        self.output = output

    def matches(self, spec):
        return spec.satisfies(self.match)

    def project(self, spec):
        target_path = join_path(spec.prefix, self.target)
        if not os.path.exists(target_path):
            raise ValueError(
                "{0} does not exist in {1}".format(self.target, spec.prefix))
        return target_path, spec.format(self.output)

def project_packages(specs, config):
    def keyFn(spec):
        pkg_cfg = get_package_config(spec.name, config)
        return pkg_cfg.project(spec)
        
    link_to_specs = map_specs(specs, keyFn)
    
    return dict(
        (x, resolve_conflict(y)) for x, y in link_to_specs.iteritems())

def project_targets(specs, config):
    output_to_targets = defaultdict(set)
    for spec in specs:
        target_projections = get_target_projections(spec.name, config)
        for tp in target_projections:
            if tp.matches(spec):
                target, output = tp.project(spec)
                output_to_targets[output].add((spec, target))
    output_to_target = {}
    for output, spec_keys in output_to_targets.iteritems():
        #TODO: warn when there is more than one target
        spec, target = max(spec_keys, key=lambda (spec, target): spec)
        output_to_target[output] = target
    return output_to_target

def map_specs(specs, keyFn):
    key_to_specs = defaultdict(set)
    for spec in specs:
        key = keyFn(spec)
        key_to_specs[key].add(spec)
    return key_to_specs

def resolve_conflict(specs):
    return max(specs)

#TODO: unfinished
def update_install(specs, config):
    projection = config.projection

    touched = set()
    for spec in specs:
        touched.update(x.name for x in spec.traverse())
    
    # All specs associated with all packages affected, along with the specs
    # associated with their dependencies
    related_specs = set(itertools.chain.from_iterable(
        spack.installed_db.query(name) for name in touched))

    link_to_spec = projection.project_packages(related_specs)
    
    config.update_links(link_to_spec)
    
    #TODO: what to do if the installed specs arent the chosen specs?

#TODO: unfinished
def update_uninstall(specs, config):
    projection = config.projection
    link_to_spec = projection.project_packages(specs)
    config.remove_links(set(link_to_spec))

    # If all instances of a package are uninstalled, there may be no entries
    # for it here.
    related_specs = set(itertools.chain.from_iterable(
        spack.installed_db.query(s.name) for s in specs))
    link_to_spec = projection.project_packages(related_specs)
    config.add_links(link_to_spec)

def get_or_set(d, key, val):
    if key in d:
        return d[key]
    else:
        d[key] = val
        return val

def softlink_command(target_path, link_path):
    return "ln -s {0} {1}".format(target_path, link_path)

def tree(parser, args):
    root = args.root
    action = args.action

    tree_config = spack.config.get_config('trees')
    projections_config = spack.config.get_config('projections')

    if action == 'add':
        tree_id, query_spec = args.target
            
        tree = get_or_set(tree_config, tree_id, {})
        update = get_or_set(
            tree, 'transitive' if args.transitive else 'single', [])
        update.append(query_spec)
        spack.config.update_config('trees', tree_config, 'user')
    elif action == 'project':
        tree_id, = args.target

        if tree_id == 'all':
            specs_to_project = spack.install_layout.all_specs()
        else:
            specs_to_project = list()
            tree = tree_config[tree_id]
            single = tree['single']
            transitive = tree['transitive']
            for query_spec in single:
                specs_to_project.extend(
                    spack.installed_db.query(query_spec))
            for query_spec in transitive:
                specs_to_project.extend(
                    itertools.chain.from_iterable(spec.traverse() for spec in
                        spack.installed_db.query(query_spec)))

        for link_path, spec in project_packages(
                specs_to_project, projections_config).iteritems():
            print softlink_command(spec.prefix, join_path(root, link_path))

        for link_path, target in project_targets(
                specs_to_project, projections_config).iteritems():
            print softlink_command(target, link_path)
    else:
        raise ValueError("Unknown action: " + action)

