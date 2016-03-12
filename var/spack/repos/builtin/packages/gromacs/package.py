from spack import *


class Gromacs(Package):
    """
    GROMACS (GROningen MAchine for Chemical Simulations) is a molecular dynamics package primarily designed for
    simulations of proteins, lipids and nucleic acids. It was originally developed in the Biophysical Chemistry
    department of University of Groningen, and is now maintained by contributors in universities and research centers
    across the world.

    GROMACS is one of the fastest and most popular software packages available and can run on CPUs as well as GPUs.
    It is free, open source released under the GNU General Public License. Starting from version 4.6, GROMACS is
    released under the GNU Lesser General Public License.
    """

    homepage = 'http://www.gromacs.org'
    url = 'ftp://ftp.gromacs.org/pub/gromacs/gromacs-5.1.2.tar.gz'

    version('5.1.2', '614d0be372f1a6f1f36382b7a6fcab98')

    variant('mpi', default=True, description='Activate MPI support')
    variant('shared', default=True, description='Enables the build of shared libraries')
    variant('debug', default=False, description='Enables debug mode')
    variant('double', default=False, description='Produces a double precision version of the executables')

    depends_on('mpi', when='+mpi')

    depends_on('fftw')

    # TODO : add GPU support

    def install(self, spec, prefix):

        options = []

        if '+mpi' in spec:
            options.append('-DGMX_MPI:BOOL=ON')

        if '+double' in spec:
            options.append('-DGMX_DOUBLE:BOOL=ON')

        if '~shared' in spec:
            options.append('-DBUILD_SHARED_LIBS:BOOL=OFF')

        if '+debug' in spec:
            options.append('-DCMAKE_BUILD_TYPE:STRING=Debug')
        else:
            options.append('-DCMAKE_BUILD_TYPE:STRING=Release')

        options.extend(std_cmake_args)

        with working_dir('spack-build', create=True):

            cmake('..', *options)
            make()
            make('install')
