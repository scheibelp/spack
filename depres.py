

(RUN, BUILD, LINK, TEST, INCLUDE) = (0, 1, 2, 3, 4)

class Package(object):
    def __init__(self, name, deps=None):
        self.name = name
        self.deps = deps or {}

class Node(object):
    def __init__(self, name, deps=None):
        self.name = name
        self.deps = deps or {}

    def __getitem__(self, name):
        return self.deps[name]

    def __setitem__(self, name, dep):
        self.deps[name] = dep

def g1():
    p3 = Package('p3')
    p2 = Package('p2', {p3: [RUN]})
    p4 = Package('p4', {p3: [RUN]})
    
    p7 = Package('p7')
    p5 = Package('p5', {p7: [RUN]})
    p6 = Package('p6', {p7: [RUN]})

    p11 = Package('p11')
    p9 = Package('p9', {p11: [LINK]})
    p10 = Package('p10', {p11: [LINK]})
    p12 = Package('p12', {p9: [LINK], p7: [RUN]})
    p8 = Package('p8', {p12: [BUILD], p9: [LINK], p10: [LINK]}) 

    p1 = Package('p1', {p2: [RUN], p4: [RUN], p5: [BUILD], p6: [BUILD], p8: [LINK], p11: [LINK]})
    return p1

def g2():
    p9 = Package('p9')
    p2 = Package('p2', {p9: [LINK]})
    
    p4 = Package('p4')
    p3 = Package('p3', {p4: [RUN]})
    p5 = Package('p5', {p4: [RUN]})

    p7 = Package('p7', {p9: [LINK]})
    p6 = Package('p6', {p4: [RUN], p7: [LINK]})
    p8 = Package('p8', {p7: [LINK]})

    p1 = Package('p1', {p2: [BUILD], p3: [RUN, BUILD], p5: [RUN], p6: [LINK, BUILD], 
                 p8: [RUN, LINK], p9: [LINK]})

    return p1

# The following 3 functions can be used to extract a package dag from a
# concretized spec to make sure that dep_dag works on existing package hierarchies

def from_concretized_spec(spec):
    p = Package(spec.name)
    for dep_spec in spec._dependencies.values():
        child = dep_spec.spec
        child_package = from_concretized_spec(child)
        itypes = []
        for i, s in [(RUN, 'run'), (BUILD, 'build'), (LINK, 'link'), (LINK, 'include'), (BUILD, 'test')]:
            if s in dep_spec.deptypes:
                itypes.append(i)
        p.deps[child_package] = itypes
    return p

def merge_package_graphs(p, shared=None):
    shared = shared or {}
    if p.name in shared:
        return shared[p.name]
    shared[p.name] = p
    new_deps = {}
    for dep_pkg, deptypes in p.deps.items():
        new_deps[merge_package_graphs(dep_pkg, shared)] = deptypes
    p.deps = new_deps
    return p

def test_qt():
    import spack.spec
    qt_spec = spack.spec.Spec('qt')
    qt_spec.concretize()
    
    qt_pkg = from_concretized_spec(qt_spec)
    qt_pkg = merge_package_graphs(qt_pkg)
    
    node_dag = dep_dag(qt_pkg, Constraints())

    with open('qt_pkg.dot', 'wb') as F:
        F.write(pkg_dot_output(qt_pkg))

    with open('qt.dot', 'wb') as F:
        F.write(dot_output(node_dag))

def dot_output(node_dag):
    nodes = set()
    edges = set()
    remaining = [node_dag]
    id = 0
    node_to_id = {}
    while remaining:
        next = remaining.pop()
        remaining.extend(next.deps.values())
        if next not in node_to_id:
            node_to_id[next] = id
            id += 1

    deptypes_map = {RUN: 'R', LINK: 'L', BUILD: 'B'}
    deptypes_label = lambda deptypes: ''.join(deptypes_map[t] for t in deptypes)

    remaining = [node_dag]
    while remaining:
        next = remaining.pop()
        remaining.extend(next.deps.values())
        for dep in next.deps.values():
            edges.add((node_to_id[next], node_to_id[dep], "D"))
            #edges.add((node_to_id[next], node_to_id[dep], deptypes_label(deptypes)))

    nodes_section = '\n'.join('{0} [label="{1}"];'.format(str(id), n.name) for n, id in node_to_id.items())
    edges_section = '\n'.join('{0} -> {1} [label="{2}"];'.format(str(s), str(d), l) for s, d, l in edges)
    
    full = """digraph result {{
{0}
{1}
}}
""".format(nodes_section, edges_section)

    return full


