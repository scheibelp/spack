##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the NOTICE and LICENSE files for our notice and the LGPL.
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

import fnmatch
import os

import pytest
import six
import spack
from llnl.util.filesystem import LibraryList, HeaderList
from llnl.util.filesystem import find_libraries, find_headers


@pytest.fixture()
def library_list():
    """Returns an instance of LibraryList."""
    l = [
        '/dir1/liblapack.a',
        '/dir2/libfoo.dylib',
        '/dir1/libblas.a',
        '/dir3/libbar.so',
        'libbaz.so'
    ]

    return LibraryList(l)


@pytest.fixture()
def header_list():
    """Returns an instance of header list"""
    h = [
        '/dir1/Python.h',
        '/dir2/datetime.h',
        '/dir1/pyconfig.h',
        '/dir3/core.h',
        'pymem.h'
    ]
    h = HeaderList(h)
    h.add_macro('-DBOOST_LIB_NAME=boost_regex')
    h.add_macro('-DBOOST_DYN_LINK')
    return h


class TestLibraryList(object):

    def test_repr(self, library_list):
        x = eval(repr(library_list))
        assert library_list == x

    def test_joined_and_str(self, library_list):

        s1 = library_list.joined()
        expected = '/dir1/liblapack.a /dir2/libfoo.dylib /dir1/libblas.a /dir3/libbar.so libbaz.so'  # noqa: E501
        assert s1 == expected

        s2 = str(library_list)
        assert s1 == s2

        s3 = library_list.joined(';')
        expected = '/dir1/liblapack.a;/dir2/libfoo.dylib;/dir1/libblas.a;/dir3/libbar.so;libbaz.so'  # noqa: E501
        assert s3 == expected

    def test_flags(self, library_list):

        search_flags = library_list.search_flags
        assert '-L/dir1' in search_flags
        assert '-L/dir2' in search_flags
        assert '-L/dir3' in search_flags
        assert isinstance(search_flags, str)
        assert search_flags == '-L/dir1 -L/dir2 -L/dir3'

        link_flags = library_list.link_flags
        assert '-llapack' in link_flags
        assert '-lfoo' in link_flags
        assert '-lblas' in link_flags
        assert '-lbar' in link_flags
        assert '-lbaz' in link_flags
        assert isinstance(link_flags, str)
        assert link_flags == '-llapack -lfoo -lblas -lbar -lbaz'

        ld_flags = library_list.ld_flags
        assert isinstance(ld_flags, str)
        assert ld_flags == search_flags + ' ' + link_flags

    def test_paths_manipulation(self, library_list):
        names = library_list.names
        assert names == ['lapack', 'foo', 'blas', 'bar', 'baz']

        directories = library_list.directories
        assert directories == ['/dir1', '/dir2', '/dir3']

    def test_get_item(self, library_list):
        a = library_list[0]
        assert a == '/dir1/liblapack.a'

        b = library_list[:]
        assert type(b) == type(library_list)
        assert library_list == b
        assert library_list is not b

    def test_add(self, library_list):
        pylist = [
            '/dir1/liblapack.a',  # removed from the final list
            '/dir2/libbaz.so',
            '/dir4/libnew.a'
        ]
        another = LibraryList(pylist)
        l = library_list + another
        assert len(l) == 7

        # Invariant : l == l + l
        assert l == l + l

        # Always produce an instance of LibraryList
        assert type(library_list + pylist) == type(library_list)
        assert type(pylist + library_list) == type(library_list)


