from typing import Optional, Any


class Value:
    def find(self):
        raise NotImplementedError("abstract")

    def _set_forwarded(self, value):
        raise NotImplementedError("abstract")


class Operation(Value):
    def __init__(self, name: str, args: list[Value]):
        self.name = name
        self.args = args
        self.forwarded = None

    def __repr__(self):
        return f"Operation({self.name}," f"{self.args}, {self.forwarded})"

    def find(self) -> Value:
        # returns the "representative" value of
        # self, in the union-find sense
        op = self
        while isinstance(op, Operation):
            # could do path compression here too
            # but not essential
            next = op.forwarded
            if next is None:
                return op
            op = next
        return op

    def arg(self, index):
        # change to above: return the
        # representative of argument 'index'
        return self.args[index].find()

    def make_equal_to(self, value: Value):
        # this is "union" in the union-find sense,
        # but the direction is important! The
        # representative of the union of Operations
        # must be either a Constant or an operation
        # that we know for sure is not optimized
        # away.

        self.find()._set_forwarded(value)

    def _set_forwarded(self, value: Value):
        self.forwarded = value


class Constant(Value):
    def __init__(self, value: Any):
        self.value = value

    def __repr__(self):
        return f"Constant({self.value})"

    def find(self):
        return self

    def _set_forwarded(self, value: Value):
        # if we found out that an Operation is
        # equal to a constant, it's a compiler bug
        # to find out that it's equal to another
        # constant
        assert isinstance(value, Constant) and value.value == self.value


class Block(list):
    def opbuilder(opname):
        def wraparg(arg):
            if not isinstance(arg, Value):
                arg = Constant(arg)
            return arg

        def build(self, *args):
            # construct an Operation, wrap the
            # arguments in Constants if necessary
            op = Operation(opname, [wraparg(arg) for arg in args])
            # add it to self, the basic block
            self.append(op)
            return op

        return build

    # a bunch of operations we support
    add = opbuilder("add")
    mul = opbuilder("mul")
    getarg = opbuilder("getarg")
    dummy = opbuilder("dummy")
    lshift = opbuilder("lshift")
    bitand = opbuilder("bitand")


def bb_to_str(bb: Block, varprefix: str = "v"):
    # the implementation is not too important,
    # look at the test below to see what the
    # result looks like

    def arg_to_str(arg: Value):
        if isinstance(arg, Constant):
            return str(arg.value)
        else:
            # the key must exist, otherwise it's
            # not a valid SSA basic block:
            # the variable must be defined before
            # its first use
            return varnames[arg]

    varnames = {}
    res = []
    for index, op in enumerate(bb):
        # give the operation a name used while
        # printing:
        var = f"{varprefix}{index}"
        varnames[op] = var
        arguments = ", ".join(arg_to_str(op.arg(i)) for i in range(len(op.args)))
        strop = f"{var} = {op.name}({arguments})"
        res.append(strop)
    return "\n".join(res)


class Parity:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    @staticmethod
    def const(value):
        if value.value % 2 == 0:
            return EVEN
        else:
            return ODD

    def add(self, other):
        if self is EVEN and other is EVEN:
            return EVEN
        if self is ODD and other is ODD:
            return EVEN
        return UNKNOWN

    def lshift(self, other):
        if other is ODD:
            return EVEN
        return UNKNOWN


UNKNOWN = Parity("unknown")
EVEN = Parity("even")
ODD = Parity("odd")

block = Block()
v0 = block.getarg(0)
v1 = block.getarg(1)
v2 = block.lshift(v0, 1)
v3 = block.lshift(v1, 1)
v4 = block.add(v2, v3)
v5 = block.bitand(v4, 1)
v6 = block.dummy(v5)


def simplify(block: Block) -> Block:
    parity = {}

    def parity_of(value):
        if isinstance(value, Constant):
            return Parity.const(value)
        return parity[value]

    result = Block()
    for op in block:
        # Try to simplify
        if isinstance(op, Operation) and op.name == "bitand":
            arg = op.arg(0)
            mask = op.arg(1)
            if isinstance(mask, Constant) and mask.value == 1:
                if parity_of(arg) is EVEN:
                    op.make_equal_to(Constant(0))
                    continue
                elif parity_of(arg) is ODD:
                    op.make_equal_to(Constant(1))
                    continue
        # Emit
        result.append(op)
        # Analyze
        transfer = getattr(Parity, op.name, lambda *args: UNKNOWN)
        args = [parity_of(arg.find()) for arg in op.args]
        parity[op] = transfer(*args)
    return result


block = simplify(block)
print(bb_to_str(block))
