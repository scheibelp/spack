from spack import *
from llnl.util.filesystem import install_tree, join_path
import llnl.util.filesystem as FS
import spack #TODO: not sure why this is required for build_env_path

import os

class Boost(Package):
    """Boost provides free peer-reviewed portable C++ source
       libraries, emphasizing libraries that work well with the C++
       Standard Library.

       Boost libraries are intended to be widely useful, and usable
       across a broad spectrum of applications. The Boost license
       encourages both commercial and non-commercial use.
    """
    homepage = "http://www.boost.org"
    url      = "http://downloads.sourceforge.net/project/boost/boost/1.55.0/boost_1_55_0.tar.bz2"
    list_url = "http://sourceforge.net/projects/boost/files/boost/"
    list_depth = 2

    version('1.59.0', '6aa9a5c6a4ca1016edd0ed1178e3cb87')
    version('1.58.0', 'b8839650e61e9c1c0a89f371dd475546')
    version('1.57.0', '1be49befbdd9a5ce9def2983ba3e7b76')
    version('1.56.0', 'a744cf167b05d72335f27c88115f211d')
    version('1.55.0', 'd6eef4b4cacb2183f2bf265a5a03a354')
    version('1.54.0', '15cb8c0803064faef0c4ddf5bc5ca279')
    version('1.53.0', 'a00d22605d5dbcfb4c9936a9b35bc4c2')
    version('1.52.0', '3a855e0f919107e0ca4de4d84ad3f750')
    version('1.51.0', '4b6bd483b692fd138aef84ed2c8eb679')
    version('1.50.0', '52dd00be775e689f55a987baebccc462')
    version('1.49.0', '0d202cb811f934282dea64856a175698')
    version('1.48.0', 'd1e9a7a7f532bb031a3c175d86688d95')
    version('1.47.0', 'a2dc343f7bc7f83f8941e47ed4a18200')
    version('1.46.1', '7375679575f4c8db605d426fc721d506')
    version('1.46.0', '37b12f1702319b73876b0097982087e0')
    version('1.45.0', 'd405c606354789d0426bc07bea617e58')
    version('1.44.0', 'f02578f5218f217a9f20e9c30e119c6a')
    version('1.43.0', 'dd49767bfb726b0c774f7db0cef91ed1')
    version('1.42.0', '7bf3b4eb841b62ffb0ade2b82218ebe6')
    version('1.41.0', '8bb65e133907db727a2a825c5400d0a6')
    version('1.40.0', 'ec3875caeac8c52c7c129802a8483bd7')
    version('1.39.0', 'a17281fd88c48e0d866e1a12deecbcc0')
    version('1.38.0', '5eca2116d39d61382b8f8235915cb267')
    version('1.37.0', '8d9f990bfb7e83769fa5f1d6f065bc92')
    version('1.36.0', '328bfec66c312150e4c2a78dcecb504b')
    version('1.35.0', 'dce952a7214e72d6597516bcac84048b')
    version('1.34.1', '2d938467e8a448a2c9763e0a9f8ca7e5')
    version('1.34.0', 'ed5b9291ffad776f8757a916e1726ad0')

    libs = ['chrono', 
        'date_time', 
        'filesystem', 
        'iostreams', 
        'program_options',
        'random', 
        'regex', 
        'signals', 
        'system', 
        'thread', 
        'wave']

    for lib in libs:
        variant(lib, default=False, description="compile with {0} library"
            .format(lib))

    variant('regex_icu', default=False, description="Include regex ICU support (by default false even if regex library is compiled)")
    
    depends_on('icu', when='+regex_icu')
    
    def url_for_version(self, version):
        """Handle Boost's weird URLs, which write the version two different ways."""
        parts = [str(p) for p in Version(version)]
        dots = ".".join(parts)
        underscores = "_".join(parts)
        return "http://downloads.sourceforge.net/project/boost/boost/%s/boost_%s.tar.bz2" % (
            dots, underscores)


    def install(self, spec, prefix):   
        withLibs = list()
        for lib in Boost.libs:
            if "+{0}".format(lib) in spec:
                withLibs.append(lib)
        if not withLibs:
            # if no libraries are specified for compilation, then you dont have 
            # to configure/build anything, just copy over to the prefix directory.
            src = FS.join_path(self.stage.source_path, 'boost')
            FS.mkdirp(FS.join_path(prefix, 'include'))
            dst = FS.join_path(prefix, 'include', 'boost')
            FS.install_tree(src, dst)
            return
        
        # TODO: dependents may need to access the $BOOST_ROOT environment 
        # variable - if we set it here will other packages see it? cmake appears
        # to be able to set it automatically. Packages which use more basic 
        # makefiles may require it to be set.
    
        bootstrap = Executable('./bootstrap.sh')
        bootstrap('--prefix=%s' % prefix,
            "--with-libraries=%s" % ','.join(withLibs))

        # b2 used to be called bjam, before 1.47 (sigh)
        b2name = './b2' if spec.satisfies('@1.47:') else './bjam'

        # TODO: map compiler.name to Boost toolset config file (the Boost names
        # don't always match the Spack names for compilers)
        toolset = self.compiler.name

        # TODO: map spec.architecture to b2's target-os option (this is mainly
        # important for cross-compiling - Boost.Build has tools to determine
        # architecture like Spack)
        
        # Edit user-config.jam & BOOST_BUILD_PATH to use specified compiler 
        # (Boost.Build does not check the top-level boost directory for 
        # user-config.jam unless it is in BOOST_BUILD_PATH)
        env['BOOST_BUILD_PATH'] = os.getcwd()
        compiler_wrapper = join_path(spack.build_env_path, 'cc')
        with open('user-config.jam', 'wb') as F:
            F.write("using {0} : : {1} ;".format(toolset, compiler_wrapper))

        b2 = Executable(b2name)
        b2('install',
           '-j %s' % make_jobs,
           '--prefix=%s' % prefix,
           '--toolset=%s' % toolset)