class TestHeaderList(object):

    def test_repr(self, header_list):
        x = eval(repr(header_list))
        assert header_list == x

    def test_joined_and_str(self, header_list):
        s1 = header_list.joined()
        expected = '/dir1/Python.h /dir2/datetime.h /dir1/pyconfig.h /dir3/core.h pymem.h'  # noqa: E501
        assert s1 == expected

        s2 = str(header_list)
        assert s1 == s2

        s3 = header_list.joined(';')
        expected = '/dir1/Python.h;/dir2/datetime.h;/dir1/pyconfig.h;/dir3/core.h;pymem.h'  # noqa: E501
        assert s3 == expected

    def test_flags(self, header_list):
        include_flags = header_list.include_flags
        assert '-I/dir1' in include_flags
        assert '-I/dir2' in include_flags
        assert '-I/dir3' in include_flags
        assert isinstance(include_flags, str)
        assert include_flags == '-I/dir1 -I/dir2 -I/dir3'

        macros = header_list.macro_definitions
        assert '-DBOOST_LIB_NAME=boost_regex' in macros
        assert '-DBOOST_DYN_LINK' in macros
        assert isinstance(macros, str)
        assert macros == '-DBOOST_LIB_NAME=boost_regex -DBOOST_DYN_LINK'

        cpp_flags = header_list.cpp_flags
        assert isinstance(cpp_flags, str)
        assert cpp_flags == include_flags + ' ' + macros

    def test_paths_manipulation(self, header_list):
        names = header_list.names
        assert names == ['Python', 'datetime', 'pyconfig', 'core', 'pymem']

        directories = header_list.directories
        assert directories == ['/dir1', '/dir2', '/dir3']

    def test_get_item(self, header_list):
        a = header_list[0]
        assert a == '/dir1/Python.h'

        b = header_list[:]
        assert type(b) == type(header_list)
        assert header_list == b
        assert header_list is not b

    def test_add(self, header_list):
        pylist = [
            '/dir1/Python.h',  # removed from the final list
            '/dir2/pyconfig.h',
            '/dir4/datetime.h'
        ]
        another = HeaderList(pylist)
        h = header_list + another
        assert len(h) == 7

        # Invariant : l == l + l
        assert h == h + h

        # Always produce an instance of HeaderList
        assert type(header_list + pylist) == type(header_list)
        assert type(pylist + header_list) == type(header_list)


#: Directory where the data for the test below is stored
search_dir = os.path.join(spack.test_path, 'data', 'directory_search')


@pytest.mark.parametrize('search_fn,search_list,root,kwargs', [
    (find_libraries, 'liba', search_dir, {'recurse': True}),
    (find_libraries, ['liba'], search_dir, {'recurse': True}),
    (find_libraries, 'libb', search_dir, {'recurse': True}),
    (find_libraries, ['libc'], search_dir, {'recurse': True}),
    (find_libraries, ['libc', 'liba'], search_dir, {'recurse': True}),
    (find_libraries, ['liba', 'libc'], search_dir, {'recurse': True}),
    (find_libraries, ['libc', 'libb', 'liba'], search_dir, {'recurse': True}),
    (find_libraries, ['liba', 'libc'], search_dir, {'recurse': True}),
    (find_libraries,
     ['libc', 'libb', 'liba'],
     search_dir,
     {'recurse': True, 'shared': False}
     ),
    (find_headers, 'a', search_dir, {'recurse': True}),
    (find_headers, ['a'], search_dir, {'recurse': True}),
    (find_headers, 'b', search_dir, {'recurse': True}),
    (find_headers, ['c'], search_dir, {'recurse': True}),
    (find_headers, ['c', 'a'], search_dir, {'recurse': True}),
    (find_headers, ['a', 'c'], search_dir, {'recurse': True}),
    (find_headers, ['c', 'b', 'a'], search_dir, {'recurse': True}),
    (find_headers, ['a', 'c'], search_dir, {'recurse': True}),
    (find_libraries,
     ['liba', 'libd'],
     os.path.join(search_dir, 'b'),
     {'recurse': False}
     ),
    (find_headers,
     ['b', 'd'],
     os.path.join(search_dir, 'b'),
     {'recurse': False}
     ),
])
def test_searching_order(search_fn, search_list, root, kwargs):

    # Test search
    result = search_fn(search_list, root, **kwargs)

    # The tests are set-up so that something is always found
    assert len(result) != 0

    # Now reverse the result and start discarding things
    # as soon as you have matches. In the end the list should
    # be emptied.
    l = list(reversed(result))

    # At this point make sure the search list is a sequence
    if isinstance(search_list, six.string_types):
        search_list = [search_list]

    # Discard entries in the order they appear in search list
    for x in search_list:
        try:
            while fnmatch.fnmatch(l[-1], x) or x in l[-1]:
                l.pop()
        except IndexError:
            # List is empty
            pass

    # List should be empty here
    assert len(l) == 0
