class IORegister:
    inputs_reg = []
    outs_reg = []

    @classmethod
    def register_inputs(cls, inputs):
        cls.inputs_reg += inputs

    @classmethod
    def register_mid(cls, mid):
        cls.outs_reg.append(mid)

