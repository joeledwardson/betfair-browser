# TODO - each component will have its own loading bar so input registering no longer needed
# TODO - still could do with intermediary register but this should be done through name and not component
class IORegister:
    inputs_reg = []
    outs_reg = []

    @classmethod
    def register_inputs(cls, inputs):
        cls.inputs_reg += inputs

    @classmethod
    def register_mid(cls, mid):
        cls.outs_reg.append(mid)