def pkg_dot_output(pkg_dag):
    nodes = set()
    edges = set()
    remaining = [pkg_dag]
    id = 0
    node_to_id = {}
    while remaining:
        next = remaining.pop()
        remaining.extend(next.deps)
        if next not in node_to_id:
            node_to_id[next] = id
            id += 1

    deptypes_map = {RUN: 'R', LINK: 'L', BUILD: 'B'}
    deptypes_label = lambda deptypes: ''.join(deptypes_map[t] for t in deptypes)

    remaining = [pkg_dag]
    while remaining:
        next = remaining.pop()
        remaining.extend(next.deps)
        for dep, deptypes in next.deps.items():
            edges.add((node_to_id[next], node_to_id[dep], deptypes_label(deptypes)))

    nodes_section = '\n'.join('{0} [label="{1}"];'.format(str(id), n.name) for n, id in node_to_id.items())
    edges_section = '\n'.join('{0} -> {1} [label="{2}"];'.format(str(s), str(d), l) for s, d, l in edges)
    
    full = """digraph result {{
{0}
{1}
}}
""".format(nodes_section, edges_section)

    return full

# All of the logic for determining which package installations should be merged
# is in 'Constraints' and 'dep_dag'

class Constraints(object):
    def __init__(self):
        self.run = {}
        self.link = {}
        self.build = {}

    def get(self, name, deptypes):
        for deptype, group in [(RUN, self.run), (LINK, self.link), (BUILD, self.build)]:
            if deptype in deptypes and name in group:
                return group[name]

    def add(self, item, deptypes):
        for deptype, group in [(RUN, self.run), (LINK, self.link), (BUILD, self.build)]:
            if deptype in deptypes:
                if item.name in group:
                    assert item is group[item.name]
                else:
                    group[item.name] = item

def dep_dag(package, parent_constraints):
    n = Node(package.name)
    
    shared_run = {}
    shared_build = {}
    for p, deptypes in package.deps.items():
        if RUN in deptypes and BUILD in deptypes:
            shared_run = parent_constraints.run
    
    for p, deptypes in package.deps.items():
        resolved = parent_constraints.get(p.name, deptypes)
        if not resolved:
            c = Constraints()
            if RUN in deptypes:
                c.run = parent_constraints.run
            elif BUILD in deptypes:
                c.run = shared_run
            
            if LINK in deptypes:
                c.link = parent_constraints.link
            
            #if BUILD in deptypes:
            #    c.build = shared_build

            resolved = dep_dag(p, c)
            parent_constraints.add(resolved, deptypes)
        n[p.name] = resolved
    
    return n
        

def test_g1():
    g = dep_dag(g1(), Constraints())
    assert g['p2']['p3'] is g['p4']['p3']
    assert g['p5']['p7'] is g['p6']['p7']

    assert g['p8']['p9']['p11'] is g['p8']['p10']['p11']
    assert g['p8']['p12']['p9'] is not g['p8']['p9']
    assert g['p11'] is g['p8']['p10']['p11']

    assert g['p8']['p12']['p7'] is not g['p5']['p7']

def test_g2():
    g = dep_dag(g2(), Constraints())
    assert g['p2']['p9'] is not g['p9']
    assert g['p3']['p4'] is g['p5']['p4']
    assert g['p6']['p4'] is g['p5']['p4']
    assert g['p6']['p7']['p9'] is g['p9']

    #with open('g2_pkg.dot', 'wb') as F:
    #    F.write(pkg_dot_output(g2()))

    #with open('g2.dot', 'wb') as F:
    #    F.write(dot_output(g))

def main():
    test_g1()
    test_g2()
    test_qt()

if __name__ == "__main__":
    main()
