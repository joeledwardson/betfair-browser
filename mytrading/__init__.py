"""
Import flumine regardless if it is used, so that it replaces list of PriceSize objects with list of dicts with
patching.py

Also replace order _on_error() to store error message in order so it can be accessed latre
"""
# from flumine.order.order import BaseOrder
import flumine
#
# class MyBaseControl(flumine.controls.BaseControl):
#     def _on_error(self, order: BaseOrder, error: str) -> None:
#         order.violation()
#         order.violation_message = error
#         flumine.controls.logger.warning(
#             'Order on selection id {0} has violated {1} and will not be placed: "{2}"'.format(
#                 order.selection_id,
#                 self.NAME,
#                 error
#             )
#             # , extra={"control": self.NAME, "error": error, "order": order.info},
#         )
# flumine.controls.BaseControl = MyBaseControl
# my_debug=1
from . import testfile