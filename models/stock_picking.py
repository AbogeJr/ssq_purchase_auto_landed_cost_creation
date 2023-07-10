from odoo import fields, models
from datetime import datetime


# class StockPicking(models.Model):
#     _inherit = "stock.picking"

#     def button_validate(self):
#         res = super(StockPicking, self).button_validate()
#         if res and self.purchase_id.landed_cost_lines:
#             line_data = []
#             for line in self.env["purchase.landed.cost.line"].search(
#                 [
#                     ("purchase_id", "=", self.purchase_id.id),
#                     ("is_landed_cost_created", "=", False),
#                 ]
#             ):
#                 line_data.append(
#                     (
#                         0,
#                         0,
#                         {
#                             "product_id": line.product_id.id,
#                             "name": line.name,
#                             "account_id": line.account_id.id,
#                             "split_method": line.split_method,
#                             "price_unit": line.price_unit,
#                         },
#                     )
#                 )
#                 line.is_landed_cost_created = True
#             landed_cost = self.env["stock.landed.cost"].create(
#                 {
#                     "date": datetime.now().date(),
#                     "purchase_id": self.purchase_id.id,
#                     "picking_ids": self.ids,
#                     "cost_lines": line_data,
#                 }
#             )
#             self.sudo().purchase_id.landed_costs_ids = [(4, landed_cost.id)]
#             landed_cost.sudo().with_context(
#                 {"is_purchase_auto_calculation": True}
#             ).button_validate()
#         return res


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    purchase_id = fields.Many2one("purchase.order")
    currency_factor = fields.Float(string="Currency Rate", default=1)
    landed_cost_factor = fields.Float(default=1)
    base_pricing_factor = fields.Float(default=1)
    pricing_preference = fields.Selection(
        [
            ("strict", "Strict"),
            ("high", "Prefer higher Price"),
            ("low", "Prefer Lower Price"),
        ]
    )
    vendor_bill_ids = fields.Many2many("account.move", string="Vendor Bills")

    def compute_landed_cost(self):
        res = super(StockLandedCost, self).compute_landed_cost()
        if self.purchase_id:
            total_purchase_qty = 0
            total_product_weight = 0
            total_product_volume = 0

            for line in self.purchase_id.order_line:
                total_purchase_qty += line.product_qty
                total_product_weight += line.product_id.weight * line.product_qty
                total_product_volume += line.product_id.volume * line.product_qty

            purchase_order_line_ids = []
            prev_former_cost = 0
            for line in self.env["stock.valuation.adjustment.lines"].search(
                [("cost_line_id", "=", self.cost_lines[0].id)]
            ):
                purchase_line_id = self.env["purchase.order.line"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("order_id", "=", self.purchase_id.id),
                        ("id", "not in", purchase_order_line_ids),
                    ],
                    limit=1,
                    order="id asc",
                )
                purchase_order_line_ids.append(purchase_line_id.id)
                prev_former_cost += (
                    line.former_cost / line.quantity * purchase_line_id.product_qty
                )

            purchase_order_line_ids = []
            cost_dict = {}
            for line in self.valuation_adjustment_lines:
                purchase_line_id = self.env["purchase.order.line"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        ("order_id", "=", self.purchase_id.id),
                        ("id", "not in", purchase_order_line_ids),
                    ],
                    limit=1,
                    order="id asc",
                )
                purchase_order_line_ids.append(purchase_line_id.id)
                if (
                    line.cost_line_id.split_method == "equal"
                    and line.quantity != purchase_line_id.product_qty
                    and purchase_line_id.product_qty > 0
                ):
                    line.additional_landed_cost = (
                        line.quantity
                        / purchase_line_id.product_qty
                        * line.additional_landed_cost
                    )
                elif line.cost_line_id.split_method == "by_quantity":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_purchase_qty
                        * line.quantity
                    )
                elif line.cost_line_id.split_method == "by_weight":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_product_weight
                        * line.quantity
                        * line.product_id.weight
                    )
                elif line.cost_line_id.split_method == "by_volume":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / total_product_volume
                        * line.quantity
                        * line.product_id.volume
                    )
                elif line.cost_line_id.split_method == "by_current_cost_price":
                    line.additional_landed_cost = (
                        line.cost_line_id.price_unit
                        / prev_former_cost
                        * line.former_cost
                    )
                if line.cost_line_id.id not in cost_dict:
                    cost_dict[line.cost_line_id.id] = line.additional_landed_cost
                else:
                    cost_dict[line.cost_line_id.id] += line.additional_landed_cost
            landed_cost_line_obj = self.env["stock.landed.cost.lines"]
            for key, value in cost_dict.items():
                landed_cost_line_obj.browse(key).write({"price_unit": value})
        return res

    def adjust_costing(self):
        for record in self:
            for bill in record.vendor_bill_ids:
                for line in bill.invoice_line_ids:
                    line.product_id.lst_price = record.valuation_adjustment_lines[
                        0
                    ].new_price
                    line.product_id.standard_price = record.valuation_adjustment_lines[
                        0
                    ].new_cost

    def revert_costing(self):
        for record in self.vendor_bill_ids:
            for line in record.costing_ids:
                line.product_id.lst_price = line.old_price
                line.product_id.standard_price = line.old_cost
